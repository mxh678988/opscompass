"""权限处置引擎：按「数据级别 × 执行者 × 动作」决定 AI 自动处置还是转人工。

权限矩阵落在 oc_ai_action_policy（内置策略见 DEFAULT_POLICIES）：
- L1 公开：AI 可全自动处置（通知 / 排查 / 优化 / 记录）；
- L2 内部：AI 可自动通知与排查，优化、修正类动作需人工复核；
- L3 敏感：AI 只能生成待办，处置权归人工（人工审批后执行）；
- L4 机密：AI 完全禁止处置，一律人工审批，且必须留审计。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import (
    DATA_LEVEL_ORDER,
    SEVERITY_ORDER,
    AiActionItem,
    AiActionPolicy,
    AiAnalysis,
    AiAuditLog,
    AiInsight,
)

DEFAULT_POLICIES: list[dict[str, Any]] = [
    {
        "code": "POL-L1-AI-AUTO",
        "name": "L1 公开数据：AI 全自动处置",
        "data_level": "L1",
        "actor": "ai",
        "action_type": "*",
        "max_severity": "critical",
        "allow": True,
        "require_review": False,
        "require_approval": False,
        "priority": 200,
        "description": "公开级数据，AI 可在权限内直接处置并留痕。",
    },
    {
        "code": "POL-L2-AI-AUTO",
        "name": "L2 内部数据：AI 自动通知/排查/记录",
        "data_level": "L2",
        "actor": "ai",
        "action_type": "notify",
        "max_severity": "critical",
        "allow": True,
        "require_review": False,
        "require_approval": False,
        "priority": 180,
    },
    {
        "code": "POL-L2-AI-INSPECT",
        "name": "L2 内部数据：AI 自动排查",
        "data_level": "L2",
        "actor": "ai",
        "action_type": "inspect",
        "max_severity": "critical",
        "allow": True,
        "require_review": False,
        "require_approval": False,
        "priority": 180,
    },
    {
        "code": "POL-L2-AI-RECORD",
        "name": "L2 内部数据：AI 自动记录",
        "data_level": "L2",
        "actor": "ai",
        "action_type": "record",
        "max_severity": "critical",
        "allow": True,
        "require_review": False,
        "require_approval": False,
        "priority": 180,
    },
    {
        "code": "POL-L2-AI-OPTIMIZE",
        "name": "L2 内部数据：AI 优化需人工复核",
        "data_level": "L2",
        "actor": "ai",
        "action_type": "optimize",
        "max_severity": "warning",
        "allow": True,
        "require_review": True,
        "require_approval": False,
        "priority": 180,
    },
    {
        "code": "POL-L2-AI-REMEDIATE",
        "name": "L2 内部数据：AI 修正需人工审批",
        "data_level": "L2",
        "actor": "ai",
        "action_type": "remediate",
        "max_severity": "warning",
        "allow": True,
        "require_review": True,
        "require_approval": True,
        "priority": 190,
    },
    {
        "code": "POL-L3-AI-NOTIFY",
        "name": "L3 敏感数据：AI 仅可生成提醒待办",
        "data_level": "L3",
        "actor": "ai",
        "action_type": "notify",
        "max_severity": "info",
        "allow": True,
        "require_review": True,
        "require_approval": True,
        "priority": 170,
        "description": "敏感数据下 AI 不得直接处置，转人工待办。",
    },
    {
        "code": "POL-L3-AI-DENY",
        "name": "L3 敏感数据：AI 处置权受限",
        "data_level": "L3",
        "actor": "ai",
        "action_type": "*",
        "max_severity": "info",
        "allow": False,
        "require_review": True,
        "require_approval": True,
        "priority": 160,
    },
    {
        "code": "POL-L4-AI-DENY",
        "name": "L4 机密数据：AI 禁止处置",
        "data_level": "L4",
        "actor": "ai",
        "action_type": "*",
        "max_severity": "info",
        "allow": False,
        "require_review": True,
        "require_approval": True,
        "priority": 210,
        "description": "机密数据一律转人工，AI 只做分析与留痕。",
    },
    {
        "code": "POL-L1-HUMAN",
        "name": "L1 公开数据：人工可直接处置",
        "data_level": "L1",
        "actor": "human",
        "action_type": "*",
        "max_severity": "critical",
        "allow": True,
        "require_review": False,
        "require_approval": False,
        "priority": 120,
    },
    {
        "code": "POL-L2-HUMAN",
        "name": "L2 内部数据：人工可直接处置",
        "data_level": "L2",
        "actor": "human",
        "action_type": "*",
        "max_severity": "critical",
        "allow": True,
        "require_review": False,
        "require_approval": False,
        "priority": 120,
    },
    {
        "code": "POL-L3-HUMAN",
        "name": "L3 敏感数据：人工处置需审批",
        "data_level": "L3",
        "actor": "human",
        "action_type": "*",
        "max_severity": "critical",
        "allow": True,
        "require_review": True,
        "require_approval": True,
        "priority": 130,
    },
    {
        "code": "POL-L4-HUMAN",
        "name": "L4 机密数据：人工处置需审批并留痕",
        "data_level": "L4",
        "actor": "human",
        "action_type": "*",
        "max_severity": "critical",
        "allow": True,
        "require_review": True,
        "require_approval": True,
        "priority": 140,
    },
]


# ---------------------------------------------------------------- 审计
def audit(
    db: Session,
    tenant_id: int,
    *,
    actor_type: str,
    actor: str,
    action: str,
    object_type: str = "",
    object_id: Optional[int] = None,
    from_state: Optional[str] = None,
    to_state: Optional[str] = None,
    detail: str = "",
    commit: bool = True,
) -> AiAuditLog:
    """写入审计日志。"""
    log = AiAuditLog(
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        from_state=from_state,
        to_state=to_state,
        detail=detail[:4000] if detail else None,
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    return log


def list_audit(db: Session, tenant_id: int, limit: int = 100) -> list[AiAuditLog]:
    return list(
        db.execute(
            select(AiAuditLog)
            .where(AiAuditLog.tenant_id == tenant_id)
            .order_by(AiAuditLog.id.desc())
            .limit(limit)
        ).scalars().all()
    )


# ---------------------------------------------------------------- 策略
def ensure_default_policies(db: Session, tenant_id: int) -> int:
    """写入缺失的内置策略，返回新增条数。"""
    existing = set(
        db.execute(
            select(AiActionPolicy.code).where(AiActionPolicy.tenant_id == tenant_id)
        ).scalars().all()
    )
    added = 0
    for item in DEFAULT_POLICIES:
        if item["code"] in existing:
            continue
        db.add(AiActionPolicy(tenant_id=tenant_id, builtin=True, enabled=True, **item))
        added += 1
    if added:
        db.commit()
    return added


def list_policies(db: Session, tenant_id: int) -> list[AiActionPolicy]:
    return list(
        db.execute(
            select(AiActionPolicy)
            .where(AiActionPolicy.tenant_id == tenant_id)
            .order_by(AiActionPolicy.data_level.asc(), AiActionPolicy.actor.asc(), AiActionPolicy.priority.desc())
        ).scalars().all()
    )


def resolve_policy(
    db: Session, tenant_id: int, level: str, actor: str, action_type: str
) -> Optional[AiActionPolicy]:
    """匹配最具体的启用策略：动作精确匹配优先，其次优先级高者。"""
    policies = [
        p
        for p in list_policies(db, tenant_id)
        if p.enabled and p.data_level == level and p.actor == actor and p.action_type in (action_type, "*")
    ]
    if not policies:
        return None
    policies.sort(key=lambda p: (p.action_type != "*", p.priority), reverse=True)
    return policies[0]


def decide(
    db: Session, tenant_id: int, *, level: str, actor: str, action_type: str, severity: str = "info"
) -> dict[str, Any]:
    """权限判定：是否允许、是否需复核、是否需审批。"""
    if DATA_LEVEL_ORDER.get(level, 2) >= DATA_LEVEL_ORDER["L4"] and actor == "ai":
        return {
            "allow": False,
            "require_review": True,
            "require_approval": True,
            "policy": None,
            "reason": "L4 机密数据禁止 AI 处置，转人工审批",
            "auto": False,
        }

    policy = resolve_policy(db, tenant_id, level, actor, action_type)
    if policy is None:
        return {
            "allow": False,
            "require_review": True,
            "require_approval": True,
            "policy": None,
            "reason": f"无匹配策略（{level}/{actor}/{action_type}），默认转人工",
            "auto": False,
        }

    severity_over = SEVERITY_ORDER.get(severity, 1) > SEVERITY_ORDER.get(policy.max_severity, 2)
    require_approval = policy.require_approval or severity_over
    auto = policy.allow and not policy.require_review and not require_approval
    reason = (
        f"命中策略 {policy.code}「{policy.name}」"
        + ("；严重度超出策略上限，升级为人工审批" if severity_over else "")
    )
    return {
        "allow": policy.allow,
        "require_review": policy.require_review or severity_over,
        "require_approval": require_approval,
        "policy": policy,
        "reason": reason,
        "auto": auto,
    }


# ---------------------------------------------------------------- 处置单
def route_insight(db: Session, tenant_id: int, insight: AiInsight, commit: bool = True) -> AiActionItem:
    """把洞察路由为处置单：权限内 AI 自动执行，超权限转人工。"""
    decision = decide(
        db,
        tenant_id,
        level=insight.data_level,
        actor="ai",
        action_type=insight.action_type,
        severity=insight.severity,
    )
    policy: Optional[AiActionPolicy] = decision.get("policy")
    auto = bool(decision.get("auto"))
    now = datetime.now(timezone.utc)

    item = AiActionItem(
        tenant_id=tenant_id,
        insight_id=insight.id,
        analysis_id=insight.analysis_id,
        policy_id=policy.id if policy else None,
        title=insight.title,
        action_type=insight.action_type,
        data_level=insight.data_level,
        severity=insight.severity,
        handler="ai" if auto else "human",
        status="auto_executed" if auto else "pending",
        review_required=bool(decision.get("require_review")),
        executed_at=now if auto else None,
        execution_result=(
            f"AI 在权限内自动处置（{decision['reason']}）：{insight.suggestion or insight.title}"
            if auto
            else None
        ),
    )
    db.add(item)
    db.flush()

    insight.status = "routed"
    audit(
        db,
        tenant_id,
        actor_type="ai" if auto else "system",
        actor="ai-analyst" if auto else "policy-engine",
        action="auto_execute" if auto else "route_to_human",
        object_type="insight",
        object_id=insight.id,
        from_state="new",
        to_state="routed",
        detail=f"数据级别 {insight.data_level}；动作 {insight.action_type}；{decision['reason']}",
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(item)
    return item


def route_analysis(db: Session, tenant_id: int, analysis_id: int) -> dict[str, Any]:
    """把一次分析下的全部新洞察路由为处置单。"""
    insights = db.execute(
        select(AiInsight).where(
            AiInsight.tenant_id == tenant_id,
            AiInsight.analysis_id == analysis_id,
            AiInsight.status == "new",
        )
    ).scalars().all()
    auto, human = 0, 0
    for insight in insights:
        item = route_insight(db, tenant_id, insight, commit=False)
        if item.handler == "ai":
            auto += 1
        else:
            human += 1
    db.commit()
    return {"routed": len(insights), "auto_executed": auto, "to_human": human}


def route_pending(db: Session, tenant_id: int) -> dict[str, Any]:
    """扫描全部未路由洞察并生成处置单。"""
    insights = db.execute(
        select(AiInsight).where(AiInsight.tenant_id == tenant_id, AiInsight.status == "new")
    ).scalars().all()
    auto, human = 0, 0
    for insight in insights:
        item = route_insight(db, tenant_id, insight, commit=False)
        if item.handler == "ai":
            auto += 1
        else:
            human += 1
    db.commit()
    return {"routed": len(insights), "auto_executed": auto, "to_human": human}


def list_actions(
    db: Session,
    tenant_id: int,
    status: Optional[str] = None,
    handler: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 100,
) -> list[AiActionItem]:
    stmt = select(AiActionItem).where(AiActionItem.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(AiActionItem.status == status)
    if handler:
        stmt = stmt.where(AiActionItem.handler == handler)
    if level:
        stmt = stmt.where(AiActionItem.data_level == level)
    return list(db.execute(stmt.order_by(AiActionItem.id.desc()).limit(limit)).scalars().all())


def get_action(db: Session, tenant_id: int, action_id: int) -> Optional[AiActionItem]:
    return db.execute(
        select(AiActionItem).where(AiActionItem.tenant_id == tenant_id, AiActionItem.id == action_id)
    ).scalars().first()


def _set_decision(
    db: Session,
    tenant_id: int,
    item: AiActionItem,
    operator: str,
    note: str,
    status: str,
    action: str,
) -> AiActionItem:
    previous = item.status
    item.status = status
    item.decision_by = operator
    item.decision_at = datetime.now(timezone.utc)
    item.decision_note = note
    audit(
        db,
        tenant_id,
        actor_type="human",
        actor=operator,
        action=action,
        object_type="action_item",
        object_id=item.id,
        from_state=previous,
        to_state=status,
        detail=f"数据级别 {item.data_level}；意见：{note or '无'}",
        commit=False,
    )
    db.commit()
    db.refresh(item)
    return item


def approve_action(db: Session, tenant_id: int, item: AiActionItem, operator: str, note: str = "") -> AiActionItem:
    """人工审批通过（待办 → 已批准）。"""
    return _set_decision(db, tenant_id, item, operator, note, "approved", "approve")


def reject_action(db: Session, tenant_id: int, item: AiActionItem, operator: str, note: str = "") -> AiActionItem:
    """人工驳回（待办 → 已驳回）。"""
    return _set_decision(db, tenant_id, item, operator, note, "rejected", "reject")


def execute_action(
    db: Session,
    tenant_id: int,
    item: AiActionItem,
    operator: str,
    note: str = "",
    result: str = "",
) -> AiActionItem:
    """人工/授权执行处置：登记执行结果并留痕。

    当前版本的执行语义为「登记式执行」——记录处置结论与结果说明，
    供外部系统或后续自动化任务消费，不对生产数据做破坏性变更。
    """
    previous = item.status
    item.status = "executed"
    item.execution_result = (result or note or "已登记执行")[:4000]
    item.decision_by = item.decision_by or operator
    item.decision_at = item.decision_at or datetime.now(timezone.utc)
    item.executed_at = datetime.now(timezone.utc)
    if note:
        item.decision_note = note
    audit(
        db,
        tenant_id,
        actor_type="human",
        actor=operator,
        action="execute",
        object_type="action_item",
        object_id=item.id,
        from_state=previous,
        to_state="executed",
        detail=f"数据级别 {item.data_level}；动作 {item.action_type}；结果：{item.execution_result}",
        commit=False,
    )
    db.commit()
    db.refresh(item)
    return item


def statistics(db: Session, tenant_id: int) -> dict[str, Any]:
    """治理概览：洞察 / 处置单 / 策略命中统计。"""
    insights = db.execute(select(AiInsight).where(AiInsight.tenant_id == tenant_id)).scalars().all()
    actions = db.execute(select(AiActionItem).where(AiActionItem.tenant_id == tenant_id)).scalars().all()
    analyses = db.execute(select(AiAnalysis).where(AiAnalysis.tenant_id == tenant_id)).scalars().all()

    by_status: dict[str, int] = {}
    for item in actions:
        by_status[item.status] = by_status.get(item.status, 0) + 1
    by_level: dict[str, int] = {}
    for insight in insights:
        by_level[insight.data_level] = by_level.get(insight.data_level, 0) + 1

    return {
        "analysis_total": len(analyses),
        "analysis_failed": len([a for a in analyses if a.status == "failed"]),
        "insight_total": len(insights),
        "insight_pending": len([i for i in insights if i.status == "new"]),
        "action_total": len(actions),
        "action_by_status": by_status,
        "insight_by_level": by_level,
        "ai_auto_executed": len([a for a in actions if a.handler == "ai"]),
        "human_pending": len([a for a in actions if a.handler == "human" and a.status == "pending"]),
    }
