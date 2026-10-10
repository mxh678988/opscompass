"""OS 内核 · 工作流引擎（M5）测试。

覆盖：
- DSL 校验：节点类型、id 唯一、next 引用、parallel/retry/wait 配置
- create_instance：物化步骤序列（parallel 展平、retry target 解析）
- run：线性 task 推进到 completed，handler 结果合并上下文
- branch：条件分支选择 + 跳过中间步骤
- parallel：分支展平执行
- retry：失败重试至成功 / 超限失败
- wait 人工节点：run 停 waiting、confirm 继续、timeout 兜底、批量扫描超时
- 失败补偿：register_compensate 后补偿并标记
- 未注册 handler / 未知节点类型：实例 failed
- 幂等：重复 run / 重复推进不产生重复副作用
- 生命周期：pause / resume / cancel
- 待办查询与进度统计

无外部依赖，直接执行：``pytest tests/test_workflow.py -v``。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.workflow import dsl
from app.core.workflow.engine import (
    WorkflowError,
    cancel_instance,
    confirm_wait_step,
    create_instance,
    get_instance,
    list_waiting_steps,
    pause_instance,
    register_compensate,
    resume_instance,
    run,
    scan_waiting_timeouts,
    step_status_counts,
    timeout_wait_step,
)
from app.core.workflow.dsl import WorkflowDSLError, parse_definition, validate_definition
from app.models.base import Base
from app.models.workflow import CoreWorkflowInstance, CoreWorkflowStep

WORKFLOW_TABLES = [
    CoreWorkflowInstance.__table__,
    CoreWorkflowStep.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建工作流所需表）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=WORKFLOW_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


LINEAR_DEF = {
    "key": "linear_demo",
    "name": "线性示例",
    "nodes": [
        {"id": "collect", "type": "task", "name": "采集", "handler": "collect_data", "next": "label"},
        {"id": "label", "type": "task", "name": "打标", "handler": "label_data", "next": "stats"},
        {"id": "stats", "type": "task", "name": "统计", "handler": "stats_data"},
    ],
}

BRANCH_DEF = {
    "key": "branch_demo",
    "name": "分支示例",
    "nodes": [
        {
            "id": "check",
            "type": "branch",
            "name": "状态检查",
            "conditions": [
                {"name": "ok", "next": "approve", "match": [{"path": "status", "op": "eq", "value": "ok"}]},
                {"name": "retry", "next": "fix", "match": [{"path": "status", "op": "eq", "value": "bad"}]},
            ],
            "default_next": "fix",
        },
        {"id": "approve", "type": "task", "name": "通过", "handler": "approve_data"},
        {"id": "fix", "type": "task", "name": "修复", "handler": "fix_data", "next": "approve"},
    ],
}

PARALLEL_DEF = {
    "key": "parallel_demo",
    "name": "并行示例",
    "nodes": [
        {
            "id": "fanout",
            "type": "parallel",
            "name": "并行分发",
            "branches": [
                {"steps": [{"id": "a1", "type": "task", "name": "A1", "handler": "h_a1"}]},
                {"steps": [{"id": "b1", "type": "task", "name": "B1", "handler": "h_b1"}]},
            ],
            "next": "merge",
        },
        {"id": "merge", "type": "task", "name": "汇总", "handler": "h_merge"},
    ],
}

WAIT_DEF = {
    "key": "wait_demo",
    "name": "人工审批示例",
    "nodes": [
        {"id": "prepare", "type": "task", "name": "准备", "handler": "h_prepare", "next": "review"},
        {
            "id": "review",
            "type": "wait",
            "name": "人工确认",
            "wait_key": "review:report",
            "assigned_to": 42,
            "confirm": "publish",
            "timeout_next": "publish",
            "timeout_minutes": 10,
        },
        {"id": "publish", "type": "task", "name": "发布", "handler": "h_publish"},
    ],
}

RETRY_DEF = {
    "key": "retry_demo",
    "name": "重试示例",
    "nodes": [
        {
            "id": "upload",
            "type": "retry",
            "name": "上传（重试3次）",
            "handler": "h_flaky",
            "max_attempts": 3,
            "next": "notify",
        },
        {"id": "notify", "type": "task", "name": "通知", "handler": "h_notify"},
    ],
}


def _handler_registry(**kwargs):
    """构造按名注册的 handler 表；kwargs 值为可调用（ctx, step）。"""
    return {name: fn for name, fn in kwargs.items()}


def _ctx_add(key, value):
    def fn(ctx, step):
        ctx[key] = value
        return {key: value}

    return fn


# ============================================================ DSL 校验


class TestDSL:
    def test_validate_ok(self):
        validate_definition(LINEAR_DEF)

    def test_parse_json(self):
        import json

        parsed = parse_definition(json.dumps(LINEAR_DEF))
        assert parsed["key"] == "linear_demo"

    def test_missing_key(self):
        with pytest.raises(WorkflowDSLError):
            validate_definition({"nodes": []})

    def test_dup_node_id(self):
        bad = {
            "key": "x",
            "nodes": [
                {"id": "a", "type": "task", "handler": "h"},
                {"id": "a", "type": "task", "handler": "h2"},
            ],
        }
        with pytest.raises(WorkflowDSLError):
            validate_definition(bad)

    def test_bad_next_ref(self):
        bad = {
            "key": "x",
            "nodes": [{"id": "a", "type": "task", "handler": "h", "next": "ghost"}],
        }
        with pytest.raises(WorkflowDSLError):
            validate_definition(bad)

    def test_task_requires_handler(self):
        bad = {"key": "x", "nodes": [{"id": "a", "type": "task"}]}
        with pytest.raises(WorkflowDSLError):
            validate_definition(bad)

    def test_wait_requires_target(self):
        bad = {"key": "x", "nodes": [{"id": "a", "type": "wait"}]}
        with pytest.raises(WorkflowDSLError):
            validate_definition(bad)

    def test_retry_requires_max_attempts(self):
        bad = {"key": "x", "nodes": [{"id": "a", "type": "retry", "handler": "h"}]}
        with pytest.raises(WorkflowDSLError):
            validate_definition(bad)

    def test_find_node(self):
        assert dsl.find_node(LINEAR_DEF, "stats")["id"] == "stats"
        assert dsl.find_node(LINEAR_DEF, "ghost") is None


# ============================================================ 创建与线性推进


class TestCreateAndLinear:
    def test_create_instance_materializes(self, db):
        inst = create_instance(db, LINEAR_DEF, context={"src": "x"})
        assert inst.def_key == "linear_demo"
        assert inst.status == "created"
        steps = db.execute(
            select(CoreWorkflowStep).where(CoreWorkflowStep.instance_id == inst.id)
        ).scalars()
        seqs = [s.seq for s in steps]
        assert seqs == [0, 1, 2]

    def test_run_linear_completes(self, db):
        inst = create_instance(db, LINEAR_DEF, context={"src": "x"})
        handlers = _handler_registry(
            collect_data=_ctx_add("n", 3),
            label_data=_ctx_add("label", "ok"),
            stats_data=_ctx_add("total", 3),
        )
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "completed"
        assert result.context["n"] == 3
        assert result.context["label"] == "ok"
        assert result.context["total"] == 3
        counts = step_status_counts(db, inst.id)
        assert counts["completed"] == 3

    def test_run_idempotent(self, db):
        """重复 run 不会产生重复副作用（handler 调用计数）。"""
        calls = {"n": 0}

        def counting(ctx, step):
            calls["n"] += 1
            return {"c": calls["n"]}

        inst = create_instance(db, LINEAR_DEF)
        handlers = _handler_registry(collect_data=counting, label_data=counting, stats_data=counting)
        run(db, inst.id, handlers=handlers)
        run(db, inst.id, handlers=handlers)  # 已 completed 应直接返回
        assert calls["n"] == 3

    def test_missing_handler_fails(self, db):
        inst = create_instance(db, LINEAR_DEF)
        result = run(db, inst.id, handlers={})
        assert result.status == "failed"
        assert "未注册 handler" in (result.error or "")
        counts = step_status_counts(db, inst.id)
        assert counts["failed"] == 1

    def test_handler_exception_fails(self, db):
        def boom(ctx, step):
            raise RuntimeError("engine boom")

        inst = create_instance(db, LINEAR_DEF)
        handlers = _handler_registry(collect_data=boom)
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "failed"
        assert "engine boom" in (result.error or "")
        step = db.execute(
            select(CoreWorkflowStep).where(
                CoreWorkflowStep.instance_id == inst.id,
                CoreWorkflowStep.seq == 0,
            )
        ).scalar_one()
        assert step.status == "failed"
        assert step.payload and step.payload.get("manual_intervention") is True


# ============================================================ 分支


class TestBranch:
    def test_choose_ok_skip_fix(self, db):
        inst = create_instance(db, BRANCH_DEF, context={"status": "ok"})
        handlers = _handler_registry(
            approve_data=_ctx_add("approved", True),
            fix_data=_ctx_add("fixed", True),
        )
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "completed"
        counts = step_status_counts(db, inst.id)
        assert counts["completed"] == 2  # check + approve
        assert counts["skipped"] == 1  # fix 被跳过

    def test_choose_bad_take_fix(self, db):
        inst = create_instance(db, BRANCH_DEF, context={"status": "bad"})
        handlers = _handler_registry(
            approve_data=_ctx_add("approved", True),
            fix_data=_ctx_add("fixed", True),
        )
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "completed"
        counts = step_status_counts(db, inst.id)
        assert counts["completed"] == 3

    def test_default_next_when_no_match(self, db):
        inst = create_instance(db, BRANCH_DEF, context={"status": "unknown"})
        handlers = _handler_registry(
            approve_data=_ctx_add("approved", True),
            fix_data=_ctx_add("fixed", True),
        )
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "completed"
        counts = step_status_counts(db, inst.id)
        assert counts["completed"] == 3  # check -> default fix -> approve


# ============================================================ 并行


class TestParallel:
    def test_parallel_branches_execute(self, db):
        inst = create_instance(db, PARALLEL_DEF, context={"v": 0})
        handlers = _handler_registry(
            h_a1=_ctx_add("a", 1),
            h_b1=_ctx_add("b", 2),
            h_merge=_ctx_add("merged", True),
        )
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "completed"
        assert result.context["a"] == 1
        assert result.context["b"] == 2
        assert result.context["merged"] is True
        counts = step_status_counts(db, inst.id)
        assert counts["completed"] == 4  # parallel 容器 + a1 + b1 + merge

    def test_parallel_child_failure(self, db):
        def boom(ctx, step):
            raise RuntimeError("branch boom")

        inst = create_instance(db, PARALLEL_DEF)
        handlers = _handler_registry(
            h_a1=_ctx_add("a", 1),
            h_b1=boom,
            h_merge=_ctx_add("merged", True),
        )
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "failed"


# ============================================================ 重试


class TestRetry:
    def test_retry_succeeds(self, db):
        attempts = {"n": 0}

        def flaky(ctx, step):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RuntimeError("transient")
            return {"uploaded": True}

        inst = create_instance(db, RETRY_DEF)
        handlers = _handler_registry(h_flaky=flaky, h_notify=_ctx_add("notified", True))
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "completed"
        assert attempts["n"] == 3
        assert result.context["uploaded"] is True
        step = db.execute(
            select(CoreWorkflowStep).where(
                CoreWorkflowStep.instance_id == inst.id,
                CoreWorkflowStep.seq == 0,
            )
        ).scalar_one()
        assert step.payload["attempts"] == 3

    def test_retry_exhausted_fails(self, db):
        def always_fail(ctx, step):
            raise RuntimeError("permanent")

        inst = create_instance(db, RETRY_DEF)
        handlers = _handler_registry(h_flaky=always_fail, h_notify=_ctx_add("n", 1))
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "failed"
        counts = step_status_counts(db, inst.id)
        assert counts["failed"] == 1
        assert counts["skipped"] == 1  # notify 未执行


# ============================================================ 人工节点


class TestWait:
    def test_run_stops_at_wait(self, db):
        inst = create_instance(db, WAIT_DEF)
        handlers = _handler_registry(
            h_prepare=_ctx_add("ready", True),
            h_publish=_ctx_add("published", True),
        )
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "waiting"
        counts = step_status_counts(db, inst.id)
        assert counts["waiting"] == 1

    def test_confirm_continues(self, db):
        inst = create_instance(db, WAIT_DEF)
        handlers = _handler_registry(
            h_prepare=_ctx_add("ready", True),
            h_publish=_ctx_add("published", True),
        )
        run(db, inst.id, handlers=handlers)
        result = confirm_wait_step(db, inst.id, 1, actor_id=7, payload={"ok": True}, handlers=handlers)
        assert result.status == "completed"
        step = db.execute(
            select(CoreWorkflowStep).where(
                CoreWorkflowStep.instance_id == inst.id,
                CoreWorkflowStep.seq == 1,
            )
        ).scalar_one()
        assert step.payload["confirmed"] is True
        assert step.payload["confirmed_by"] == 7

    def test_timeout_continues(self, db):
        inst = create_instance(db, WAIT_DEF)
        handlers = _handler_registry(
            h_prepare=_ctx_add("ready", True),
            h_publish=_ctx_add("published", True),
        )
        run(db, inst.id, handlers=handlers)
        result = timeout_wait_step(db, inst.id, 1, handlers=handlers)
        assert result.status == "completed"
        step = db.execute(
            select(CoreWorkflowStep).where(
                CoreWorkflowStep.instance_id == inst.id,
                CoreWorkflowStep.seq == 1,
            )
        ).scalar_one()
        assert step.payload["timeout"] is True

    def test_scan_timeouts(self, db):
        inst = create_instance(db, WAIT_DEF)
        handlers = _handler_registry(h_prepare=_ctx_add("r", True), h_publish=_ctx_add("p", True))
        run(db, inst.id, handlers=handlers)
        # 伪造过去超时点
        step = db.execute(
            select(CoreWorkflowStep).where(
                CoreWorkflowStep.instance_id == inst.id,
                CoreWorkflowStep.seq == 1,
            )
        ).scalar_one()
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        step.payload = {**step.payload, "timeout_at": past}
        db.commit()
        handled = scan_waiting_timeouts(db, handlers=handlers)
        assert handled == 1
        inst = get_instance(db, inst.id)
        assert inst.status == "completed"

    def test_confirm_bad_seq(self, db):
        inst = create_instance(db, WAIT_DEF)
        run(db, inst.id, handlers=_handler_registry(h_prepare=_ctx_add("r", True), h_publish=_ctx_add("p", True)))
        with pytest.raises(WorkflowError):
            confirm_wait_step(db, inst.id, 2)  # publish 已 pending 非 waiting

    def test_list_waiting(self, db):
        inst = create_instance(db, WAIT_DEF)
        run(db, inst.id, handlers=_handler_registry(h_prepare=_ctx_add("r", True), h_publish=_ctx_add("p", True)))
        steps = list_waiting_steps(db, assigned_to=42)
        assert len(steps) == 1
        assert steps[0].payload["wait_key"] == "review:report"
        assert list_waiting_steps(db, wait_key="other") == []


# ============================================================ 补偿


class TestCompensate:
    def test_compensate_marks(self, db):
        compensated = {"n": 0}

        def boom(ctx, step):
            raise RuntimeError("boom")

        def undo(ctx, step):
            compensated["n"] += 1

        register_compensate("undo_collect", undo)
        bad_def = {
            "key": "comp_demo",
            "nodes": [
                {"id": "collect", "type": "task", "name": "采集", "handler": "collect", "compensate": "undo_collect", "next": "stats"},
                {"id": "stats", "type": "task", "name": "统计", "handler": "stats"},
            ],
        }
        inst = create_instance(db, bad_def)
        handlers = _handler_registry(collect=boom, stats=_ctx_add("s", 1))
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "failed"
        assert compensated["n"] == 1
        step = db.execute(
            select(CoreWorkflowStep).where(
                CoreWorkflowStep.instance_id == inst.id,
                CoreWorkflowStep.seq == 0,
            )
        ).scalar_one()
        assert step.payload["compensated"] is True


# ============================================================ 生命周期


class TestLifecycle:
    def test_pause_resume(self, db):
        inst = create_instance(db, LINEAR_DEF)
        handlers = _handler_registry(
            collect_data=_ctx_add("n", 1),
            label_data=_ctx_add("l", 2),
            stats_data=_ctx_add("t", 3),
        )
        paused = pause_instance(db, inst.id, reason="pause for review")
        assert paused.status == "paused"
        result = resume_instance(db, inst.id, handlers=handlers)
        # resume 后重新 run
        result = run(db, inst.id, handlers=handlers)
        assert result.status == "completed"

    def test_cancel(self, db):
        inst = create_instance(db, WAIT_DEF)
        run(db, inst.id, handlers=_handler_registry(h_prepare=_ctx_add("r", True), h_publish=_ctx_add("p", True)))
        result = cancel_instance(db, inst.id, reason="manual")
        assert result.status == "cancelled"
        counts = step_status_counts(db, inst.id)
        assert counts["skipped"] == 1  # publish 被跳过


class TestProgress:
    def test_status_counts_empty(self, db):
        inst = create_instance(db, LINEAR_DEF)
        counts = step_status_counts(db, inst.id)
        assert counts["pending"] == 3
