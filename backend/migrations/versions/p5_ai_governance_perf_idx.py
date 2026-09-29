"""P5 AI 治理性能：高频筛选复合索引补齐

为 AI 洞察（status+severity）、处置单（status+handler）与按分析追溯
（analysis_id）补 tenant_id 前缀复合索引，覆盖治理台与追溯接口的常用过滤路径。

Revision ID: p5_ai_gov_perf_idx
Revises: p4_ai_governance_perf
Create Date: 2026-09-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "p5_ai_gov_perf_idx"
down_revision: Union[str, Sequence[str], None] = "p4_ai_governance_perf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # oc_ai_insight: 洞察列表按 租户+状态+严重度 过滤
    op.create_index(
        "ix_ai_insight_tenant_status_severity",
        "oc_ai_insight",
        ["tenant_id", "status", "severity"],
        unique=False,
    )

    # oc_ai_action_item: 治理台按 租户+状态+处理方 过滤
    op.create_index(
        "ix_ai_action_tenant_status_handler",
        "oc_ai_action_item",
        ["tenant_id", "status", "handler"],
        unique=False,
    )

    # oc_ai_action_item: 按分析回溯处置单（替代内存过滤）
    op.create_index(
        "ix_ai_action_tenant_analysis",
        "oc_ai_action_item",
        ["tenant_id", "analysis_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_action_tenant_analysis", table_name="oc_ai_action_item")
    op.drop_index("ix_ai_action_tenant_status_handler", table_name="oc_ai_action_item")
    op.drop_index("ix_ai_insight_tenant_status_severity", table_name="oc_ai_insight")
