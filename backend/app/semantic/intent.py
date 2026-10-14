"""Text2Metric 意图理解：自然语言 → 结构化查询意图。

双通道：
1. 模型路由（route_model capability=semantic_intent）输出结构化 JSON；
2. 规则兜底：指标名/别名关键词 + 时间词 + 粒度词 + 维度词匹配，
   保证模型不可用时问数闭环仍可演示。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.model_router.routing import ModelRouterError, route_model

GRANULARITY_KEYWORDS = [
    ("hour", ["按小时", "每小时", "分小时"]),
    ("day", ["按天", "按日", "每日", "每天", "天粒度"]),
    ("week", ["按周", "每周", "周粒度"]),
    ("month", ["按月", "每月", "月粒度"]),
]

RANGE_KEYWORDS = [
    ("today", ["今天", "今日"]),
    ("yesterday", ["昨天", "昨日"]),
    ("this_week", ["本周", "这周"]),
    ("last_week", ["上周", "上周"]),
    ("this_month", ["本月", "这个月"]),
    ("last_month", ["上月", "上个月"]),
    ("last_7d", ["近7天", "近七天", "最近7天", "7天内", "七天"]),
    ("last_30d", ["近30天", "近三十天", "最近30天", "30天内", "三十天", "近一个月"]),
    ("last_90d", ["近90天", "近九十天", "最近90天", "90天内", "近三个月"]),
]

# 相对时间范围解析（Asia/Shanghai）
TIMEZONE = "Asia/Shanghai"


class SemanticIntentError(ValueError):
    """意图解析失败（无可用指标 / 参数非法）。"""


@dataclass
class IntentResult:
    """结构化查询意图。"""

    metric_codes: list[str] = field(default_factory=list)
    granularity: str = "day"
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    dims_filter: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    model: Optional[str] = None
    mode: str = "rule"  # local / api / rule
    fallback: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


def _now() -> datetime:
    """当前时间（Asia/Shanghai，naive）。"""
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)


def _range_start_end(range_key: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """相对时间词 → (start, end)，end 为开区间。"""
    now = _now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    monday = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    table = {
        "today": (today, today + timedelta(days=1)),
        "yesterday": (today - timedelta(days=1), today),
        "this_week": (monday, today + timedelta(days=1)),
        "last_week": (monday - timedelta(days=7), monday),
        "this_month": (month_start, next_month),
        "last_month": ((month_start - timedelta(days=1)).replace(day=1), month_start),
        "last_7d": (today - timedelta(days=6), today + timedelta(days=1)),
        "last_30d": (today - timedelta(days=29), today + timedelta(days=1)),
        "last_90d": (today - timedelta(days=89), today + timedelta(days=1)),
    }
    if range_key not in table:
        return None, None
    return table[range_key]


def _match_range(question: str) -> Optional[str]:
    for key, kws in RANGE_KEYWORDS:
        for kw in kws:
            if kw in question:
                return key
    return None


def _match_granularity(question: str) -> Optional[str]:
    for g, kws in GRANULARITY_KEYWORDS:
        for kw in kws:
            if kw in question:
                return g
    return None


def _match_metrics(question: str, catalog: list[dict[str, Any]]) -> list[str]:
    """指标匹配：code/name/tags 任一命中即候选，按命中片段长度降序。"""
    hits: list[tuple[int, str]] = []
    for item in catalog:
        code = item.get("code", "")
        name = item.get("name", "")
        tags = item.get("tags") or []
        for kw in [code, name, *[str(t) for t in tags]]:
            if kw and kw in question:
                hits.append((len(kw), code))
                break
    hits.sort(key=lambda x: (-x[0], x[1]))
    return [code for _, code in hits]


def _match_dims(question: str, dims: list[dict[str, Any]]) -> dict[str, Any]:
    """维度匹配：命中维度 code/name 时输出按该维度分组意图。"""
    result: dict[str, Any] = {}
    for dim in dims or []:
        code = dim.get("code", "")
        name = dim.get("name", "")
        if code and (code in question or name in question):
            result[code] = "__group__"
    return result


def _rule_parse(
    question: str,
    catalog: list[dict[str, Any]],
    dims: list[dict[str, Any]],
) -> IntentResult:
    metrics = _match_metrics(question, catalog)
    if not metrics:
        raise SemanticIntentError("未识别到指标（可在指标中心登记后重试）")
    granularity = _match_granularity(question) or "day"
    range_key = _match_range(question) or "last_30d"
    start, end = _range_start_end(range_key)
    dims_filter = _match_dims(question, dims)
    reason = f"规则匹配：指标{metrics}，粒度{granularity}，范围{range_key}"
    if dims_filter:
        reason += f"，维度{list(dims_filter.keys())}"
    return IntentResult(
        metric_codes=metrics[:3],
        granularity=granularity,
        start=start,
        end=end,
        dims_filter=dims_filter,
        reason=reason,
        mode="rule",
        fallback=True,
    )


def _parse_llm_json(text: str) -> Optional[dict[str, Any]]:
    """从模型输出中提取 JSON（容忍代码块包裹 / 前后杂文本）。"""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _resolve_llm_range(raw_range: Any) -> tuple[Optional[datetime], Optional[datetime]]:
    """LLM 时间范围：支持相对词或 ISO 起止（含日期/时间）。"""
    if isinstance(raw_range, str):
        start, end = _range_start_end(raw_range.strip().lower())
        if start is not None:
            return start, end
        # 支持 "2026-10-01~2026-10-14" 形式
        parts = re.split(r"[~至到]", raw_range)
        if len(parts) == 2:
            try:
                return (
                    datetime.fromisoformat(parts[0].strip()),
                    datetime.fromisoformat(parts[1].strip()),
                )
            except ValueError:
                return None, None
        return None, None
    if isinstance(raw_range, dict):
        try:
            start = datetime.fromisoformat(str(raw_range.get("start", "")).replace("T", " ").strip() or "") if raw_range.get("start") else None
            end = datetime.fromisoformat(str(raw_range.get("end", "")).replace("T", " ").strip() or "") if raw_range.get("end") else None
            return start, end
        except ValueError:
            return None, None
    return None, None


def _llm_parse(
    db: Session,
    tenant_id: int,
    question: str,
    catalog: list[dict[str, Any]],
    baseline: IntentResult,
) -> Optional[IntentResult]:
    """模型路由解析：要求输出结构化 JSON，失败返回 None 交由规则兜底。"""
    catalog_view = [
        {"code": c.get("code"), "name": c.get("name"), "tags": c.get("tags") or [], "agg_func": c.get("agg_func")}
        for c in catalog[:80]
    ]
    payload = {
        "task": "从用户问数中抽取结构化意图，仅输出 JSON（不要输出任何其他文字）。",
        "question": question,
        "catalog": catalog_view,
        "schema": {
            "metric_codes": ["指标编码，从 catalog 中选 1-3 个，必须存在"],
            "granularity": "hour|day|week|month",
            "range": "today|yesterday|this_week|last_week|this_month|last_month|last_7d|last_30d|last_90d 或 {\"start\":\"YYYY-MM-DD\",\"end\":\"YYYY-MM-DD\"}",
            "dims_filter": {"维度编码": "值 或 __group__（按维度分组）"},
            "reason": "一句话解释",
        },
        "rule_baseline": {
            "metric_codes": baseline.metric_codes,
            "granularity": baseline.granularity,
            "range": "last_30d",
            "dims_filter": baseline.dims_filter,
        },
    }
    try:
        result = route_model(
            db,
            "semantic_intent",
            payload,
            tenant_id=tenant_id,
            temperature=0.1,
            max_tokens=800,
        )
    except (ModelRouterError, Exception):  # noqa: BLE001 模型链路不可用时走规则
        db.rollback()
        return None
    parsed = _parse_llm_json(result.text)
    if parsed is None:
        return None
    metrics = parsed.get("metric_codes") or []
    valid = [c for c in metrics if any(c == it.get("code") for it in catalog)][:3]
    if not valid:
        valid = baseline.metric_codes
    granularity = str(parsed.get("granularity") or "day").lower()
    if granularity not in ("hour", "day", "week", "month"):
        granularity = baseline.granularity
    start, end = _resolve_llm_range(parsed.get("range"))
    if start is None:
        start, end = baseline.start, baseline.end
    dims_filter = parsed.get("dims_filter") or {}
    if not isinstance(dims_filter, dict):
        dims_filter = baseline.dims_filter
    reason = str(parsed.get("reason") or result.text[:120])
    return IntentResult(
        metric_codes=valid,
        granularity=granularity,
        start=start,
        end=end,
        dims_filter=dims_filter,
        reason=reason,
        model=result.model,
        mode=result.mode,
        fallback=result.fallback or result.rule_fallback,
        raw=parsed,
    )


def extract_intent(
    db: Session,
    tenant_id: int,
    question: str,
    catalog: list[dict[str, Any]],
    dims: list[dict[str, Any]],
) -> IntentResult:
    """意图总入口：先规则保底，再尝试模型路由增强，最终必有可用结果。"""
    baseline = _rule_parse(question, catalog, dims)
    if not settings.SEMANTIC_ENABLED:
        return baseline
    try:
        enhanced = _llm_parse(db, tenant_id, question, catalog, baseline)
    except Exception:  # noqa: BLE001
        db.rollback()
        enhanced = None
    if enhanced is not None:
        return enhanced
    return baseline
