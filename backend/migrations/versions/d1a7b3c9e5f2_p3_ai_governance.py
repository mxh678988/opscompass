"""P3 AI 治理：决策分级 / 叫停撤销 / 演练标识 字段补齐

背景：
- AI 治理模型（decision_level / decision_source / sim_mode / revoked 系列）已在
  app/models/ai.py 定义，接口层与前端亦按三级决策授权（仅用户决策 / 需用户授权 /
  智能体自主）设计；
- 但上一次迭代缺少配套迁移，导致 oc_ai_analysis / oc_ai_insight /
  oc_ai_action_item 三张表实际缺列，decision_board / revoke / trace 能力无法落库。

本次变更（纯增量，不修改、不删除既有列与数据）：
- oc_ai_analysis    + sim_mode / data_sources / evidence_metrics / credibility
- oc_ai_insight     + data_sources / evidence_metrics / generated_at / sim_mode /
                      decision_level，并补 (tenant_id, decision_level) 索引
- oc_ai_action_item + decision_level / decision_source / sim_mode / revoked /
                      revoked_at / revoked_by / revoke_reason / prev_status，
                      并补 (tenant_id, decision_level) 索引

历史数据：全部走 server_default 回填（decision_level=user_authorized、
decision_source=policy、sim_mode=false、revoked=false），不改变既有业务语义。

Revision ID: d1a7b3c9e5f2
Revises: c9d4e7b1a3f6
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1a7b3c9e5f2"
down_revision: Union[str, Sequence[str], None] = "c9d4e7b1a3f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ANALYSIS = "oc_ai_analysis"
INSIGHT = "oc_ai_insight"
ACTION = "oc_ai_action_item"


def upgrade() -> None:
    # ---------------- oc_ai_analysis：结论可信度与演练标识
    op.add_column(
        ANALYSIS,
        sa.Column("sim_mode", sa.Boolean(), nullable=False, server_default=sa.text("false"),
                  comment="是否演练/模拟模式（结论不作为真实决策依据）"),
    )
    op.add_column(ANALYSIS, sa.Column("data_sources", sa.JSON(), nullable=True, comment="结论引用的数据来源清单"))
    op.add_column(ANALYSIS, sa.Column("evidence_metrics", sa.JSON(), nullable=True, comment="结论依据的指标清单"))
    op.add_column(ANALYSIS, sa.Column("credibility", sa.Numeric(5, 4), nullable=True, comment="本次分析结论整体置信度 0-1"))

    # ---------------- oc_ai_insight：来源可溯 + 决策分级
    op.add_column(INSIGHT, sa.Column("data_sources", sa.JSON(), nullable=True,
                                     comment="数据来源清单（指标表/导入任务/数据源）"))
    op.add_column(INSIGHT, sa.Column("evidence_metrics", sa.JSON(), nullable=True,
                                     comment="依据指标清单（编码 + 取值 + 环比）"))
    op.add_column(INSIGHT, sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True,
                                     comment="结论生成时间"))
    op.add_column(INSIGHT, sa.Column("sim_mode", sa.Boolean(), nullable=False, server_default=sa.text("false"),
                                     comment="是否演练/模拟模式"))
    op.add_column(INSIGHT, sa.Column("decision_level", sa.String(24), nullable=False,
                                     server_default=sa.text("'user_authorized'"),
                                     comment="决策分级 user_only/user_authorized/agent_autonomous"))
    op.create_index("ix_ai_insight_tenant_decision", INSIGHT, ["tenant_id", "decision_level"])

    # ---------------- oc_ai_action_item：决策分级 + 叫停/撤销留痕
    op.add_column(ACTION, sa.Column("decision_level", sa.String(24), nullable=False,
                                    server_default=sa.text("'user_authorized'"),
                                    comment="决策分级 user_only 仅用户本人 / user_authorized 需用户授权 / agent_autonomous 智能体自主"))
    op.add_column(ACTION, sa.Column("decision_source", sa.String(16), nullable=False,
                                    server_default=sa.text("'policy'"), comment="分级来源 policy/manual/rule"))
    op.add_column(ACTION, sa.Column("sim_mode", sa.Boolean(), nullable=False, server_default=sa.text("false"),
                                    comment="是否来自演练/模拟模式：为真时不得作为真实经营决策依据"))
    op.add_column(ACTION, sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false"),
                                    comment="是否已被用户撤销/叫停"))
    op.add_column(ACTION, sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True, comment="撤销/叫停时间"))
    op.add_column(ACTION, sa.Column("revoked_by", sa.String(64), nullable=True, comment="撤销/叫停操作人"))
    op.add_column(ACTION, sa.Column("revoke_reason", sa.Text(), nullable=True, comment="撤销/叫停原因"))
    op.add_column(ACTION, sa.Column("prev_status", sa.String(16), nullable=True, comment="撤销前的状态，用于回溯与还原"))
    op.create_index("ix_ai_action_tenant_decision", ACTION, ["tenant_id", "decision_level"])


def downgrade() -> None:
    op.drop_index("ix_ai_action_tenant_decision", table_name=ACTION)
    for col in ("prev_status", "revoke_reason", "revoked_by", "revoked_at", "revoked",
                "sim_mode", "decision_source", "decision_level"):
        op.drop_column(ACTION, col)

    op.drop_index("ix_ai_insight_tenant_decision", table_name=INSIGHT)
    for col in ("decision_level", "sim_mode", "generated_at", "evidence_metrics", "data_sources"):
        op.drop_column(INSIGHT, col)

    for col in ("credibility", "evidence_metrics", "data_sources", "sim_mode"):
        op.drop_column(ANALYSIS, col)
