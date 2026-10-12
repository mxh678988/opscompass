"""M12 智能体编排：编排运行 / 分析洞察 / 执行动作

- oc_agent_run：分析 Agent + 执行 Agent 双角色编排主记录，
  状态机 pending→analyzing→awaiting_approval→executing→done/failed/rejected，
  人工确认闸门（approval_required=True 时必须 approve/reject 才可执行）；
- oc_agent_insight：分析 Agent 产出洞察（诊断结论 + 证据 + 建议动作）；
- oc_agent_action：执行 Agent 落地动作登记，结果回写事件总线（published/event_name），
  形成「诊断→确认→落地→回写」闭环。

Revision ID: p16_agent
Revises: p15_knowledge
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "p16_agent"
down_revision = "p15_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_agent_run",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False, comment="运行名称"),
        sa.Column("scenario", sa.String(32), nullable=False, server_default="custom", comment="场景模板"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending", comment="运行状态"),
        sa.Column("datasource_bindings", sa.JSON(), nullable=True, comment="数据源绑定"),
        sa.Column("knowledge_refs", sa.JSON(), nullable=True, comment="引用的知识库文档 ID"),
        sa.Column("action_config", sa.JSON(), nullable=True, comment="执行动作配置"),
        sa.Column("insight_agent", sa.String(64), nullable=False, server_default="insight-agent", comment="分析 Agent 标识"),
        sa.Column("action_agent", sa.String(64), nullable=False, server_default="action-agent", comment="执行 Agent 标识"),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default="true", comment="是否强制人工确认闸门"),
        sa.Column("approved_by", sa.String(64), nullable=True, comment="确认人"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True, comment="确认时间"),
        sa.Column("approve_note", sa.Text(), nullable=True, comment="确认意见"),
        sa.Column("result_summary", sa.Text(), nullable=True, comment="交付结果摘要"),
        sa.Column("result_published", sa.Boolean(), nullable=False, server_default="false", comment="结果是否已回写事件总线"),
        sa.Column("result_event_id", sa.String(64), nullable=True, comment="回写的事件 ID"),
        sa.Column("error", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system", comment="发起人"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True, comment="完成时间"),
    )
    op.create_index("ix_agent_run_tenant_time", "oc_agent_run", ["tenant_id", "created_at"])
    op.create_index("ix_agent_run_scenario_status", "oc_agent_run", ["scenario", "status"])

    op.create_table(
        "oc_agent_insight",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("oc_agent_run.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="1", comment="序号"),
        sa.Column("title", sa.String(200), nullable=False, comment="洞察标题"),
        sa.Column("detail", sa.Text(), nullable=True, comment="诊断详情"),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info", comment="info/warning/critical"),
        sa.Column("evidence", sa.JSON(), nullable=True, comment="数据依据"),
        sa.Column("suggestion", sa.Text(), nullable=True, comment="可行动建议"),
        sa.Column("suggested_action_type", sa.String(24), nullable=False, server_default="create_task", comment="建议动作类型"),
        sa.Column("status", sa.String(16), nullable=False, server_default="new", comment="new/confirmed/rejected/executed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_agent_insight_run", "oc_agent_insight", ["run_id", "created_at"])
    op.create_index("ix_agent_insight_tenant_status", "oc_agent_insight", ["tenant_id", "status"])

    op.create_table(
        "oc_agent_action",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("oc_agent_run.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "insight_id",
            sa.Integer(),
            sa.ForeignKey("oc_agent_insight.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action_type", sa.String(24), nullable=False, server_default="create_task", comment="动作类型"),
        sa.Column("payload", sa.JSON(), nullable=True, comment="动作配置载荷"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", comment="pending/approved/rejected/executed/failed"),
        sa.Column("executed_by", sa.String(64), nullable=True, comment="执行者（Action Agent）"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True, comment="执行时间"),
        sa.Column("result", sa.JSON(), nullable=True, comment="执行结果"),
        sa.Column("published", sa.Boolean(), nullable=False, server_default="false", comment="是否已回写事件总线"),
        sa.Column("event_name", sa.String(128), nullable=True, comment="回写事件名"),
        sa.Column("error", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_agent_action_run", "oc_agent_action", ["run_id", "created_at"])
    op.create_index("ix_agent_action_tenant_status", "oc_agent_action", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_agent_action_tenant_status", table_name="oc_agent_action")
    op.drop_index("ix_agent_action_run", table_name="oc_agent_action")
    op.drop_table("oc_agent_action")
    op.drop_index("ix_agent_insight_tenant_status", table_name="oc_agent_insight")
    op.drop_index("ix_agent_insight_run", table_name="oc_agent_insight")
    op.drop_table("oc_agent_insight")
    op.drop_index("ix_agent_run_scenario_status", table_name="oc_agent_run")
    op.drop_index("ix_agent_run_tenant_time", table_name="oc_agent_run")
    op.drop_table("oc_agent_run")
