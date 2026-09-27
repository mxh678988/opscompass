"""示例数据初始化（幂等）：默认租户 + 示例数据源 + 核心指标 + 近 30 天指标值。

用法：
    docker compose exec backend python -m app.seed_demo
"""

from datetime import datetime, timedelta, time
from decimal import Decimal
from random import Random
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.base import SessionLocal
from app.models.datasource import DataSource
from app.models.metric import Metric, MetricCategory, MetricValue
from app.services.metric_service import dims_hash

TZ = ZoneInfo(settings.TIMEZONE)
RNG = Random(20260922)

# 指标编码 -> (名称, 分类, 单位, 精度, 基准值, 日波动, 日增长)
DEMO_METRICS = {
    "gmv": ("成交总额", "交易", "元", 2, 1_850_000.0, 0.09, 0.006),
    "orders": ("订单量", "交易", "单", 0, 12_600.0, 0.08, 0.004),
    "users": ("活跃用户数", "用户", "人", 0, 86_000.0, 0.05, 0.002),
    "conversion_rate": ("支付转化率", "转化", "%", 2, 6.8, 0.06, 0.0),
}


def _ensure_tenant(db: Session) -> int:
    from app.models.tenant import Tenant

    tenant = db.execute(select(Tenant).where(Tenant.code == "default")).scalars().first()
    if tenant is None:
        tenant = Tenant(code="default", name="示例租户", remark="seed_demo 自动创建")
        db.add(tenant)
        db.flush()
    return tenant.id


def _ensure_category(db: Session, tenant_id: int, code: str, name: str) -> MetricCategory:
    cat = db.execute(
        select(MetricCategory).where(
            MetricCategory.tenant_id == tenant_id, MetricCategory.code == code
        )
    ).scalars().first()
    if cat is None:
        cat = MetricCategory(tenant_id=tenant_id, code=code, name=name)
        db.add(cat)
        db.flush()
    return cat


def _ensure_datasource(db: Session, tenant_id: int) -> DataSource:
    ds = db.execute(
        select(DataSource).where(DataSource.tenant_id == tenant_id, DataSource.code == "dw_demo")
    ).scalars().first()
    if ds is None:
        ds = DataSource(
            tenant_id=tenant_id,
            code="dw_demo",
            name="示例数仓（演示用）",
            ds_type="postgresql",
            host="postgres",
            port=5432,
            db_name="opscompass",
            username="opscompass",
            extra_config={"note": "仅演示，未真实拉数"},
            status="enabled",
        )
        db.add(ds)
        db.flush()
    return ds


def _ensure_metric(
    db: Session,
    tenant_id: int,
    code: str,
    spec: tuple,
    category: MetricCategory,
    source: DataSource,
) -> Metric:
    name, _cat, unit, precision, *_ = spec
    metric = db.execute(
        select(Metric).where(Metric.tenant_id == tenant_id, Metric.code == code)
    ).scalars().first()
    if metric is None:
        metric = Metric(
            tenant_id=tenant_id,
            category_id=category.id,
            source_id=source.id,
            code=code,
            name=name,
            description=f"{name}（示例口径：按自然日汇总）",
            metric_type="atomic" if code != "conversion_rate" else "derived",
            agg_func="sum" if code != "conversion_rate" else "ratio",
            formula=None if code != "conversion_rate" else "orders / users * 100",
            unit=unit,
            precision=precision,
            granularity="day",
            owner="ops-demo",
            tags=["demo", "core"],
            status="online",
        )
        db.add(metric)
        db.flush()
    return metric


def _seed_values(db: Session, tenant_id: int, metric: Metric, days: int = 30) -> int:
    _name, _cat, _unit, _precision, base, wave, growth = DEMO_METRICS[metric.code]
    today = datetime.now(TZ).date()
    count = 0
    for offset in range(days, -1, -1):
        day = today - timedelta(days=offset)
        stat_time = datetime.combine(day, time(0, 0), tzinfo=TZ)
        factor = (1 + growth) ** (days - offset)
        value = base * factor * (1 + RNG.uniform(-wave, wave))
        if metric.code == "conversion_rate":
            value = round(value, 2)

        existing = db.execute(
            select(MetricValue).where(
                MetricValue.metric_id == metric.id,
                MetricValue.stat_time == stat_time,
                MetricValue.granularity == "day",
                MetricValue.dims_hash == "",
            )
        ).scalars().first()
        if existing is None:
            db.add(
                MetricValue(
                    tenant_id=tenant_id,
                    metric_id=metric.id,
                    stat_time=stat_time,
                    granularity="day",
                    dims=None,
                    dims_hash=dims_hash(None),
                    value=Decimal(str(round(value, 6))),
                )
            )
        else:
            existing.value = Decimal(str(round(value, 6)))
        count += 1
    return count


def main() -> None:
    db = SessionLocal()
    try:
        tenant_id = _ensure_tenant(db)
        source = _ensure_datasource(db, tenant_id)
        categories = {
            "交易": _ensure_category(db, tenant_id, "trade", "交易"),
            "用户": _ensure_category(db, tenant_id, "user", "用户"),
            "转化": _ensure_category(db, tenant_id, "conversion", "转化"),
        }

        total_points = 0
        for code, spec in DEMO_METRICS.items():
            metric = _ensure_metric(db, tenant_id, code, spec, categories[spec[1]], source)
            total_points += _seed_values(db, tenant_id, metric)

        db.commit()
        print(f"[seed_demo] 租户 ID={tenant_id}，指标 {len(DEMO_METRICS)} 个，写入/更新指标值 {total_points} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main()
