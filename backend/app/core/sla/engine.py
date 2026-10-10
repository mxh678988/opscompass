"""OS 内核 · 任务 SLA 引擎（M4）。

职责（对应设计文档 3.4 任务 SLA）：
- 创建/认领/暂停/恢复/完成/取消：事件驱动计时，暂停冻结；
- 节点：临期提醒（剩余 1/3 或 30 分钟取更晚）、最终提醒（默认剩余 5 分钟）、
  逾期、逾期升级（责任人 → 上级 → 值班长，逐级可配，缺位自动跳级）；
- 评估幂等：以 ``oc_core_sla_event`` 事件表去重，重复扫描不产生重复触发；
- 升级留痕：写 SLA 事件 + ``oc_audit_log`` 审计。

对外主入口：``create_sla``（业务方直调）、``scan_and_evaluate``（调度侧批量
评估，验收 A5：节点触发时间误差 ≤ 1 分钟由调用方按秒级扫描保证）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.sla.calendar import WorkingCalendar
from app.models.auth import AuditLog
from app.models.sla import CoreSla, CoreSlaEvent

# ---- 默认参数（可经 create_sla 逐项覆盖） ----
DEFAULT_REMIND_1_FRACTION = 1 / 3  # 临期提醒：剩余总时长 1/3
DEFAULT_REMIND_1_MINUTES = 30  # 临期提醒：或剩余 30 分钟（取更晚者）
DEFAULT_REMIND_2_MINUTES = 5  # 最终提醒：剩余 5 分钟
ESCALATE_STEP2_MINUTES = 30  # 升上级后 30 分钟仍未处理，升值班长

AUDIT_EVENT_TYPE = "sla_escalation"  # 审计事件类型

# 事件类型常量
EVT_CREATED = "created"
EVT_CLAIMED = "claimed"
EVT_PAUSED = "paused"
EVT_RESUMED = "resumed"
EVT_DUE_SOON = "due_soon"
EVT_DUE_FINAL = "due_final"
EVT_OVERDUE = "overdue"
EVT_ESCALATED = "escalated"
EVT_COMPLETED = "completed"
EVT_CANCELLED = "cancelled"

_EVALUATION_EVENTS = (EVT_DUE_SOON, EVT_DUE_FINAL, EVT_OVERDUE, EVT_ESCALATED)


class SlaError(Exception):
    """SLA 业务错误。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """把可能 naive 的时间统一视为 UTC 并返回 aware。

    SQLite 的 ``DateTime(timezone=True)`` 不保留 tzinfo，回读为 naive；
    与 ``_utcnow()``（aware）相减/比较前必须统一。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _add_event(
    db: Session,
    sla: CoreSla,
    event_type: str,
    payload: Optional[dict] = None,
    occurred_at: Optional[datetime] = None,
) -> CoreSlaEvent:
    evt = CoreSlaEvent(
        sla_id=sla.id,
        event_type=event_type,
        payload=payload or {},
        occurred_at=occurred_at or _utcnow(),
    )
    db.add(evt)
    return evt


def _add_audit(
    db: Session,
    sla: CoreSla,
    *,
    action: str,
    user_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            username=None,
            event_type=AUDIT_EVENT_TYPE,
            action=action,
            status="success",
            detail=detail or f"sla_id={sla.id} object={sla.object_type}:{sla.object_id}",
        )
    )


def _has_event(db: Session, sla_id: int, event_type: str) -> bool:
    stmt = (
        select(CoreSlaEvent.id)
        .where(
            CoreSlaEvent.sla_id == sla_id,
            CoreSlaEvent.event_type == event_type,
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def _get(db: Session, sla_id: int) -> CoreSla:
    sla = db.get(CoreSla, sla_id)
    if sla is None:
        raise SlaError(f"SLA 不存在: {sla_id}")
    return sla


# ---- 生命周期操作 ----


def create_sla(
    db: Session,
    *,
    object_type: str,
    object_id: str,
    title: str,
    deadline_at: Optional[datetime] = None,
    due_in_minutes: Optional[float] = None,
    assignee_id: Optional[int] = None,
    supervisor_id: Optional[int] = None,
    duty_officer_id: Optional[int] = None,
    remind_1_minutes: Optional[float] = None,
    remind_2_minutes: Optional[float] = None,
    created_by: Optional[int] = None,
    trace_id: Optional[str] = None,
    calendar: Optional[WorkingCalendar] = None,
) -> CoreSla:
    """创建带时限的任务并自动计算提醒节点。

    ``deadline_at`` 与 ``due_in_minutes`` 二选一；提供 ``calendar`` 时按
    工作时间段展开截止时间。
    """
    if not object_type or not object_id or not title:
        raise SlaError("object_type/object_id/title 均为必填")
    if (deadline_at is None) == (due_in_minutes is None):
        raise SlaError("deadline_at 与 due_in_minutes 必须二选一")

    now = _utcnow()
    if due_in_minutes is not None:
        if due_in_minutes <= 0:
            raise SlaError("due_in_minutes 必须为正数")
        if calendar is not None:
            deadline_at = calendar.add_working_minutes(now, due_in_minutes)
        else:
            deadline_at = now + timedelta(minutes=float(due_in_minutes))
    if deadline_at <= now:
        raise SlaError("deadline_at 必须晚于当前时间")

    # 临期提醒：剩余 1/3 或 30 分钟，取更晚的时间点
    total_minutes = max((deadline_at - now).total_seconds() / 60.0, 0.001)
    r1 = remind_1_minutes if remind_1_minutes is not None else max(
        total_minutes * DEFAULT_REMIND_1_FRACTION, DEFAULT_REMIND_1_MINUTES
    )
    r2 = remind_2_minutes if remind_2_minutes is not None else DEFAULT_REMIND_2_MINUTES

    sla = CoreSla(
        object_type=object_type,
        object_id=object_id,
        title=title,
        status="open",
        deadline_at=deadline_at,
        remind_1_at=deadline_at - timedelta(minutes=float(r1)),
        remind_2_at=deadline_at - timedelta(minutes=float(r2)),
        assignee_id=assignee_id,
        supervisor_id=supervisor_id,
        duty_officer_id=duty_officer_id,
        created_by=created_by,
        trace_id=trace_id,
        created_at=now,
        updated_at=now,
    )
    db.add(sla)
    db.flush()
    _add_event(db, sla, EVT_CREATED, {"title": title}, occurred_at=now)
    db.commit()
    db.refresh(sla)
    return sla


def claim_sla(
    db: Session, sla_id: int, user_id: Optional[int] = None
) -> CoreSla:
    """认领任务（记录认领时间与认领人，不重置截止）。"""
    sla = _get(db, sla_id)
    if sla.status not in ("open", "paused"):
        raise SlaError(f"状态 {sla.status} 不可认领")
    sla.claimed_at = _utcnow()
    sla.updated_at = _utcnow()
    _add_event(db, sla, EVT_CLAIMED, {"user_id": user_id})
    db.commit()
    db.refresh(sla)
    return sla


def pause_sla(db: Session, sla_id: int, reason: Optional[str] = None) -> CoreSla:
    """暂停计时：等待外部响应等场景，需记录原因。"""
    sla = _get(db, sla_id)
    if sla.status != "open":
        raise SlaError(f"状态 {sla.status} 不可暂停")
    sla.status = "paused"
    sla.paused_at = _utcnow()
    sla.pause_reason = reason
    sla.updated_at = _utcnow()
    _add_event(db, sla, EVT_PAUSED, {"reason": reason})
    db.commit()
    db.refresh(sla)
    return sla


def resume_sla(db: Session, sla_id: int) -> CoreSla:
    """恢复计时：把暂停时段累入 paused_seconds（冻结语义）。"""
    sla = _get(db, sla_id)
    if sla.status != "paused":
        raise SlaError(f"状态 {sla.status} 不可恢复")
    now = _utcnow()
    paused_at = _as_utc(sla.paused_at)
    if paused_at is not None:
        sla.paused_seconds = int(sla.paused_seconds or 0) + int(
            (now - paused_at).total_seconds()
        )
    sla.status = "open"
    sla.paused_at = None
    sla.updated_at = now
    _add_event(db, sla, EVT_RESUMED, {"paused_seconds": sla.paused_seconds})
    db.commit()
    db.refresh(sla)
    return sla


def complete_sla(
    db: Session,
    sla_id: int,
    user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> CoreSla:
    """完成任务：计入按期/逾期统计。"""
    sla = _get(db, sla_id)
    if sla.status in ("done", "cancelled"):
        raise SlaError(f"状态 {sla.status} 不可重复完成")
    sla.status = "done"
    sla.completed_at = _utcnow()
    sla.updated_at = sla.completed_at
    _add_event(db, sla, EVT_COMPLETED, {"user_id": user_id, "note": note})
    db.commit()
    db.refresh(sla)
    return sla


def cancel_sla(
    db: Session,
    sla_id: int,
    user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> CoreSla:
    """取消任务（保留留痕，不计入统计）。"""
    sla = _get(db, sla_id)
    if sla.status in ("done", "cancelled"):
        raise SlaError(f"状态 {sla.status} 不可重复取消")
    sla.status = "cancelled"
    sla.updated_at = _utcnow()
    _add_event(db, sla, EVT_CANCELLED, {"user_id": user_id, "reason": reason})
    db.commit()
    db.refresh(sla)
    return sla


def sla_events(db: Session, sla_id: int) -> list[CoreSlaEvent]:
    """按时间序返回 SLA 全部事件（审计/调试用）。"""
    stmt = (
        select(CoreSlaEvent)
        .where(CoreSlaEvent.sla_id == sla_id)
        .order_by(CoreSlaEvent.id)
    )
    return list(db.execute(stmt).scalars().all())


# ---- 节点评估 ----


def _next_escalation_target(sla: CoreSla, level: int) -> Optional[int]:
    """升级链取下一级非空对象；缺位自动跳级。"""
    if level == 0:
        if sla.supervisor_id is not None:
            return sla.supervisor_id
        return sla.duty_officer_id
    return sla.duty_officer_id


def evaluate_sla(db: Session, sla: CoreSla, now: Optional[datetime] = None) -> list[str]:
    """评估单个 SLA 当前应触发的节点（幂等：已触发节点不重复）。

    返回本次新触发的事件类型列表。仅 ``status=open`` 且存在截止时间的实例
    参与评估；暂停中不触发任何节点（计时冻结）。
    """
    now = _as_utc(now) if now is not None else _utcnow()
    if sla.status != "open" or sla.effective_deadline is None:
        return []

    triggered: list[str] = []
    effective = _as_utc(sla.effective_deadline)
    remind_1 = _as_utc(sla.remind_1_at)
    remind_2 = _as_utc(sla.remind_2_at)

    if now >= effective:
        # 逾期
        if not _has_event(db, sla.id, EVT_OVERDUE):
            sla.is_overdue = True
            sla.updated_at = now
            _add_event(db, sla, EVT_OVERDUE, {"effective_deadline": effective.isoformat()}, occurred_at=now)
            triggered.append(EVT_OVERDUE)

        # 逾期升级：责任人 → 上级 → 值班长
        if sla.escalate_level < 2:
            next_level = sla.escalate_level + 1
            target = _next_escalation_target(sla, sla.escalate_level)
            if target is not None:
                if sla.escalate_level == 1:
                    # 升第二级需等待设定延迟
                    step2_at = _as_utc(sla.escalated_at) + timedelta(minutes=ESCALATE_STEP2_MINUTES)
                    if now < step2_at:
                        return triggered
                sla.escalate_level = next_level
                sla.escalated_to = target
                sla.escalated_at = now
                sla.updated_at = now
                _add_event(
                    db,
                    sla,
                    EVT_ESCALATED,
                    {
                        "level": next_level,
                        "to_user_id": target,
                        "effective_deadline": effective.isoformat(),
                    },
                    occurred_at=now,
                )
                _add_audit(
                    db,
                    sla,
                    action=f"sla_escalate_level_{next_level}",
                    detail=f"sla_id={sla.id} to_user_id={target} level={next_level}",
                )
                triggered.append(EVT_ESCALATED)
        db.commit()
        return triggered

    if remind_2 is not None and now >= remind_2:
        if not _has_event(db, sla.id, EVT_DUE_FINAL):
            _add_event(db, sla, EVT_DUE_FINAL, {"effective_deadline": effective.isoformat()}, occurred_at=now)
            triggered.append(EVT_DUE_FINAL)
    elif remind_1 is not None and now >= remind_1:
        if not _has_event(db, sla.id, EVT_DUE_SOON):
            _add_event(db, sla, EVT_DUE_SOON, {"effective_deadline": effective.isoformat()}, occurred_at=now)
            triggered.append(EVT_DUE_SOON)

    if triggered:
        db.commit()
    return triggered


def scan_and_evaluate(
    db: Session,
    now: Optional[datetime] = None,
    limit: int = 200,
) -> dict[str, int]:
    """批量扫描 open 状态的 SLA 并评估节点，返回触发统计。

    供内核定时调度（后续 M5 工作流引擎或独立调度协程）按秒级周期调用，
    满足验收 A5（触发时间误差 ≤ 1 分钟）。
    """
    now = now or _utcnow()
    stmt = (
        select(CoreSla)
        .where(CoreSla.status == "open")
        .order_by(CoreSla.remind_1_at.asc().nulls_last(), CoreSla.id)
        .limit(limit)
    )
    counter: dict[str, int] = {}
    for sla in db.execute(stmt).scalars().all():
        for evt in evaluate_sla(db, sla, now=now):
            counter[evt] = counter.get(evt, 0) + 1
    return counter


# ---- 插件接入（SDK task 门面回调） ----


def create_for_plugin(
    db: Session,
    plugin_id: str,
    title: str,
    sla: Optional[dict] = None,
    **kwargs: Any,
) -> dict:
    """SDK ``task.create`` 的内核实现：为插件创建带 SLA 的待办。

    ``sla`` 传参为 ``{"due_in_minutes": 120}`` 或 ``{"deadline_at": ...}``
    等与 ``create_sla`` 兼容的键；不传表示创建无时限待办（仅留痕不评估）。
    返回给插件侧的可序列化字典。
    """
    opts = dict(sla or {})
    if not opts:
        obj = CoreSla(
            object_type=f"plugin:{plugin_id}",
            object_id=uuid.uuid4().hex,
            title=title,
            status="open",
            deadline_at=None,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(obj)
        db.flush()
        _add_event(db, obj, EVT_CREATED, {"title": title})
        db.commit()
        return {
            "sla_id": obj.id,
            "title": title,
            "status": obj.status,
            "deadline_at": None,
            "plugin_id": plugin_id,
        }

    opts.setdefault("object_type", f"plugin:{plugin_id}")
    opts.setdefault("object_id", uuid.uuid4().hex)
    opts.setdefault("title", title)
    row = create_sla(db, **opts)
    return {
        "sla_id": row.id,
        "title": row.title,
        "status": row.status,
        "deadline_at": row.deadline_at.isoformat() if row.deadline_at else None,
        "effective_deadline": (
            row.effective_deadline.isoformat() if row.effective_deadline else None
        ),
        "plugin_id": plugin_id,
    }
