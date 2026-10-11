"""M7 plugin signing key tables

Revision ID: f2e3d4c5a6b7
Revises: f1a2b3c4d5e6
Create Date: 2026-10-11
"""
from alembic import op
import sqlalchemy as sa
from app.models.kernel import BIGINT, TIMESTAMP

revision = "f2e3d4c5a6b7"
down_revision = "f1a2b3c4d5e6"

TABLE_PREFIX = "oc_core_"
TIMESTAMP_NOW = "CURRENT_TIMESTAMP"


def upgrade():
    op.create_table(
        f"{TABLE_PREFIX}plugin_key",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("plugin_id", sa.String(64), nullable=False, index=True),
        sa.Column("public_key", sa.Text, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("key_state", sa.String(16), nullable=False, server_default=sa.text("'enabled'")),
        sa.Column("revoked_at", TIMESTAMP, nullable=True),
        sa.Column("revoked_reason", sa.Text, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=TIMESTAMP_NOW),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=TIMESTAMP_NOW),
    )
    op.create_unique_constraint(
        f"uq_{TABLE_PREFIX}plugin_key_fingerprint",
        f"{TABLE_PREFIX}plugin_key",
        ["fingerprint"],
    )
    op.create_index(
        f"ix_{TABLE_PREFIX}plugin_key_state",
        f"{TABLE_PREFIX}plugin_key",
        ["plugin_id", "key_state"],
    )


def downgrade():
    op.drop_index(f"ix_{TABLE_PREFIX}plugin_key_state", table_name=f"{TABLE_PREFIX}plugin_key")
    op.drop_constraint(
        f"uq_{TABLE_PREFIX}plugin_key_fingerprint",
        f"{TABLE_PREFIX}plugin_key",
        type_="unique",
    )
    op.drop_table(f"{TABLE_PREFIX}plugin_key")
