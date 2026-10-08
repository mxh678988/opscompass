"""事件总线核心：发布、派发、重试、死信、重放与积压观测。

这是 OS 内核的第一项能力，也是其余内核能力的前置依赖：
工作流引擎、任务 SLA、模型路由的异步动作全部经此投递。

投递语义：至少一次（at-least-once）。消费方以 ``ctx.event_id`` 去重。

用法:：

    from app.core.bus import bus, subscribe

    @subscribe("metric.value.written", subscriber="sla")
    def on_metric(ctx): ...

    bus.publish(db, "metric.value.written", {"metric_id": 1}, tenant_id=1)

派发由后台工作者周期性调用 ``bus.dispatch_once(db, worker_id=...)`` 完成；
单实例默认 8 个消费协程（见 ``DEFAULT_CONCURRENCY``）。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.bus import registry
from app.models.kernel import CoreEvent, CoreEventCursor, CoreEventDead

logger = logging.getLogger(__name__)

# 单实例默认消费并发度
DEFAULT_CONCURRENCY = 8
# 退避基数与上限（秒）
BACKOFF_BASE_SECONDS = 5
BACKOFF_MAX_SECONDS = 300
# 领取租约时长：超时未完结的事件视为工作者崩溃，可被重新领取
DEFAULT_LEASE_SECONDS = 300


@dataclass
class EventContext:
    """投递给订阅方的上下文。"""

    event_id: str
    event_name: str
    payload: dict
    trace_id: Optional[str]
    tenant_id: Optional[int]
    occurred_at: Optional[datetime]
    attempts: int
    subscriber: str
    db: Session = field(repr=False)

    def payload_get(self, key: str, default: Any = None) -> Any:
        """便捷读取载荷字段。"""
        return (self.payload or {}).get(key, default)


@dataclass
class DispatchResult:
    """一次派发批次的统计结果。"""

    scanned: int = 0
    delivered: int = 0
    retried: int = 0
    dead: int = 0
    skipped: int = 0

    def as_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "delivered": self.delivered,
            "retried": self.retried,
            "dead": self.dead,
            "skipped": self.skipped,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """统一时间为 UTC aware。

    PostgreSQL ``timestamptz`` 读回即带时区；SQLite 不保存时区信息，
    读回为 naive，此处按 UTC 解释，保证跨方言行为一致。
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _backoff_seconds(attempts: int) -> int:
    """指数退避：5s, 10s, 20s, 40s ... 上限 300s。"""
    return min(BACKOFF_BASE_SECONDS * (2 ** max(attempts - 1, 0)), BACKOFF_MAX_SECONDS)


class EventBus:
    """持久化事件总线。"""

    # ---- 发布 ----------------------------------------------------------

    def publish(
        self,
        db: Session,
        event_name: str,
        payload: Optional[dict] = None,
        *,
        tenant_id: Optional[int] = None,
        partition_key: Optional[str] = None,
        trace_id: Optional[str] = None,
        delay_seconds: int = 0,
        max_attempts: int = 5,
        event_id: Optional[str] = None,
        commit: bool = True,
        occurred_at: Optional[datetime] = None,
    ) -> str:
        """发布一个事件，返回事件 ID。

        :param db: 数据库会话；与业务写入同事务时传 ``commit=False``，
            由调用方在业务事务提交时一并落库，避免「事件已发、业务回滚」。
        :param delay_seconds: 延迟投递秒数（定时/延时事件）
        :param event_id: 外部指定事件 ID（重放场景保持原 ID 以复用幂等语义）
        """
        if not event_name:
            raise ValueError("event_name 不能为空")
        now = _now()
        ev = CoreEvent(
            event_id=event_id or uuid.uuid4().hex,
            event_name=event_name,
            payload=payload or {},
            trace_id=trace_id,
            tenant_id=tenant_id,
            partition_key=partition_key,
            status="pending",
            attempts=0,
            max_attempts=max_attempts,
            available_at=now + timedelta(seconds=max(delay_seconds, 0)),
            occurred_at=occurred_at or now,
        )
        db.add(ev)
        if commit:
            db.commit()
        else:
            db.flush()
        logger.debug("事件已发布：%s (%s)", event_name, ev.event_id)
        return ev.event_id

    # ---- 派发 ----------------------------------------------------------

    def dispatch_once(
        self,
        db: Session,
        *,
        worker_id: str = "default",
        limit: int = 20,
        now: Optional[datetime] = None,
        reclaim_expired: bool = True,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> DispatchResult:
        """扫描并投递一批待处理事件（供后台工作者周期调用）。"""
        now = now or _now()
        result = DispatchResult()

        if reclaim_expired:
            self.requeue_expired(db, lease_seconds=lease_seconds, now=now)

        stmt = (
            select(CoreEvent)
            .where(CoreEvent.status == "pending", CoreEvent.available_at <= now)
            .order_by(CoreEvent.id)
            .limit(limit)
        )
        # 多实例部署时用行锁跳过被其它工作者领取的行；SQLite 不支持 SKIP LOCKED
        if db.get_bind().dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        events = list(db.execute(stmt).scalars().all())
        result.scanned = len(events)

        for ev in events:
            self._deliver_one(db, ev, worker_id=worker_id, now=now, result=result)

        return result

    def _deliver_one(
        self,
        db: Session,
        ev: CoreEvent,
        *,
        worker_id: str,
        now: datetime,
        result: DispatchResult,
    ) -> None:
        subs = registry.match(ev.event_name)
        if not subs:
            # 无人订阅：直接完结，避免无谓积压（订阅方上线后可回放补数）
            ev.status = "done"
            ev.finished_at = now
            db.commit()
            result.skipped += 1
            return

        ev.status = "processing"
        ev.locked_by = worker_id
        ev.locked_at = now
        db.commit()

        errors: list[str] = []
        for sub in subs:
            ctx = EventContext(
                event_id=ev.event_id,
                event_name=ev.event_name,
                payload=ev.payload or {},
                trace_id=ev.trace_id,
                tenant_id=ev.tenant_id,
                occurred_at=ev.occurred_at,
                attempts=ev.attempts + 1,
                subscriber=sub.subscriber,
                db=db,
            )
            try:
                sub.handler(ctx)
            except Exception as exc:  # noqa: BLE001 —— 单个订阅失败不影响其它订阅
                errors.append(f"{sub.subscriber}: {exc}")
                logger.warning(
                    "事件投递失败：%s -> %s (%s)", ev.event_name, sub.subscriber, exc
                )

        ev.attempts += 1
        if errors:
            ev.last_error = "; ".join(errors)[:2000]
            if ev.attempts >= ev.max_attempts:
                self._to_dead(db, ev, now=now)
                result.dead += 1
            else:
                ev.status = "pending"
                ev.available_at = now + timedelta(seconds=_backoff_seconds(ev.attempts))
                ev.locked_by = None
                ev.locked_at = None
                result.retried += 1
        else:
            ev.status = "done"
            ev.finished_at = now
            ev.locked_by = None
            ev.locked_at = None
            result.delivered += 1
        db.commit()

    def _to_dead(self, db: Session, ev: CoreEvent, *, now: datetime) -> None:
        """把事件转入死信表并从队列移除。"""
        db.add(
            CoreEventDead(
                event_id=ev.event_id,
                event_name=ev.event_name,
                payload=ev.payload or {},
                trace_id=ev.trace_id,
                tenant_id=ev.tenant_id,
                attempts=ev.attempts,
                last_error=ev.last_error,
                failed_at=now,
            )
        )
        db.delete(ev)
        logger.error("事件转入死信：%s (%s)", ev.event_name, ev.event_id)

    def requeue_expired(
        self, db: Session, *, lease_seconds: int = DEFAULT_LEASE_SECONDS, now: Optional[datetime] = None
    ) -> int:
        """回收租约超时的 processing 事件（工作者崩溃恢复）。"""
        now = now or _now()
        deadline = now - timedelta(seconds=lease_seconds)
        stmt = (
            update(CoreEvent)
            .where(
                CoreEvent.status == "processing",
                CoreEvent.locked_at.is_not(None),
                CoreEvent.locked_at < deadline,
            )
            .values(status="pending", locked_by=None, locked_at=None, available_at=now)
        )
        # 具备 RETURNING 的方言可拿到行数；否则以 rowcount 兜底
        res = db.execute(stmt)
        db.commit()
        count = res.rowcount or 0
        if count:
            logger.warning("回收超时租约事件 %d 条", count)
        return count

    # ---- 死信与维护 ----------------------------------------------------

    def replay_dead(
        self,
        db: Session,
        *,
        event_ids: Optional[Sequence[str]] = None,
        limit: int = 100,
        now: Optional[datetime] = None,
    ) -> int:
        """重放死信：搬回队列头（保持原 ``event_id``，消费方幂等语义不变）。"""
        now = now or _now()
        stmt = select(CoreEventDead).where(CoreEventDead.replayed.is_(False)).order_by(
            CoreEventDead.id
        )
        if event_ids:
            stmt = stmt.where(CoreEventDead.event_id.in_(list(event_ids)))
        stmt = stmt.limit(limit)

        rows = list(db.execute(stmt).scalars().all())
        for row in rows:
            db.add(
                CoreEvent(
                    event_id=row.event_id,
                    event_name=row.event_name,
                    payload=row.payload or {},
                    trace_id=row.trace_id,
                    tenant_id=row.tenant_id,
                    status="pending",
                    attempts=0,
                    max_attempts=5,
                    available_at=now,
                    occurred_at=now,
                )
            )
            row.replayed = True
            row.replayed_at = now
        db.commit()
        if rows:
            logger.info("死信重放 %d 条", len(rows))
        return len(rows)

    def prune_done(self, db: Session, *, keep_days: int = 7, now: Optional[datetime] = None) -> int:
        """清理已完结事件，保留热区（默认 7 天）。"""
        now = now or _now()
        deadline = now - timedelta(days=keep_days)
        res = db.execute(
            delete(CoreEvent).where(CoreEvent.status == "done", CoreEvent.finished_at < deadline)
        )
        db.commit()
        return res.rowcount or 0

    def stats(self, db: Session) -> dict:
        """积压与死信概览，供内核状态页与运维告警使用。"""
        pending = db.execute(
            select(func.count()).select_from(CoreEvent).where(CoreEvent.status == "pending")
        ).scalar_one()
        processing = db.execute(
            select(func.count()).select_from(CoreEvent).where(CoreEvent.status == "processing")
        ).scalar_one()
        dead = db.execute(select(func.count()).select_from(CoreEventDead)).scalar_one()
        oldest = db.execute(
            select(func.min(CoreEvent.occurred_at)).where(CoreEvent.status == "pending")
        ).scalar_one()
        return {
            "pending": pending,
            "processing": processing,
            "dead": dead,
            "oldest_pending_at": (
                _as_utc(oldest).isoformat() if oldest else None
            ),
            "subscriptions": registry.registered_names(),
        }

    def advance_cursor(
        self, db: Session, *, subscriber: str, event_name: str, event_id: int, commit: bool = True
    ) -> None:
        """记录订阅位点（补数与积压观测用）。"""
        row = db.execute(
            select(CoreEventCursor).where(CoreEventCursor.subscriber == subscriber)
        ).scalar_one_or_none()
        if row is None:
            db.add(
                CoreEventCursor(
                    subscriber=subscriber, event_name=event_name, last_event_id=event_id
                )
            )
        elif event_id > row.last_event_id:
            row.last_event_id = event_id
        if commit:
            db.commit()


# 进程内单例：内核各模块统一通过该实例发布事件
bus = EventBus()

# 便捷导出：订阅声明
subscribe = registry.subscribe
unsubscribe = registry.unsubscribe
disable_plugin_subscriptions = registry.disable_plugin
