"""P2 存储适配层与数据一致性表

新增：
- oc_storage_route_rule  数据源类型识别与存储引擎路由规则
- oc_doc_index           全文检索索引（tsvector + GIN，可替换适配器承载）
- oc_ts_metric_point     时序指标点（按 stat_time RANGE 分区的分区表）
- oc_storage_consistency_check  跨存储一致性对账记录

说明：
- 全部落地在既有 PostgreSQL 16 实例内，不引入新镜像/新依赖；
- oc_ts_metric_point 为分区表，主键包含分区键 stat_time；迁移内预建近期月分区，
  运行期由 app/storage/timeseries.py 按需自动补建；
- 全文检索优先使用 tsvector + GIN，pg_trgm 扩展可用时自动叠加模糊匹配，不可用则降级 ILIKE。

Revision ID: c9d4e7b1a3f6
Revises: b7c1f2a4d9e3
Create Date: 2026-09-23

"""
from datetime import datetime, timedelta, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c9d4e7b1a3f6"
down_revision: Union[str, Sequence[str], None] = "b7c1f2a4d9e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TS_TABLE = "oc_ts_metric_point"
PARTITION_PREFIX = "oc_ts_metric_point_p"
# 分区边界时区：与 app.storage.timeseries 的 STORAGE_TS_PARTITION_UTC_OFFSET_HOURS 保持一致
PARTITION_TZ = timezone(timedelta(hours=8))


def _month_key(dt: datetime) -> str:
    """202609 形式的月份标识。"""
    return f"{dt.year}{dt.month:02d}"


def _month_shift(base: datetime, months: int) -> datetime:
    """按月偏移，返回该月 1 日 00:00（分区时区口径）。"""
    total = base.year * 12 + (base.month - 1) + months
    return datetime(total // 12, total % 12 + 1, 1, tzinfo=PARTITION_TZ)


def _partition_ddl(name: str, start: datetime, end: datetime) -> str:
    """分区边界 DDL。

    边界必须带显式时区偏移：若写成不带偏移的裸日期，PostgreSQL 会按会话时区
    （如 Asia/Shanghai）解析，与运行时适配器（东八区显式偏移）口径不一致时
    会出现分区重叠，导致相邻月份分区无法再创建。
    """
    return (
        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {TS_TABLE} "
        f"FOR VALUES FROM ('{_tz_bound(start)}') TO ('{_tz_bound(end)}')"
    )


def _tz_bound(dt: datetime) -> str:
    """输出东八区口径的边界字面量，如 2026-08-01T00:00:00+08:00。"""
    local = dt.astimezone(timezone(timedelta(hours=8)))
    return local.isoformat()


def upgrade() -> None:
    """创建 P2 存储适配层所需的四张表及索引。"""
    # ------------------------------------------------------ 可选扩展（失败不阻塞）
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception:  # pragma: no cover
        pass

    # ------------------------------------------------------ 路由规则
    op.create_table(
        "oc_storage_route_rule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True, comment="租户 ID，NULL 为全局内置规则"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="规则名称"),
        sa.Column(
            "match_field",
            sa.String(length=32),
            nullable=False,
            comment="识别依据：ds_type 数据源类型 / file_ext 文件后缀 / content_hint 内容特征",
        ),
        sa.Column("match_value", sa.String(length=128), nullable=False, comment="匹配值"),
        sa.Column("data_kind", sa.String(length=32), nullable=False, comment="接入数据类型"),
        sa.Column("engine", sa.String(length=64), nullable=False, comment="目标存储引擎标识"),
        sa.Column(
            "priority",
            sa.Integer(),
            server_default=sa.text("100"),
            nullable=False,
            comment="优先级，数值越小越先匹配",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="是否启用",
        ),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "match_field", "match_value", name="uq_oc_storage_route_rule_match"
        ),
        comment="数据源类型识别与存储引擎路由规则",
    )
    op.create_index(
        "ix_oc_storage_route_rule_kind", "oc_storage_route_rule", ["data_kind"], unique=False
    )
    op.create_index(
        "ix_oc_storage_route_rule_tenant_id", "oc_storage_route_rule", ["tenant_id"], unique=False
    )

    # ------------------------------------------------------ 全文检索索引
    op.create_table(
        "oc_doc_index",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, comment="租户 ID"),
        sa.Column(
            "doc_type", sa.String(length=32), nullable=False, comment="文档类型：metric / datasource / ..."
        ),
        sa.Column("doc_id", sa.String(length=64), nullable=False, comment="源对象标识"),
        sa.Column(
            "title", sa.String(length=255), server_default=sa.text("''"), nullable=False, comment="标题"
        ),
        sa.Column("content", sa.Text(), nullable=True, comment="正文/描述"),
        sa.Column("keywords", sa.String(length=512), nullable=True, comment="关键词（空格分隔）"),
        sa.Column("url", sa.String(length=512), nullable=True, comment="来源链接"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="附加字段快照"),
        sa.Column("tsv", postgresql.TSVECTOR(), nullable=True, comment="全文检索向量"),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="索引时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_type", "doc_id", name="uq_oc_doc_index_doc"),
        comment="全文检索索引（可替换适配器承载）",
    )
    op.create_index(
        "ix_oc_doc_index_tenant_type", "oc_doc_index", ["tenant_id", "doc_type"], unique=False
    )
    op.create_index(
        "ix_oc_doc_index_tsv",
        "oc_doc_index",
        ["tsv"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index("ix_oc_doc_index_tenant_id", "oc_doc_index", ["tenant_id"], unique=False)

    # ------------------------------------------------------ 时序分区表
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TS_TABLE} (
            tenant_id   INTEGER        NOT NULL,
            metric_id   INTEGER        NOT NULL,
            metric_code VARCHAR(64)    NOT NULL DEFAULT '',
            stat_time   TIMESTAMPTZ    NOT NULL,
            granularity VARCHAR(16)    NOT NULL DEFAULT 'day',
            dims_hash   VARCHAR(64)    NOT NULL DEFAULT '',
            dims        JSONB,
            value       NUMERIC(20, 6) NOT NULL DEFAULT 0,
            source_id   INTEGER,
            origin      VARCHAR(32)    NOT NULL DEFAULT 'mirror',
            created_at  TIMESTAMPTZ    NOT NULL DEFAULT now(),
            CONSTRAINT pk_oc_ts_metric_point PRIMARY KEY
                (tenant_id, metric_id, stat_time, granularity, dims_hash)
        ) PARTITION BY RANGE (stat_time)
        """
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_ts_point_metric_time "
        f"ON {TS_TABLE} (tenant_id, metric_code, stat_time)"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_ts_point_tenant_time ON {TS_TABLE} (tenant_id, stat_time)"
    )

    # 预建「上月起 ~ 未来两月」共四个月分区
    base = datetime.now(PARTITION_TZ).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    for offset in (-1, 0, 1, 2):
        start = _month_shift(base, offset)
        end = _month_shift(base, offset + 1)
        op.execute(_partition_ddl(f"{PARTITION_PREFIX}{_month_key(start)}", start, end))

    # ------------------------------------------------------ 一致性对账记录
    op.create_table(
        "oc_storage_consistency_check",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, comment="租户 ID"),
        sa.Column("scope", sa.String(length=64), nullable=False, comment="对账范围标识"),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'passed'"),
            nullable=False,
            comment="passed / warning / failed / skipped",
        ),
        sa.Column(
            "checked", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="核对条目数"
        ),
        sa.Column(
            "matched", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="一致条目数"
        ),
        sa.Column(
            "missing", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="目标存储缺失条目数"
        ),
        sa.Column(
            "extra", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="目标存储多余条目数"
        ),
        sa.Column(
            "mismatched", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="值不一致条目数"
        ),
        sa.Column(
            "repaired", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="自动修复条目数"
        ),
        sa.Column(
            "auto_repair",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否启用自动修复",
        ),
        sa.Column(
            "elapsed_ms", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="耗时毫秒"
        ),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="对账明细报告"),
        sa.Column("operator", sa.String(length=64), nullable=True, comment="操作人"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="跨存储一致性对账记录",
    )
    op.create_index(
        "ix_oc_consistency_tenant_time",
        "oc_storage_consistency_check",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_oc_consistency_scope", "oc_storage_consistency_check", ["scope"], unique=False
    )


def downgrade() -> None:
    """回滚：删除 P2 新增表（分区表随父表一并删除）。"""
    op.drop_index("ix_oc_consistency_scope", table_name="oc_storage_consistency_check")
    op.drop_index("ix_oc_consistency_tenant_time", table_name="oc_storage_consistency_check")
    op.drop_table("oc_storage_consistency_check")

    op.execute(f"DROP TABLE IF EXISTS {TS_TABLE} CASCADE")

    op.drop_index("ix_oc_doc_index_tenant_id", table_name="oc_doc_index")
    op.drop_index("ix_oc_doc_index_tsv", table_name="oc_doc_index")
    op.drop_index("ix_oc_doc_index_tenant_type", table_name="oc_doc_index")
    op.drop_table("oc_doc_index")

    op.drop_index("ix_oc_storage_route_rule_tenant_id", table_name="oc_storage_route_rule")
    op.drop_index("ix_oc_storage_route_rule_kind", table_name="oc_storage_route_rule")
    op.drop_table("oc_storage_route_rule")
