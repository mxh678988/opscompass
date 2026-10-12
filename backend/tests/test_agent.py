"""M12 智能体编排测试。

覆盖：
- 状态机流转：pending -> analyzing -> awaiting_approval（人工确认闸门）；
  approval_required=False 自动跳过闸门直达 executing
- 确认闸门强制：仅 awaiting_approval 可 approve/reject；非闸门状态操作抛错
- 人工驳回：reject 置 rejected，终态不可再 approve
- 非法状态/参数：非法转移、非法 scenario / action_type 抛错
- 执行动作登记：仅 executing 可登记，动作回写事件总线（published=True），
  来源洞察置 confirmed
- 结果回写：complete_run 标记 result_published / result_event_id；
  终态重复操作抛错；fail_run 兜底且终态不可再失败
- 租户隔离：跨租户访问运行不可见

无外部依赖，直接执行：``pytest tests/test_agent.py -v``。
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.bus import bus
from app.models.agent import (
    AgentAction,
    AgentInsight,
    AgentRun,
)
from app.models.base import Base
from app.models.kernel import CoreEvent, CoreEventAudit
from app.schemas.agent import AgentActionIn, AgentRunIn, AgentRunPatch
from app.services.agent_service import (
    AgentServiceError,
    analyze_run,
    complete_run,
    create_run,
    fail_run,
    get_run,
    list_runs,
    patch_run,
    record_action,
)

AGENT_TABLES = [
    AgentRun.__table__,
    AgentInsight.__table__,
    AgentAction.__table__,
]
KERNEL_TABLES = [
    CoreEvent.__table__,
    CoreEventAudit.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建智能体编排与事件总线所需表，避开 JSONB）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=AGENT_TABLES + KERNEL_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_run_in(
    name: str = "流失召回-编排",
    scenario: str = "churn_recall",
    approval_required: bool = True,
) -> AgentRunIn:
    return AgentRunIn(
        name=name,
        scenario=scenario,
        datasource_bindings={"ds_1": "primary"},
        action_config={"target": "u_1"},
        approval_required=approval_required,
        created_by="tester",
    )


def seed_run(db, tenant_id: int = 1, **kwargs) -> int:
    """创建运行并返回 run_id。"""
    data = create_run(db, tenant_id, make_run_in(**kwargs))
    return data["id"]


class TestStateMachine:
    """状态机流转与确认闸门。"""

    def test_create_run_pending(self, db):
        data = create_run(db, 1, make_run_in())
        assert data["status"] == "pending"
        assert data["tenant_id"] == 1
        assert data["approval_required"] is True
        assert data["result_published"] is False

    def test_analyze_awaiting_approval(self, db):
        run_id = seed_run(db, approval_required=True)
        data = analyze_run(db, 1, run_id)
        assert data["status"] == "awaiting_approval"
        assert len(data["insights"]) == 1
        assert data["insights"][0]["status"] == "new"
        assert data["insights"][0]["suggested_action_type"] == "create_task"

    def test_auto_approve_skips_gate(self, db):
        """approval_required=False 自动跳过人工确认闸门直达 executing。"""
        run_id = seed_run(db, approval_required=False)
        data = analyze_run(db, 1, run_id)
        assert data["status"] == "executing"
        assert data["approved_by"] == "insight-agent"
        assert data["approve_note"] == "自动确认（approval_required=False）"

    def test_analyze_custom_insights(self, db):
        run_id = seed_run(db)
        data = analyze_run(
            db,
            1,
            run_id,
            insights=[
                {
                    "title": "高流失风险用户",
                    "detail": "u_1 概率 0.90",
                    "severity": "critical",
                    "suggestion": "立即召回",
                    "suggested_action_type": "notify",
                },
                {
                    "title": "中风险跟进",
                    "detail": "u_2 概率 0.80",
                    "severity": "warning",
                    "suggested_action_type": "create_segment",
                },
            ],
        )
        assert data["status"] == "awaiting_approval"
        assert len(data["insights"]) == 2
        assert [i["seq"] for i in data["insights"]] == [1, 2]
        assert data["insights"][0]["severity"] == "critical"

    def test_approve_executing(self, db):
        run_id = seed_run(db)
        analyze_run(db, 1, run_id)
        data = patch_run(
            db,
            1,
            run_id,
            AgentRunPatch(status="executing", approved_by="ops", approve_note="同意执行"),
        )
        assert data["status"] == "executing"
        assert data["approved_by"] == "ops"
        assert data["approve_note"] == "同意执行"

    def test_reject_rejected(self, db):
        run_id = seed_run(db)
        analyze_run(db, 1, run_id)
        data = patch_run(
            db,
            1,
            run_id,
            AgentRunPatch(status="rejected", approve_note="风险不可控"),
        )
        assert data["status"] == "rejected"
        assert data["approve_note"] == "风险不可控"

    def test_gate_forced_before_approval(self, db):
        """未过闸门（pending）不可直接执行动作或完成。"""
        run_id = seed_run(db)
        with pytest.raises(AgentServiceError):
            record_action(
                db,
                1,
                run_id,
                AgentActionIn(action_type="create_task", payload={"t": 1}),
            )
        with pytest.raises(AgentServiceError):
            complete_run(db, 1, run_id)

    def test_patch_not_in_gate_rejected(self, db):
        """非 awaiting_approval 状态不可确认。"""
        run_id = seed_run(db)
        with pytest.raises(AgentServiceError):
            patch_run(db, 1, run_id, AgentRunPatch(status="executing"))
        # 已驳回（终态）不可再 approve
        run_id2 = seed_run(db)
        analyze_run(db, 1, run_id2)
        patch_run(db, 1, run_id2, AgentRunPatch(status="rejected"))
        with pytest.raises(AgentServiceError):
            patch_run(db, 1, run_id2, AgentRunPatch(status="executing"))

    def test_illegal_transition(self, db):
        """pending 不可直接 done / failed 之外的终态转移被拒。"""
        run_id = seed_run(db)
        with pytest.raises(AgentServiceError):
            complete_run(db, 1, run_id)  # pending -> done 非法
        with pytest.raises(AgentServiceError):
            patch_run(db, 1, run_id, AgentRunPatch(status="rejected"))  # 非闸门态

    def test_fail_any_non_terminal(self, db):
        run_id = seed_run(db)
        data = fail_run(db, 1, run_id, error="数据源不可用")
        assert data["status"] == "failed"
        assert data["error"] == "数据源不可用"
        # 终态不可再失败
        with pytest.raises(AgentServiceError):
            fail_run(db, 1, run_id)

    def test_fail_after_analyzing(self, db):
        run_id = seed_run(db)
        analyze_run(db, 1, run_id)
        data = fail_run(db, 1, run_id, error="分析超时")
        assert data["status"] == "failed"

    def test_invalid_scenario(self, db):
        with pytest.raises(AgentServiceError):
            create_run(db, 1, make_run_in(scenario="unknown_scenario"))

    def test_invalid_insight_action_type(self, db):
        run_id = seed_run(db)
        with pytest.raises(AgentServiceError):
            analyze_run(
                db,
                1,
                run_id,
                insights=[{"title": "x", "suggested_action_type": "hack"}],
            )


class TestExecutionLoop:
    """执行动作登记与结果回写。"""

    def test_record_action_executed_and_published(self, db):
        run_id = seed_run(db, approval_required=False)
        analyze_run(db, 1, run_id)
        data = record_action(
            db,
            1,
            run_id,
            AgentActionIn(action_type="create_task", payload={"title": "召回任务"}),
            operator="action-agent",
        )
        assert data["status"] == "executed"
        assert data["published"] is True
        assert data["executed_by"] == "action-agent"
        assert data["event_name"] == "agent.action.executed"

        # 事件总线已落库
        events = list(db.execute(select(CoreEvent)).scalars().all())
        assert any(e.event_name == "agent.action.executed" for e in events)

    def test_record_action_confirms_insight(self, db):
        run_id = seed_run(db, approval_required=False)
        data = analyze_run(
            db,
            1,
            run_id,
            insights=[{"title": "关键洞察"}],
        )
        insight_id = data["insights"][0]["id"]
        record_action(
            db,
            1,
            run_id,
            AgentActionIn(insight_id=insight_id, action_type="notify"),
        )
        insight = db.scalar(select(AgentInsight).where(AgentInsight.id == insight_id))
        assert insight.status == "confirmed"

    def test_record_action_foreign_insight_rejected(self, db):
        run_id = seed_run(db, approval_required=False)
        data = analyze_run(db, 1, run_id, insights=[{"title": "x"}])
        other_run_id = seed_run(db, approval_required=False)
        analyze_run(db, 1, other_run_id)
        other_insight_id = data["insights"][0]["id"]  # 属于 run_id 而非 other_run_id
        with pytest.raises(AgentServiceError):
            record_action(
                db,
                1,
                other_run_id,
                AgentActionIn(insight_id=other_insight_id, action_type="record"),
            )

    def test_invalid_action_type(self, db):
        run_id = seed_run(db, approval_required=False)
        analyze_run(db, 1, run_id)
        with pytest.raises(AgentServiceError):
            record_action(db, 1, run_id, AgentActionIn(action_type="boom"))

    def test_complete_publishes_result(self, db):
        run_id = seed_run(db, approval_required=False)
        analyze_run(db, 1, run_id)
        record_action(db, 1, run_id, AgentActionIn(action_type="record"))
        data = complete_run(db, 1, run_id, result_summary="已创建召回任务并推送通知")
        assert data["status"] == "done"
        assert data["result_published"] is True
        assert data["result_event_id"]
        assert data["finished_at"] is not None

        events = list(db.execute(select(CoreEvent)).scalars().all())
        assert any(e.event_name == "agent.run.completed" for e in events)

    def test_complete_terminal_rejected(self, db):
        run_id = seed_run(db, approval_required=False)
        analyze_run(db, 1, run_id)
        complete_run(db, 1, run_id)
        with pytest.raises(AgentServiceError):
            complete_run(db, 1, run_id)


class TestQueriesAndIsolation:
    """列表分页过滤与租户隔离。"""

    def test_list_runs_filter(self, db):
        seed_run(db, name="A-流失", scenario="churn_recall")
        seed_run(db, name="B-转化", scenario="conversion_promote")
        seed_run(db, name="C-渠道", scenario="channel_roi")
        data = list_runs(db, 1)
        assert data["total"] == 3
        assert data["page_size"] == 20
        assert len(data["items"]) == 3

        data = list_runs(db, 1, scenario="churn_recall")
        assert data["total"] == 1
        assert data["items"][0]["name"] == "A-流失"

        data = list_runs(db, 1, keyword="转化")
        assert data["total"] == 1

    def test_list_runs_pagination(self, db):
        for i in range(25):
            seed_run(db, name=f"run-{i}")
        data = list_runs(db, 1, page=1, size=10)
        assert data["total"] == 25
        assert len(data["items"]) == 10
        data2 = list_runs(db, 1, page=3, size=10)
        assert len(data2["items"]) == 5

    def test_list_runs_invalid_status(self, db):
        with pytest.raises(AgentServiceError):
            list_runs(db, 1, status="hacked")

    def test_get_run_detail(self, db):
        run_id = seed_run(db, approval_required=False)
        analyze_run(db, 1, run_id)
        data = get_run(db, 1, run_id)
        assert data["id"] == run_id
        assert len(data["insights"]) == 1
        assert data["actions"] == []

    def test_tenant_isolation_get(self, db):
        run_id = seed_run(db, tenant_id=1)
        assert get_run(db, 2, run_id) is None

    def test_tenant_isolation_mutate(self, db):
        run_id = seed_run(db, tenant_id=1, approval_required=False)
        analyze_run(db, 1, run_id)
        # 租户 2 无法对租户 1 的运行执行任何操作
        with pytest.raises(AgentServiceError):
            analyze_run(db, 2, run_id)
        with pytest.raises(AgentServiceError):
            record_action(db, 2, run_id, AgentActionIn(action_type="record"))
        with pytest.raises(AgentServiceError):
            complete_run(db, 2, run_id)
        with pytest.raises(AgentServiceError):
            fail_run(db, 2, run_id)

    def test_tenant_isolation_list(self, db):
        seed_run(db, tenant_id=1)
        seed_run(db, tenant_id=2)
        data = list_runs(db, 1)
        assert data["total"] == 1
        assert data["items"][0]["tenant_id"] == 1
