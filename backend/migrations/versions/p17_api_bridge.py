"""M13 API 申请助手：平台申请模板 / 代申请任务

- oc_api_platform_template：电商/网站平台 API 申请模板（申请地址 / 表单字段映射 /
  是否需人工验证 / 分类 / 启用状态）；
- oc_api_apply_task：代申请任务，credentials_ref 保存 AES 密文引用（严禁明文密码），
  状态机 pending -> submitted -> awaiting_manual -> done/failed。

Revision ID: p17_api_bridge
Revises: p16_agent
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "p17_api_bridge"
down_revision = "p16_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_api_platform_template",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True, comment="租户 ID"),
        sa.Column("name", sa.String(200), nullable=False, comment="平台名称"),
        sa.Column("apply_url", sa.String(500), nullable=False, comment="申请地址"),
        sa.Column("field_schema", sa.JSON(), nullable=True, comment="表单字段映射"),
        sa.Column("requires_manual", sa.Boolean(), nullable=False, server_default="false", comment="是否需人工验证/付费/资质审核"),
        sa.Column("category", sa.String(16), nullable=False, server_default="other", comment="分类 ecommerce/website/other"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true", comment="是否启用"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
    )
    op.create_table(
        "oc_api_apply_task",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True, comment="租户 ID"),
        sa.Column("platform_id", sa.Integer(), nullable=True, comment="平台模板 ID"),
        sa.Column("platform", sa.String(200), nullable=False, comment="目标平台名称（冗余快照）"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending", comment="pending/submitted/awaiting_manual/done/failed"),
        sa.Column("credentials_ref", sa.String(2048), nullable=True, comment="凭据密文引用（AES 加密，严禁明文）"),
        sa.Column("account", sa.String(255), nullable=False, comment="申请账号"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0", comment="进度 0-100"),
        sa.Column("result_message", sa.Text(), nullable=True, comment="结果消息"),
        sa.Column("error", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system", comment="申请人"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True, comment="结束时间（done/failed）"),
    )
    op.create_index("ix_api_task_tenant_time", "oc_api_apply_task", ["tenant_id", "created_at"])
    op.create_index("ix_api_task_platform_status", "oc_api_apply_task", ["platform", "status"])


def downgrade() -> None:
    op.drop_index("ix_api_task_platform_status", table_name="oc_api_apply_task")
    op.drop_index("ix_api_task_tenant_time", table_name="oc_api_apply_task")
    op.drop_table("oc_api_apply_task")
    op.drop_table("oc_api_platform_template")
