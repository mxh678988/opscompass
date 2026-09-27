"""P8 学习进化闭环服务：决策反馈回流 / 策略权重自调 / 经验案例库 / A-B 对照实验。

闭环链路：
1) 反馈回流：AI 洞察 -> 处置单 -> 执行结果落 oc_learn_feedback（采纳与否 + 实际效果）。
2) 权重自调：按 policy_code + action_type 聚合反馈，成功率驱动权重在 [floor, ceil] 内浮动。
3) 经验沉淀：高价值反馈一键转 oc_learn_case，供后续决策检索复用。
4) A/B 对照：同场景两套方案并行采样，按 lift 判定胜出方并回写结论。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.learning import LearnCase, LearnExperiment, LearnFeedback, LearnPolicyWeight

# 计入采纳的决策结果
_ADOPTED = ("adopted", "partial")
# 权重基准
_BASE_WEIGHT = 1.0


def _now() -> datetime:
    return datetime.now()


def _f(value: Any, default: float = 0.0) -> float:
    """Decimal / None -> float。"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _paginate(
    db: Session,
    model,
    conditions: list,
    page: int = 1,
    size: int = 20,
    order_by=None,
) -> tuple[int, list]:
    """通用分页查询，返回 (total, rows)。"""
    page = max(1, int(page or 1))
    size = min(200, max(1, int(size or 20)))
    total = db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    order = order_by if order_by is not None else model.id.desc()
    rows = (
        db.execute(
            select(model).where(*conditions).order_by(order).offset((page - 1) * size).limit(size)
        )
        .scalars()
        .all()
    )
    return int(total), list(rows)


# ============================================================ 反馈回流
def record_feedback(db: Session, tenant_id: int, payload: Any, operator: str = "") -> dict:
    """登记一条决策反馈；applied=True 时即时增量刷新该策略权重。"""
    row = LearnFeedback(
        tenant_id=tenant_id,
        insight_id=getattr(payload, "insight_id", None),
        action_item_id=getattr(payload, "action_item_id", None),
        policy_code=(getattr(payload, "policy_code", "") or "").strip(),
        action_type=(getattr(payload, "action_type", "") or "").strip(),
        data_level=getattr(payload, "data_level", "L1") or "L1",
        decision=getattr(payload, "decision", "adopted") or "adopted",
        outcome=getattr(payload, "outcome", "unknown") or "unknown",
        outcome_score=getattr(payload, "outcome_score", None),
        effect_note=getattr(payload, "effect_note", "") or "",
        remark=getattr(payload, "remark", "") or "",
        recorded_by=operator or "",
        applied=bool(getattr(payload, "applied", True)),
        applied_at=_now() if bool(getattr(payload, "applied", True)) else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if row.applied and row.policy_code:
        refresh_policy_weight(db, tenant_id, row.policy_code, row.action_type)
    return feedback_to_dict(row)

def feedback_to_dict(row: LearnFeedback) -> dict:
    """反馈序列化。"""
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "insight_id": row.insight_id,
        "action_item_id": row.action_item_id,
        "policy_code": row.policy_code,
        "action_type": row.action_type,
        "data_level": row.data_level,
        "decision": row.decision,
        "outcome": row.outcome,
        "outcome_score": _f(row.outcome_score, None) if row.outcome_score is not None else None,
        "effect_note": row.effect_note,
        "remark": row.remark,
        "recorded_by": row.recorded_by,
        "applied": bool(row.applied),
        "applied_at": row.applied_at.strftime("%Y-%m-%d %H:%M:%S") if row.applied_at else None,
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
        "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M:%S") if row.updated_at else None,
    }


def list_feedbacks(
    db: Session,
    tenant_id: int,
    keyword: Optional[str] = None,
    decision: Optional[str] = None,
    outcome: Optional[str] = None,
    policy_code: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    """反馈列表（按策略编码 / 采纳结果 / 效果过滤）。"""
    conds = [LearnFeedback.tenant_id == tenant_id]
    if policy_code:
        conds.append(LearnFeedback.policy_code == policy_code)
    if decision:
        conds.append(LearnFeedback.decision == decision)
    if outcome:
        conds.append(LearnFeedback.outcome == outcome)
    if keyword:
        like = f"%{keyword.strip()}%"
        conds.append(
            or_(
                LearnFeedback.policy_code.like(like),
                LearnFeedback.action_type.like(like),
                LearnFeedback.effect_note.like(like),
                LearnFeedback.remark.like(like),
            )
        )
    total, rows = _paginate(db, LearnFeedback, conds, page, size)
    return {"total": total, "page": page, "page_size": size, "items": [feedback_to_dict(r) for r in rows]}


def get_feedback(db: Session, tenant_id: int, fid: int) -> Optional[LearnFeedback]:
    return db.execute(
        select(LearnFeedback).where(LearnFeedback.tenant_id == tenant_id, LearnFeedback.id == fid)
    ).scalars().first()


def patch_feedback(db: Session, tenant_id: int, fid: int, payload: Any) -> dict:
    """补录实际效果；applied 打开时刷新对应策略权重。"""
    row = get_feedback(db, tenant_id, fid)
    if row is None:
        raise ValueError("反馈记录不存在")
    for field in ("decision", "outcome", "outcome_score", "effect_note", "remark", "applied"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(row, field, value)
    if row.applied and row.applied_at is None:
        row.applied_at = _now()
    db.commit()
    db.refresh(row)
    if row.applied and row.policy_code:
        refresh_policy_weight(db, tenant_id, row.policy_code, row.action_type)
    return feedback_to_dict(row)


# ============================================================ 策略权重自调
def weight_to_dict(row: LearnPolicyWeight) -> dict:
    return {
        "id": row.id,
        "policy_code": row.policy_code,
        "action_type": row.action_type,
        "policy_name": row.policy_name,
        "weight": round(_f(row.weight, _BASE_WEIGHT), 4),
        "base_weight": round(_f(row.base_weight, _BASE_WEIGHT), 4),
        "sample_count": row.sample_count,
        "adopt_count": row.adopt_count,
        "success_count": row.success_count,
        "success_rate": round(_f(row.success_rate), 4),
        "avg_score": round(_f(row.avg_score), 2),
        "last_adjusted_at": row.last_adjusted_at.strftime("%Y-%m-%d %H:%M:%S") if row.last_adjusted_at else None,
        "adjust_note": row.adjust_note,
        "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M:%S") if row.updated_at else None,
    }


def _aggregate(db: Session, tenant_id: int, policy_code: str, action_type: str) -> dict:
    """聚合某策略维度的反馈统计。"""
    conds = [
        LearnFeedback.tenant_id == tenant_id,
        LearnFeedback.policy_code == policy_code,
        LearnFeedback.applied.is_(True),
    ]
    if action_type:
        conds.append(LearnFeedback.action_type == action_type)
    row = db.execute(
        select(
            func.count(LearnFeedback.id),
            func.sum(case((LearnFeedback.decision.in_(_ADOPTED), 1), else_=0)),
            func.sum(case((LearnFeedback.outcome == "success", 1), else_=0)),
            func.avg(LearnFeedback.outcome_score),
        ).where(*conds)
    ).first()
    sample = int(row[0] or 0) if row else 0
    adopt = int(row[1] or 0) if row else 0
    success = int(row[2] or 0) if row else 0
    avg_score = _f(row[3], 0.0) if row else 0.0
    return {"sample_count": sample, "adopt_count": adopt, "success_count": success, "avg_score": avg_score}


def _calc_weight(stat: dict, min_samples: int, lr: float, floor: float, ceil: float) -> tuple[float, float, float]:
    """按成功率与采纳率计算目标权重，返回 (weight, success_rate, adopt_rate)。"""
    sample = stat["sample_count"]
    if sample <= 0:
        return _BASE_WEIGHT, 0.0, 0.0
    success_rate = stat["success_count"] / sample
    adopt_rate = stat["adopt_count"] / sample
    if sample < min_samples:
        return _BASE_WEIGHT, success_rate, adopt_rate
    score = 0.6 * success_rate + 0.4 * adopt_rate  # 0~1
    weight = _BASE_WEIGHT * (1 + lr * (score - 0.5))
    weight = max(floor, min(ceil, weight))
    return round(weight, 4), success_rate, adopt_rate


def refresh_policy_weight(db: Session, tenant_id: int, policy_code: str, action_type: str = "") -> dict:
    """增量刷新单个策略维度权重（反馈落库后自动调用）。"""
    return recompute_weights(
        db,
        tenant_id,
        policy_code=policy_code,
        action_type=action_type,
        min_samples=1,
        learning_rate=0.5,
        weight_floor=0.2,
        weight_ceil=3.0,
        remark="反馈回流自动刷新",
    )

def recompute_weights(
    db: Session,
    tenant_id: int,
    policy_code: Optional[str] = None,
    action_type: Optional[str] = None,
    min_samples: int = 5,
    learning_rate: float = 0.5,
    weight_floor: float = 0.2,
    weight_ceil: float = 3.0,
    remark: str = "",
) -> dict:
    """策略权重自调：按反馈聚合结果重算权重并落库。

    传 policy_code 时只重算该策略；不传则全量重算。样本不足 min_samples 的策略保持基准权重。
    """
    conds = [LearnFeedback.tenant_id == tenant_id, LearnFeedback.applied.is_(True)]
    if policy_code:
        conds.append(LearnFeedback.policy_code == policy_code)
    if action_type:
        conds.append(LearnFeedback.action_type == action_type)
    groups = db.execute(
        select(LearnFeedback.policy_code, LearnFeedback.action_type)
        .where(*conds)
        .group_by(LearnFeedback.policy_code, LearnFeedback.action_type)
    ).all()
    pairs = [(str(g[0] or ""), str(g[1] or "")) for g in groups if (g[0] or "")]
    if not pairs and policy_code:
        pairs = [(policy_code, action_type or "")]

    updated: list[dict] = []
    for code, atype in pairs:
        stat = _aggregate(db, tenant_id, code, atype)
        weight, success_rate, adopt_rate = _calc_weight(
            stat, min_samples, learning_rate, weight_floor, weight_ceil
        )
        row = db.execute(
            select(LearnPolicyWeight).where(
                LearnPolicyWeight.tenant_id == tenant_id,
                LearnPolicyWeight.policy_code == code,
                LearnPolicyWeight.action_type == atype,
            )
        ).scalars().first()
        if row is None:
            row = LearnPolicyWeight(
                tenant_id=tenant_id,
                policy_code=code,
                action_type=atype,
                policy_name=code,
                base_weight=_BASE_WEIGHT,
                weight=_BASE_WEIGHT,
            )
            db.add(row)
        row.weight = weight
        row.sample_count = stat["sample_count"]
        row.adopt_count = stat["adopt_count"]
        row.success_count = stat["success_count"]
        row.success_rate = round(success_rate, 4)
        row.avg_score = round(stat["avg_score"], 2)
        row.last_adjusted_at = _now()
        row.adjust_note = remark or (
            f"样本 {stat['sample_count']} / 成功率 {success_rate:.0%} / 采纳率 {adopt_rate:.0%}"
        )
        updated.append(row)
    db.commit()
    return {"updated": len(updated), "items": [weight_to_dict(r) for r in updated]}


def list_weights(
    db: Session,
    tenant_id: int,
    keyword: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    """策略权重列表（按权重倒序）。"""
    conds = [LearnPolicyWeight.tenant_id == tenant_id]
    if keyword:
        like = f"%{keyword.strip()}%"
        conds.append(
            or_(LearnPolicyWeight.policy_code.like(like), LearnPolicyWeight.policy_name.like(like))
        )
    total, rows = _paginate(db, LearnPolicyWeight, conds, page, size, order_by=LearnPolicyWeight.weight.desc())
    return {"total": total, "page": page, "page_size": size, "items": [weight_to_dict(r) for r in rows]}


def stats_overview(db: Session, tenant_id: int) -> dict:
    """学习进化总览：采纳率 / 成功率 / 权重 Top / 案例与实验计数。"""
    agg = db.execute(
        select(
            func.count(LearnFeedback.id),
            func.sum(case((LearnFeedback.decision.in_(_ADOPTED), 1), else_=0)),
            func.sum(case((LearnFeedback.outcome == "success", 1), else_=0)),
            func.avg(LearnFeedback.outcome_score),
        ).where(LearnFeedback.tenant_id == tenant_id)
    ).first()
    total = int(agg[0] or 0) if agg else 0
    adopt = int(agg[1] or 0) if agg else 0
    success = int(agg[2] or 0) if agg else 0
    avg_score = _f(agg[3], 0.0) if agg else 0.0

    weight_rows = db.execute(
        select(LearnPolicyWeight)
        .where(LearnPolicyWeight.tenant_id == tenant_id)
        .order_by(LearnPolicyWeight.weight.desc())
        .limit(5)
    ).scalars().all()
    case_total = db.scalar(
        select(func.count()).select_from(LearnCase).where(LearnCase.tenant_id == tenant_id)
    ) or 0
    case_verified = db.scalar(
        select(func.count())
        .select_from(LearnCase)
        .where(LearnCase.tenant_id == tenant_id, LearnCase.status == "verified")
    ) or 0
    exp_total = db.scalar(
        select(func.count()).select_from(LearnExperiment).where(LearnExperiment.tenant_id == tenant_id)
    ) or 0
    exp_running = db.scalar(
        select(func.count())
        .select_from(LearnExperiment)
        .where(LearnExperiment.tenant_id == tenant_id, LearnExperiment.status == "running")
    ) or 0
    return {
        "feedback_total": total,
        "adopt_count": adopt,
        "success_count": success,
        "adopt_rate": round(adopt / total, 4) if total else 0.0,
        "success_rate": round(success / total, 4) if total else 0.0,
        "avg_score": round(avg_score, 2),
        "top_weights": [weight_to_dict(r) for r in weight_rows],
        "weight_total": db.scalar(
            select(func.count()).select_from(LearnPolicyWeight).where(LearnPolicyWeight.tenant_id == tenant_id)
        ) or 0,
        "case_total": int(case_total),
        "case_verified": int(case_verified),
        "experiment_total": int(exp_total),
        "experiment_running": int(exp_running),
    }


# ============================================================ 经验案例库
def case_to_dict(row: LearnCase) -> dict:
    return {
        "id": row.id,
        "case_no": row.case_no,
        "title": row.title,
        "category": row.category,
        "tags": row.tags or [],
        "scenario": row.scenario,
        "action_taken": row.action_taken,
        "outcome": row.outcome,
        "outcome_score": _f(row.outcome_score, None) if row.outcome_score is not None else None,
        "lesson": row.lesson,
        "source_insight_id": row.source_insight_id,
        "source_feedback_id": row.source_feedback_id,
        "status": row.status,
        "hit_count": row.hit_count,
        "last_hit_at": row.last_hit_at.strftime("%Y-%m-%d %H:%M:%S") if row.last_hit_at else None,
        "created_by": row.created_by,
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
        "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M:%S") if row.updated_at else None,
    }


def _next_case_no(db: Session, tenant_id: int) -> str:
    prefix = "LC" + _now().strftime("%Y%m%d")
    count = db.scalar(
        select(func.count()).select_from(LearnCase).where(
            LearnCase.tenant_id == tenant_id, LearnCase.case_no.like(prefix + "%")
        )
    ) or 0
    return f"{prefix}{int(count) + 1:04d}"


def create_case(db: Session, tenant_id: int, payload: Any, operator: str = "") -> dict:
    """新建经验案例（自动生成案例编号）。"""
    row = LearnCase(
        tenant_id=tenant_id,
        case_no=_next_case_no(db, tenant_id),
        title=(getattr(payload, "title", "") or "").strip(),
        category=getattr(payload, "category", "") or "",
        tags=getattr(payload, "tags", None),
        scenario=getattr(payload, "scenario", "") or "",
        action_taken=getattr(payload, "action_taken", "") or "",
        outcome=getattr(payload, "outcome", "") or "",
        outcome_score=getattr(payload, "outcome_score", None),
        lesson=getattr(payload, "lesson", "") or "",
        source_insight_id=getattr(payload, "source_insight_id", None),
        source_feedback_id=getattr(payload, "source_feedback_id", None),
        status=getattr(payload, "status", "draft") or "draft",
        created_by=operator or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return case_to_dict(row)


def list_cases(
    db: Session,
    tenant_id: int,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    conds = [LearnCase.tenant_id == tenant_id]
    if category:
        conds.append(LearnCase.category == category)
    if status:
        conds.append(LearnCase.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        conds.append(
            or_(
                LearnCase.title.like(like),
                LearnCase.case_no.like(like),
                LearnCase.scenario.like(like),
                LearnCase.lesson.like(like),
            )
        )
    total, rows = _paginate(db, LearnCase, conds, page, size)
    return {"total": total, "page": page, "page_size": size, "items": [case_to_dict(r) for r in rows]}


def get_case(db: Session, tenant_id: int, cid: int) -> Optional[LearnCase]:
    return db.execute(
        select(LearnCase).where(LearnCase.tenant_id == tenant_id, LearnCase.id == cid)
    ).scalars().first()


def patch_case(db: Session, tenant_id: int, cid: int, payload: Any) -> dict:
    row = get_case(db, tenant_id, cid)
    if row is None:
        raise ValueError("案例不存在")
    for field in (
        "title",
        "category",
        "tags",
        "scenario",
        "action_taken",
        "outcome",
        "outcome_score",
        "lesson",
        "status",
    ):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return case_to_dict(row)

def case_from_feedback(db: Session, tenant_id: int, payload: Any, operator: str = "") -> dict:
    """把一条已回流的反馈一键沉淀为经验案例。"""
    fid = int(getattr(payload, "feedback_id"))
    fb = get_feedback(db, tenant_id, fid)
    if fb is None:
        raise ValueError("来源反馈不存在")
    title = (getattr(payload, "title", None) or "").strip() or (
        f"{fb.policy_code or '策略'} / {fb.action_type or '动作'} 决策回流"
    )
    category = (getattr(payload, "category", None) or fb.action_type or "general").strip()
    scenario = fb.effect_note or fb.remark or f"数据分级 {fb.data_level}，决策 {fb.decision}"
    outcome_text = {"success": "效果达标", "neutral": "效果持平", "fail": "效果不达预期"}.get(
        fb.outcome, "效果待评估"
    )
    row = LearnCase(
        tenant_id=tenant_id,
        case_no=_next_case_no(db, tenant_id),
        title=title[:255],
        category=category[:64],
        tags=[t for t in [fb.policy_code, fb.action_type] if t],
        scenario=scenario,
        action_taken=f"采纳程度：{fb.decision}",
        outcome=outcome_text,
        outcome_score=fb.outcome_score,
        lesson=getattr(payload, "lesson", "") or "",
        source_insight_id=fb.insight_id,
        source_feedback_id=fb.id,
        status=getattr(payload, "status", "draft") or "draft",
        created_by=operator or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return case_to_dict(row)


def hit_case(db: Session, tenant_id: int, cid: int) -> dict:
    """标记案例被命中引用（命中次数 +1）。"""
    row = get_case(db, tenant_id, cid)
    if row is None:
        raise ValueError("案例不存在")
    row.hit_count = int(row.hit_count or 0) + 1
    row.last_hit_at = _now()
    db.commit()
    db.refresh(row)
    return case_to_dict(row)


def archive_case(db: Session, tenant_id: int, cid: int) -> dict:
    """归档案例（软删除，保留可追溯）。"""
    row = get_case(db, tenant_id, cid)
    if row is None:
        raise ValueError("案例不存在")
    row.status = "archived"
    db.commit()
    db.refresh(row)
    return case_to_dict(row)


# ============================================================ A/B 对照实验
def experiment_to_dict(row: LearnExperiment) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "hypothesis": row.hypothesis,
        "metric_code": row.metric_code,
        "status": row.status,
        "variant_a": row.variant_a,
        "variant_b": row.variant_b,
        "sample_a": row.sample_a,
        "sample_b": row.sample_b,
        "result_a": round(_f(row.result_a), 4),
        "result_b": round(_f(row.result_b), 4),
        "lift": round(_f(row.lift), 4),
        "confidence": round(_f(row.confidence), 4),
        "winner": row.winner,
        "conclusion": row.conclusion,
        "started_at": row.started_at.strftime("%Y-%m-%d %H:%M:%S") if row.started_at else None,
        "finished_at": row.finished_at.strftime("%Y-%m-%d %H:%M:%S") if row.finished_at else None,
        "created_by": row.created_by,
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
    }


def _next_exp_code(db: Session, tenant_id: int) -> str:
    prefix = "EX" + _now().strftime("%Y%m%d")
    count = db.scalar(
        select(func.count()).select_from(LearnExperiment).where(
            LearnExperiment.tenant_id == tenant_id, LearnExperiment.code.like(prefix + "%")
        )
    ) or 0
    return f"{prefix}{int(count) + 1:03d}"


def create_experiment(db: Session, tenant_id: int, payload: Any, operator: str = "") -> dict:
    code = (getattr(payload, "code", None) or "").strip() or _next_exp_code(db, tenant_id)
    status = getattr(payload, "status", "draft") or "draft"
    row = LearnExperiment(
        tenant_id=tenant_id,
        code=code[:64],
        name=(getattr(payload, "name", "") or "").strip()[:255],
        hypothesis=getattr(payload, "hypothesis", "") or "",
        metric_code=getattr(payload, "metric_code", "") or "",
        status=status,
        variant_a=getattr(payload, "variant_a", "") or "",
        variant_b=getattr(payload, "variant_b", "") or "",
        started_at=_now() if status == "running" else None,
        created_by=operator or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return experiment_to_dict(row)


def list_experiments(
    db: Session,
    tenant_id: int,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    conds = [LearnExperiment.tenant_id == tenant_id]
    if status:
        conds.append(LearnExperiment.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        conds.append(or_(LearnExperiment.name.like(like), LearnExperiment.code.like(like)))
    total, rows = _paginate(db, LearnExperiment, conds, page, size)
    return {"total": total, "page": page, "page_size": size, "items": [experiment_to_dict(r) for r in rows]}


def get_experiment(db: Session, tenant_id: int, eid: int) -> Optional[LearnExperiment]:
    return db.execute(
        select(LearnExperiment).where(
            LearnExperiment.tenant_id == tenant_id, LearnExperiment.id == eid
        )
    ).scalars().first()

def patch_experiment(db: Session, tenant_id: int, eid: int, payload: Any) -> dict:
    row = get_experiment(db, tenant_id, eid)
    if row is None:
        raise ValueError("实验不存在")
    for field in ("name", "hypothesis", "metric_code", "variant_a", "variant_b", "status"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(row, field, value)
    if row.status == "running" and row.started_at is None:
        row.started_at = _now()
    db.commit()
    db.refresh(row)
    return experiment_to_dict(row)


def record_sample(db: Session, tenant_id: int, eid: int, payload: Any) -> dict:
    """登记一次对照样本：按方案累加计数并滚动更新均值。"""
    row = get_experiment(db, tenant_id, eid)
    if row is None:
        raise ValueError("实验不存在")
    variant = (getattr(payload, "variant", "") or "").strip().lower()
    if variant not in ("a", "b"):
        raise ValueError("样本归属方案必须为 a 或 b")
    value = float(getattr(payload, "result"))
    if variant == "a":
        n = int(row.sample_a or 0)
        row.result_a = round((_f(row.result_a) * n + value) / (n + 1), 4)
        row.sample_a = n + 1
    else:
        n = int(row.sample_b or 0)
        row.result_b = round((_f(row.result_b) * n + value) / (n + 1), 4)
        row.sample_b = n + 1
    if row.status == "draft":
        row.status = "running"
        row.started_at = row.started_at or _now()
    row.lift = _calc_lift(_f(row.result_a), _f(row.result_b))
    db.commit()
    db.refresh(row)
    return experiment_to_dict(row)


def _calc_lift(result_a: float, result_b: float) -> float:
    """相对提升率 (B - A) / |A|；A 为 0 时用绝对差值。"""
    if abs(result_a) > 1e-9:
        return round((result_b - result_a) / abs(result_a), 4)
    return round(result_b - result_a, 4)


def finish_experiment(db: Session, tenant_id: int, eid: int, payload: Any) -> dict:
    """结项：按 lift 与样本量自动判定胜出方案，也可显式指定 winner。"""
    row = get_experiment(db, tenant_id, eid)
    if row is None:
        raise ValueError("实验不存在")
    result_a, result_b = _f(row.result_a), _f(row.result_b)
    lift = _calc_lift(result_a, result_b)
    min_sample = min(int(row.sample_a or 0), int(row.sample_b or 0))
    enough = min_sample >= 5 and abs(lift) >= 0.02
    auto_winner = "none"
    if enough:
        auto_winner = "b" if lift > 0 else "a"
    winner = (getattr(payload, "winner", None) or "").strip().lower() or auto_winner
    if winner not in ("a", "b", "none"):
        raise ValueError("胜出方案必须为 a / b / none")
    confidence = round(min(1.0, min_sample / 30.0) * min(1.0, abs(lift) / 0.1), 4)
    row.lift = lift
    row.winner = winner
    row.confidence = confidence
    row.status = "finished"
    row.finished_at = _now()
    conclusion = getattr(payload, "conclusion", "") or ""
    if not conclusion:
        label = {"a": row.variant_a or "方案 A", "b": row.variant_b or "方案 B", "none": "无显著差异"}
        conclusion = f"{label.get(winner, winner)} 胜出；提升 {lift:.2%}，样本 {min_sample}，置信度 {confidence:.0%}"
    row.conclusion = conclusion
    db.commit()
    db.refresh(row)
    return experiment_to_dict(row)
