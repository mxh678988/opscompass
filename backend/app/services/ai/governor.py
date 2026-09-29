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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai import (
    ACTION_STATUSES,
    DATA_LEVEL_ORDER,
    DECISION_LEVEL_META,
    DECISION_LEVEL_ORDER,
    DECISION_LEVELS,
    DECISION_SOURCES,
    SEVERITY_ORDER,
    AiActionItem,
    AiActionPolicy,
    AiAnalysis,
    AiAuditLog,
    AiInsight,
)

from app.storage.cache import cache_adapter

GOVERNANCE_CACHE_TTL = 20  # 秒：治理看板/概览短缓存，兼顾实时性与读压力

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


# ---------------------------------------------------------------- 决策分级授权
def list_decision_levels() -> list[dict[str, Any]]:
    """返回三级决策授权元数据（供前端展示与筛选）。"""
    items: list[dict[str, Any]] = []
    for code in DECISION_LEVELS:
        meta = DECISION_LEVEL_META.get(code, {})
        items.append(
            {
                "code": code,
                "name": meta.get("name", code),
                "desc": meta.get("desc", ""),
                "order": DECISION_LEVEL_ORDER.get(code, 0),
                "auto_execute": bool(meta.get("auto_execute", False)),
                "need_approval": code != "agent_autonomous",
            }
        )
    items.sort(key=lambda x: x["order"])
    return items


def validate_decision_level(level: str) -> str:
    """校验决策分级取值。"""
    value = (level or "").strip()
    if value not in DECISION_LEVELS:
        raise ValueError(f"非法决策分级：{level}，可选 {'/'.join(DECISION_LEVELS)}")
    return value


def resolve_decision_level(
    db: Session, tenant_id: int, *, level: str, action_type: str, severity: str = "info"
) -> dict[str, Any]:
    """按「数据级别 × 动作 × 严重度」推导 AI 决策分级。

    边界（与国家层面「智能体决策权限边界」要求一致）：
    - L3 敏感 / L4 机密：一律「仅用户本人决策」，AI 只给建议，不产生任何自动执行；
    - L1 公开 / L2 内部：命中策略且允许自动执行 → 「智能体自主决策」；
      否则 → 「需用户授权决策」，执行前必须由用户授权；
    - 无论哪一级，用户始终保留知情权与一键叫停权。
    """
    decision = decide(db, tenant_id, level=level, actor="ai", action_type=action_type, severity=severity)
    policy: Optional[AiActionPolicy] = decision.get("policy")
    if level in ("L3", "L4"):
        decision_level = "user_only"
    elif decision.get("auto"):
        decision_level = "agent_autonomous"
    else:
        decision_level = "user_authorized"
    return {
        "decision_level": decision_level,
        "decision_source": "policy",
        "policy_id": policy.id if policy else None,
        "reason": decision.get("reason", ""),
        "allow": bool(decision.get("allow")),
        "auto": decision_level == "agent_autonomous",
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
    grade = resolve_decision_level(
        db,
        tenant_id,
        level=insight.data_level,
        action_type=insight.action_type,
        severity=insight.severity,
    )
    now = datetime.now(timezone.utc)
    sim_mode = bool(getattr(insight, "sim_mode", False))

    item = AiActionItem(
        tenant_id=tenant_id,
        insight_id=insight.id,
        analysis_id=insight.analysis_id,
        policy_id=policy.id if policy else None,
        title=insight.title,
        action_type=insight.action_type,
        data_level=insight.data_level,
        severity=insight.severity,
        decision_level=grade["decision_level"],
        decision_source=grade["decision_source"],
        sim_mode=sim_mode,
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
    insight.decision_level = grade["decision_level"]
    level_name = DECISION_LEVEL_META.get(grade["decision_level"], {}).get("name", grade["decision_level"])
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
        detail=(
            f"数据级别 {insight.data_level}；动作 {insight.action_type}；"
            f"决策分级 {level_name}（{grade['decision_level']}）；{decision['reason']}"
            + ("；【演练/模拟模式】结论不得作为真实决策依据" if sim_mode else "")
        ),
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(item)
    invalidate_governance_cache(tenant_id)
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
    decision_level: Optional[str] = None,
    revoked: Optional[bool] = None,
    analysis_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AiActionItem]:
    stmt = select(AiActionItem).where(AiActionItem.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(AiActionItem.status == status)
    if handler:
        stmt = stmt.where(AiActionItem.handler == handler)
    if level:
        stmt = stmt.where(AiActionItem.data_level == level)
    if decision_level:
        stmt = stmt.where(AiActionItem.decision_level == decision_level)
    if revoked is not None:
        stmt = stmt.where(AiActionItem.revoked == revoked)
    if analysis_id is not None:
        stmt = stmt.where(AiActionItem.analysis_id == analysis_id)
    return list(db.execute(stmt.order_by(AiActionItem.id.desc()).offset(offset).limit(limit)).scalars().all())


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
    if item.revoked:
        raise ValueError("该决策已被撤销/叫停，不可再处置；如需继续请先还原")
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
    invalidate_governance_cache(tenant_id)
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
    if item.revoked:
        raise ValueError("该决策已被撤销/叫停，不可执行；如需继续请先还原")
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
    invalidate_governance_cache(tenant_id)
    return item


def _get_insight(db: Session, tenant_id: int, insight_id: Optional[int]) -> Optional[AiInsight]:
    if not insight_id:
        return None
    return db.execute(
        select(AiInsight).where(AiInsight.tenant_id == tenant_id, AiInsight.id == insight_id)
    ).scalars().first()


def update_decision_level(
    db: Session,
    tenant_id: int,
    item: AiActionItem,
    decision_level: str,
    operator: str,
    note: str = "",
) -> AiActionItem:
    """人工调整处置单的决策分级，分级来源记为 manual 并留痕。"""
    target = validate_decision_level(decision_level)
    if item.revoked:
        raise ValueError("该决策已被撤销/叫停，不可再调整分级")
    previous = item.decision_level
    if previous == target:
        return item

    item.decision_level = target
    item.decision_source = "manual"
    level_name = DECISION_LEVEL_META.get(target, {}).get("name", target)
    if target == "user_only":
        # 仅用户本人决策：撤回 AI 自动执行权，回到待办由用户本人处置
        item.review_required = True
        if item.handler == "ai":
            item.handler = "human"
            item.status = "pending"
            item.executed_at = None
            item.execution_result = None
    elif target == "agent_autonomous":
        item.review_required = False

    audit(
        db,
        tenant_id,
        actor_type="human",
        actor=operator,
        action="set_decision_level",
        object_type="action_item",
        object_id=item.id,
        from_state=previous,
        to_state=target,
        detail=f"决策分级调整为 {level_name}（{target}）；说明：{note or '无'}",
        commit=False,
    )
    db.commit()
    db.refresh(item)
    invalidate_governance_cache(tenant_id)
    return item


def revoke_action(
    db: Session, tenant_id: int, item: AiActionItem, operator: str, reason: str = ""
) -> AiActionItem:
    """用户一键撤销 / 叫停 AI 决策：立即失效、关联结论停止引用、全过程留痕。"""
    if item.revoked:
        raise ValueError("该决策已处于撤销/叫停状态")
    if item.status == "rejected":
        raise ValueError("已驳回的处置单无需撤销")

    previous = item.status
    now = datetime.now(timezone.utc)
    text = (reason or "用户一键叫停 AI 决策")[:2000]
    invalidated = previous in ("auto_executed", "executed", "approved")

    item.prev_status = previous
    item.status = "revoked"
    item.revoked = True
    item.revoked_at = now
    item.revoked_by = operator
    item.revoke_reason = text
    item.review_required = True
    if invalidated:
        stamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        item.execution_result = (
            (item.execution_result or "") + f"\n[已叫停 {stamp}] {text}"
        )[:4000]

    # 关联洞察同步失效，避免被叫停的结论继续作为决策依据
    insight = _get_insight(db, tenant_id, item.insight_id)
    insight_state: Optional[str] = None
    if insight is not None:
        insight_state = insight.status
        if invalidated and insight.status != "dismissed":
            insight.status = "dismissed"

    audit(
        db,
        tenant_id,
        actor_type="human",
        actor=operator,
        action="revoke",
        object_type="action_item",
        object_id=item.id,
        from_state=previous,
        to_state="revoked",
        detail=(
            f"用户行使叫停权；决策分级 {item.decision_level}；原因：{text}"
            + (f"；关联洞察状态 {insight_state} → dismissed" if invalidated and insight_state else "")
        ),
        commit=False,
    )
    db.commit()
    db.refresh(item)
    invalidate_governance_cache(tenant_id)
    return item


def restore_action(
    db: Session, tenant_id: int, item: AiActionItem, operator: str, note: str = ""
) -> AiActionItem:
    """还原被撤销/叫停的决策（回到撤销前状态），用于误叫停场景。"""
    if not item.revoked:
        raise ValueError("该决策未处于撤销/叫停状态")
    target = item.prev_status or "pending"
    if target not in ACTION_STATUSES or target == "revoked":
        target = "pending"

    item.status = target
    item.revoked = False
    item.revoked_at = None
    if note:
        item.decision_note = note

    insight = _get_insight(db, tenant_id, item.insight_id)
    restored_insight = False
    if insight is not None and insight.status == "dismissed" and target != "pending":
        insight.status = "routed"
        restored_insight = True

    audit(
        db,
        tenant_id,
        actor_type="human",
        actor=operator,
        action="restore",
        object_type="action_item",
        object_id=item.id,
        from_state="revoked",
        to_state=target,
        detail=(
            f"还原被叫停的决策；原因：{item.revoke_reason or '无'}"
            + ("；关联洞察恢复为 routed" if restored_insight else "")
            + f"；说明：{note or '无'}"
        ),
        commit=False,
    )
    db.commit()
    db.refresh(item)
    invalidate_governance_cache(tenant_id)
    return item


def decision_trace(db: Session, tenant_id: int, item: AiActionItem) -> list[dict[str, Any]]:
    """决策全过程留痕：洞察生成 → 分级路由 → 人工审批/执行 → 撤销/还原。"""
    entries: list[dict[str, Any]] = []
    insight = _get_insight(db, tenant_id, item.insight_id)

    if insight is not None:
        entries.append(
            {
                "at": insight.created_at,
                "actor_type": "ai",
                "actor": "ai-analyst",
                "action": "insight_created",
                "from_state": None,
                "to_state": insight.status,
                "detail": f"洞察《{insight.title}》生成；数据级别 {insight.data_level}；置信度 {insight.confidence}",
            }
        )
        logs = db.execute(
            select(AiAuditLog)
            .where(
                AiAuditLog.tenant_id == tenant_id,
                AiAuditLog.object_type == "insight",
                AiAuditLog.object_id == insight.id,
            )
            .order_by(AiAuditLog.id.asc())
        ).scalars().all()
        for log in logs:
            entries.append(
                {
                    "at": log.created_at,
                    "actor_type": log.actor_type,
                    "actor": log.actor,
                    "action": log.action,
                    "from_state": log.from_state,
                    "to_state": log.to_state,
                    "detail": log.detail,
                }
            )

    entries.append(
        {
            "at": item.created_at,
            "actor_type": "system",
            "actor": "policy-engine",
            "action": "action_created",
            "from_state": None,
            "to_state": item.status,
            "detail": (
                f"生成处置单并完成决策分级：{item.decision_level}（来源 {item.decision_source}）；"
                f"数据级别 {item.data_level}；处置方 {item.handler}"
                + ("；【演练/模拟模式】" if item.sim_mode else "")
            ),
        }
    )

    action_logs = db.execute(
        select(AiAuditLog)
        .where(
            AiAuditLog.tenant_id == tenant_id,
            AiAuditLog.object_type == "action_item",
            AiAuditLog.object_id == item.id,
        )
        .order_by(AiAuditLog.id.asc())
    ).scalars().all()
    for log in action_logs:
        entries.append(
            {
                "at": log.created_at,
                "actor_type": log.actor_type,
                "actor": log.actor,
                "action": log.action,
                "from_state": log.from_state,
                "to_state": log.to_state,
                "detail": log.detail,
            }
        )

    entries.sort(key=lambda e: (e["at"] is None, e["at"] or datetime.min.replace(tzinfo=timezone.utc)))
    for idx, entry in enumerate(entries, start=1):
        entry["seq"] = idx
    return entries


def _gov_cache_key(namespace: str, tenant_id: int) -> str:
    return cache_adapter.build_key("ai_gov", namespace, tenant_id)


def invalidate_governance_cache(tenant_id: int) -> None:
    """治理数据写变更后失效看板与概览缓存（缓存不可用时静默跳过）。"""
    cache_adapter.delete(
        _gov_cache_key("board", tenant_id),
        _gov_cache_key("stats", tenant_id),
    )


def _count_rows(db: Session, model, tenant_id: int, *conditions) -> int:
    """按条件在数据库端聚合计数，避免把整表载入内存。"""
    stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    for cond in conditions:
        stmt = stmt.where(cond)
    return int(db.execute(stmt).scalar() or 0)


def decision_board(db: Session, tenant_id: int) -> dict[str, Any]:
    """决策分级授权看板：三级元数据 + 各级数量 + 叫停/待办/自主执行/模拟模式概览。"""
    cache_key = _gov_cache_key("board", tenant_id)
    cached = cache_adapter.get_json(cache_key)
    if cached is not None:
        return cached
    level_rows = db.execute(
        select(AiActionItem.decision_level, func.count())
        .where(AiActionItem.tenant_id == tenant_id)
        .group_by(AiActionItem.decision_level)
    ).all()
    counts: dict[str, int] = {code: 0 for code in DECISION_LEVELS}
    for code, cnt in level_rows:
        key = code if code in counts else "user_authorized"
        counts[key] = counts.get(key, 0) + int(cnt or 0)
    payload = {
        "levels": list_decision_levels(),
        "counts": counts,
        "revoked_total": _count_rows(db, AiActionItem, tenant_id, AiActionItem.revoked.is_(True)),
        "pending_total": _count_rows(db, AiActionItem, tenant_id, AiActionItem.status == "pending"),
        "auto_executed_total": _count_rows(
            db, AiActionItem, tenant_id, AiActionItem.status == "auto_executed"
        ),
        "sim_mode_total": _count_rows(db, AiActionItem, tenant_id, AiActionItem.sim_mode.is_(True)),
    }
    cache_adapter.set_json(cache_key, payload, GOVERNANCE_CACHE_TTL)
    return payload


def statistics(db: Session, tenant_id: int) -> dict[str, Any]:
    """治理概览：洞察 / 处置单 / 策略命中统计（数据库端聚合，避免全表载入）。"""
    cache_key = _gov_cache_key("stats", tenant_id)
    cached = cache_adapter.get_json(cache_key)
    if cached is not None:
        return cached
    action_by_status: dict[str, int] = {
        str(code): int(cnt or 0)
        for code, cnt in db.execute(
            select(AiActionItem.status, func.count())
            .where(AiActionItem.tenant_id == tenant_id)
            .group_by(AiActionItem.status)
        ).all()
    }
    insight_by_level: dict[str, int] = {
        str(code): int(cnt or 0)
        for code, cnt in db.execute(
            select(AiInsight.data_level, func.count())
            .where(AiInsight.tenant_id == tenant_id)
            .group_by(AiInsight.data_level)
        ).all()
    }
    by_decision: dict[str, int] = {code: 0 for code in DECISION_LEVELS}
    for code, cnt in db.execute(
        select(AiActionItem.decision_level, func.count())
        .where(AiActionItem.tenant_id == tenant_id)
        .group_by(AiActionItem.decision_level)
    ).all():
        key = code if code in by_decision else "user_authorized"
        by_decision[key] = by_decision.get(key, 0) + int(cnt or 0)

    payload = {
        "analysis_total": _count_rows(db, AiAnalysis, tenant_id),
        "analysis_failed": _count_rows(db, AiAnalysis, tenant_id, AiAnalysis.status == "failed"),
        "insight_total": _count_rows(db, AiInsight, tenant_id),
        "insight_pending": _count_rows(db, AiInsight, tenant_id, AiInsight.status == "new"),
        "action_total": _count_rows(db, AiActionItem, tenant_id),
        "action_by_status": action_by_status,
        "insight_by_level": insight_by_level,
        "ai_auto_executed": _count_rows(db, AiActionItem, tenant_id, AiActionItem.handler == "ai"),
        "human_pending": _count_rows(
            db, AiActionItem, tenant_id, AiActionItem.handler == "human", AiActionItem.status == "pending"
        ),
        "action_by_decision_level": by_decision,
        "revoked_total": _count_rows(db, AiActionItem, tenant_id, AiActionItem.revoked.is_(True)),
        "sim_mode_total": _count_rows(db, AiActionItem, tenant_id, AiActionItem.sim_mode.is_(True)),
    }
    cache_adapter.set_json(cache_key, payload, GOVERNANCE_CACHE_TTL)
    return payload
