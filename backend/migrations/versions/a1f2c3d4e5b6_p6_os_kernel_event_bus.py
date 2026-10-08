"""P6 OS 内核：事件总线（事件队列 / 死信 / 订阅位点）建表

背景：
- v0.11.0 为「内核地基」版本，第一项内核能力是事件总线，作为其余内核能力
  （工作流引擎 / 任务 SLA / 模型路由）与插件间协作的唯一异步通道；
- 设计见 docs/os-kernel-design.md 第 3.1 节：PostgreSQL 持久化队列 + Redis 唤醒，
  不引入外部消息中间件，保证单机可跑。

本次变更（纯新增表，不修改、不删除既有表与数据）：
- oc_core_event         事件队列（pending/processing/done/dead 四态 + 租约字段）
- oc_core_event_dead    死信（超最大投递次数转存，支持重放）
- oc_core_event_cursor  订阅位点（补数与积压观测）

索引：
- ix_core_event_dispatch (status, available_at, id)  派发扫描主索引
- ix_core_event_name     (event_name, id)            事件回溯
- ix_core_event_partition(partition_key, id)         分区内保序
- ix_core_event_dead_time(failed_at, id)             死信排查
- event_id 唯一索引，作为消费方幂等键

回退：直接 drop 三张表，既有业务表不受影响。

Revision ID: a1f2c3d4e5b6
Revises: p5_ai_gov_perf_idx
Create Date: 2026-10-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f2c3d4e5b6"
down_revision: Union[str, Sequence[str], None] = "p5_ai_gov_perf_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建事件总线三张表。"""
    op.create_table(
        "oc_core_event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="自增 ID"),
        sa.Column("event_id", sa.String(length=64), nullable=False, comment="事件全局唯一 ID"),
        sa.Column("event_name", sa.String(length=128), nullable=False, comment="事件名"),
        sa.Column("payload", sa.JSON(), nullable=False, comment="事件载荷"),
        sa.Column("trace_id", sa.String(length=64), nullable=True, comment="链路追踪 ID"),
        sa.Column("tenant_id", sa.Integer(), nullable=True, comment="租户 ID"),
        sa.Column("partition_key", sa.String(length=128), nullable=True, comment="分区键"),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
            comment="状态：pending/processing/done/dead",
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False, comment="尝试次数"),
        sa.Column(
            "max_attempts", sa.Integer(), server_default="5", nullable=False, comment="最大投递次数"
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="可投递时间",
        ),
        sa.Column("locked_by", sa.String(length=64), nullable=True, comment="领取者"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True, comment="领取时间"),
        sa.Column("last_error", sa.Text(), nullable=True, comment="最近失败原因"),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="事件发生时间",
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True, comment="完成时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_core_event_event_id", "oc_core_event", ["event_id"], unique=True)
    op.create_index("ix_core_event_event_name", "oc_core_event", ["event_name"])
    op.create_index("ix_core_event_tenant_id", "oc_core_event", ["tenant_id"])
    op.create_index("ix_core_event_trace_id", "oc_core_event", ["trace_id"])
    op.create_index("ix_core_event_dispatch", "oc_core_event", ["status", "available_at", "id"])
    op.create_index("ix_core_event_name", "oc_core_event", ["event_name", "id"])
    op.create_index("ix_core_event_partition", "oc_core_event", ["partition_key", "id"])

    op.create_table(
        "oc_core_event_dead",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False, comment="原事件 ID"),
        sa.Column("event_name", sa.String(length=128), nullable=False, comment="原事件名"),
        sa.Column("payload", sa.JSON(), nullable=False, comment="原事件载荷"),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True, comment="最终失败原因"),
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="转入死信时间",
        ),
        sa.Column(
            "replayed", sa.Boolean(), server_default=sa.false(), nullable=False, comment="是否已重放"
        ),
        sa.Column("replayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_core_event_dead_event_id", "oc_core_event_dead", ["event_id"])
    op.create_index("ix_core_event_dead_event_name", "oc_core_event_dead", ["event_name"])
    op.create_index("ix_core_event_dead_time", "oc_core_event_dead", ["failed_at", "id"])

    op.create_table(
        "oc_core_event_cursor",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscriber", sa.String(length=128), nullable=False, comment="订阅方标识"),
        sa.Column("event_name", sa.String(length=128), nullable=False, comment="订阅的事件名"),
        sa.Column(
            "last_event_id", sa.BigInteger(), server_default="0", nullable=False, comment="已消费进度"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_core_event_cursor_subscriber", "oc_core_event_cursor", ["subscriber"], unique=True)


def downgrade() -> None:
    """回退：删除事件总线三张表（既有业务表不受影响）。"""
    op.drop_index("ix_core_event_cursor_subscriber", table_name="oc_core_event_cursor")
    op.drop_table("oc_core_event_cursor")

    op.drop_index("ix_core_event_dead_time", table_name="oc_core_event_dead")
    op.drop_index("ix_core_event_dead_event_name", table_name="oc_core_event_dead")
    op.drop_index("ix_core_event_dead_event_id", table_name="oc_core_event_dead")
    op.drop_table("oc_core_event_dead")

    op.drop_index("ix_core_event_partition", table_name="oc_core_event")
    op.drop_index("ix_core_event_name", table_name="oc_core_event")
    op.drop_index("ix_core_event_dispatch", table_name="oc_core_event")
    op.drop_index("ix_core_event_trace_id", table_name="oc_core_event")
    op.drop_index("ix_core_event_tenant_id", table_name="oc_core_event")
    op.drop_index("ix_core_event_event_name", table_name="oc_core_event")
    op.drop_index("ix_core_event_event_id", table_name="oc_core_event")
    op.drop_table("oc_core_event")
