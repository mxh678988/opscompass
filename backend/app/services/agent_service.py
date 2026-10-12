"""M12 智能体编排服务：分析 Agent 与执行 Agent 的双 Agent 闭环。

链路：create_run 创建运行（pending）-> analyze_run 执行分析产出洞察
（pending -> analyzing -> awaiting_approval）-> 人工确认闸门 patch_run
（approve 置 executing / reject 置 rejected，approval_required=False 自动跳过）
-> record_action 登记执行动作 -> complete_run 执行完成并回写事件总线
（标记 result_published / result_event_id）-> fail_run 失败兜底。

状态机：pending -> analyzing -> awaiting_approval -> executing -> done/failed，
awaiting_approval 可经 reject 进入 rejected；任何非终态可失败进入 failed。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.bus import bus
from app.models.agent import (
    AGENT_ACTION_TYPES,
    AGENT_RUN_STATUSES,
    AGENT_SCENARIOS,
    AgentAction,
    AgentInsight,
    AgentRun,
)
from app.schemas.agent import AgentActionIn, AgentRunIn, AgentRunPatch

# 运行状态机合法转移表
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"analyzing", "failed"},
    "analyzing": {"awaiting_approval", "failed"},
    "awaiting_approval": {"executing", "rejected", "failed"},
    "executing": {"done", "failed"},
    "done": set(),
    "rejected": set(),
    "failed": set(),
}
TERMINAL_STATUSES = ("done", "rejected", "failed")


class AgentServiceError(RuntimeError):
    """智能体编排服务业务异常（参数 / 状态非法）。"""


def _now() -> datetime:
    return datetime.now()


def _check_scenario(scenario: str) -> None:
    if scenario not in AGENT_SCENARIOS:
        raise AgentServiceError(
            f"不支持的场景模板: {scenario}（可选 {' / '.join(AGENT_SCENARIOS)}）"
        )


def _check_action_type(action_type: str) -> None:
    if action_type not in AGENT_ACTION_TYPES:
        raise AgentServiceError(
            f"不支持的执行动作类型: {action_type}（可选 {' / '.join(AGENT_ACTION_TYPES)}）"
        )


def _transition(run: AgentRun, to_status: str) -> None:
    """状态机流转校验并落地。"""
    if run.status not in VALID_TRANSITIONS:
        raise AgentServiceError(f"非法运行状态: {run.status}")
    if to_status not in VALID_TRANSITIONS[run.status]:
        raise AgentServiceError(
            f"非法状态转移: {run.status} -> {to_status}"
        )
    run.status = to_status


def _get_run(db: Session, tenant_id: int, run_id: int) -> AgentRun:
    """按租户隔离取运行，不存在抛 404 语义错误。"""
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.tenant_id == tenant_id,
        )
    )
    if run is None:
        raise AgentServiceError("运行不存在或不属于当前租户")
    return run


def create_run(
    db: Session,
    tenant_id: int,
    payload: AgentRunIn,
) -> dict[str, Any]:
    """创建一次智能体编排运行（pending，等待分析）。"""
    _check_scenario(payload.scenario)
    run = AgentRun(
        tenant_id=tenant_id,
        name=payload.name,
        scenario=payload.scenario,
        status="pending",
        datasource_bindings=payload.datasource_bindings,
        action_config=payload.action_config,
        approval_required=payload.approval_required,
        created_by=payload.created_by,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run_to_dict(run)


def analyze_run(
    db: Session,
    tenant_id: int,
    run_id: int,
    *,
    insights: Optional[list[dict[str, Any]]] = None,
    insight_agent: str = "insight-agent",
) -> dict[str, Any]:
    """执行分析并产出洞察：pending -> analyzing -> awaiting_approval。

    自动确认运行（approval_required=False）在产出洞察后直接进入 executing，
    跳过人工确认闸门。insights 为空时写入一条默认诊断摘要。
    """
    run = _get_run(db, tenant_id, run_id)
    _transition(run, "analyzing")
    db.flush()

    default_insights: list[dict[str, Any]] = [
        {
            "seq": 1,
            "title": f"{run.scenario} 场景诊断摘要",
            "detail": "分析 Agent 已完成数据绑定与诊断，建议结合执行动作落地。",
            "severity": "info",
            "suggestion": "请人工确认后由执行 Agent 落地动作。",
        }
    ]
    for i, item in enumerate(insights or default_insights, start=1):
        _check_action_type(item.get("suggested_action_type", "create_task"))
        db.add(
            AgentInsight(
                tenant_id=tenant_id,
                run_id=run.id,
                seq=i,
                title=item.get("title", f"洞察 #{i}"),
                detail=item.get("detail"),
                severity=item.get("severity", "info"),
                evidence=item.get("evidence"),
                suggestion=item.get("suggestion"),
                suggested_action_type=item.get("suggested_action_type", "create_task"),
                status="new",
            )
        )
    db.flush()

    if run.approval_required:
        _transition(run, "awaiting_approval")
    else:
        # 自动确认：先落闸门态再跳过，保证状态机转移链合法
        _transition(run, "awaiting_approval")
        _transition(run, "executing")
        run.approved_by = insight_agent
        run.approved_at = _now()
        run.approve_note = "自动确认（approval_required=False）"
    db.commit()
    db.refresh(run)
    return run_to_dict(run, db, with_children=True)


def patch_run(
    db: Session,
    tenant_id: int,
    run_id: int,
    payload: AgentRunPatch,
    operator: str = "system",
) -> dict[str, Any]:
    """人工确认闸门：approve（executing）或 reject（rejected）。

    仅 awaiting_approval 状态可操作；approve 需记录确认人与意见。
    """
    run = _get_run(db, tenant_id, run_id)
    if run.status != "awaiting_approval":
        raise AgentServiceError(
            f"当前状态 {run.status} 不可确认，需等待洞察产出（awaiting_approval）"
        )
    to_status = payload.status or "executing"
    if to_status not in ("executing", "rejected"):
        raise AgentServiceError(
            f"确认操作仅支持 executing（通过）或 rejected（驳回），收到: {to_status}"
        )
    _transition(run, to_status)
    if to_status == "executing":
        run.approved_by = payload.approved_by or operator
        run.approved_at = _now()
        if payload.approve_note is not None:
            run.approve_note = payload.approve_note
    else:
        run.approve_note = payload.approve_note or "人工驳回"
    db.commit()
    db.refresh(run)
    return run_to_dict(run, with_children=True)


def record_action(
    db: Session,
    tenant_id: int,
    run_id: int,
    payload: AgentActionIn,
    operator: str = "system",
) -> dict[str, Any]:
    """登记执行动作（Action Agent 落地入口）。

    仅 executing 状态可登记；动作直接置 executed 并回写事件总线。
    """
    run = _get_run(db, tenant_id, run_id)
    if run.status != "executing":
        raise AgentServiceError(
            f"当前状态 {run.status} 不可登记动作，需先通过人工确认闸门（executing）"
        )
    _check_action_type(payload.action_type)

    insight_id = payload.insight_id
    if insight_id is not None:
        insight = db.scalar(
            select(AgentInsight).where(
                AgentInsight.id == insight_id,
                AgentInsight.tenant_id == tenant_id,
                AgentInsight.run_id == run.id,
            )
        )
        if insight is None:
            raise AgentServiceError("来源洞察不存在或不属于当前运行")
        insight.status = "confirmed"

    event_name = "agent.action.executed"
    event_id = bus.publish(
        db,
        event_name,
        {
            "run_id": run.id,
            "run_name": run.name,
            "action_type": payload.action_type,
            "payload": payload.payload or {},
        },
        tenant_id=tenant_id,
        commit=False,
    )
    action = AgentAction(
        tenant_id=tenant_id,
        run_id=run.id,
        insight_id=insight_id,
        action_type=payload.action_type,
        payload=payload.payload,
        status="executed",
        executed_by=operator,
        executed_at=_now(),
        published=True,
        event_name=event_name,
        result={"event_id": event_id, "summary": "动作已登记并回写事件总线"},
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action_to_dict(action)


def complete_run(
    db: Session,
    tenant_id: int,
    run_id: int,
    *,
    result_summary: Optional[str] = None,
) -> dict[str, Any]:
    """完成运行：executing -> done，结果回写事件总线并标记 result_published。"""
    run = _get_run(db, tenant_id, run_id)
    _transition(run, "done")
    run.result_summary = result_summary
    run.finished_at = _now()
    if not run.result_published:
        event_name = "agent.run.completed"
        run.result_event_id = bus.publish(
            db,
            event_name,
            {
                "run_id": run.id,
                "run_name": run.name,
                "scenario": run.scenario,
                "result_summary": result_summary,
                "action_count": _action_count(db, tenant_id, run.id),
            },
            tenant_id=tenant_id,
            commit=False,
        )
        run.result_published = True
    db.commit()
    db.refresh(run)
    return run_to_dict(run, db, with_children=True)


def fail_run(
    db: Session,
    tenant_id: int,
    run_id: int,
    *,
    error: str = "执行失败",
) -> dict[str, Any]:
    """失败兜底：任意非终态 -> failed。"""
    run = _get_run(db, tenant_id, run_id)
    if run.status in TERMINAL_STATUSES:
        raise AgentServiceError(f"终态运行不可再失败: {run.status}")
    _transition(run, "failed")
    run.error = error
    run.finished_at = _now()
    db.commit()
    db.refresh(run)
    return run_to_dict(run, with_children=True)


def list_runs(
    db: Session,
    tenant_id: int,
    *,
    status: Optional[str] = None,
    scenario: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    """运行列表：分页 + status/scenario/keyword 过滤，租户隔离。"""
    if status is not None and status not in AGENT_RUN_STATUSES:
        raise AgentServiceError(
            f"不支持的运行状态: {status}（可选 {' / '.join(AGENT_RUN_STATUSES)}）"
        )
    if scenario is not None:
        _check_scenario(scenario)

    page = max(1, int(page or 1))
    size = min(200, max(1, int(size or 20)))
    conditions = [AgentRun.tenant_id == tenant_id]
    if status:
        conditions.append(AgentRun.status == status)
    if scenario:
        conditions.append(AgentRun.scenario == scenario)
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            or_(
                AgentRun.name.like(like),
                AgentRun.result_summary.like(like),
            )
        )

    total = (
        db.scalar(
            select(func.count()).select_from(AgentRun).where(*conditions)
        )
        or 0
    )
    rows = (
        db.execute(
            select(AgentRun)
            .where(*conditions)
            .order_by(AgentRun.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return {
        "total": int(total),
        "page": page,
        "page_size": size,
        "items": [run_to_dict(r) for r in rows],
    }


def get_run(
    db: Session,
    tenant_id: int,
    run_id: int,
    *,
    with_children: bool = True,
) -> Optional[dict[str, Any]]:
    """运行详情，含洞察与动作明细。"""
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.tenant_id == tenant_id,
        )
    )
    if run is None:
        return None
    return run_to_dict(run, db, with_children=with_children)


# ------------------------------------------------------------ 序列化与辅助


def _action_count(db: Session, tenant_id: int, run_id: int) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(AgentAction).where(
                AgentAction.tenant_id == tenant_id,
                AgentAction.run_id == run_id,
            )
        )
        or 0
    )


def _list_insights(db: Session, tenant_id: int, run_id: int) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(AgentInsight)
            .where(
                AgentInsight.tenant_id == tenant_id,
                AgentInsight.run_id == run_id,
            )
            .order_by(AgentInsight.seq.asc(), AgentInsight.id.asc())
        )
        .scalars()
        .all()
    )
    return [insight_to_dict(i) for i in rows]


def _list_actions(db: Session, tenant_id: int, run_id: int) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(AgentAction)
            .where(
                AgentAction.tenant_id == tenant_id,
                AgentAction.run_id == run_id,
            )
            .order_by(AgentAction.id.asc())
        )
        .scalars()
        .all()
    )
    return [action_to_dict(a) for a in rows]


def run_to_dict(
    run: AgentRun,
    db: Optional[Session] = None,
    *,
    with_children: bool = False,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": run.id,
        "tenant_id": run.tenant_id,
        "name": run.name,
        "scenario": run.scenario,
        "status": run.status,
        "datasource_bindings": run.datasource_bindings,
        "knowledge_refs": run.knowledge_refs,
        "action_config": run.action_config,
        "insight_agent": run.insight_agent,
        "action_agent": run.action_agent,
        "approval_required": bool(run.approval_required),
        "approved_by": run.approved_by,
        "approved_at": run.approved_at.isoformat() if run.approved_at else None,
        "approve_note": run.approve_note,
        "result_summary": run.result_summary,
        "result_published": bool(run.result_published),
        "result_event_id": run.result_event_id,
        "error": run.error,
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
    if with_children and db is not None:
        data["insights"] = _list_insights(db, run.tenant_id, run.id)
        data["actions"] = _list_actions(db, run.tenant_id, run.id)
    return data


def insight_to_dict(insight: AgentInsight) -> dict[str, Any]:
    return {
        "id": insight.id,
        "run_id": insight.run_id,
        "seq": insight.seq,
        "title": insight.title,
        "detail": insight.detail,
        "severity": insight.severity,
        "evidence": insight.evidence,
        "suggestion": insight.suggestion,
        "suggested_action_type": insight.suggested_action_type,
        "status": insight.status,
        "created_at": insight.created_at.isoformat() if insight.created_at else None,
    }


def action_to_dict(action: AgentAction) -> dict[str, Any]:
    return {
        "id": action.id,
        "run_id": action.run_id,
        "insight_id": action.insight_id,
        "action_type": action.action_type,
        "payload": action.payload,
        "status": action.status,
        "executed_by": action.executed_by,
        "executed_at": action.executed_at.isoformat() if action.executed_at else None,
        "result": action.result,
        "published": bool(action.published),
        "event_name": action.event_name,
        "error": action.error,
        "created_at": action.created_at.isoformat() if action.created_at else None,
    }
