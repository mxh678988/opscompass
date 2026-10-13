"""p21_knowledge_base: 知识库与知识库文件表

Revision ID: p21_knowledge_base
Revises: p20_site_resource
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision = "p21_knowledge_base"
down_revision = "p20_site_resource"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_knowledge_base",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kb_tenant_name", "oc_knowledge_base", ["tenant_id", "name"])

    op.create_table(
        "oc_knowledge_base_file",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("base_id", sa.Integer(), nullable=False, index=True),
        sa.Column("file_name", sa.String(length=200), nullable=False),
        sa.Column("file_path", sa.String(length=600), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False, server_default="other"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploader", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kb_file_tenant_time", "oc_knowledge_base_file", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("oc_knowledge_base_file")
    op.drop_table("oc_knowledge_base")
