"""M10 人群包引擎：人群包与成员表

- oc_audience_segment：一次概率区间圈选结果（来源预测任务 source_job_id 联动 M9）；
- oc_audience_member：圈选出的成员（subject_key + 概率 + 档位 + 来源结果 ID），
  同一人群包内 subject_key 唯一，支持复用再圈选。

Revision ID: p14_audience
Revises: p13_predictive
Create Date: 2026-10-12
"""
from alembic import op
import sqlalchemy as sa

revision = "p14_audience"
down_revision = "p13_predictive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_audience_segment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("target", sa.String(16), nullable=False, server_default="churn"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ready"),
        sa.Column(
            "source_job_id",
            sa.Integer(),
            sa.ForeignKey("oc_prediction_job.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("min_prob", sa.Numeric(6, 5), nullable=True),
        sa.Column("max_prob", sa.Numeric(6, 5), nullable=True),
        sa.Column("band", sa.String(16), nullable=True),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criteria", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_audience_segment_tenant_time", "oc_audience_segment", ["tenant_id", "created_at"])
    op.create_index("ix_audience_segment_target_status", "oc_audience_segment", ["target", "status"])

    op.create_table(
        "oc_audience_member",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "segment_id",
            sa.Integer(),
            sa.ForeignKey("oc_audience_segment.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("subject_name", sa.String(128), nullable=True),
        sa.Column("probability", sa.Numeric(6, 5), nullable=False, server_default="0.5"),
        sa.Column("band", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("source_result_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_unique_constraint(
        "uq_audience_member_segment_subject", "oc_audience_member", ["segment_id", "subject_key"]
    )
    op.create_index("ix_audience_member_segment_prob", "oc_audience_member", ["segment_id", "probability"])


def downgrade() -> None:
    op.drop_index("ix_audience_member_segment_prob", table_name="oc_audience_member")
    op.drop_constraint("uq_audience_member_segment_subject", "oc_audience_member", type_="unique")
    op.drop_table("oc_audience_member")
    op.drop_index("ix_audience_segment_target_status", table_name="oc_audience_segment")
    op.drop_index("ix_audience_segment_tenant_time", table_name="oc_audience_segment")
    op.drop_table("oc_audience_segment")
