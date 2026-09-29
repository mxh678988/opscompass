"""P4 AI 治理性能：高频查询复合索引补齐

补全决策分级看板（status+decision_level 分组）、处置单治理表
（status+decision_level 筛选 + revoked 统计）所需的索引。

Revision ID: p4_ai_governance_perf
Revises: d1a7b3c9e5f2
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p4_ai_governance_perf"
down_revision: Union[str, Sequence[str], None] = "d1a7b3c9e5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # oc_ai_insight: 决策分级看板常用 status+decision_level 分组
    op.create_index(
        "ix_ai_insight_status_decision",
        "oc_ai_insight",
        ["status", "decision_level"],
        unique=False,
    )

    # oc_ai_analysis: 数据域筛选（scope）
    op.create_index(
        "ix_ai_analysis_scope",
        "oc_ai_analysis",
        ["scope"],
        unique=False,
    )

    # oc_ai_action_item: 治理台常用 status+decision_level 筛选
    op.create_index(
        "ix_ai_action_status_decision",
        "oc_ai_action_item",
        ["status", "decision_level"],
        unique=False,
    )

    # oc_ai_action_item: revoked 状态统计
    op.create_index(
        "ix_ai_action_revoked",
        "oc_ai_action_item",
        ["revoked"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_action_revoked", table_name="oc_ai_action_item")
    op.drop_index("ix_ai_action_status_decision", table_name="oc_ai_action_item")
    op.drop_index("ix_ai_analysis_scope", table_name="oc_ai_analysis")
    op.drop_index("ix_ai_insight_status_decision", table_name="oc_ai_insight")
