"""p19_site_project: 响应式网站项目表。

Revision ID: p19_site_project
Revises: p18_import_export
Create Date: 2026-10-13
"""
import sqlalchemy as sa
from alembic import op

revision = "p19_site_project"
down_revision = "p18_import_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_site_project",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("template", sa.String(length=60), server_default="default", nullable=False),
        sa.Column("seo_title", sa.String(length=160), nullable=True),
        sa.Column("seo_description", sa.String(length=320), nullable=True),
        sa.Column("seo_keywords", sa.String(length=500), nullable=True),
        sa.Column("geo_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("geo_region", sa.String(length=120), nullable=True),
        sa.Column("geo_org_type", sa.String(length=120), nullable=True),
        sa.Column("host_mode", sa.String(length=20), server_default="link", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("publish_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_site_project_tenant_id", "oc_site_project", ["tenant_id"])
    op.create_index("ix_site_project_status", "oc_site_project", ["status"])
    op.create_index("ix_site_project_tenant_slug", "oc_site_project", ["tenant_id", "slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_site_project_tenant_slug", table_name="oc_site_project")
    op.drop_index("ix_site_project_status", table_name="oc_site_project")
    op.drop_index("ix_site_project_tenant_id", table_name="oc_site_project")
    op.drop_table("oc_site_project")
