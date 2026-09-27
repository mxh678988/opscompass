"""数据源类型识别与存储引擎路由。

识别依据（按优先级）：
1. 数据源类型 ds_type（mysql/postgresql/clickhouse/hive/api/csv）
2. 文件后缀 file_ext（csv/xlsx/json/log/txt/md/pdf/docx/...）
3. 内容特征 content_hint（时序 / 全文 / 缓存 / 文件 / 结构化关键词）

规则持久化在 oc_storage_route_rule，内置全局规则（tenant_id=NULL）由 bootstrap 幂等写入，
租户可新增覆盖规则（同 match_field+match_value 优先取租户规则，再按 priority 排序）。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import or_, text

from app.core.config import settings
from app.models.storage import DATA_KINDS, StorageRouteRule
from app.storage.cache import cache_adapter
from app.storage.files import file_adapter
from app.storage.relational import relational_adapter
from app.storage.search import search_adapter
from app.storage.timeseries import timeseries_adapter

logger = logging.getLogger(__name__)

# 内置全局规则：(name, match_field, match_value, data_kind, engine, priority)
DEFAULT_RULES: tuple[tuple[str, str, str, str, str, int], ...] = (
    # ---- 数据源类型 ----
    ("MySQL 数据源", "ds_type", "mysql", "relational", "postgresql", 100),
    ("PostgreSQL 数据源", "ds_type", "postgresql", "relational", "postgresql", 100),
    ("ClickHouse 数据源(时序)", "ds_type", "clickhouse", "timeseries", "postgresql_partitioned", 100),
    ("Hive 数据源", "ds_type", "hive", "relational", "postgresql", 100),
    ("Redis 数据源(缓存)", "ds_type", "redis", "cache", "redis", 100),
    ("Elasticsearch 数据源(全文)", "ds_type", "elasticsearch", "fulltext", "postgresql_gin", 100),
    ("API 数据源", "ds_type", "api", "relational", "postgresql", 100),
    ("CSV 数据源", "ds_type", "csv", "relational", "postgresql", 100),
    # ---- 文件后缀 ----
    ("CSV 文件", "file_ext", "csv", "relational", "postgresql", 110),
    ("Excel 文件", "file_ext", "xlsx", "relational", "postgresql", 110),
    ("Excel 97-2003 文件", "file_ext", "xls", "relational", "postgresql", 110),
    ("JSON 文件", "file_ext", "json", "relational", "postgresql", 110),
    ("Parquet 文件", "file_ext", "parquet", "relational", "postgresql", 110),
    ("日志文件", "file_ext", "log", "fulltext", "postgresql_gin", 110),
    ("文本文件", "file_ext", "txt", "fulltext", "postgresql_gin", 110),
    ("Markdown 文件", "file_ext", "md", "fulltext", "postgresql_gin", 110),
    ("PDF 文件", "file_ext", "pdf", "fulltext", "postgresql_gin", 110),
    ("Word 文件", "file_ext", "docx", "fulltext", "postgresql_gin", 110),
    ("Word 文件(doc)", "file_ext", "doc", "fulltext", "postgresql_gin", 110),
    ("图片文件", "file_ext", "png", "file", "local_fs", 110),
    ("图片文件(jpg)", "file_ext", "jpg", "file", "local_fs", 110),
    ("图片文件(jpeg)", "file_ext", "jpeg", "file", "local_fs", 110),
    ("压缩包", "file_ext", "zip", "file", "local_fs", 110),
    # ---- 内容特征（关键词以 | 分隔）----
    ("时序类数据", "content_hint", "时间序列|时序|时间戳|stat_time|timestamp|分钟级|小时级聚合", "timeseries", "postgresql_partitioned", 200),
    ("全文检索类数据", "content_hint", "全文|日志|文本|描述|备注|文档|评论|反馈|log", "fulltext", "postgresql_gin", 210),
    ("缓存类数据", "content_hint", "热点|缓存|高频读取|排行榜|cache", "cache", "redis", 220),
    ("文件类数据", "content_hint", "文件|附件|图片|照片|file|attachment", "file", "local_fs", 230),
    ("结构化业务数据", "content_hint", "指标|维度|订单|用户|渠道|商品|门店|营收|结构化", "relational", "postgresql", 240),
)

ADAPTERS = {
    "relational": relational_adapter,
    "timeseries": timeseries_adapter,
    "fulltext": search_adapter,
    "cache": cache_adapter,
    "file": file_adapter,
}


def get_adapter(kind: str):
    """按数据类型取适配器（未知类型回落关系型）。"""
    return ADAPTERS.get(kind or "", relational_adapter)


# ------------------------------------------------------------ 规则维护
def ensure_default_rules(db, tenant_id: Optional[int] = None) -> int:
    """幂等写入内置全局规则；可按租户复制一份（用于租户自定义覆盖）。"""
    created = 0
    for name, field, value, kind, engine, priority in DEFAULT_RULES:
        exists = (
            db.query(StorageRouteRule)
            .filter(
                StorageRouteRule.tenant_id.is_(None) if tenant_id is None else StorageRouteRule.tenant_id == tenant_id,
                StorageRouteRule.match_field == field,
                StorageRouteRule.match_value == value,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            StorageRouteRule(
                tenant_id=tenant_id,
                name=name,
                match_field=field,
                match_value=value,
                data_kind=kind,
                engine=engine,
                priority=priority,
                enabled=True,
                remark="系统内置规则",
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def load_rules(db, tenant_id: Optional[int] = None, enabled_only: bool = True) -> list[StorageRouteRule]:
    """加载生效规则：租户规则优先，其次全局规则。"""
    query = db.query(StorageRouteRule).filter(
        or_(StorageRouteRule.tenant_id.is_(None), StorageRouteRule.tenant_id == tenant_id)
    )
    if enabled_only:
        query = query.filter(StorageRouteRule.enabled.is_(True))
    return query.order_by(StorageRouteRule.priority.asc(), StorageRouteRule.id.asc()).all()


# ------------------------------------------------------------ 类型识别
def _normalize(file_ext: Optional[str]) -> Optional[str]:
    if not file_ext:
        return None
    return file_ext.strip().lower().lstrip(".")


def identify(
    db,
    ds_type: Optional[str] = None,
    file_ext: Optional[str] = None,
    content: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> dict:
    """识别接入数据类型并给出目标存储引擎。"""
    rules = load_rules(db, tenant_id)
    ds_type_n = (ds_type or "").strip().lower()
    file_ext_n = _normalize(file_ext)
    content_n = (content or "").strip().lower()

    candidates: list[tuple[int, StorageRouteRule, str]] = []
    for rule in rules:
        field, value = rule.match_field, (rule.match_value or "").lower()
        if field == "ds_type" and ds_type_n and value == ds_type_n:
            candidates.append((0, rule, f"data source type = {ds_type_n}"))
        elif field == "file_ext" and file_ext_n and value == file_ext_n:
            candidates.append((0, rule, f"file extension = .{file_ext_n}"))
        elif field == "content_hint" and content_n:
            keywords = [k.strip() for k in value.split("|") if k.strip()]
            hit = next((k for k in keywords if k in content_n), None)
            if hit:
                candidates.append((1, rule, f"content keyword = {hit}"))

    if not candidates:
        adapter = relational_adapter
        return {
            "data_kind": "relational",
            "engine": adapter.engine,
            "label": adapter.label,
            "matched": False,
            "reason": "未命中任何规则，默认按结构化数据落入关系型存储",
            "inputs": {"ds_type": ds_type_n or None, "file_ext": file_ext_n, "content": bool(content)},
        }

    candidates.sort(key=lambda x: (x[0], x[1].priority, x[1].id))
    _, rule, reason = candidates[0]
    adapter = get_adapter(rule.data_kind)
    return {
        "data_kind": rule.data_kind,
        "engine": rule.engine or adapter.engine,
        "label": adapter.label,
        "matched": True,
        "reason": f"命中规则「{rule.name}」（{reason}）",
        "rule_id": rule.id,
        "inputs": {"ds_type": ds_type_n or None, "file_ext": file_ext_n, "content": bool(content)},
    }


def route_overview(db, tenant_id: Optional[int] = None) -> dict:
    """路由规则与识别概览。"""
    rules = load_rules(db, tenant_id, enabled_only=False)
    by_kind: dict[str, int] = {}
    for rule in rules:
        by_kind[rule.data_kind] = by_kind.get(rule.data_kind, 0) + 1
    return {
        "routing_enabled": settings.STORAGE_ROUTING_ENABLED,
        "rule_count": len(rules),
        "custom_rule_count": sum(1 for r in rules if r.tenant_id is not None),
        "by_kind": by_kind,
        "kinds": [
            {
                "data_kind": kind,
                "engine": get_adapter(kind).engine,
                "label": get_adapter(kind).label,
            }
            for kind in DATA_KINDS
        ],
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "match_field": r.match_field,
                "match_value": r.match_value,
                "data_kind": r.data_kind,
                "engine": r.engine,
                "priority": r.priority,
                "enabled": r.enabled,
                "tenant_id": r.tenant_id,
            }
            for r in rules
        ],
    }


def example_identifications(db, tenant_id: Optional[int] = None) -> list[dict]:
    """内置样例识别结果，便于在概览接口中直观展示路由效果。"""
    samples = [
        {"ds_type": "mysql", "file_ext": None, "content": None},
        {"ds_type": "clickhouse", "file_ext": None, "content": None},
        {"ds_type": None, "file_ext": "csv", "content": None},
        {"ds_type": None, "file_ext": None, "content": "门店日报表，含 stat_time 时间序列字段"},
        {"ds_type": None, "file_ext": None, "content": "客户评论与日志全文，需要按关键词检索"},
        {"ds_type": None, "file_ext": None, "content": "首页排行榜，高频读取热点数据"},
        {"ds_type": None, "file_ext": None, "content": "合同扫描件附件文件"},
    ]
    results = []
    for sample in samples:
        results.append(identify(db, tenant_id=tenant_id, **sample))
    return results


def table_exists(db, name: str) -> bool:
    return bool(db.execute(text("SELECT to_regclass(:n) IS NOT NULL"), {"n": name}).scalar())
