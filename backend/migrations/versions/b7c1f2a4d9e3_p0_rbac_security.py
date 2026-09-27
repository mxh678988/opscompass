"""P0 RBAC 与安全审计表

新增：oc_permission / oc_role / oc_user / oc_user_role / oc_role_permission / oc_audit_log
说明：既有业务表（oc_tenant 等 24 张）由早期建表脚本创建，基线版本 de8ccdb09354 已 stamp。

Revision ID: b7c1f2a4d9e3
Revises: de8ccdb09354
Create Date: 2026-09-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c1f2a4d9e3"
down_revision: Union[str, Sequence[str], None] = "de8ccdb09354"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 RBAC 与审计相关表。"""
    # ------------------------------------------------------ 权限点
    op.create_table(
        "oc_permission",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False, comment="权限编码"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="权限名称"),
        sa.Column("module", sa.String(length=64), nullable=False, comment="所属模块"),
        sa.Column("description", sa.String(length=255), nullable=True, comment="描述"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="权限点",
    )
    op.create_index("ix_oc_permission_code", "oc_permission", ["code"], unique=True)

    # ------------------------------------------------------ 角色
    op.create_table(
        "oc_role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False, comment="角色编码"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="角色名称"),
        sa.Column("description", sa.String(length=255), nullable=True, comment="描述"),
        sa.Column(
            "is_builtin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否内置角色",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="角色",
    )
    op.create_index("ix_oc_role_code", "oc_role", ["code"], unique=True)

    # ------------------------------------------------------ 用户
    op.create_table(
        "oc_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "tenant_id", sa.Integer(), nullable=True, comment="所属租户"
        ),
        sa.Column("username", sa.String(length=64), nullable=False, comment="登录名"),
        sa.Column("full_name", sa.String(length=128), nullable=True, comment="姓名"),
        sa.Column("email", sa.String(length=128), nullable=True, comment="邮箱"),
        sa.Column(
            "hashed_password", sa.String(length=255), nullable=False, comment="密码哈希（bcrypt）"
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False, comment="是否启用"
        ),
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否超级管理员",
        ),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="连续登录失败次数",
        ),
        sa.Column(
            "locked_until", sa.DateTime(timezone=True), nullable=True, comment="锁定截止时间"
        ),
        sa.Column(
            "last_login_at", sa.DateTime(timezone=True), nullable=True, comment="最近登录时间"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["oc_tenant.id"], name="fk_oc_user_tenant_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="用户",
    )
    op.create_index("ix_oc_user_username", "oc_user", ["username"], unique=True)
    op.create_index("ix_oc_user_tenant_id", "oc_user", ["tenant_id"], unique=False)
    op.create_index("ix_user_tenant_status", "oc_user", ["tenant_id", "is_active"], unique=False)

    # ------------------------------------------------------ 关联表
    op.create_table(
        "oc_user_role",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["oc_user.id"], name="fk_oc_user_role_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["oc_role.id"], name="fk_oc_user_role_role_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        comment="用户角色关联",
    )

    op.create_table(
        "oc_role_permission",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"], ["oc_role.id"], name="fk_oc_role_permission_role_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["oc_permission.id"],
            name="fk_oc_role_permission_permission_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        comment="角色权限关联",
    )

    # ------------------------------------------------------ 审计日志
    op.create_table(
        "oc_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True, comment="租户"),
        sa.Column("user_id", sa.Integer(), nullable=True, comment="操作人 ID"),
        sa.Column("username", sa.String(length=64), nullable=True, comment="操作人登录名"),
        sa.Column("event_type", sa.String(length=32), nullable=False, comment="事件类型"),
        sa.Column("action", sa.String(length=128), nullable=True, comment="动作摘要"),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'success'"),
            nullable=False,
            comment="结果：success/failure",
        ),
        sa.Column("status_code", sa.Integer(), nullable=True, comment="HTTP 状态码"),
        sa.Column("method", sa.String(length=16), nullable=True, comment="请求方法"),
        sa.Column("path", sa.String(length=255), nullable=True, comment="请求路径"),
        sa.Column("client_ip", sa.String(length=64), nullable=True, comment="客户端 IP"),
        sa.Column("user_agent", sa.String(length=255), nullable=True, comment="客户端 UA"),
        sa.Column("detail", sa.Text(), nullable=True, comment="详细信息"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="发生时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="安全审计日志",
    )
    op.create_index("ix_oc_audit_log_tenant_id", "oc_audit_log", ["tenant_id"], unique=False)
    op.create_index("ix_oc_audit_log_event_type", "oc_audit_log", ["event_type"], unique=False)
    op.create_index("ix_oc_audit_log_created_at", "oc_audit_log", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_tenant_time", "oc_audit_log", ["tenant_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_audit_event_time", "oc_audit_log", ["event_type", "created_at"], unique=False
    )
    op.create_index("ix_audit_user_time", "oc_audit_log", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    """回滚：删除本次新增的 RBAC 与审计表。"""
    op.drop_index("ix_audit_user_time", table_name="oc_audit_log")
    op.drop_index("ix_audit_event_time", table_name="oc_audit_log")
    op.drop_index("ix_audit_tenant_time", table_name="oc_audit_log")
    op.drop_index("ix_oc_audit_log_created_at", table_name="oc_audit_log")
    op.drop_index("ix_oc_audit_log_event_type", table_name="oc_audit_log")
    op.drop_index("ix_oc_audit_log_tenant_id", table_name="oc_audit_log")
    op.drop_table("oc_audit_log")

    op.drop_table("oc_role_permission")
    op.drop_table("oc_user_role")

    op.drop_index("ix_user_tenant_status", table_name="oc_user")
    op.drop_index("ix_oc_user_tenant_id", table_name="oc_user")
    op.drop_index("ix_oc_user_username", table_name="oc_user")
    op.drop_table("oc_user")

    op.drop_index("ix_oc_role_code", table_name="oc_role")
    op.drop_table("oc_role")

    op.drop_index("ix_oc_permission_code", table_name="oc_permission")
    op.drop_table("oc_permission")
