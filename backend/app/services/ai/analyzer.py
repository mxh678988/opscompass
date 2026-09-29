"""AI 分析器：采集运营数据快照 → 调用模型（api/local 双模式）→ 落洞察与建议。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import (
    INSIGHT_CATEGORIES,
    INSIGHT_SEVERITIES,
    ACTION_TYPES,
    AiAnalysis,
    AiInsight,
)
from app.models.import_task import ImportTask
from app.services import metric_service
from app.services.ai import grader
from app.services.ai.llm_client import LLMClient, LLMError, extract_json

MAX_SNAPSHOT_METRICS = 20
MAX_BREAKDOWN_ITEMS = 5
MAX_TREND_POINTS = 14

ANALYST_SYSTEM_PROMPT = (
    "你是一名资深全域运营数据分析师，服务于「运营智脑」系统（产品理念：让数据自动做出最优决策）。"
    "你的任务是基于给定的指标快照做全方位分析：识别异常波动、趋势变化、增长机会、经营风险与数据质量问题，并给出可执行的处置建议。\n"
    "要求：\n"
    "1. 结论必须基于给出的数据，禁止编造不存在的指标或数值；\n"
    "2. 每条洞察都要给出严重度（info/warning/critical）与建议动作类型"
    "（notify 通知 / inspect 排查 / optimize 优化 / remediate 修正 / escalate 上报 / record 仅记录）；\n"
    "3. 只输出 JSON，不要输出任何解释性文字，格式如下：\n"
    '{"summary": "总体结论（120字以内）", "insights": [{"title": "洞察标题", "detail": "具体分析", '
    '"category": "anomaly|trend|opportunity|risk|quality", "severity": "info|warning|critical", '
    '"metric_codes": ["gmv"], "evidence": {"指标编码": {"value": 0, "delta_ratio": 0}}, '
    '"suggestion": "建议动作", "action_type": "notify|inspect|optimize|remediate|escalate|record", '
    '"confidence": 0.0}]}'
)


# ---------------------------------------------------------------- 快照采集
def _compact_metric(item: dict[str, Any]) -> dict[str, Any]:
    """压缩单个指标信息，控制送模型的体积。"""
    trend = item.get("trend") or []
    points = [round(float(p.get("value") or 0), 4) for p in trend][-MAX_TREND_POINTS:]
    breakdown = []
    for row in (item.get("breakdown") or [])[:MAX_BREAKDOWN_ITEMS]:
        breakdown.append(
            {
                "dim_value": row.get("dim_value"),
                "value": round(float(row.get("value") or 0), 4),
                "delta_ratio": row.get("delta_ratio"),
                "share": row.get("share"),
            }
        )
    return {
        "code": item.get("code"),
        "name": item.get("name"),
        "unit": item.get("unit"),
        "has_data": item.get("has_data"),
        "value": round(float(item.get("value") or 0), 4),
        "prev_value": item.get("prev_value"),
        "delta_ratio": item.get("delta_ratio"),
        "stat_time": str(item.get("stat_time")) if item.get("stat_time") else None,
        "breakdown": breakdown,
        "trend_tail": points,
    }


def collect_snapshot(
    db: Session,
    tenant_id: int,
    scope: str = "overview",
    granularity: str = "day",
    dim_key: Optional[str] = None,
    codes: Optional[list[str]] = None,
) -> dict[str, Any]:
    """按范围采集数据快照。"""
    snapshot: dict[str, Any] = {
        "scope": scope,
        "granularity": granularity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": [],
        "quality": {},
    }

    if scope in ("overview", "compass", "metric", "mixed"):
        data = metric_service.compass(db, tenant_id, granularity=granularity, dim_key=dim_key, codes=codes)
        metrics = data.items[:MAX_SNAPSHOT_METRICS]
        snapshot["dim_key"] = data.dim_key
        snapshot["latest_stat"] = str(data.latest_stat) if data.latest_stat else None
        snapshot["metrics"] = [
            _compact_metric(item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item))
            for item in metrics
        ]
        snapshot["metric_total"] = len(data.items)

    if scope in ("quality", "ingest", "mixed"):
        total = db.execute(
            select(func.count()).select_from(ImportTask).where(ImportTask.tenant_id == tenant_id)
        ).scalar_one()
        rows = db.execute(
            select(ImportTask)
            .where(ImportTask.tenant_id == tenant_id)
            .order_by(ImportTask.id.desc())
            .limit(30)
        ).scalars().all()
        status_count: dict[str, int] = {}
        for task in rows:
            status = getattr(task, "status", "unknown")
            status_count[status] = status_count.get(status, 0) + 1
        snapshot["quality"] = {
            "import_total": int(total),
            "recent_status": status_count,
            "recent_tasks": [
                {
                    "file_name": getattr(task, "file_name", ""),
                    "status": getattr(task, "status", ""),
                    "success_rows": getattr(task, "success_rows", None),
                    "failed_rows": getattr(task, "failed_rows", None),
                }
                for task in rows[:10]
            ],
            "metrics_without_data": [
                item["code"] for item in snapshot["metrics"] if not item.get("has_data")
            ],
        }

    if scope == "datasource":
        from app.models.datasource import DataSource

        sources = db.execute(select(DataSource).where(DataSource.tenant_id == tenant_id)).scalars().all()
        snapshot["datasources"] = [
            {
                "name": src.name,
                "type": getattr(src, "ds_type", ""),
                "status": getattr(src, "status", ""),
            }
            for src in sources[:20]
        ]

    return snapshot


def build_messages(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    """构造送模型的消息。"""
    body = json.dumps(snapshot, ensure_ascii=False, default=str)
    if len(body) > 12000:
        body = body[:12000] + "...(已截断)"
    user_prompt = (
        f"分析范围：{snapshot.get('scope')}，统计粒度：{snapshot.get('granularity')}"
        f"{'，拆解维度：' + str(snapshot.get('dim_key')) if snapshot.get('dim_key') else ''}\n"
        f"数据快照如下：\n{body}\n"
        "请完成全方位分析，输出 JSON。\n"
        "硬性约束：指标涨跌必须严格依据快照中的 delta_ratio 正负号判断（>0 为上升/增长，<0 为下降/减少），"
        "禁止出现与数值方向矛盾的表述；detail 中引用的数值必须与快照一致。"
    )
    return [
        {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


# ---------------------------------------------------------------- 结果落库
_UP_WORDS = ("上升", "增长", "上涨", "提升", "回升", "抬高")
_DOWN_WORDS = ("下降", "减少", "下跌", "下滑", "回落", "降低")


def _fix_direction(detail: str, evidence: dict[str, Any]) -> str:
    """事实兜底：当文字描述与快照 delta_ratio 方向矛盾时，追加校正标注。"""
    if not detail or len(evidence) != 1:
        return detail
    ratios = [
        value.get("delta_ratio")
        for value in evidence.values()
        if isinstance(value, dict) and isinstance(value.get("delta_ratio"), (int, float))
    ]
    if len(ratios) != 1 or ratios[0] == 0:
        return detail
    actual_up = ratios[0] > 0
    has_up = any(word in detail for word in _UP_WORDS)
    has_down = any(word in detail for word in _DOWN_WORDS)
    conflict = (actual_up and has_down and not has_up) or (not actual_up and has_up and not has_down)
    if not conflict:
        return detail
    code = next(iter(evidence))
    direction = "上升" if actual_up else "下降"
    return f"{detail}（注：经快照校验，{code} 较上期实际{direction} {abs(ratios[0]) * 100:.2f}%，以数据为准）"


def _normalize_insights(parsed: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    raw_items = parsed.get("insights")
    if not isinstance(raw_items, list):
        raw_items = []
    insights: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_items[:limit], start=1):
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "anomaly").lower()
        if category not in INSIGHT_CATEGORIES:
            category = "anomaly"
        severity = str(item.get("severity") or "info").lower()
        if severity not in INSIGHT_SEVERITIES:
            severity = "info"
        action_type = str(item.get("action_type") or "record").lower()
        if action_type not in ACTION_TYPES:
            action_type = "record"
        metric_codes = item.get("metric_codes")
        if not isinstance(metric_codes, list):
            metric_codes = []
        confidence = item.get("confidence")
        try:
            confidence = max(0.0, min(1.0, float(confidence))) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
        insights.append(
            {
                "seq": idx,
                "title": str(item.get("title") or f"洞察 {idx}")[:200],
                "detail": _fix_direction(str(item.get("detail") or ""), evidence),
                "category": category,
                "severity": severity,
                "metric_codes": [str(code) for code in metric_codes],
                "evidence": evidence,
                "suggestion": str(item.get("suggestion") or ""),
                "action_type": action_type,
                "confidence": confidence,
            }
        )
    return insights


def run_analysis(
    db: Session,
    tenant_id: int,
    *,
    scope: str = "overview",
    granularity: str = "day",
    dim_key: Optional[str] = None,
    codes: Optional[list[str]] = None,
    title: str = "",
    mode: Optional[str] = None,
    model: Optional[str] = None,
    max_insights: int = 8,
    created_by: str = "api",
) -> AiAnalysis:
    """执行一次 AI 分析并落库（分析 + 洞察），失败也落库以便追溯。"""
    client = LLMClient(mode=mode, model=model)
    analysis = AiAnalysis(
        tenant_id=tenant_id,
        scope=scope,
        title=title or f"{scope} 分析 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        mode=client.mode,
        model=client.model,
        status="running",
        granularity=granularity,
        dim_key=dim_key,
        request_params={
            "scope": scope,
            "granularity": granularity,
            "dim_key": dim_key,
            "codes": codes,
            "max_insights": max_insights,
        },
        created_by=created_by,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    try:
        snapshot = collect_snapshot(db, tenant_id, scope=scope, granularity=granularity, dim_key=dim_key, codes=codes)
        analysis.input_snapshot = snapshot
        messages = build_messages(snapshot)
        analysis.prompt_digest = messages[-1]["content"][:2000]

        result = client.chat(messages)
        parsed = extract_json(result.text)
        if not parsed:
            raise LLMError("模型输出无法解析为 JSON 洞察结构")

        insights = _normalize_insights(parsed, max_insights)
        for item in insights:
            levels = [
                grader.level_of_metric_code(db, tenant_id, code) for code in item["metric_codes"]
            ]
            data_level = grader.max_level(levels) if levels else grader.DEFAULT_LEVEL
            db.add(
                AiInsight(
                    tenant_id=tenant_id,
                    analysis_id=analysis.id,
                    data_level=data_level,
                    **item,
                )
            )

        analysis.status = "success"
        analysis.result_summary = str(parsed.get("summary") or "")[:2000]
        analysis.insight_count = len(insights)
        analysis.duration_ms = result.duration_ms
        analysis.prompt_tokens = result.prompt_tokens
        analysis.completion_tokens = result.completion_tokens
        analysis.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(analysis)
        return analysis
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        analysis = db.get(AiAnalysis, analysis.id) or analysis
        analysis.status = "failed"
        analysis.error = str(exc)[:2000]
        analysis.finished_at = datetime.now(timezone.utc)
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis


# ---------------------------------------------------------------- 查询
def list_analyses(db: Session, tenant_id: int, limit: int = 20) -> list[AiAnalysis]:
    return list(
        db.execute(
            select(AiAnalysis)
            .where(AiAnalysis.tenant_id == tenant_id)
            .order_by(AiAnalysis.id.desc())
            .limit(limit)
        ).scalars().all()
    )


def get_analysis(db: Session, tenant_id: int, analysis_id: int) -> Optional[AiAnalysis]:
    return db.execute(
        select(AiAnalysis).where(AiAnalysis.tenant_id == tenant_id, AiAnalysis.id == analysis_id)
    ).scalars().first()


def analysis_insights(db: Session, tenant_id: int, analysis_id: int) -> list[AiInsight]:
    return list(
        db.execute(
            select(AiInsight)
            .where(AiInsight.tenant_id == tenant_id, AiInsight.analysis_id == analysis_id)
            .order_by(AiInsight.seq.asc())
        ).scalars().all()
    )


def list_insights(
    db: Session,
    tenant_id: int,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AiInsight]:
    stmt = select(AiInsight).where(AiInsight.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(AiInsight.status == status)
    if severity:
        stmt = stmt.where(AiInsight.severity == severity)
    return list(db.execute(stmt.order_by(AiInsight.id.desc()).offset(offset).limit(limit)).scalars().all())


def ai_mode_info() -> dict[str, Any]:
    """当前 AI 模式概览，供 /ai/config 展示。"""
    meta = settings.ai_mode_meta
    return {
        "enabled": settings.AI_ENABLED,
        "mode": settings.ai_mode,
        "model": settings.ai_model,
        "base_url": settings.ai_base_url,
        "ready": settings.ai_ready,
        "modes": meta,
        "timeout": settings.AI_TIMEOUT,
        "max_tokens": settings.AI_MAX_TOKENS,
        "temperature": settings.AI_TEMPERATURE,
    }
