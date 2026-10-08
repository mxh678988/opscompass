"""P7 OS 内核：插件注册表与插件配置分区建表（M2）

背景：
- v0.11.0 内核 M1（事件总线）已落地并推送；M2 交付插件运行时与 SDK，
  插件表是运行时状态机的持久化落点（设计见 docs/os-kernel-design.md 插件章节）。

本次变更（纯新增表，不修改、不删除既有表与数据）：
- oc_core_plugin         已注册插件（清单校验通过后登记；含状态机字段）
- oc_core_plugin_config  插件配置项（按 plugin_id 分区，插件间互不可见）

索引与约束：
- oc_core_plugin.plugin_id 唯一索引（插件身份）
- ix_core_plugin_state (state, id)   按状态批量调度（启用/禁用/卸载）
- ix_core_plugin_kind  (kind, plugin_id)  官方/社区筛选
- uq_core_plugin_config_key (plugin_id, key)  配置键唯一
- ix_core_plugin_config_plugin (plugin_id, id) 按插件取配置

回退：直接 drop 两张表，事件总线与既有业务表不受影响。

Revision ID: b2e3f4a5c6d7
Revises: a1f2c3d4e5b6
Create Date: 2026-10-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2e3f4a5c6d7"
down_revision: Union[str, Sequence[str], None] = "a1f2c3d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建插件注册表与插件配置两张表。"""
    op.create_table(
        "oc_core_plugin",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="自增 ID"),
        sa.Column("plugin_id", sa.String(length=64), nullable=False, comment="插件唯一 ID（目录名）"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="插件显示名"),
        sa.Column("version", sa.String(length=32), nullable=False, comment="插件语义化版本"),
        sa.Column(
            "kind",
            sa.String(length=16),
            server_default="community",
            nullable=False,
            comment="official / community",
        ),
        sa.Column(
            "min_kernel_version",
            sa.String(length=32),
            server_default="0.0.0",
            nullable=False,
            comment="要求的最低内核版本",
        ),
        sa.Column("namespace", sa.JSON(), nullable=False, comment="命名空间声明"),
        sa.Column("permissions", sa.JSON(), nullable=False, comment="权限点声明"),
        sa.Column(
            "state",
            sa.String(length=16),
            server_default="installed",
            nullable=False,
            comment="生命周期状态：installed/enabled/disabled/uninstalled",
        ),
        sa.Column("checksum", sa.String(length=128), nullable=True, comment="发布包校验和"),
        sa.Column("entry", sa.String(length=256), nullable=True, comment="入口声明，形如 main:register"),
        sa.Column("description", sa.Text(), nullable=True, comment="插件描述"),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True, comment="最近一次启用时间"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="登记时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="最近更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_core_plugin_plugin_id", "oc_core_plugin", ["plugin_id"], unique=True)
    op.create_index("ix_core_plugin_state", "oc_core_plugin", ["state", "id"], unique=False)
    op.create_index("ix_core_plugin_kind", "oc_core_plugin", ["kind", "plugin_id"], unique=False)

    op.create_table(
        "oc_core_plugin_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="自增 ID"),
        sa.Column("plugin_id", sa.String(length=64), nullable=False, comment="所属插件 ID"),
        sa.Column("key", sa.String(length=128), nullable=False, comment="配置键"),
        sa.Column("value", sa.JSON(), nullable=True, comment="配置值（JSON）"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="最近更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "key", name="uq_core_plugin_config_key"),
    )
    op.create_index(
        "ix_core_plugin_config_plugin", "oc_core_plugin_config", ["plugin_id", "id"], unique=False
    )


def downgrade() -> None:
    """回退：先删索引随表删除，再删表。"""
    op.drop_index("ix_core_plugin_config_plugin", table_name="oc_core_plugin_config")
    op.drop_table("oc_core_plugin_config")

    op.drop_index("ix_core_plugin_kind", table_name="oc_core_plugin")
    op.drop_index("ix_core_plugin_state", table_name="oc_core_plugin")
    op.drop_index("ix_core_plugin_plugin_id", table_name="oc_core_plugin")
    op.drop_table("oc_core_plugin")
