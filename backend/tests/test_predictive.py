"""M9 预测引擎测试。

覆盖：
- 引擎路由：mode=rule 直接规则打分；mode=local/api 未注册时按 rule_fallback
  降级规则，禁止兜底时抛错
- 规则打分：churn/conversion 特征加权、无特征回落 0.5 基准、概率 clamp [0.05, 0.95]
- 置信度：按特征覆盖度落在 [0.4, 0.95]
- 可插拔：注册自定义 provider 后优先于规则兜底
- 服务层：run_job 建任务 + 结果落库（job_id 唯一约束、状态 success、兜底标记），
  batch 批量预测、list/get 查询
- 边界：非法 target / mode / 空主体抛错

无外部依赖，直接执行：``pytest tests/test_predictive.py -v``。
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import predictive as engine_mod
from app.core.predictive import engine as engine_impl
from app.core.predictive import (
    PredictiveEngineError,
    RuleProvider,
    SubjectPrediction,
    register_provider,
    run_prediction,
)
from app.models.base import Base
from app.models.predictive import (
    PredictionJob,
    PredictionResult,
)

PREDICTIVE_TABLES = [
    PredictionJob.__table__,
    PredictionResult.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建预测所需表，避开 JSONB）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=PREDICTIVE_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


SUBJECTS = [
    {
        "key": "u_1001",
        "name": "用户A",
        "features": {
            "last_active_days": 30,
            "login_count": 2,
            "order_count": 1,
            "spend_amount": 100,
            "complaint_count": 0,
            "support_tickets": 3,
        },
    }
]

HIGH_RISK_SUBJECTS = [
    {
        "key": "u_9001",
        "name": "高风险用户",
        "features": {
            "last_active_days": 90,
            "login_count": 0,
            "order_count": 0,
            "spend_amount": 0,
            "complaint_count": 5,
            "support_tickets": 10,
        },
    }
]


# ============================================================ 引擎：路由与兜底
def test_rule_mode_direct_scoring():
    outcome = run_prediction(
        tenant_id=1,
        target="churn",
        subjects=SUBJECTS,
        mode="rule",
        threshold=0.5,
    )
    assert outcome.mode_used == "rule"
    assert outcome.model_used == "rule"
    assert not outcome.rule_fallback
    p = outcome.predictions[0]
    assert p.subject_key == "u_1001"
    assert p.mode == "rule"
    assert p.model == "rule"
    assert 0.0 < p.probability <= 1.0
    assert p.probability == round(p.probability, 5)
    assert p.reasons  # 可解释理由非空


def test_local_mode_falls_back_to_rule_by_default():
    outcome = run_prediction(
        tenant_id=1,
        target="churn",
        subjects=SUBJECTS,
        mode="local",
        threshold=0.5,
        rule_fallback=True,
    )
    assert outcome.rule_fallback
    assert outcome.mode_used == "rule"
    assert outcome.model_used == "rule"
    assert outcome.predictions[0].mode == "rule"


def test_local_mode_without_fallback_raises():
    with pytest.raises(PredictiveEngineError):
        run_prediction(
            tenant_id=1,
            target="churn",
            subjects=SUBJECTS,
            mode="local",
            rule_fallback=False,
        )


def test_api_mode_falls_back_to_rule_by_default():
    outcome = run_prediction(
        tenant_id=1,
        target="conversion",
        subjects=SUBJECTS,
        mode="api",
        rule_fallback=True,
    )
    assert outcome.rule_fallback
    assert outcome.mode_used == "rule"


def test_unknown_mode_raises():
    with pytest.raises(PredictiveEngineError):
        run_prediction(tenant_id=1, target="churn", subjects=SUBJECTS, mode="svm")


# ============================================================ 引擎：规则打分边界
def test_churn_high_risk_band_high():
    outcome = run_prediction(
        tenant_id=1, target="churn", subjects=HIGH_RISK_SUBJECTS, mode="rule"
    )
    p = outcome.predictions[0]
    assert p.probability >= 0.7  # 高风险特征应落 high 档
    assert p.band == "high"


def test_no_features_falls_back_to_baseline():
    outcome = run_prediction(
        tenant_id=1,
        target="churn",
        subjects=[{"key": "u_1", "name": "无特征", "features": {}}],
        mode="rule",
    )
    p = outcome.predictions[0]
    assert p.probability == 0.5
    assert p.band == "medium"
    assert p.confidence == pytest.approx(0.4, abs=1e-4)  # 覆盖度为 0 时置信度最低


def test_probability_clamped_range():
    outcome = run_prediction(
        tenant_id=1,
        target="conversion",
        subjects=[
            {
                "key": "u_extreme",
                "features": {
                    "visit_count": 1000,
                    "cart_count": 1000,
                    "content_views": 1000,
                    "recent_purchase_days": 0,
                    "coupon_used": 1,
                    "click_rate": 1,
                },
            }
        ],
        mode="rule",
    )
    p = outcome.predictions[0]
    assert 0.05 <= p.probability <= 0.95


def test_confidence_in_range_by_coverage():
    outcome = run_prediction(
        tenant_id=1,
        target="churn",
        subjects=SUBJECTS,
        mode="rule",
    )
    for p in outcome.predictions:
        assert p.confidence is not None
        assert 0.4 <= p.confidence <= 0.95


# ============================================================ 引擎：可插拔 provider
class _FakeLocalProvider:
    name = "local"

    def predict(self, *, tenant_id, target, subjects, features, threshold):
        return [
            SubjectPrediction(
                subject_key=s.get("key"),
                subject_name=s.get("name"),
                probability=0.88,
                band="high",
                mode="local",
                model="fake_model",
                confidence=0.9,
                features=s.get("features") or {},
                reasons=["fake provider 输出"],
            )
            for s in subjects
        ]


def test_plugin_provider_preferred_over_rule():
    register_provider(_FakeLocalProvider())
    try:
        outcome = run_prediction(
            tenant_id=1,
            target="churn",
            subjects=SUBJECTS,
            mode="local",
            rule_fallback=True,
        )
        assert not outcome.rule_fallback
        assert outcome.mode_used == "local"
        assert outcome.model_used == "local"  # provider 注册名
        assert outcome.predictions[0].model == "fake_model"  # provider 内部模型标识
        assert outcome.predictions[0].probability == 0.88
    finally:
        engine_impl._PROVIDERS.pop("local", None)


# ============================================================ 服务层：任务落库与查询
def test_run_job_persists_job_and_results(db):
    from app.schemas.predictive import PredictionRunIn
    from app.services.predictive_service import run_job

    payload = PredictionRunIn(
        name="流失预测-测试",
        target="churn",
        subject_keys=["u_1001", "u_1002"],
        features={
            "u_1001": {
                "last_active_days": 60,
                "login_count": 1,
                "order_count": 0,
                "spend_amount": 20,
                "complaint_count": 2,
                "support_tickets": 5,
            },
            "u_1002": {
                "last_active_days": 3,
                "login_count": 20,
                "order_count": 10,
                "spend_amount": 500,
                "complaint_count": 0,
                "support_tickets": 0,
            },
        },
        mode="local",
        rule_fallback=True,
    )
    data = run_job(db, tenant_id=7, payload=payload, operator="tester")

    assert data["status"] == "success"
    assert data["tenant_id"] == 7
    assert data["subject_count"] == 2
    assert data["rule_fallback_used"] is True  # local 未注册 -> 规则兜底
    assert data["mode"] == "rule"
    assert len(data["results"]) == 2

    job = db.scalar(select(PredictionJob).where(PredictionJob.id == data["id"]))
    assert job is not None
    assert job.status == "success"
    assert job.rule_fallback_used is True

    rows = db.execute(select(PredictionResult)).scalars().all()
    assert len(rows) == 2
    for row in rows:
        assert row.job_id == job.id
        assert row.tenant_id == 7
        assert row.target == "churn"
        assert 0.0 < row.probability <= 1.0
        assert row.confidence is not None
        assert row.mode == "rule"
        # 高风险用户概率应高于低风险用户
    prob_by_key = {r.subject_key: float(r.probability) for r in rows}
    assert prob_by_key["u_1001"] > prob_by_key["u_1002"]


def test_run_job_batch_mode(db):
    from app.schemas.predictive import PredictionBatchIn
    from app.services.predictive_service import run_job

    payload = PredictionBatchIn(
        target="conversion",
        subjects=[
            {"key": "u_a", "name": "A", "features": {"visit_count": 50, "cart_count": 8, "click_rate": 0.3}},
            {"key": "u_b", "name": "B", "features": {"visit_count": 1, "cart_count": 0, "click_rate": 0.01}},
        ],
        mode="rule",
    )
    data = run_job(db, tenant_id=3, payload=payload, operator="tester")
    assert data["status"] == "success"
    assert data["source"] == "batch"
    assert len(data["results"]) == 2
    assert data["rule_fallback_used"] is False
    assert all(r["mode"] == "rule" for r in data["results"])


def test_run_job_rejects_invalid_target(db):
    from app.schemas.predictive import PredictionRunIn
    from app.services.predictive_service import PredictiveServiceError, run_job

    payload = PredictionRunIn(
        name="非法目标", target="upsell", subject_keys=["u_1"], mode="rule"
    )
    with pytest.raises(PredictiveServiceError):
        run_job(db, tenant_id=1, payload=payload)


def test_list_and_get_jobs(db):
    from app.schemas.predictive import PredictionRunIn
    from app.services.predictive_service import get_job, list_jobs, run_job

    payload = PredictionRunIn(name="查询测试", target="churn", subject_keys=["u_1"], mode="rule")
    run_job(db, tenant_id=9, payload=payload, operator="tester")

    page = list_jobs(db, tenant_id=9, target="churn", page=1, size=10)
    assert page["total"] == 1
    assert page["items"][0]["name"] == "查询测试"

    detail = get_job(db, tenant_id=9, job_id=page["items"][0]["id"])
    assert detail is not None
    assert len(detail["results"]) == 1
    assert detail["results"][0]["confidence"] is not None
    assert get_job(db, tenant_id=999, job_id=page["items"][0]["id"]) is None


def test_run_job_duplicate_subject_keys_dedup(db):
    from app.schemas.predictive import PredictionRunIn
    from app.services.predictive_service import run_job

    payload = PredictionRunIn(
        name="去重测试", target="churn", subject_keys=["u_1", "u_1"], mode="rule"
    )
    data = run_job(db, tenant_id=5, payload=payload, operator="tester")
    assert data["subject_count"] == 1
    assert len(data["results"]) == 1
