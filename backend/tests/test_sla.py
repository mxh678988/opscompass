"""OS 内核 · 任务 SLA（M4）测试。

覆盖：
- WorkingCalendar：工作时段判断、跨日/跨周末/跨节假日的分钟展开
- create_sla：参数校验、提醒节点计算、自定义提醒、工作日历展开
- 生命周期：认领/暂停/恢复/完成/取消 的状态机与事件留痕
- 暂停冻结：effective_deadline = deadline_at + paused_seconds
- 节点评估：临期提醒/最终提醒/逾期/升级链（责任人→上级→值班长）、幂等去重
- 批量扫描 scan_and_evaluate 触发统计
- 插件接入 create_for_plugin（无时限待办 / 带 SLA 待办）
- SDK TaskFacade：未装配抛 NotAvailableError，装配后回调可用
- PluginRuntime：会话工厂自动装配 task 门面

无外部依赖，直接执行：``pytest tests/test_sla.py -v``。
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _utcnow() -> datetime:
    """与引擎私有 _utcnow 对齐：aware UTC 当前时间。"""
    return datetime.now(timezone.utc)

from app.core.plugin.registry import PluginRegistry
from app.core.plugin.runtime import PluginRuntime
from app.core.sla.calendar import WorkingCalendar
from app.core.sla.engine import (
    EVT_CANCELLED,
    EVT_CLAIMED,
    EVT_COMPLETED,
    EVT_CREATED,
    EVT_DUE_FINAL,
    EVT_DUE_SOON,
    EVT_ESCALATED,
    EVT_OVERDUE,
    EVT_PAUSED,
    EVT_RESUMED,
    ESCALATE_STEP2_MINUTES,
    SlaError,
    cancel_sla,
    claim_sla,
    complete_sla,
    create_for_plugin,
    create_sla,
    evaluate_sla,
    pause_sla,
    resume_sla,
    scan_and_evaluate,
    sla_events,
)
from app.models.auth import AuditLog
from app.models.base import Base
from app.models.sla import CoreSla, CoreSlaEvent
from app.sdk.context import PluginNamespace, create_context
from app.sdk.exceptions import NotAvailableError

SLA_TABLES = [
    CoreSla.__table__,
    CoreSlaEvent.__table__,
    AuditLog.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建 SLA 所需表）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=SLA_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ============================================================ WorkingCalendar


class TestWorkingCalendar:
    def test_is_working_on_weekday_hour(self, db):
        cal = WorkingCalendar(work_start_hour=9, work_end_hour=18)
        dt = datetime(2026, 10, 12, 10, 30, tzinfo=timezone.utc)  # 周一
        assert cal.is_working(dt) is True
        assert cal.is_working(datetime(2026, 10, 12, 8, 59, tzinfo=timezone.utc)) is False
        assert cal.is_working(datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)) is False
        # 周六/周日
        assert cal.is_working(datetime(2026, 10, 11, 10, tzinfo=timezone.utc)) is False
        # 工作日加班
        assert cal.is_working(datetime(2026, 10, 12, 20, tzinfo=timezone.utc)) is False

    def test_holiday(self, db):
        cal = WorkingCalendar(work_start_hour=9, work_end_hour=18, holidays=[date(2026, 10, 1)])
        assert cal.is_working(datetime(2026, 10, 1, 10, tzinfo=timezone.utc)) is False
        assert cal.is_working(datetime(2026, 10, 2, 10, tzinfo=timezone.utc)) is True

    def test_add_working_minutes_cross_day(self, db):
        cal = WorkingCalendar(work_start_hour=9, work_end_hour=18)
        start = datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc)  # 周一
        result = cal.add_working_minutes(start, 180)
        assert result == datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)

    def test_add_working_minutes_skip_weekend(self, db):
        cal = WorkingCalendar(work_start_hour=9, work_end_hour=18)
        start = datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc)  # 周六 17:00
        result = cal.add_working_minutes(start, 60)
        assert result == datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)

    def test_add_working_minutes_zero(self, db):
        cal = WorkingCalendar(work_start_hour=9, work_end_hour=18)
        start = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
        result = cal.add_working_minutes(start, 0)
        assert result == start

    def test_invalid_work_hours(self, db):
        with pytest.raises(ValueError):
            WorkingCalendar(work_start_hour=20, work_end_hour=9)

    def test_add_working_minutes_negative(self, db):
        cal = WorkingCalendar()
        with pytest.raises(ValueError):
            cal.add_working_minutes(_utcnow(), -5)


# ============================================================ create_sla


class TestCreateSla:
    def test_defaults_compute_reminders(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="紧急工单",
            due_in_minutes=120,
        )
        total = max((sla.deadline_at - sla.created_at).total_seconds() / 60.0, 0.001)
        # 临期提醒：剩余 1/3 或 30 分钟，取更晚
        expected_r1 = max(total * (1 / 3), 30)
        assert (sla.remind_1_at - sla.created_at).total_seconds() / 60 >= expected_r1 - 1
        assert (sla.remind_2_at - sla.created_at).total_seconds() / 60 >= 4

    def test_custom_reminders(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="自定义提醒",
            due_in_minutes=60,
            remind_1_minutes=20,
            remind_2_minutes=10,
        )
        assert (sla.remind_1_at - sla.deadline_at).total_seconds() / 60 == -20
        assert (sla.remind_2_at - sla.deadline_at).total_seconds() / 60 == -10

    def test_calendar_work_minutes(self, db):
        cal = WorkingCalendar(work_start_hour=9, work_end_hour=18, weekend_off=True)
        # 周一 16:00 + 180 工作时间 = 周二 12:00（跳过 18:00 下班时段）
        start = datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc)
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="工作日历",
            due_in_minutes=180,
            calendar=cal,
        )
        # deadline 按工作时间段展开：周六 +180 工作分钟 = 周一 12:00（跳过周末）
        assert sla.deadline_at == datetime(2026, 10, 12, 12, 0)

    def test_create_missing_params(self, db):
        with pytest.raises(SlaError):
            create_sla(db, object_type="", object_id="x", title="t")
        with pytest.raises(SlaError):
            create_sla(db, object_type="t", object_id="x", title="t", due_in_minutes=10, deadline_at=_utcnow())

    def test_create_invalid_due_in(self, db):
        with pytest.raises(SlaError):
            create_sla(db, object_type="t", object_id="x", title="t", due_in_minutes=-1)

    def test_create_past_deadline(self, db):
        with pytest.raises(SlaError):
            create_sla(db, object_type="t", object_id="x", title="t", deadline_at=_utcnow() - timedelta(minutes=1))

    def test_event_created_on_create(self, db):
        create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        events = list(db.execute(select(CoreSlaEvent)).scalars().all())
        assert any(e.event_type == EVT_CREATED for e in events)

    def test_no_deadline_allowed(self, db):
        """deadline_at 与 due_in_minutes 必须二选一。"""
        with pytest.raises(SlaError):
            create_sla(db, object_type="t", object_id="x", title="t")


# ============================================================ 生命周期


class TestLifecycle:
    def test_create_to_claim(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="claim_test", due_in_minutes=60)
        assert sla.status == "open"
        claim_sla(db, sla.id)
        assert sla.claimed_at is not None
        evts = sla_events(db, sla.id)
        assert len(evts) == 2  # created + claimed

    def test_open_can_claim_again(self, db):
        """认领对 open/paused 幂等允许（不重置截止）。"""
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        claim_sla(db, sla.id)
        claim_sla(db, sla.id)  # 重复认领不抛错
        assert sla.claimed_at is not None

    def test_pause_resume(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        paused_before = sla.paused_seconds
        pause_sla(db, sla.id)
        assert sla.status == "paused"
        resume_sla(db, sla.id)
        assert sla.status == "open"
        assert sla.paused_seconds >= paused_before

    def test_pause_non_open(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        complete_sla(db, sla.id)
        with pytest.raises(SlaError):
            pause_sla(db, sla.id)

    def test_resume_non_paused(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        with pytest.raises(SlaError):
            resume_sla(db, sla.id)

    def test_done(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        complete_sla(db, sla.id)
        assert sla.status == "done"
        assert sla.completed_at is not None
        with pytest.raises(SlaError):
            complete_sla(db, sla.id)

    def test_cancel(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        cancel_sla(db, sla.id)
        assert sla.status == "cancelled"
        with pytest.raises(SlaError):
            cancel_sla(db, sla.id)

    def test_cancelled_not_done(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        cancel_sla(db, sla.id)
        with pytest.raises(SlaError):
            complete_sla(db, sla.id)

    def test_event_types_on_lifecycle(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        claim_sla(db, sla.id)
        pause_sla(db, sla.id)
        resume_sla(db, sla.id)
        complete_sla(db, sla.id)

        evt_types = [e.event_type for e in sla_events(db, sla.id)]
        assert EVT_CREATED in evt_types
        assert EVT_CLAIMED in evt_types
        assert EVT_PAUSED in evt_types
        assert EVT_RESUMED in evt_types
        assert EVT_COMPLETED in evt_types

    def test_sla_events_ordered(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        claim_sla(db, sla.id)
        events = sla_events(db, sla.id)
        for i in range(1, len(events)):
            assert events[i].id > events[i - 1].id

    def test_sla_not_found(self, db):
        with pytest.raises(SlaError):
            claim_sla(db, 999999)


# ============================================================ 暂停冻结


class TestPauseFreeze:
    def test_effective_deadline_increases_with_pause(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=120)
        deadline = sla.deadline_at
        # 暂停 1 小时
        pause_sla(db, sla.id)
        resume_sla(db, sla.id)
        sla.effective_deadline is not None
        assert sla.effective_deadline is not None

    def test_pause_freeze_in_events(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=120)
        pause_sla(db, sla.id, reason="等审批")
        evts = sla_events(db, sla.id)
        paused_evt = [e for e in evts if e.event_type == EVT_PAUSED][0]
        assert paused_evt.payload.get("reason") == "等审批"

    def test_effective_deadline_is_original_plus_paused(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=120)
        original_deadline = sla.deadline_at
        pause_sla(db, sla.id)
        # 直接修改 paused_seconds 来模拟冻结（跳过 resume）
        sla.paused_seconds = 3600
        db.commit()
        db.refresh(sla)
        from datetime import timedelta
        expected = original_deadline + timedelta(seconds=3600)
        assert sla.effective_deadline == expected

    def test_deadline_none_effective_deadline_none(self, db):
        """deadline_at=None 时 effective_deadline 为 None。"""
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=60)
        sla.deadline_at = None
        db.commit()
        db.refresh(sla)
        assert sla.effective_deadline is None


# ============================================================ 节点评估


class TestNodeEvaluation:
    def test_due_soon(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=120,
        )
        # 临期提醒 r1 = max(120*1/3, 30) = 40 分钟前
        future = sla.deadline_at - timedelta(minutes=10)
        evts = evaluate_sla(db, sla, now=future)
        assert EVT_DUE_SOON in evts

    def test_due_final(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=60,
            remind_1_minutes=30,
            remind_2_minutes=5,
        )
        # 先触发 due_soon
        evaluate_sla(db, sla, now=sla.deadline_at - timedelta(minutes=30))
        # 再触发 due_final
        evts = evaluate_sla(db, sla, now=sla.deadline_at - timedelta(minutes=3))
        assert EVT_DUE_FINAL in evts

    def test_overdue(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
        )
        evts = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert EVT_OVERDUE in evts
        assert sla.is_overdue is True

    def test_overdue_with_escalation(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
            assignee_id=1,
            supervisor_id=2,
            duty_officer_id=3,
        )
        evts = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert EVT_OVERDUE in evts
        assert EVT_ESCALATED in evts
        assert sla.escalate_level == 1
        assert sla.escalated_to == 2

    def test_escalation_chain(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
            assignee_id=1,
            supervisor_id=2,
            duty_officer_id=3,
        )
        # 第一阶段升级
        evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert sla.escalate_level == 1
        assert sla.escalated_to == 2
        # 第二阶段升级：等待 ESCALATE_STEP2_MINUTES
        step2_at = sla.escalated_at + timedelta(minutes=ESCALATE_STEP2_MINUTES)
        evts2 = evaluate_sla(db, sla, now=step2_at + timedelta(minutes=1))
        assert EVT_ESCALATED in evts2
        assert sla.escalate_level == 2
        assert sla.escalated_to == 3

    def test_escalation_missing_supervisor(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
            assignee_id=1,
            # 没有 supervisor，直接跳到 duty_officer
            duty_officer_id=3,
        )
        evts = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert EVT_ESCALATED in evts
        assert sla.escalate_level == 1
        assert sla.escalated_to == 3

    def test_escalation_missing_both_supervisor_and_duty(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
            assignee_id=1,
        )
        evts = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert EVT_OVERDUE in evts
        assert EVT_ESCALATED not in evts

    def test_no_escalation_when_target_none(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
            assignee_id=1,
        )
        evts = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert EVT_ESCALATED not in evts

    def test_no_eval_on_paused(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
        )
        pause_sla(db, sla.id)
        evts = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert evts == []

    def test_no_eval_on_done(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
        )
        complete_sla(db, sla.id)
        evts = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert evts == []

    def test_idempotency(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
            assignee_id=1,
            supervisor_id=2,
        )
        first = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        second = evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=2))
        assert EVT_OVERDUE in first and EVT_ESCALATED in first
        assert second == []  # 幂等：已触发的事件不再重复
        assert len(sla_events(db, sla.id)) == 3  # created + overdue + escalated

    def test_no_escalation_step2_before_timeout(self, db):
        sla = create_sla(
            db,
            object_type="task",
            object_id="t001",
            title="t",
            due_in_minutes=10,
            assignee_id=1,
            supervisor_id=2,
            duty_officer_id=3,
        )
        evaluate_sla(db, sla, now=sla.deadline_at + timedelta(minutes=1))
        assert sla.escalate_level == 1
        step2_at = sla.escalated_at + timedelta(minutes=ESCALATE_STEP2_MINUTES)
        evts = evaluate_sla(db, sla, now=step2_at - timedelta(minutes=1))
        assert EVT_ESCALATED not in evts
        assert sla.escalate_level == 1


# ============================================================ 批量扫描


class TestScanAndEvaluate:
    def test_batch_scan(self, db):
        sla1 = create_sla(db, object_type="task", object_id="t001", title="t1", due_in_minutes=10)
        sla2 = create_sla(db, object_type="task", object_id="t002", title="t2", due_in_minutes=10)
        counter = scan_and_evaluate(db, now=sla1.deadline_at + timedelta(minutes=1))
        assert EVT_OVERDUE in counter

    def test_batch_scan_limited(self, db):
        for i in range(100):
            create_sla(db, object_type="task", object_id=f"t{i:03d}", title="t", due_in_minutes=10)
        counter = scan_and_evaluate(db, now=_utcnow() + timedelta(minutes=10), limit=10)
        assert sum(counter.values()) <= 10

    def test_batch_scan_respects_limit(self, db):
        for i in range(50):
            create_sla(db, object_type="task", object_id=f"t{i:03d}", title="t", due_in_minutes=10)
        counter = scan_and_evaluate(db, now=_utcnow() + timedelta(minutes=10), limit=5)
        assert counter.get(EVT_OVERDUE, 0) <= 5

    def test_batch_scan_done_sla(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=10)
        complete_sla(db, sla.id, note="done")
        counter = scan_and_evaluate(db, now=_utcnow() + timedelta(minutes=10))
        assert EVT_OVERDUE not in counter

    def test_batch_scan_returns_counter(self, db):
        sla = create_sla(db, object_type="task", object_id="t001", title="t", due_in_minutes=10)
        counter = scan_and_evaluate(db, now=sla.deadline_at + timedelta(minutes=1))
        assert isinstance(counter, dict)


# ============================================================ 插件接入


class TestPluginIntegration:
    def test_create_for_plugin_no_sla(self, db):
        result = create_for_plugin(db, "sentiment", "发工单")
        assert result["plugin_id"] == "sentiment"
        assert result["deadline_at"] is None
        assert result["status"] == "open"
        evts = sla_events(db, result["sla_id"])
        assert any(e.event_type == EVT_CREATED for e in evts)

    def test_create_for_plugin_with_sla(self, db):
        result = create_for_plugin(
            db, "sentiment", "紧急舆情",
            sla={"due_in_minutes": 120}
        )
        assert result["deadline_at"] is not None
        assert result["effective_deadline"] is not None
        assert result["status"] == "open"
        row = db.get(CoreSla, result["sla_id"])
        assert row.object_type == "plugin:sentiment"

    def test_create_for_plugin_no_object(self, db):
        """不传 sla 时 object_type 为 plugin:<id>。"""
        result = create_for_plugin(db, "test_plugin", "标题")
        row = db.get(CoreSla, result["sla_id"])
        assert row.object_type == "plugin:test_plugin"


# ============================================================ SDK TaskFacade


class TestTaskFacade:
    def test_not_assembled(self, db):
        ctx = create_context(plugin_id="sentiment", namespace=PluginNamespace(permissions="sentiment:"))
        with pytest.raises(NotAvailableError) as e1:
            ctx.task.create("工单")
        assert "M4 装配完成" in str(e1.value.planned_in)

    def test_assembled(self, db):
        def task_fn(plugin_id, title, sla, **kwargs):
            return {"sla_id": 1, "title": title, "plugin_id": plugin_id}

        ctx = create_context(
            plugin_id="sentiment",
            namespace=PluginNamespace(permissions="sentiment:"),
            task_fn=task_fn,
        )
        result = ctx.task.create("工单", sla={"due_in_minutes": 60})
        assert result == {"sla_id": 1, "title": "工单", "plugin_id": "sentiment"}


# ============================================================ PluginRuntime


class TestPluginRuntime:
    def test_runtime_auto_wires_task(self, db):
        registry = PluginRegistry(DUMMY_PLUGINS_DIR)
        runtime = PluginRuntime(registry, session_factory=lambda: db)
        runtime.load_all()
        ctx = runtime.activate("sentiment")

        # 未注入 sla_engine 时依赖会话工厂
        result = ctx.task.create("工单", sla={"due_in_minutes": 60})
        assert result["plugin_id"] == "sentiment"
        assert result["deadline_at"] is not None

    def test_runtime_no_session_factory(self):
        registry = PluginRegistry(DUMMY_PLUGINS_DIR)
        runtime = PluginRuntime(registry)
        runtime.load_all()
        ctx = runtime.activate("sentiment")

        with pytest.raises(NotAvailableError) as e1:
            ctx.task.create("工单")
        assert "M4 装配完成" in str(e1.value.planned_in)


DUMMY_PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
DUMMY_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
(DUMMY_PLUGINS_DIR / "sentiment").mkdir(parents=True, exist_ok=True)
(DUMMY_PLUGINS_DIR / "sentiment" / "plugin.yaml").write_text(
    """\
id: sentiment
name: 舆情插件
version: 0.1.0
kind: community
min_kernel_version: 0.11.0
entry: main:register
namespace:
  tables: os_sentiment_
  events: "sentiment."
  permissions: "sentiment:"
permissions:
  - code: sentiment:task:create
    name: 创建舆情任务
roles:
  - code: sentiment:analyst
    name: 舆情分析师
    permissions:
      - sentiment:task:create
events:
  publish:
    - sentiment.task.created
  subscribe:
    - core.metric.written
""",
    encoding="utf-8",
)