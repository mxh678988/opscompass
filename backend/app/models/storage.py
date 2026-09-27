"""P2 存储适配层模型：路由规则 / 全文检索索引 / 时序指标点 / 一致性对账记录。

说明：
- oc_ts_metric_point 为按 stat_time 范围分区的 PostgreSQL 分区表，
  由迁移脚本创建父表与月分区，程序侧按需自动补建分区（见 app/storage/timeseries.py）。
- oc_doc_index 维护 tsvector 全文索引列 tsv，供检索适配器读写。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 接入数据类型 -> 存储引擎种类（适配层路由的 key）
DATA_KINDS = ("relational", "timeseries", "fulltext", "cache", "file")

# 识别字段类型
MATCH_FIELDS = ("ds_type", "file_ext", "content_hint")


class StorageRouteRule(Base):
    """数据源类型识别与存储引擎路由规则。

    tenant_id 为 NULL 表示内置全局规则；同租户可覆盖同名匹配项。
    """

    __tablename__ = "oc_storage_route_rule"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "match_field", "match_value", name="uq_oc_storage_route_rule_match"
        ),
        Index("ix_oc_storage_route_rule_kind", "data_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, index=True, default=None, comment="租户 ID，NULL 为全局内置规则"
    )
    name: Mapped[str] = mapped_column(String(128), comment="规则名称")
    match_field: Mapped[str] = mapped_column(
        String(32), comment="识别依据：ds_type 数据源类型 / file_ext 文件后缀 / content_hint 内容特征"
    )
    match_value: Mapped[str] = mapped_column(String(128), comment="匹配值，如 csv / *.log / 时序")
    data_kind: Mapped[str] = mapped_column(String(32), comment="接入数据类型")
    engine: Mapped[str] = mapped_column(String(64), comment="目标存储引擎标识")
    priority: Mapped[int] = mapped_column(
        Integer, default=100, server_default="100", comment="优先级，数值越小越先匹配"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否启用"
    )
    remark: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class DocIndex(Base):
    """全文检索索引：统一收纳各类可检索文档（指标/数据源/运营资产等）。"""

    __tablename__ = "oc_doc_index"
    __table_args__ = (
        UniqueConstraint("doc_type", "doc_id", name="uq_oc_doc_index_doc"),
        Index("ix_oc_doc_index_tenant_type", "tenant_id", "doc_type"),
        Index("ix_oc_doc_index_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    doc_type: Mapped[str] = mapped_column(String(32), comment="文档类型：metric / datasource / ...")
    doc_id: Mapped[str] = mapped_column(String(64), comment="源对象标识（字符串化主键或编码）")
    title: Mapped[str] = mapped_column(String(255), default="", server_default="", comment="标题")
    content: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="正文/描述")
    keywords: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="关键词（空格分隔）")
    url: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="来源链接")
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, default=None, comment="附加字段快照")
    tsv: Mapped[Optional[str]] = mapped_column(TSVECTOR, default=None, comment="全文检索向量")
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="索引时间"
    )


class TsMetricPoint(Base):
    """时序指标点：按 stat_time 范围分区的指标事实表。

    主键必须包含分区键 stat_time（PostgreSQL 分区表约束）。
    """

    __tablename__ = "oc_ts_metric_point"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "metric_id",
            "stat_time",
            "granularity",
            "dims_hash",
            name="pk_oc_ts_metric_point",
        ),
        Index("ix_ts_point_metric_time", "tenant_id", "metric_code", "stat_time"),
        Index("ix_ts_point_tenant_time", "tenant_id", "stat_time"),
        {"postgresql_partition_by": "RANGE (stat_time)"},
    )

    tenant_id: Mapped[int] = mapped_column(Integer, comment="租户 ID")
    metric_id: Mapped[int] = mapped_column(Integer, comment="指标 ID")
    metric_code: Mapped[str] = mapped_column(String(64), comment="指标编码（冗余，便于按编码聚合）")
    stat_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="统计时间点（分区键）")
    granularity: Mapped[str] = mapped_column(String(16), comment="统计粒度 hour/day/week/month")
    dims_hash: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="维度组合哈希")
    dims: Mapped[Optional[dict]] = mapped_column(JSONB, default=None, comment="维度组合")
    value: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), default=Decimal("0"), server_default="0", comment="指标值"
    )
    source_id: Mapped[Optional[int]] = mapped_column(Integer, default=None, comment="来源数据源 ID")
    origin: Mapped[str] = mapped_column(
        String(32), default="mirror", server_default="mirror", comment="写入来源：mirror 镜像 / direct 直写"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="写入时间"
    )


class ConsistencyCheck(Base):
    """跨存储一致性对账记录。"""

    __tablename__ = "oc_storage_consistency_check"
    __table_args__ = (
        Index("ix_oc_consistency_tenant_time", "tenant_id", "created_at"),
        Index("ix_oc_consistency_scope", "scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    scope: Mapped[str] = mapped_column(String(64), comment="对账范围标识")
    status: Mapped[str] = mapped_column(
        String(16), default="passed", server_default="passed", comment="passed / warning / failed / skipped"
    )
    checked: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="核对条目数")
    matched: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="一致条目数")
    missing: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="目标存储缺失条目数")
    extra: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="目标存储多余条目数")
    mismatched: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="值不一致条目数")
    repaired: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="自动修复条目数")
    auto_repair: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否启用自动修复"
    )
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="耗时毫秒")
    report: Mapped[Optional[dict]] = mapped_column(JSONB, default=None, comment="对账明细报告")
    operator: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="操作人")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
