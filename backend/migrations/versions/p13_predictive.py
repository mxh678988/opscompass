"""M9 预测引擎：预测任务与预测结果表

- oc_prediction_job：一次预测任务的元信息（目标/状态/模式/特征与主体统计/阈值/兜底标记）；
- oc_prediction_result：每个主体的概率输出（概率/档位/模式/模型/置信度/特征/理由），
  供人群包引擎（M10）圈选复用，唯一约束 job_id+subject_key。

Revision ID: p13_predictive
Revises: f2e3d4c5a6b7
Create Date: 2026-10-12
"""
from alembic import op
import sqlalchemy as sa

revision = "p13_predictive"
down_revision = "f2e3d4c5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_prediction_job",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("target", sa.String(16), nullable=False, server_default="churn"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("mode", sa.String(16), nullable=False, server_default="local"),
        sa.Column("model", sa.String(128), nullable=False, server_default=""),
        sa.Column("source", sa.String(64), nullable=False, server_default="event_bus"),
        sa.Column("input_snapshot", sa.JSON(), nullable=True),
        sa.Column("feature_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subject_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("threshold", sa.Numeric(5, 4), nullable=True),
        sa.Column("rule_fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_prediction_job_tenant_time", "oc_prediction_job", ["tenant_id", "created_at"])
    op.create_index("ix_prediction_job_target_status", "oc_prediction_job", ["target", "status"])

    op.create_table(
        "oc_prediction_result",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("oc_prediction_job.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("target", sa.String(16), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("subject_name", sa.String(128), nullable=True),
        sa.Column("probability", sa.Numeric(6, 5), nullable=False, server_default="0.5"),
        sa.Column("band", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("mode", sa.String(16), nullable=False, server_default="rule"),
        sa.Column("model", sa.String(128), nullable=False, server_default=""),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_unique_constraint(
        "uq_prediction_result_job_subject", "oc_prediction_result", ["job_id", "subject_key"]
    )
    op.create_index("ix_prediction_result_job_band", "oc_prediction_result", ["job_id", "band"])
    op.create_index("ix_prediction_result_job_prob", "oc_prediction_result", ["job_id", "probability"])
    op.create_index("ix_prediction_result_tenant_target", "oc_prediction_result", ["tenant_id", "target"])


def downgrade() -> None:
    op.drop_index("ix_prediction_result_tenant_target", table_name="oc_prediction_result")
    op.drop_index("ix_prediction_result_job_prob", table_name="oc_prediction_result")
    op.drop_index("ix_prediction_result_job_band", table_name="oc_prediction_result")
    op.drop_constraint("uq_prediction_result_job_subject", "oc_prediction_result", type_="unique")
    op.drop_table("oc_prediction_result")
    op.drop_index("ix_prediction_job_target_status", table_name="oc_prediction_job")
    op.drop_index("ix_prediction_job_tenant_time", table_name="oc_prediction_job")
    op.drop_table("oc_prediction_job")
