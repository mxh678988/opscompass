"""指标中心模型：分类 / 指标定义 / 维度 / 指标值。"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# 指标类型
METRIC_TYPES = ("atomic", "derived")
# 聚合方式
AGG_FUNCS = ("sum", "avg", "count", "count_distinct", "max", "min", "ratio")
# 统计粒度
GRANULARITIES = ("hour", "day", "week", "month")

# 指标 ↔ 维度 多对多关联表
metric_dimension_rel = Table(
    "oc_metric_dimension_rel",
    Base.metadata,
    Column("metric_id", Integer, ForeignKey("oc_metric.id", ondelete="CASCADE"), primary_key=True),
    Column("dimension_id", Integer, ForeignKey("oc_metric_dimension.id", ondelete="CASCADE"), primary_key=True),
    comment="指标与维度的关联",
)


class MetricCategory(Base):
    """指标分类（支持两级以上树形结构）。"""

    __tablename__ = "oc_metric_category"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_category_tenant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    code: Mapped[str] = mapped_column(String(64), comment="分类编码")
    name: Mapped[str] = mapped_column(String(128), comment="分类名称")
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, default=None, comment="父分类 ID")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="排序")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    metrics: Mapped[list["Metric"]] = relationship(back_populates="category")


class MetricDimension(Base):
    """维度定义：如渠道、地区、商品类目。"""

    __tablename__ = "oc_metric_dimension"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_dimension_tenant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    code: Mapped[str] = mapped_column(String(64), comment="维度编码")
    name: Mapped[str] = mapped_column(String(128), comment="维度名称")
    dim_type: Mapped[str] = mapped_column(
        String(16), default="enum", server_default="enum", comment="类型：enum 枚举 / datetime 时间 / number 数值"
    )
    source_field: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="来源字段")
    value_scope: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="可选值范围")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    metrics: Mapped[list["Metric"]] = relationship(
        secondary=metric_dimension_rel, back_populates="dimensions"
    )


class Metric(Base):
    """指标定义：指标中心的核心元数据。"""

    __tablename__ = "oc_metric"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_metric_tenant_code"),
        Index("ix_metric_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_metric_category.id", ondelete="SET NULL"), default=None, comment="分类 ID"
    )
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_data_source.id", ondelete="SET NULL"), default=None, comment="来源数据源 ID"
    )
    code: Mapped[str] = mapped_column(String(64), comment="指标编码，如 gmv")
    name: Mapped[str] = mapped_column(String(128), comment="指标名称")
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="口径说明")
    metric_type: Mapped[str] = mapped_column(
        String(16), default="atomic", server_default="atomic", comment="类型：atomic 原子 / derived 派生"
    )
    agg_func: Mapped[str] = mapped_column(
        String(24), default="sum", server_default="sum", comment="聚合方式"
    )
    formula: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="计算表达式（派生指标）")
    unit: Mapped[str] = mapped_column(String(16), default="", server_default="", comment="单位：元/单/人/%")
    precision: Mapped[int] = mapped_column(Integer, default=2, server_default="2", comment="小数位")
    granularity: Mapped[str] = mapped_column(
        String(16), default="day", server_default="day", comment="默认统计粒度"
    )
    owner: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="负责人")
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="标签")
    status: Mapped[str] = mapped_column(
        String(16), default="draft", server_default="draft", comment="状态：draft 草稿 / online 上线 / offline 下线"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped[Optional[MetricCategory]] = relationship(back_populates="metrics")
    dimensions: Mapped[list[MetricDimension]] = relationship(
        secondary=metric_dimension_rel, back_populates="metrics"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Metric {self.code}>"


class MetricValue(Base):
    """指标值：按「指标 + 时间 + 粒度 + 维度组合」唯一。"""

    __tablename__ = "oc_metric_value"
    __table_args__ = (
        UniqueConstraint("metric_id", "stat_time", "granularity", "dims_hash", name="uq_value_unique"),
        Index("ix_value_metric_time", "metric_id", "stat_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    metric_id: Mapped[int] = mapped_column(
        ForeignKey("oc_metric.id", ondelete="CASCADE"), index=True, comment="指标 ID"
    )
    stat_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="统计时间点")
    granularity: Mapped[str] = mapped_column(
        String(16), default="day", server_default="day", comment="统计粒度"
    )
    dims: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="维度组合，如 {channel: 'app'}")
    dims_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default="", comment="维度组合哈希，用于唯一约束"
    )
    value: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), default=Decimal("0"), server_default="0", comment="指标值"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
