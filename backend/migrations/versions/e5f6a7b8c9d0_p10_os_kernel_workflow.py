"""p10: OS 内核工作流引擎（M5）—— 新增 oc_core_workflow_instance / oc_core_workflow_step

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-10

说明：
- 仅新表，不改动既有表结构（兼容红线）；
- 实例表 + 步骤表：步骤以 instance_id + seq 为幂等键（唯一约束），
  支持中断续跑、人工节点待办与超时兜底；
- 表统一 oc_core_ 前缀，与业务表隔离。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oc_core_workflow_instance",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("def_key", sa.String(length=128), nullable=False, comment="流程定义键（如 sentiment_analysis_workflow）"),
        sa.Column("title", sa.String(length=200), nullable=False, comment="实例标题"),
        sa.Column("status", sa.String(length=16), server_default="created", nullable=False, comment="状态：created/running/waiting/paused/completed/failed/cancelled"),
        sa.Column("context", sa.JSON(), nullable=True, comment="初始上下文数据（JSON）"),
        sa.Column("current_step", sa.Integer(), nullable=True, comment="当前步骤序号"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True, comment="开始执行时间"),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True, comment="结束时间（完成/失败/取消）"),
        sa.Column("error", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="创建者用户 ID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="OS 内核·工作流实例（M5）",
    )
    op.create_index("ix_core_wf_def_status", "oc_core_workflow_instance", ["def_key", "status", "id"])
    op.create_index("ix_core_wf_created", "oc_core_workflow_instance", ["created_at"])
    op.create_index("ix_core_wf_creator", "oc_core_workflow_instance", ["created_by"])

    op.create_table(
        "oc_core_workflow_step",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("instance_id", sa.BigInteger(), nullable=False, comment="工作流实例 ID"),
        sa.Column("seq", sa.Integer(), nullable=False, comment="步骤序号（从 0 开始）"),
        sa.Column("node_type", sa.String(length=16), nullable=False, comment="节点类型：task/branch/parallel/wait/retry"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="步骤名称"),
        sa.Column("config", sa.JSON(), nullable=True, comment="步骤配置（handler/next/conditions 等）"),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False, comment="状态：pending/running/waiting/completed/failed/skipped"),
        sa.Column("payload", sa.JSON(), nullable=True, comment="执行结果或上下文数据"),
        sa.Column("error", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="开始执行时间"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="完成时间"),
        sa.ForeignKeyConstraint(["instance_id"], ["oc_core_workflow_instance.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id", "seq", name="uq_core_wf_step_inst_seq"),
        comment="OS 内核·工作流步骤（M5）",
    )
    op.create_index("ix_core_wf_step_inst_status", "oc_core_workflow_step", ["instance_id", "status", "seq"])
    op.create_index("ix_core_wf_step_waiting", "oc_core_workflow_step", ["status", "seq"])


def downgrade() -> None:
    op.drop_index("ix_core_wf_step_waiting", table_name="oc_core_workflow_step")
    op.drop_index("ix_core_wf_step_inst_status", table_name="oc_core_workflow_step")
    op.drop_table("oc_core_workflow_step")
    op.drop_index("ix_core_wf_creator", table_name="oc_core_workflow_instance")
    op.drop_index("ix_core_wf_created", table_name="oc_core_workflow_instance")
    op.drop_index("ix_core_wf_def_status", table_name="oc_core_workflow_instance")
    op.drop_table("oc_core_workflow_instance")
