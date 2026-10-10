"""OS 内核模型：任务 SLA（M4）。

设计要点（对应 docs/os-kernel-design.md 3.4）：
- 适用范围：待办、工单、工作流步骤、预警认领等任意「有时限的对象」；
- 计时模型：以绝对截止时间 ``deadline_at`` 为基准，暂停/恢复通过累计
  ``paused_seconds`` 冻结计时，``effective_deadline = deadline_at + paused_seconds``；
- 节点：临期提醒（剩余 1/3 或 30 分钟取更晚）、最终提醒（默认剩余 5 分钟）、
  逾期、逾期升级（责任人 → 上级 → 值班长，逐级可配）；
- 事件表承担审计留痕：创建/认领/暂停/恢复/临期/逾期/升级/完成/取消均落
  ``oc_core_sla_event``，评估幂等靠事件去重，统计直接聚合事件表。

所有表统一 ``oc_core_`` 前缀，与既有 ``oc_`` 业务表隔离，升级/回退互不影响。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.kernel import ID_TYPE

# SLA 状态：open 计时中 / paused 暂停计时 / done 已完成 / cancelled 已取消
SLA_STATUSES = ("open", "paused", "done", "cancelled")

# SLA 事件类型（审计留痕 + 评估幂等键）
SLA_EVENT_TYPES = (
    "created",
    "claimed",
    "paused",
    "resumed",
    "due_soon",
    "due_final",
    "overdue",
    "escalated",
    "completed",
    "cancelled",
)


class CoreSla(Base):
    """任务 SLA 实例：任何有时限对象的计时、节点与升级状态。"""

    __tablename__ = "oc_core_sla"
    __table_args__ = (
        # 评估扫描主索引：按状态 + 提醒时间
        Index("ix_core_sla_eval", "status", "remind_1_at", "id"),
        # 按对象回溯
        Index("ix_core_sla_object", "object_type", "object_id"),
        # 按责任人看板
        Index("ix_core_sla_assignee", "assignee_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(
        String(64), comment="对象类型：task/ticket/workflow_step/plugin:<id> 等"
    )
    object_id: Mapped[str] = mapped_column(String(64), comment="对象 ID")
    title: Mapped[str] = mapped_column(String(200), comment="任务标题")
    status: Mapped[str] = mapped_column(
        String(16),
        default="open",
        server_default="open",
        comment="状态：open/paused/done/cancelled",
    )

    # 升级链：责任人 → 上级 → 值班长（逐级可配，缺位自动跳级）
    assignee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="责任人 ID"
    )
    supervisor_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="上级 ID（升级链第一级）"
    )
    duty_officer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="值班长 ID（升级链第二级）"
    )

    # 计时：绝对截止 + 累计暂停冻结
    deadline_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="原始截止时间（不含暂停）"
    )
    paused_seconds: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", comment="累计暂停秒数"
    )
    paused_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="当前暂停起始点"
    )
    pause_reason: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="最近一次暂停原因"
    )
    claimed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="认领时间"
    )

    # 节点：临期提醒 / 最终提醒 / 逾期 / 升级
    remind_1_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="临期提醒触发点（剩余 1/3 或 30 分钟）"
    )
    remind_2_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="最终提醒触发点（默认剩余 5 分钟）"
    )
    is_overdue: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否已逾期"
    )
    escalate_level: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="升级级别：0 未升级 / 1 已升上级 / 2 已升值班长"
    )
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="最近一次升级时间"
    )
    escalated_to: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="升级对象 ID"
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="完成时间"
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="创建人 ID"
    )
    trace_id: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, index=True, comment="链路追踪 ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    @property
    def effective_deadline(self) -> Optional[datetime]:
        """实际截止时间：原始截止 + 累计暂停秒数（暂停冻结）。"""
        if self.deadline_at is None:
            return None
        from datetime import timedelta

        return self.deadline_at + timedelta(seconds=int(self.paused_seconds or 0))


class CoreSlaEvent(Base):
    """SLA 事件/审计留痕：评估幂等键 + 统计数据源。"""

    __tablename__ = "oc_core_sla_event"
    __table_args__ = (
        Index("ix_core_sla_event_sla", "sla_id", "id"),
        Index("ix_core_sla_event_type", "event_type", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    sla_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="SLA 实例 ID")
    event_type: Mapped[str] = mapped_column(
        String(32), index=True, comment="事件类型：created/claimed/paused/resumed/due_soon/due_final/overdue/escalated/completed/cancelled"
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, comment="事件载荷（原因/升级对象等）")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="发生时间"
    )
