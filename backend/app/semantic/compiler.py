"""指标编译解析层：指标注册表声明 → 确定性 SQL（v0.15.0 迭代1）。

安全护栏：
1. 只允许注册表内的指标与维度参与编译，外部表/列一律来自白名单元数据；
2. WHERE 全部命名参数化，严禁拼接用户输入；
3. 非白名单表名/字段名直接拒绝编译；
4. 仅生成只读 SELECT，不产生任何写操作。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.metric import Metric

DIALECTS = ("postgresql", "mysql", "clickhouse")
GRANULARITIES = ("hour", "day", "week", "month")

_AGG_SQL = {
    "sum": "SUM({expr})",
    "avg": "AVG({expr})",
    "count": "COUNT(*)",
    "count_distinct": "COUNT(DISTINCT {expr})",
    "max": "MAX({expr})",
    "min": "MIN({expr})",
    # 派生指标内部模式：MetricValue 中已存预计算值，按 SUM 聚合示意
    "ratio": "SUM({expr})",
}

_BUCKET_SQL = {
    "postgresql": {
        "hour": "date_trunc('hour', {col})",
        "day": "date_trunc('day', {col})",
        "week": "date_trunc('week', {col})",
        "month": "date_trunc('month', {col})",
    },
    "mysql": {
        "hour": "DATE_FORMAT({col}, '%Y-%m-%d %H:00:00')",
        "day": "DATE_FORMAT({col}, '%Y-%m-%d')",
        "week": "DATE_FORMAT({col}, '%x-W%v')",
        "month": "DATE_FORMAT({col}, '%Y-%m')",
    },
    "clickhouse": {
        "hour": "toStartOfHour({col})",
        "day": "toStartOfDay({col})",
        "week": "toStartOfWeek({col})",
        "month": "toStartOfMonth({col})",
    },
}

_ALLOWED_FORMULA_CHARS = set("0123456789+-*/(). ") | set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_FORMULA_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FORMULA_KEYWORDS = {"NULLIF", "COALESCE", "ABS", "ROUND"}


class SemanticCompileError(ValueError):
    """编译失败（非法参数 / 越界引用 / 护栏拒绝）。"""


@dataclass
class CompiledQuery:
    """编译产物：SQL 文本 + 参数 + 元信息。"""

    sql: str
    params: dict[str, Any] = field(default_factory=dict)
    dialect: str = "internal"  # internal / postgresql / mysql / clickhouse
    internal: bool = True  # True 表示面向 oc_metric_value 的内部查询计划
    note: str = ""
    derived: bool = False
    ref_metrics: list[str] = field(default_factory=list)


def _validate_dialect(dialect: str) -> str:
    if dialect not in DIALECTS:
        raise SemanticCompileError(f"不支持的方言: {dialect}，可选 {DIALECTS}")
    return dialect


def _validate_granularity(granularity: str) -> str:
    if granularity not in GRANULARITIES:
        raise SemanticCompileError(f"不支持的粒度: {granularity}，可选 {GRANULARITIES}")
    return granularity


def _agg_expr(agg_func: str, value_field: str) -> str:
    template = _AGG_SQL.get(agg_func or "sum")
    if template is None:
        raise SemanticCompileError(f"不支持的聚合函数: {agg_func}")
    if agg_func == "count":
        return template
    return template.format(expr=value_field)


def _bucket_expr(dialect: str, granularity: str, time_field: str) -> str:
    return _BUCKET_SQL[dialect][granularity].format(col=time_field)


def _escape_ident(ident: str) -> str:
    """标识符安全化：仅允许字母数字下划线，拒绝注入。"""
    if not ident or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ident):
        raise SemanticCompileError(f"非法标识符: {ident!r}")
    return ident


def _formula_operands(formula: str) -> list[str]:
    """提取公式中引用的指标 code；含非法字符直接拒绝。"""
    if not formula:
        return []
    if any(ch not in _ALLOWED_FORMULA_CHARS for ch in formula):
        raise SemanticCompileError(f"公式包含非法字符: {formula!r}")
    return [t for t in _FORMULA_TOKEN.findall(formula) if t not in _FORMULA_KEYWORDS]


def _dims_hash(dims: Optional[dict[str, Any]]) -> str:
    """与 metric_service.dims_hash 对齐的内部维度指纹。"""
    if not dims:
        return ""
    return "&".join(f"{k}={v}" for k, v in sorted(dims.items(), key=lambda x: x[0]))


def compile_internal(
    metric: Metric,
    *,
    granularity: str = "day",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    dims_filter: Optional[dict[str, Any]] = None,
    value_field: str = "value",
    time_field: str = "stat_time",
) -> CompiledQuery:
    """内部查询计划：面向 oc_metric_value 表（指标值表）编译只读 SQL。

    执行层通常不直接跑这段 SQL，而是转调 metric_service.query_values
    做 Python 聚合；此处产出 SQL 供 sql-preview 展示与审计。
    """
    _validate_granularity(granularity)
    _escape_ident(value_field)
    _escape_ident(time_field)
    params: dict[str, Any] = {"metric_id": metric.id}
    where = ["metric_id = :metric_id"]
    if start is not None:
        params["start"] = start
        where.append(f"{time_field} >= :start")
    if end is not None:
        params["end"] = end
        where.append(f"{time_field} < :end")
    dim_hash = ""
    if dims_filter:
        dim_hash = _dims_hash(dims_filter)
        params["dims_hash"] = dim_hash
        where.append("dims_hash = :dims_hash")
    bucket = _BUCKET_SQL["postgresql"][granularity].format(col=time_field)
    sql = (
        f"SELECT {bucket} AS bucket,\n"
        f"       {_agg_expr(metric.agg_func or 'sum', value_field)} AS value\n"
        f"FROM oc_metric_value\n"
        f"WHERE {' AND '.join(where)}\n"
        f"GROUP BY 1\n"
        f"ORDER BY 1 ASC"
    )
    note = "内部指标值表查询计划"
    if dim_hash:
        note += f"（维度指纹 {dim_hash}）"
    return CompiledQuery(sql=sql, params=params, dialect="internal", internal=True, note=note)


def compile_external(
    metric: Metric,
    *,
    granularity: str = "day",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    dims_filter: Optional[dict[str, Any]] = None,
    dialect: str = "postgresql",
    source_table: str = "",
    time_field: str = "created_at",
    value_field: str = "value",
    dim_map: Optional[dict[str, str]] = None,
) -> CompiledQuery:
    """外部查询计划：面向数据源事实表编译只读 SQL。

    source_table / time_field / value_field 必须来自数据源 extra_config 白名单，
    dim_map 必须来自指标注册表维度（dim.code → dim.source_field）。
    """
    _validate_dialect(dialect)
    _validate_granularity(granularity)
    table = _escape_ident(source_table)
    tcol = _escape_ident(time_field)
    vcol = _escape_ident(value_field)
    params: dict[str, Any] = {}
    where = []
    if start is not None:
        params["start"] = start
        where.append(f"{tcol} >= :start")
    if end is not None:
        params["end"] = end
        where.append(f"{tcol} < :end")
    dim_cols: list[str] = []
    if dims_filter:
        for code, val in sorted(dims_filter.items()):
            if val == "__group__":
                raise SemanticCompileError(f"外部模式暂不支持按维度分组（{code}），请使用内部模式")
            field_name = (dim_map or {}).get(code)
            if not field_name:
                raise SemanticCompileError(f"维度未在指标注册表中声明: {code}")
            col = _escape_ident(field_name)
            pkey = f"dim_{code}"
            params[pkey] = val
            where.append(f"{col} = :{pkey}")
            dim_cols.append(col)
    bucket = _BUCKET_SQL[dialect][granularity].format(col=tcol)
    group_cols = ", ".join([f"1"] + dim_cols) if dim_cols else "1"
    select_cols = ", ".join([f"{bucket} AS bucket"] + dim_cols + [f"{_agg_expr(metric.agg_func or 'sum', vcol)} AS value"])
    sql = (
        f"SELECT {select_cols}\n"
        f"FROM {table}\n"
        + (f"WHERE {' AND '.join(where)}\n" if where else "")
        + f"GROUP BY {group_cols}\n"
        + f"ORDER BY 1 ASC"
    )
    return CompiledQuery(
        sql=sql,
        params=params,
        dialect=dialect,
        internal=False,
        note=f"外部事实表 {table} 查询计划",
    )


def compile_derived_external(
    metric: Metric,
    *,
    refs: list[dict[str, Any]],
    formula: str = "",
    granularity: str = "day",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    dialect: str = "postgresql",
) -> CompiledQuery:
    """派生指标外部编译：公式引用指标各自聚合成 CTE，再按 bucket 对齐求比值/表达式。

    refs 每项含 {code, agg_func, source_table, time_field, value_field}，
    均由注册表/数据源白名单提供。MySQL 不支持 FULL OUTER JOIN，拒绝编译。
    """
    _validate_dialect(dialect)
    if dialect == "mysql":
        raise SemanticCompileError("派生指标外部编译暂不支持 MySQL（FULL OUTER JOIN 缺失），请使用内部模式")
    _validate_granularity(granularity)
    if not formula:
        raise SemanticCompileError("派生指标缺少 formula")
    operands = _formula_operands(formula)
    if not operands:
        raise SemanticCompileError("派生指标公式未引用任何指标")
    ref_by_code: dict[str, dict[str, Any]] = {}
    for ref in refs:
        ref_by_code[ref["code"]] = ref
    for op in operands:
        if op not in ref_by_code:
            raise SemanticCompileError(f"公式引用的指标不在注册表中: {op}")

    params: dict[str, Any] = {}
    ctes: list[str] = []
    alias_exprs: dict[str, str] = {}
    for i, op in enumerate(operands):
        ref = ref_by_code[op]
        table = _escape_ident(ref["source_table"])
        tcol = _escape_ident(ref["time_field"])
        vcol = _escape_ident(ref["value_field"])
        agg = _agg_expr(ref.get("agg_func") or "sum", vcol)
        where = []
        if start is not None:
            pkey = f"r{i}_start"
            params[pkey] = start
            where.append(f"{tcol} >= :{pkey}")
        if end is not None:
            pkey = f"r{i}_end"
            params[pkey] = end
            where.append(f"{tcol} < :{pkey}")
        bucket = _BUCKET_SQL[dialect][granularity].format(col=tcol)
        ctes.append(
            f"r{i} AS (\n"
            f"  SELECT {bucket} AS bucket, {agg} AS v FROM {table}\n"
            + (f"  WHERE {' AND '.join(where)}\n" if where else "")
            + "  GROUP BY 1\n)"
        )
        alias_exprs[op] = f"COALESCE(r{i}.v, 0)"
    expr = formula
    for op, alias in alias_exprs.items():
        expr = re.sub(rf"\b{op}\b", alias, expr)
    join_sql = " FULL OUTER JOIN ".join(
        [f"r{i}" for i in range(len(operands))]
    )
    join_ons = " AND ".join(
        f"r0.bucket = r{i}.bucket" for i in range(1, len(operands))
    )
    select_cols = ["COALESCE(r0.bucket, r1.bucket) AS bucket" if len(operands) > 1 else "r0.bucket AS bucket", f"({expr}) AS value"]
    sql = (
        f"WITH {', '.join(ctes)}\n"
        f"SELECT {', '.join(select_cols)}\n"
        f"FROM {join_sql}" + (f" ON {join_ons}" if join_ons else "") + "\n"
        f"ORDER BY 1 ASC"
    )
    return CompiledQuery(
        sql=sql,
        params=params,
        dialect=dialect,
        internal=False,
        derived=True,
        ref_metrics=operands,
        note=f"派生指标（{formula}）外部查询计划",
    )


def compile_metric(
    metric: Metric,
    *,
    granularity: str = "day",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    dims_filter: Optional[dict[str, Any]] = None,
    dialect: Optional[str] = None,
    source_table: Optional[str] = None,
    time_field: Optional[str] = None,
    value_field: Optional[str] = None,
    dim_map: Optional[dict[str, str]] = None,
    ref_metrics: Optional[list[dict[str, Any]]] = None,
) -> CompiledQuery:
    """编译总入口：按指标属性选择内部 / 外部 / 派生路径。

    - formula 非空且提供 ref_metrics → 派生外部编译（MySQL 自动降级内部）；
    - source_table 非空 → 外部事实表编译；
    - 否则 → 内部指标值表编译（默认）。
    """
    if metric.formula:
        if ref_metrics and dialect != "mysql":
            try:
                return compile_derived_external(
                    metric,
                    refs=ref_metrics,
                    formula=metric.formula,
                    granularity=granularity,
                    start=start,
                    end=end,
                    dialect=dialect or "postgresql",
                )
            except SemanticCompileError:
                # 外部派生不可行（缺引用元数据 / 方言限制）时降级内部计划
                pass
        return compile_internal(
            metric,
            granularity=granularity,
            start=start,
            end=end,
            dims_filter=dims_filter,
        )
    if source_table:
        return compile_external(
            metric,
            granularity=granularity,
            start=start,
            end=end,
            dims_filter=dims_filter,
            dialect=dialect or "postgresql",
            source_table=source_table,
            time_field=time_field or "created_at",
            value_field=value_field or "value",
            dim_map=dim_map,
        )
    return compile_internal(
        metric,
        granularity=granularity,
        start=start,
        end=end,
        dims_filter=dims_filter,
    )


def compile_for_metric(
    db: Session,
    metric: Metric,
    *,
    tenant_id: int,
    granularity: str = "day",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    dims_filter: Optional[dict[str, Any]] = None,
    dialect: Optional[str] = None,
) -> CompiledQuery:
    """服务层编译入口：按注册表/数据源元数据组装外部编译上下文后编译。

    从数据库补齐三块白名单信息：
    - dim_map：指标注册表维度（dim.code → dim.source_field）；
    - source_table/time_field/value_field：绑定数据源 extra_config 白名单；
    - ref_metrics：派生指标公式引用的基础指标及其来源列。
    任一信息缺失时自动降级为内部查询计划，不抛异常。
    """
    dim_map: dict[str, str] = {}
    try:
        from app.models.metric import MetricDimension

        dims = (
            db.query(MetricDimension)
            .filter(MetricDimension.tenant_id == tenant_id)
            .all()
        )
        dim_map = {
            d.code: d.source_field for d in dims if d.code and d.source_field
        }
    except Exception:  # noqa: BLE001 维度元数据不可用视为无白名单
        dim_map = {}

    source_table: Optional[str] = None
    time_field: Optional[str] = None
    value_field: Optional[str] = None
    if metric.source_id is not None:
        try:
            from app.models.datasource import DataSource

            ds = db.get(DataSource, metric.source_id)
            if ds is not None:
                extra = ds.extra_config or {}
                source_table = extra.get("source_table") or ""
                time_field = extra.get("time_field") or "created_at"
                value_field = extra.get("value_field") or "value"
        except Exception:  # noqa: BLE001 数据源不可用视为未配置外部表
            source_table = None

    ref_metrics: Optional[list[dict[str, Any]]] = None
    if metric.formula:
        operands = _formula_operands(metric.formula)
        if operands:
            ref_metrics = []
            try:
                from app.models.metric import Metric as _Metric

                rows = (
                    db.query(_Metric)
                    .filter(_Metric.code.in_(operands), _Metric.tenant_id == tenant_id)
                    .all()
                )
                for rm in rows:
                    entry: dict[str, Any] = {
                        "code": rm.code,
                        "agg_func": rm.agg_func or "sum",
                    }
                    if rm.source_id is not None:
                        try:
                            from app.models.datasource import DataSource as _DS

                            ds = db.get(_DS, rm.source_id)
                            if ds is not None:
                                extra = ds.extra_config or {}
                                entry["source_table"] = extra.get("source_table") or ""
                                entry["time_field"] = extra.get("time_field") or "created_at"
                                entry["value_field"] = extra.get("value_field") or "value"
                        except Exception:  # noqa: BLE001 引用指标无外部表时留空
                            pass
                    ref_metrics.append(entry)
            except Exception:  # noqa: BLE001 引用指标查询失败则退化为内部派生
                ref_metrics = []

    return compile_metric(
        metric,
        granularity=granularity,
        start=start,
        end=end,
        dims_filter=dims_filter,
        dialect=dialect,
        source_table=source_table or None,
        time_field=time_field,
        value_field=value_field,
        dim_map=dim_map or None,
        ref_metrics=ref_metrics,
    )
