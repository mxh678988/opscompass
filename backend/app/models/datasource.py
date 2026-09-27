"""数据源模型：指标中心的数据供给端。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 支持的数据源类型
DS_TYPES = ("mysql", "postgresql", "clickhouse", "hive", "api", "csv")


class DataSource(Base):
    """数据源连接配置。

    只保存连接元信息；密码等敏感字段以密文形式落库（password_enc），
    对外接口一律不回显明文。
    """

    __tablename__ = "oc_data_source"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_datasource_tenant_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    code: Mapped[str] = mapped_column(String(64), comment="数据源编码")
    name: Mapped[str] = mapped_column(String(128), comment="数据源名称")
    ds_type: Mapped[str] = mapped_column(String(32), comment="类型：mysql/postgresql/clickhouse/hive/api/csv")
    host: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="主机")
    port: Mapped[Optional[int]] = mapped_column(Integer, default=None, comment="端口")
    db_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="库名")
    username: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="账号")
    password_enc: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="加密后的密码")
    extra_config: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="扩展配置（API 地址、字符集等）")
    status: Mapped[str] = mapped_column(
        String(16), default="enabled", server_default="enabled", comment="状态：enabled/disabled"
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="最近同步时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DataSource {self.code}>"
