"""M6 model router tables

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-10-11
"""
from alembic import op
import sqlalchemy as sa
from app.models.kernel import BIGINT, TIMESTAMP

revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9d0"

TABLE_PREFIX = "oc_core_"
TIMESTAMP_NOW = "CURRENT_TIMESTAMP"


def upgrade():
    op.create_table(
        f"{TABLE_PREFIX}model_capability",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("capability_key", sa.String(128), nullable=False, index=True),
        sa.Column("capability_type", sa.String(32), nullable=False),
        sa.Column("sensitive_level", sa.Integer, server_default=sa.text("0")),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("model_param", sa.JSON, nullable=True),
        sa.Column("cache_ttl", sa.Integer, server_default=sa.text("300")),
        sa.Column("force_local", sa.Boolean, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("1")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=TIMESTAMP_NOW),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=TIMESTAMP_NOW),
    )
    op.create_unique_constraint(
        f"uq_{TABLE_PREFIX}model_capability_key",
        f"{TABLE_PREFIX}model_capability",
        ["capability_key"],
    )

    op.create_table(
        f"{TABLE_PREFIX}model_route_log",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("tenant_id", BIGINT, nullable=False, index=True),
        sa.Column("capability_key", sa.String(128), nullable=False, index=True),
        sa.Column("route_result", sa.String(32), nullable=False),
        sa.Column("selected_model", sa.String(128), nullable=True),
        sa.Column("fallback_reason", sa.String(256), nullable=True),
        sa.Column("duration_ms", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=TIMESTAMP_NOW),
    )

    op.create_table(
        f"{TABLE_PREFIX}model_cache",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("tenant_id", BIGINT, nullable=False, index=True),
        sa.Column("capability_key", sa.String(128), nullable=False, index=True),
        sa.Column("input_fingerprint", sa.String(64), nullable=False, index=True),
        sa.Column("output_data", sa.JSON, nullable=False),
        sa.Column("ttl", TIMESTAMP, nullable=False, index=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=TIMESTAMP_NOW),
    )


def downgrade():
    op.drop_table(f"{TABLE_PREFIX}model_cache")
    op.drop_table(f"{TABLE_PREFIX}model_route_log")
    op.drop_table(f"{TABLE_PREFIX}model_capability")
