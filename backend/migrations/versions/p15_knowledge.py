"""M11 企业知识库：知识文档与引用日志

- oc_knowledge_doc：业务经验 / SOP / 洞察 / 策略 / 手册，供 Agent（M12）引用；
- oc_knowledge_ref_log：每次被引用轨迹，ref_count 累计热度，
  形成「知识沉淀 → 引用 → 反馈」的进化闭环。

Revision ID: p15_knowledge
Revises: p14_audience
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "p15_knowledge"
down_revision = "p14_audience"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_knowledge_doc",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("doc_type", sa.String(16), nullable=False, server_default="experience"),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("scenario", sa.String(200), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="manual"),
        sa.Column("ref_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("author", sa.String(64), nullable=False, server_default="system"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_knowledge_doc_tenant_type", "oc_knowledge_doc", ["tenant_id", "doc_type"])
    op.create_index("ix_knowledge_doc_tenant_status", "oc_knowledge_doc", ["tenant_id", "status"])
    op.create_index("ix_knowledge_doc_ref_count", "oc_knowledge_doc", ["ref_count"])

    op.create_table(
        "oc_knowledge_ref_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "doc_id",
            sa.Integer(),
            sa.ForeignKey("oc_knowledge_doc.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("source", sa.String(32), nullable=False, server_default="agent"),
        sa.Column("ref_key", sa.String(128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_knowledge_ref_log_doc", "oc_knowledge_ref_log", ["doc_id", "created_at"])
    op.create_index("ix_knowledge_ref_log_tenant_time", "oc_knowledge_ref_log", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_ref_log_tenant_time", table_name="oc_knowledge_ref_log")
    op.drop_index("ix_knowledge_ref_log_doc", table_name="oc_knowledge_ref_log")
    op.drop_table("oc_knowledge_ref_log")
    op.drop_index("ix_knowledge_doc_ref_count", table_name="oc_knowledge_doc")
    op.drop_index("ix_knowledge_doc_tenant_status", table_name="oc_knowledge_doc")
    op.drop_index("ix_knowledge_doc_tenant_type", table_name="oc_knowledge_doc")
    op.drop_table("oc_knowledge_doc")
