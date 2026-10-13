"""p20_site_resource: 网站资源索引表

Revision ID: p20_site_resource
Revises: p19_site_project
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "p20_site_resource"
down_revision = "p19_site_project"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_site_resource",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), nullable=True, index=True),
        sa.Column("resource_type", sa.String(length=20), nullable=False, server_default="other"),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("path", sa.String(length=600), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active", index=True),
        sa.Column("meta", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("oc_site_resource")
