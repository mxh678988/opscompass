"""OS 内核 · 事件总线测试。

使用 SQLite 内存库独立建表，不依赖运行中的 PostgreSQL / Redis，
保证 CI 与本地均可直接执行：``pytest tests/test_event_bus.py -v``。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.bus import bus, registry
from app.models.base import Base
from app.models.kernel import CoreEvent, CoreEventCursor, CoreEventDead

KERNEL_TABLES = [CoreEvent.__table__, CoreEventDead.__table__, CoreEventCursor.__table__]


@pytest.fixture()
def db():
    """独立内存库会话，测试结束自动清理订阅注册表。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=KERNEL_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    registry.clear()
    try:
        yield session
    finally:
        session.close()
        registry.clear()
        engine.dispose()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """SQLite 不保存时区信息，读回为 naive；统一按 UTC 解释后再比较。"""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _events(db) -> list[CoreEvent]:
    return list(db.execute(select(CoreEvent).order_by(CoreEvent.id)).scalars().all())


class Recorder:
    """测试用订阅方：记录收到的上下文。"""

    def __init__(self) -> None:
        self.received: list = []

    def __call__(self, ctx) -> None:
        self.received.append(ctx)


def test_publish_and_dispatch(db) -> None:
    """发布的事件被订阅方消费，事件完结为 done。"""
    rec = Recorder()
    registry.subscribe("core.metric.written", rec, subscriber="sla")

    bus.publish(db, "core.metric.written", {"metric_id": 7}, tenant_id=1)
    result = bus.dispatch_once(db, worker_id="w1")

    assert result.delivered == 1
    assert len(rec.received) == 1
    assert rec.received[0].payload["metric_id"] == 7
    assert rec.received[0].tenant_id == 1
    assert _events(db)[0].status == "done"


def test_no_subscriber_marks_done(db) -> None:
    """无人订阅的事件直接完结，不产生积压。"""
    bus.publish(db, "core.nobody.cares", {})
    result = bus.dispatch_once(db)

    assert result.skipped == 1
    assert _events(db)[0].status == "done"


def test_delay_defers_delivery(db) -> None:
    """延迟发布的事件在到期前不被派发。"""
    rec = Recorder()
    registry.subscribe("core.later", rec, subscriber="t")

    bus.publish(db, "core.later", {}, delay_seconds=60)
    assert bus.dispatch_once(db).scanned == 0
    assert bus.dispatch_once(db, now=_now() + timedelta(seconds=61)).delivered == 1


def test_failure_retry_then_dead_letter(db) -> None:
    """投递失败按退避重试，超出最大次数转入死信。"""

    def boom(ctx) -> None:
        raise RuntimeError("下游不可用")

    registry.subscribe("core.flaky", boom, subscriber="flaky")
    bus.publish(db, "core.flaky", {"k": 1}, max_attempts=2)

    first = bus.dispatch_once(db)
    assert first.retried == 1
    ev = _events(db)[0]
    assert ev.status == "pending" and ev.attempts == 1
    assert _as_utc(ev.available_at) > _now()
    assert "下游不可用" in ev.last_error

    # 第二次投递（跳过退避等待窗口）
    second = bus.dispatch_once(db, now=_now() + timedelta(hours=1))
    assert second.dead == 1
    assert _events(db) == []

    dead = db.execute(select(CoreEventDead)).scalars().all()
    assert len(dead) == 1 and dead[0].event_name == "core.flaky" and dead[0].attempts == 2


def test_replay_dead_keeps_event_id(db) -> None:
    """死信重放保持原 event_id，消费方幂等语义不变。"""
    def boom(ctx) -> None:
        raise RuntimeError("x")

    registry.subscribe("core.replay", boom, subscriber="r")
    event_id = bus.publish(db, "core.replay", {}, max_attempts=1)
    bus.dispatch_once(db)
    assert len(db.execute(select(CoreEventDead)).scalars().all()) == 1

    assert bus.replay_dead(db) == 1
    ev = _events(db)[0]
    assert ev.event_id == event_id and ev.status == "pending" and ev.attempts == 0

    dead = db.execute(select(CoreEventDead)).scalars().one()
    assert dead.replayed is True and dead.replayed_at is not None


def test_lease_reclaim_after_worker_crash(db) -> None:
    """工作者崩溃（租约超时）后，事件可被重新领取。"""
    bus.publish(db, "core.stuck", {})
    ev = _events(db)[0]
    ev.status = "processing"
    ev.locked_by = "dead-worker"
    ev.locked_at = _now() - timedelta(hours=1)
    db.commit()

    assert bus.requeue_expired(db, lease_seconds=300) == 1
    db.refresh(ev)
    assert ev.status == "pending" and ev.locked_by is None


def test_wildcard_and_namespace_isolation(db) -> None:
    """前缀通配订阅生效；插件越权订阅其它命名空间被拒绝。"""
    senti, core = Recorder(), Recorder()
    registry.subscribe("sentiment.*", senti, subscriber="senti", plugin_id="sentiment")
    registry.subscribe("core.*", core, subscriber="kernel-audit")

    bus.publish(db, "sentiment.alert.created", {})
    bus.publish(db, "core.event.test", {})
    bus.dispatch_once(db, limit=10)

    # senti 只收 sentiment.* 事件；core 收全部 core.* 事件
    assert len(senti.received) == 1 and senti.received[0].event_name == "sentiment.alert.created"
    assert len(core.received) == 1 and core.received[0].event_name == "core.event.test"

    with pytest.raises(PermissionError):
        registry.subscribe("crisis.*", Recorder(), subscriber="senti", plugin_id="sentiment")


def test_disable_plugin_removes_subscriptions(db) -> None:
    """插件禁用后其订阅被摘除，事件不再投递给它。"""
    rec = Recorder()
    registry.subscribe("sentiment.*", rec, subscriber="senti", plugin_id="sentiment")
    assert registry.disable_plugin("sentiment") == 1

    bus.publish(db, "sentiment.alert.created", {})
    assert bus.dispatch_once(db).skipped == 1
    assert rec.received == []


def test_stats_and_prune(db) -> None:
    """统计与历史清理可用。"""
    registry.subscribe("core.x", Recorder(), subscriber="t")
    bus.publish(db, "core.x", {})
    bus.dispatch_once(db)

    stats = bus.stats(db)
    assert stats["pending"] == 0 and stats["dead"] == 0
    assert stats["subscriptions"] == ["core.x"]

    # 完结事件早于保留窗口 → 可被清理
    assert bus.prune_done(db, keep_days=7, now=_now() + timedelta(days=30)) == 1
