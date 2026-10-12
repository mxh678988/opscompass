"""OS 内核 · 事件总线测试。

使用 SQLite 内存库独立建表，不依赖运行中的 PostgreSQL / Redis，
保证 CI 与本地均可直接执行：``pytest tests/test_event_bus.py -v``。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.bus import EventBus, bus, registry
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


def test_publish_idempotent_done(db) -> None:
    """重复发布已 done 的同 event_id 事件，返回原 ID 且不创建副本。"""
    rec = Recorder()
    registry.subscribe("core.idempotent", rec, subscriber="idm")

    event_id = bus.publish(db, "core.idempotent", {"v": 1}, event_id="same-id-1")
    assert bus.dispatch_once(db).delivered == 1
    assert len(_events(db)) == 1  # 只有 1 条事件

    # 重复发布同一 event_id
    ret2 = bus.publish(db, "core.idempotent", {"v": 2}, event_id="same-id-1")
    assert ret2 == event_id
    assert len(_events(db)) == 1  # 仍只有 1 条事件


def test_stats_high_watermark_alert(db) -> None:
    """S3: pending 超过水位阈值时触发告警回调。"""
    alert_bus = EventBus(max_pending=3)
    fired: list[dict] = []
    alert_bus.on_high_watermark(fired.append)

    for i in range(4):
        alert_bus.publish(db, "core.hwm", {"i": i})
    db.commit()

    snap = alert_bus.stats(db)
    assert snap["pending"] == 4
    assert len(fired) == 1  # 超过阈值触发一次
    assert fired[0]["pending"] == 4


def test_stats_under_threshold_no_alert(db) -> None:
    """S3: pending 未超过阈值时不触发告警回调。"""
    quiet_bus = EventBus(max_pending=10)
    fired: list[dict] = []
    quiet_bus.on_high_watermark(fired.append)

    quiet_bus.publish(db, "core.hwm", {"i": 1})
    db.commit()

    snap = quiet_bus.stats(db)
    assert snap["pending"] == 1
    assert fired == []  # 未超过阈值不告警


def test_dead_letter_alert_fires_on_dead(db) -> None:
    """S2: 事件转入死信时触发死信告警回调，携带完整详情。"""
    alert_bus = EventBus()
    fired: list[dict] = []
    alert_bus.on_dead_letter(fired.append)

    def boom(ctx) -> None:
        raise RuntimeError("下游不可用")

    registry.subscribe("core.alerting", boom, subscriber="alerter")
    event_id = alert_bus.publish(db, "core.alerting", {"k": 2}, max_attempts=1)
    alert_bus.dispatch_once(db)

    assert len(fired) == 1
    detail = fired[0]
    assert detail["event_id"] == event_id
    assert detail["event_name"] == "core.alerting"
    assert detail["attempts"] == 1
    assert "下游不可用" in detail["last_error"]
    assert detail["failed_at"]  # 非空 ISO 时间


def test_dead_letter_alert_only_on_terminal(db) -> None:
    """S2: 仅重试耗尽转入死信时告警；可重试的失败不误报。"""
    alert_bus = EventBus()
    fired: list[dict] = []
    alert_bus.on_dead_letter(fired.append)

    def boom(ctx) -> None:
        raise RuntimeError("暂时抖动")

    registry.subscribe("core.noalert", boom, subscriber="noal")
    alert_bus.publish(db, "core.noalert", {}, max_attempts=3)

    # 第一次失败进入退避重试，不转入死信
    alert_bus.dispatch_once(db)
    assert fired == []  # 未到终态不告警

    # 跳过退避窗口继续派发直至耗尽
    alert_bus.dispatch_once(db, now=_now() + timedelta(hours=1))
    alert_bus.dispatch_once(db, now=_now() + timedelta(hours=2))
    assert len(fired) == 1
    assert fired[0]["attempts"] == 3


def test_dead_letter_alert_absent_callback_no_crash(db) -> None:
    """S2: 未注册回调时转入死信不抛异常（默认行为兼容）。"""
    plain_bus = EventBus()

    def boom(ctx) -> None:
        raise RuntimeError("x")

    registry.subscribe("core.plain", boom, subscriber="plain")
    plain_bus.publish(db, "core.plain", {}, max_attempts=1)

    result = plain_bus.dispatch_once(db)
    assert result.dead == 1  # 正常进入死信，无回调不报错
