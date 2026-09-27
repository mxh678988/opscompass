"""数据分级引擎：规则匹配定级 + AI 辅助定级 + 人工覆盖。

分级对象：指标(metric) / 数据源(data_source) / 导入任务(import_task) / 分析结果(analysis)。
默认规则见 DEFAULT_RULES；未命中任何规则时回落默认级别 DEFAULT_LEVEL（L2 内部）。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import (
    DATA_LEVEL_META,
    DATA_LEVEL_ORDER,
    AiDataLevelRecord,
    AiDataLevelRule,
)
from app.models.import_task import ImportTask
from app.models.metric import Metric
from app.models.datasource import DataSource
from app.services.ai.llm_client import LLMClient, LLMError, extract_json

DEFAULT_LEVEL = "L2"

# 内置分级规则（priority 越大越先匹配）
DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "code": "B101",
        "name": "疑似个人敏感信息 / 凭据兜底",
        "object_type": "*",
        "field": "text",
        "operator": "regex",
        "threshold": ["(手机号|身份证|银行卡|密码|口令|密钥|secret|passwd|token|私钥)"],
        "level": "L4",
        "priority": 300,
        "description": "对象名称/描述/编码中出现个人敏感信息或密钥类关键词，直接定级 L4 机密。",
    },
    {
        "code": "B102",
        "name": "含连接凭据的数据源",
        "object_type": "data_source",
        "field": "has_credential",
        "operator": "eq",
        "threshold": ["true"],
        "level": "L3",
        "priority": 280,
        "description": "数据源配置中落库了连接凭据（密文），定级 L3 敏感。",
    },
    {
        "code": "B103",
        "name": "用户标识类指标",
        "object_type": "metric",
        "field": "code",
        "operator": "in",
        "threshold": ["users", "uv", "dau", "mau", "user_active", "conversion_rate", "new_users"],
        "level": "L3",
        "priority": 250,
        "description": "与用户标识/转化明细相关的指标，定级 L3 敏感。",
    },
    {
        "code": "B104",
        "name": "小时级细粒度数据",
        "object_type": "metric",
        "field": "granularity",
        "operator": "in",
        "threshold": ["hour"],
        "level": "L2",
        "priority": 200,
        "description": "小时级粒度可反推经营细节，定级 L2 内部。",
    },
    {
        "code": "B105",
        "name": "文件型数据源",
        "object_type": "data_source",
        "field": "ds_type",
        "operator": "in",
        "threshold": ["csv", "file", "excel", "upload", "manual"],
        "level": "L2",
        "priority": 150,
        "description": "本地文件上传类数据源，定级 L2 内部。",
    },
    {
        "code": "B106",
        "name": "聚合指标（日/周/月）",
        "object_type": "metric",
        "field": "granularity",
        "operator": "in",
        "threshold": ["day", "week", "month"],
        "level": "L1",
        "priority": 100,
        "description": "已聚合的常规粒度指标，可对外披露，定级 L1 公开。",
    },
    {
        "code": "B107",
        "name": "异常导入任务",
        "object_type": "import_task",
        "field": "status",
        "operator": "in",
        "threshold": ["failed", "partial"],
        "level": "L2",
        "priority": 80,
        "description": "失败/部分成功的导入任务，涉及数据质量，定级 L2 内部。",
    },
]

_CREDENTIAL_FIELDS = (
    "password_enc",
    "password_encrypted",
    "password",
    "credential",
    "credentials",
    "config_encrypted",
    "access_token",
    "token",
)


# ---------------------------------------------------------------- 默认规则
def ensure_default_rules(db: Session, tenant_id: int) -> int:
    """写入缺失的内置分级规则，返回新增条数。"""
    existing = set(
        db.execute(
            select(AiDataLevelRule.code).where(AiDataLevelRule.tenant_id == tenant_id)
        ).scalars().all()
    )
    added = 0
    for item in DEFAULT_RULES:
        if item["code"] in existing:
            continue
        db.add(AiDataLevelRule(tenant_id=tenant_id, builtin=True, enabled=True, **item))
        added += 1
    if added:
        db.commit()
    return added


def list_rules(db: Session, tenant_id: int) -> list[AiDataLevelRule]:
    return list(
        db.execute(
            select(AiDataLevelRule)
            .where(AiDataLevelRule.tenant_id == tenant_id)
            .order_by(AiDataLevelRule.priority.desc(), AiDataLevelRule.id.asc())
        ).scalars().all()
    )


# ---------------------------------------------------------------- 对象上下文
def build_context(obj: Any) -> dict[str, Any]:
    """把 ORM 对象摊平成可判定的字段字典。"""
    data: dict[str, Any] = {}
    for key in (
        "code",
        "name",
        "description",
        "granularity",
        "status",
        "type",
        "owner",
        "unit",
        "file_name",
        "source_type",
        "title",
    ):
        if hasattr(obj, key):
            value = getattr(obj, key)
            if value is not None:
                data[key] = value
    for key in _CREDENTIAL_FIELDS:
        if hasattr(obj, key):
            data["has_credential"] = bool(getattr(obj, key))
            break
    if "has_credential" not in data:
        data["has_credential"] = False
    data["text"] = " ".join(str(v) for v in data.values() if not isinstance(v, bool))
    return data


def _as_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def _match(rule: AiDataLevelRule, ctx: dict[str, Any]) -> bool:
    """单条规则匹配。"""
    if rule.field not in ctx:
        return False
    value = ctx.get(rule.field)
    thresholds = [_as_str(t) for t in (rule.threshold or [])]
    current = _as_str(value)
    op = (rule.operator or "in").lower()

    if op == "eq":
        return bool(thresholds) and current == thresholds[0]
    if op == "ne":
        return bool(thresholds) and current != thresholds[0]
    if op == "in":
        return current in thresholds
    if op == "contains":
        return any(t and t in current for t in thresholds)
    if op == "regex":
        return any(t and re.search(t, current, flags=re.I) for t in thresholds)
    if op == "exists":
        want = thresholds[0].lower() == "true" if thresholds else True
        return bool(current) is want
    if op in ("gte", "lte"):
        try:
            left, right = float(current), float(thresholds[0])
        except (TypeError, ValueError, IndexError):
            return False
        return left >= right if op == "gte" else left <= right
    return False


def resolve_level(
    db: Session, tenant_id: int, object_type: str, ctx: dict[str, Any]
) -> tuple[str, Optional[AiDataLevelRule], str]:
    """按优先级匹配规则，返回 (级别, 命中规则, 判定依据)。"""
    rules = list_rules(db, tenant_id)
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.object_type not in ("*", object_type):
            continue
        if _match(rule, ctx):
            return rule.level, rule, f"命中规则 {rule.code}「{rule.name}」"
    return DEFAULT_LEVEL, None, f"未命中任何规则，回落默认级别 {DEFAULT_LEVEL}"


def upsert_record(
    db: Session,
    tenant_id: int,
    *,
    object_type: str,
    object_id: int,
    object_code: str,
    level: str,
    source: str = "rule",
    rule: Optional[AiDataLevelRule] = None,
    confidence: Optional[float] = None,
    grader: str = "rule-engine",
    reason: str = "",
    commit: bool = True,
) -> AiDataLevelRecord:
    """写入/更新分级结果（同对象唯一）。"""
    record = db.execute(
        select(AiDataLevelRecord).where(
            AiDataLevelRecord.tenant_id == tenant_id,
            AiDataLevelRecord.object_type == object_type,
            AiDataLevelRecord.object_id == object_id,
        )
    ).scalars().first()
    if record is None:
        record = AiDataLevelRecord(
            tenant_id=tenant_id, object_type=object_type, object_id=object_id
        )
        db.add(record)
    record.object_code = object_code or record.object_code or ""
    record.level = level
    record.source = source
    record.rule_id = rule.id if rule else None
    record.rule_code = rule.code if rule else None
    record.confidence = confidence
    record.grader = grader
    record.reason = reason
    if commit:
        db.commit()
        db.refresh(record)
    return record


def grade_object(
    db: Session,
    tenant_id: int,
    object_type: str,
    obj: Any,
    *,
    source: str = "rule",
    grader: str = "rule-engine",
    commit: bool = True,
) -> AiDataLevelRecord:
    """对单个对象定级并落库。"""
    ctx = build_context(obj)
    level, rule, reason = resolve_level(db, tenant_id, object_type, ctx)
    return upsert_record(
        db,
        tenant_id,
        object_type=object_type,
        object_id=int(obj.id),
        object_code=_as_str(ctx.get("code") or ctx.get("name")),
        level=level,
        source=source,
        rule=rule,
        grader=grader,
        reason=reason,
        commit=commit,
    )


def grade_all(
    db: Session, tenant_id: int, object_types: Optional[list[str]] = None
) -> dict[str, Any]:
    """批量定级：指标 / 数据源 / 导入任务。"""
    targets = object_types or ["metric", "data_source", "import_task"]
    ensure_default_rules(db, tenant_id)

    graded = 0
    summary: dict[str, int] = {level: 0 for level in DATA_LEVEL_META}
    details: list[dict[str, Any]] = []

    if "metric" in targets:
        for metric in db.execute(select(Metric).where(Metric.tenant_id == tenant_id)).scalars():
            record = grade_object(db, tenant_id, "metric", metric, commit=False)
            graded += 1
            summary[record.level] = summary.get(record.level, 0) + 1
            details.append(
                {"object_type": "metric", "code": metric.code, "level": record.level, "reason": record.reason}
            )
    if "data_source" in targets:
        for source_obj in db.execute(
            select(DataSource).where(DataSource.tenant_id == tenant_id)
        ).scalars():
            record = grade_object(db, tenant_id, "data_source", source_obj, commit=False)
            graded += 1
            summary[record.level] = summary.get(record.level, 0) + 1
            details.append(
                {
                    "object_type": "data_source",
                    "code": source_obj.name,
                    "level": record.level,
                    "reason": record.reason,
                }
            )
    if "import_task" in targets:
        tasks = db.execute(
            select(ImportTask).where(ImportTask.tenant_id == tenant_id).order_by(ImportTask.id.desc()).limit(200)
        ).scalars().all()
        for task in tasks:
            record = grade_object(db, tenant_id, "import_task", task, commit=False)
            graded += 1
            summary[record.level] = summary.get(record.level, 0) + 1
            details.append(
                {
                    "object_type": "import_task",
                    "code": getattr(task, "file_name", f"task-{task.id}"),
                    "level": record.level,
                    "reason": record.reason,
                }
            )

    db.commit()
    return {"graded": graded, "level_summary": summary, "details": details[:100]}


# ---------------------------------------------------------------- 查询
def get_level(db: Session, tenant_id: int, object_type: str, object_id: int) -> Optional[AiDataLevelRecord]:
    return db.execute(
        select(AiDataLevelRecord).where(
            AiDataLevelRecord.tenant_id == tenant_id,
            AiDataLevelRecord.object_type == object_type,
            AiDataLevelRecord.object_id == object_id,
        )
    ).scalars().first()


def level_of_metric_code(db: Session, tenant_id: int, code: str) -> str:
    """按指标编码取级别，未定级时返回默认级别。"""
    record = db.execute(
        select(AiDataLevelRecord).where(
            AiDataLevelRecord.tenant_id == tenant_id,
            AiDataLevelRecord.object_type == "metric",
            AiDataLevelRecord.object_code == code,
        )
    ).scalars().first()
    return record.level if record else DEFAULT_LEVEL


def max_level(levels: list[str]) -> str:
    """取一组级别中最高（最严）的一级。"""
    if not levels:
        return DEFAULT_LEVEL
    return max(levels, key=lambda item: DATA_LEVEL_ORDER.get(item, 0))


def list_records(
    db: Session, tenant_id: int, object_type: Optional[str] = None, level: Optional[str] = None
) -> list[AiDataLevelRecord]:
    stmt = select(AiDataLevelRecord).where(AiDataLevelRecord.tenant_id == tenant_id)
    if object_type:
        stmt = stmt.where(AiDataLevelRecord.object_type == object_type)
    if level:
        stmt = stmt.where(AiDataLevelRecord.level == level)
    return list(
        db.execute(stmt.order_by(AiDataLevelRecord.graded_at.desc(), AiDataLevelRecord.id.desc())).scalars()
    )


# ---------------------------------------------------------------- AI 辅助定级
AI_GRADE_SYSTEM_PROMPT = (
    "你是企业数据安全分级专家。依据给定的数据资产清单，判定每项数据的敏感级别：\n"
    "L1=公开（已聚合、可对外披露）；L2=内部（内部粒度数据）；L3=敏感（含用户标识、连接凭据或经营敏感信息）；"
    "L4=机密（含个人敏感信息或密钥）。\n"
    "严格只输出 JSON，不要解释，格式："
    '{"items":[{"index":1,"level":"L1|L2|L3|L4","confidence":0.0-1.0,"reason":"简短依据"}]}'
)


def ai_suggest_levels(
    db: Session, tenant_id: int, object_type: str, objects: list[Any], limit: int = 20
) -> dict[str, Any]:
    """用大模型为对象给出分级建议并落库（source=ai，grader=AI 模型名）。

    返回 {"items": [...], "mode": ..., "model": ..., "applied": n}
    """
    if not objects:
        return {"items": [], "mode": settings.ai_mode, "model": settings.ai_model, "applied": 0}

    lines = []
    for idx, obj in enumerate(objects[:limit], start=1):
        ctx = build_context(obj)
        brief = {k: v for k, v in ctx.items() if k != "text"}
        lines.append(f"{idx}. {brief}")

    user_prompt = (
        f"对象类型：{object_type}\n数据资产清单（JSON 行）：\n" + "\n".join(lines) + "\n请逐项给出级别判定。"
    )
    client = LLMClient()
    result = client.chat(
        [
            {"role": "system", "content": AI_GRADE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    parsed = extract_json(result.text)
    if not parsed:
        raise LLMError("AI 定级返回内容无法解析为 JSON")

    items = parsed.get("items") or []
    applied: list[dict[str, Any]] = []
    for item in items:
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if index < 1 or index > len(objects):
            continue
        obj = objects[index - 1]
        level = str(item.get("level", "")).upper()
        if level not in DATA_LEVEL_META:
            continue
        confidence = item.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None
        ctx = build_context(obj)
        rule_level, rule, _rule_reason = resolve_level(db, tenant_id, object_type, ctx)
        # 安全原则：AI 建议不得降低规则判定的级别，就高不就低
        final_level = max_level([rule_level, level])
        downgrade_blocked = DATA_LEVEL_ORDER.get(level, 0) < DATA_LEVEL_ORDER.get(rule_level, 0)
        reason = f"AI 定级（{result.mode}）：{item.get('reason', '')}"
        if downgrade_blocked:
            reason = (
                f"{reason}；AI 建议 {level} 低于规则级别 {rule_level}"
                f"（{rule.code if rule else '-'}），按就高原则取 {final_level}"
            )
        record = upsert_record(
            db,
            tenant_id,
            object_type=object_type,
            object_id=int(obj.id),
            object_code=_as_str(ctx.get("code") or ctx.get("name")),
            level=final_level,
            source="ai",
            rule=rule,
            confidence=confidence,
            grader=result.model,
            reason=reason,
            commit=False,
        )
        applied.append(
            {
                "object_id": obj.id,
                "code": record.object_code,
                "level": final_level,
                "ai_level": level,
                "rule_level": rule_level,
                "downgrade_blocked": downgrade_blocked,
                "confidence": confidence,
                "reason": record.reason,
                "needs_human": final_level == "L4" or downgrade_blocked,
            }
        )
    db.commit()
    return {
        "items": applied,
        "mode": result.mode,
        "model": result.model,
        "duration_ms": result.duration_ms,
        "applied": len(applied),
    }
