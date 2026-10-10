"""p8: OS 内核统一身份治理（M3）—— 新增身份委派表 oc_core_delegation

Revision ID: c3f4a5b6d7e8
Revises: b2e3f4a5c6d7
Create Date: 2026-10-08

说明：
- 仅新表，不改动既有 54 表结构（兼容红线）；
- 权限点仍复用既有 oc_permission / oc_role / oc_role_permission，不新建表；
- 委派表以「状态 + 时间窗」双保险失效，禁止无期限临时授权（服务层校验 ≤90 天）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f4a5b6d7e8"
down_revision: Union[str, Sequence[str], None] = "b2e3f4a5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oc_core_delegation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("delegator_id", sa.BigInteger(), nullable=False, comment="委托人（权限来源）"),
        sa.Column("delegatee_id", sa.BigInteger(), nullable=False, comment="被委托人（代理执行者）"),
        sa.Column("scope_roles", sa.JSON(), nullable=True, comment="委派角色码（须为委托人自身角色子集）"),
        sa.Column(
            "scope_permissions", sa.JSON(), nullable=True, comment="委派权限码（须为委托人自身权限子集）"
        ),
        sa.Column("reason", sa.Text(), nullable=True, comment="委派事由"),
        sa.Column(
            "status", sa.String(length=16), server_default="active", nullable=False, comment="active/expired/revoked"
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False, comment="生效时间"),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False, comment="失效时间（必填）"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="操作人 ID"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True, comment="撤销时间"),
        sa.Column("revoked_by", sa.BigInteger(), nullable=True, comment="撤销人 ID"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="创建时间"
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="最近更新时间"
        ),
        sa.ForeignKeyConstraint(["delegator_id"], ["oc_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegatee_id"], ["oc_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="OS 内核·身份委派（临时授权/代理，M3）",
    )
    op.create_index("ix_oc_core_delegation_status", "oc_core_delegation", ["status"])
    op.create_index(
        "ix_core_delegation_delegatee", "oc_core_delegation", ["delegatee_id", "status"]
    )
    op.create_index(
        "ix_core_delegation_delegator", "oc_core_delegation", ["delegator_id", "status"]
    )
    op.create_index("ix_core_delegation_window", "oc_core_delegation", ["status", "end_at"])


def downgrade() -> None:
    op.drop_index("ix_core_delegation_window", table_name="oc_core_delegation")
    op.drop_index("ix_core_delegation_delegator", table_name="oc_core_delegation")
    op.drop_index("ix_core_delegation_delegatee", table_name="oc_core_delegation")
    op.drop_index("ix_oc_core_delegation_status", table_name="oc_core_delegation")
    op.drop_table("oc_core_delegation")
