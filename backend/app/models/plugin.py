"""OS 内核模型：插件注册表与插件配置分区（M2）。

设计要点：
- 插件生命周期状态机与 ``app.core.plugin.registry.PluginState`` 一一对应，
  持久化字段只存状态名，避免枚举序号在版本间漂移；
- ``namespace`` / ``permissions`` 以 JSON 落库，便于清单演进时无需加列；
- 插件配置独立成表并按 ``plugin_id`` 隔离，插件间配置互不可见（M3 起叠加行级鉴权）；
- 所有表统一 ``oc_core_`` 前缀，与既有 ``oc_`` 业务表隔离。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.kernel import ID_TYPE

# 插件生命周期状态（与 registry.PluginState 同名）
PLUGIN_STATES = ("installed", "enabled", "disabled", "uninstalled")

# 插件来源类型：官方内置 / 社区
PLUGIN_KINDS = ("official", "community")


class CorePlugin(Base):
    """已注册插件（清单校验通过后登记）。"""

    __tablename__ = "oc_core_plugin"
    __table_args__ = (
        Index("ix_core_plugin_state", "state", "id"),
        Index("ix_core_plugin_kind", "kind", "plugin_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, comment="插件唯一 ID（目录名）"
    )
    name: Mapped[str] = mapped_column(String(128), comment="插件显示名")
    version: Mapped[str] = mapped_column(String(32), comment="插件语义化版本")
    kind: Mapped[str] = mapped_column(
        String(16), default="community", comment="official / community"
    )
    min_kernel_version: Mapped[str] = mapped_column(
        String(32), default="0.0.0", comment="要求的最低内核版本"
    )
    namespace: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="命名空间声明：tables / events / permissions 前缀",
    )
    permissions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, comment="插件声明的权限点列表"
    )
    state: Mapped[str] = mapped_column(
        String(16), default="installed", index=True, comment="生命周期状态"
    )
    checksum: Mapped[Optional[str]] = mapped_column(
        String(128), default=None, comment="发布包校验和（官方签名校验用）"
    )
    entry: Mapped[Optional[str]] = mapped_column(
        String(256), default=None, comment="入口声明，形如 main:register"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="插件描述"
    )
    enabled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="最近一次启用时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="登记时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="最近更新时间",
    )


class CorePluginKey(Base):
    """插件签名公钥注册表（M7 插件签名密钥体系）。

    同一插件同一时刻至多一个 ``enabled`` 公钥，轮换时旧钥置 ``revoked`` 留痕；
    ``fingerprint`` 全局唯一，用于核对 ``.sig`` 内嵌指纹，防止公钥错配。
    """

    __tablename__ = "oc_core_plugin_key"
    __table_args__ = (
        Index("ix_core_plugin_key_state", "plugin_id", "key_state"),
        Index("ix_core_plugin_key_fingerprint", "fingerprint"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(
        String(64), index=True, comment="所属插件 ID"
    )
    public_key: Mapped[str] = mapped_column(
        Text, comment="Ed25519 公钥 PEM（SubjectPublicKeyInfo）"
    )
    fingerprint: Mapped[str] = mapped_column(
        String(64), unique=True, comment="公钥指纹 SHA-256 十六进制"
    )
    key_state: Mapped[str] = mapped_column(
        String(16), default="enabled", comment="enabled / revoked"
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="吊销时间（轮换/撤销）"
    )
    revoked_reason: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="吊销/轮换原因"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="登记时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="最近更新时间",
    )


class CorePluginConfig(Base):
    """插件配置项（按插件分区，键值隔离）。"""

    __tablename__ = "oc_core_plugin_config"
    __table_args__ = (
        UniqueConstraint("plugin_id", "key", name="uq_core_plugin_config_key"),
        Index("ix_core_plugin_config_plugin", "plugin_id", "id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(
        String(64), index=True, comment="所属插件 ID"
    )
    key: Mapped[str] = mapped_column(String(128), comment="配置键")
    value: Mapped[Any] = mapped_column(JSON, default=None, comment="配置值（JSON）")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="最近更新时间",
    )
