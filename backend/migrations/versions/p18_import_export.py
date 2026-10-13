"""M14 导入导出安全中心：压缩传输记录

- oc_import_record：导入解压记录（zip-slip 防护落盘后登记 file_count）；
- oc_export_record：导出压缩记录（encrypted/plugin_required/password_ref 密文引用）。

Revision ID: p18_import_export
Revises: p17_api_bridge
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "p18_import_export"
down_revision = "p17_api_bridge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_import_record",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True, comment="租户 ID"),
        sa.Column("source_name", sa.String(500), nullable=False, comment="源压缩包文件名"),
        sa.Column("archive_type", sa.String(16), nullable=False, server_default="zip", comment="压缩类型 zip/tar.gz"),
        sa.Column("target_dir", sa.String(500), nullable=False, comment="解压目标目录"),
        sa.Column("extracted", sa.Boolean(), nullable=False, server_default="false", comment="是否已解压提取"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0", comment="解压文件数"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", comment="pending/done/failed"),
        sa.Column("error", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
    )
    op.create_table(
        "oc_export_record",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True, comment="租户 ID"),
        sa.Column("target_name", sa.String(500), nullable=False, comment="导出压缩包文件名"),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default="false", comment="是否加密压缩"),
        sa.Column("password_ref", sa.String(2048), nullable=True, comment="密码密文引用（AES）"),
        sa.Column("plugin_required", sa.Boolean(), nullable=False, server_default="false", comment="是否依赖付费插件 secure-export"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0", comment="导出文件数"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", comment="pending/done/failed"),
        sa.Column("target_path", sa.String(500), nullable=True, comment="导出文件落盘路径"),
        sa.Column("error", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
    )
    op.create_index("ix_import_tenant_time", "oc_import_record", ["tenant_id", "created_at"])
    op.create_index("ix_export_tenant_time", "oc_export_record", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_export_tenant_time", table_name="oc_export_record")
    op.drop_index("ix_import_tenant_time", table_name="oc_import_record")
    op.drop_table("oc_export_record")
    op.drop_table("oc_import_record")
