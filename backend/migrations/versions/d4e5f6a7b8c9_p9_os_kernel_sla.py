"""p9: OS 内核任务 SLA（M4）—— 新增 oc_core_sla / oc_core_sla_event

Revision ID: d4e5f6a7b8c9
Revises: c3f4a5b6d7e8
Create Date: 2026-10-10

说明：
- 仅新表，不改动既有表结构（兼容红线）；
- SLA 实例表 + 事件留痕表，评估幂等/统计均聚合事件表；
- 表统一 oc_core_ 前缀，与业务表隔离。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3f4a5b6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oc_core_sla",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("object_type", sa.String(length=64), nullable=False, comment="对象类型：task/ticket/workflow_step/plugin:<id> 等"),
        sa.Column("object_id", sa.String(length=64), nullable=False, comment="对象 ID"),
        sa.Column("title", sa.String(length=200), nullable=False, comment="任务标题"),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False, comment="状态：open/paused/done/cancelled"),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True, comment="责任人 ID"),
        sa.Column("supervisor_id", sa.BigInteger(), nullable=True, comment="上级 ID（升级链第一级）"),
        sa.Column("duty_officer_id", sa.BigInteger(), nullable=True, comment="值班长 ID（升级链第二级）"),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True, comment="原始截止时间（不含暂停）"),
        sa.Column("paused_seconds", sa.BigInteger(), server_default="0", nullable=False, comment="累计暂停秒数"),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True, comment="当前暂停起始点"),
        sa.Column("pause_reason", sa.Text(), nullable=True, comment="最近一次暂停原因"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True, comment="认领时间"),
        sa.Column("remind_1_at", sa.DateTime(timezone=True), nullable=True, comment="临期提醒触发点（剩余 1/3 或 30 分钟）"),
        sa.Column("remind_2_at", sa.DateTime(timezone=True), nullable=True, comment="最终提醒触发点（默认剩余 5 分钟）"),
        sa.Column("is_overdue", sa.Boolean(), server_default="false", nullable=False, comment="是否已逾期"),
        sa.Column("escalate_level", sa.Integer(), server_default="0", nullable=False, comment="升级级别：0 未升级 / 1 已升上级 / 2 已升值班长"),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True, comment="最近一次升级时间"),
        sa.Column("escalated_to", sa.BigInteger(), nullable=True, comment="升级对象 ID"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="完成时间"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="创建人 ID"),
        sa.Column("trace_id", sa.String(length=64), nullable=True, comment="链路追踪 ID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="最近更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="OS 内核·任务 SLA（M4）",
    )
    op.create_index("ix_core_sla_eval", "oc_core_sla", ["status", "remind_1_at", "id"])
    op.create_index("ix_core_sla_object", "oc_core_sla", ["object_type", "object_id"])
    op.create_index("ix_core_sla_assignee", "oc_core_sla", ["assignee_id", "status"])
    op.create_index("ix_core_sla_trace", "oc_core_sla", ["trace_id"])

    op.create_table(
        "oc_core_sla_event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("sla_id", sa.BigInteger(), nullable=False, comment="SLA 实例 ID"),
        sa.Column("event_type", sa.String(length=32), nullable=False, comment="事件类型：created/claimed/paused/resumed/due_soon/due_final/overdue/escalated/completed/cancelled"),
        sa.Column("payload", sa.JSON(), nullable=True, comment="事件载荷（原因/升级对象等）"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="发生时间"),
        sa.ForeignKeyConstraint(["sla_id"], ["oc_core_sla.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="OS 内核·SLA 事件留痕（M4）",
    )
    op.create_index("ix_core_sla_event_sla", "oc_core_sla_event", ["sla_id", "id"])
    op.create_index("ix_core_sla_event_type", "oc_core_sla_event", ["event_type", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_core_sla_event_type", table_name="oc_core_sla_event")
    op.drop_index("ix_core_sla_event_sla", table_name="oc_core_sla_event")
    op.drop_table("oc_core_sla_event")
    op.drop_index("ix_core_sla_trace", table_name="oc_core_sla")
    op.drop_index("ix_core_sla_assignee", table_name="oc_core_sla")
    op.drop_index("ix_core_sla_object", table_name="oc_core_sla")
    op.drop_index("ix_core_sla_eval", table_name="oc_core_sla")
    op.drop_table("oc_core_sla")
