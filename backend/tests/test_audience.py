"""M10 人群包引擎测试。

覆盖：
- 引擎校验：normalize_range 闭区间（含端点）、越界与反序抛错、开放区间；
  validate_target / validate_band / validate_filters 合法性
- 区间命中：in_probability_range 闭区间语义（含端点）、matches_band 档位匹配
- 服务层：create_segment 从预测结果按区间/档位圈选落库（成员数、区间端点、
  档位、快照 criteria、来源 job 追溯）、无约束/非法区间抛错；
  reuse_segment 从既有包再圈选、来源不存在抛错；
  list_segments 分页过滤、get_segment 详情带成员、update_segment 状态流转
  与非法状态抛错

无外部依赖，直接执行：``pytest tests/test_audience.py -v``。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.audience import (
    AudienceEngineError,
    in_probability_range,
    matches_band,
    normalize_range,
    validate_band,
    validate_filters,
    validate_target,
)
from app.models.base import Base
from app.models.audience import (
    AudienceMember,
    AudienceSegment,
)
from app.models.predictive import (
    PredictionJob,
    PredictionResult,
)
from app.schemas.audience import (
    AudienceReuseIn,
    AudienceSegmentIn,
)
from app.services.audience_service import (
    AudienceServiceError,
    create_segment,
    get_segment,
    list_segments,
    reuse_segment,
    update_segment,
)

AUDIENCE_TABLES = [
    AudienceSegment.__table__,
    AudienceMember.__table__,
]
PREDICTIVE_TABLES = [
    PredictionJob.__table__,
    PredictionResult.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建人群包与预测所需表，避开 JSONB）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=AUDIENCE_TABLES + PREDICTIVE_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def seed_job_with_results(db, tenant_id: int = 1, target: str = "churn") -> int:
    """构造一个成功预测任务及其结果集，返回 job_id。

    结果集：
      u_1 0.90 high / u_2 0.80 high / u_3 0.65 medium /
      u_4 0.45 medium / u_5 0.20 low
    """
    job = PredictionJob(
        tenant_id=tenant_id,
        name="流失预测-测试",
        target=target,
        status="success",
        mode="rule",
        model="rule",
        subject_count=5,
    )
    db.add(job)
    db.flush()
    rows = [
        ("u_1", "用户1", 0.90, "high"),
        ("u_2", "用户2", 0.80, "high"),
        ("u_3", "用户3", 0.65, "medium"),
        ("u_4", "用户4", 0.45, "medium"),
        ("u_5", "用户5", 0.20, "low"),
    ]
    for key, name, prob, band in rows:
        db.add(
            PredictionResult(
                tenant_id=tenant_id,
                job_id=job.id,
                target=target,
                subject_key=key,
                subject_name=name,
                probability=prob,
                band=band,
            )
        )
    db.commit()
    return job.id


# ============================================================ 引擎：区间归一化与校验
def test_normalize_range_closed_interval():
    assert normalize_range(0.6, 0.9) == (0.6, 0.9)
    # 五位小数归一
    assert normalize_range(0.600001, 0.9000004) == (0.60000, 0.90000)


def test_normalize_range_open_ends_allowed():
    assert normalize_range(None, None) == (None, None)
    assert normalize_range(0.6, None) == (0.6, None)
    assert normalize_range(None, 0.9) == (None, 0.9)


def test_normalize_range_rejects_out_of_bounds():
    with pytest.raises(AudienceEngineError):
        normalize_range(-0.1, 0.9)
    with pytest.raises(AudienceEngineError):
        normalize_range(0.1, 1.1)


def test_normalize_range_rejects_reversed():
    with pytest.raises(AudienceEngineError):
        normalize_range(0.9, 0.6)


def test_validate_target():
    validate_target("churn")
    validate_target("conversion")
    with pytest.raises(AudienceEngineError):
        validate_target("growth")


def test_validate_band():
    validate_band(None)
    validate_band("high")
    validate_band("medium")
    validate_band("low")
    with pytest.raises(AudienceEngineError):
        validate_band("ultra")


def test_validate_filters_requires_at_least_one():
    # 任一条件即可
    validate_filters(min_prob=0.5)
    validate_filters(band="high")
    validate_filters(source_job_id=1)
    validate_filters(source_segment_id=1)
    # 全空必须拒绝，避免无约束全量圈选
    with pytest.raises(AudienceEngineError):
        validate_filters()


def test_in_probability_range_closed_interval():
    assert in_probability_range(0.60, 0.6, 0.9)   # 下限含端点
    assert in_probability_range(0.90, 0.6, 0.9)   # 上限含端点
    assert in_probability_range(0.75, 0.6, 0.9)
    assert not in_probability_range(0.59, 0.6, 0.9)
    assert not in_probability_range(0.91, 0.6, 0.9)
    # 开放区间
    assert in_probability_range(0.95, 0.9, None)
    assert in_probability_range(0.10, None, 0.2)
    assert in_probability_range(0.5, None, None)


def test_matches_band():
    assert matches_band("high", None)          # 未指定档位全匹配
    assert matches_band("high", "high")
    assert matches_band("medium", "medium")
    assert not matches_band("high", "low")
    assert not matches_band(None, "high")      # 空档位不匹配指定档位


# ============================================================ 服务层：创建人群包
def test_create_segment_by_range_and_band(db):
    job_id = seed_job_with_results(db)
    segment = create_segment(
        db,
        tenant_id=1,
        payload=AudienceSegmentIn(
            name="高流失-重点召回",
            target="churn",
            source_job_id=job_id,
            min_prob=0.6,
            max_prob=0.95,
            band="high",
            description="测试包",
        ),
        operator="tester",
    )
    assert segment["status"] == "ready"
    assert segment["source_job_id"] == job_id
    assert segment["min_prob"] == 0.6
    assert segment["max_prob"] == 0.95
    assert segment["band"] == "high"
    assert segment["member_count"] == 2  # u_1(0.90) / u_2(0.80)
    keys = {m["subject_key"] for m in segment["members"]}
    assert keys == {"u_1", "u_2"}
    assert segment["criteria"]["target"] == "churn"
    assert segment["criteria"]["source_job_id"] == job_id


def test_create_segment_closed_interval_single_point(db):
    job_id = seed_job_with_results(db)
    segment = create_segment(
        db,
        tenant_id=1,
        payload=AudienceSegmentIn(
            name="精确0.9",
            target="churn",
            source_job_id=job_id,
            min_prob=0.9,
            max_prob=0.9,
        ),
    )
    assert segment["member_count"] == 1
    assert segment["members"][0]["subject_key"] == "u_1"


def test_create_segment_open_range(db):
    job_id = seed_job_with_results(db)
    segment = create_segment(
        db,
        tenant_id=1,
        payload=AudienceSegmentIn(
            name="高概率开放区间",
            target="churn",
            source_job_id=job_id,
            min_prob=0.75,
        ),
    )
    assert segment["member_count"] == 2  # u_1(0.90) / u_2(0.80)


def test_create_segment_requires_filter(db):
    with pytest.raises(AudienceServiceError):
        create_segment(
            db,
            tenant_id=1,
            payload=AudienceSegmentIn(
                name="无约束包",
                target="churn",
                source_job_id=None,
                min_prob=None,
                max_prob=None,
                band=None,
            ),
        )


def test_create_segment_rejects_invalid_range(db):
    job_id = seed_job_with_results(db)
    with pytest.raises(AudienceServiceError):
        create_segment(
            db,
            tenant_id=1,
            payload=AudienceSegmentIn(
                name="反序区间",
                target="churn",
                source_job_id=job_id,
                min_prob=0.9,
                max_prob=0.6,
            ),
        )


def test_create_segment_rejects_invalid_target(db):
    job_id = seed_job_with_results(db)
    with pytest.raises(AudienceServiceError):
        create_segment(
            db,
            tenant_id=1,
            payload=AudienceSegmentIn(
                name="非法目标",
                target="growth",
                source_job_id=job_id,
                min_prob=0.5,
            ),
        )


# ============================================================ 服务层：复用人群包
def test_reuse_segment_from_existing(db):
    job_id = seed_job_with_results(db)
    first = create_segment(
        db,
        tenant_id=1,
        payload=AudienceSegmentIn(
            name="原始高流失包",
            target="churn",
            source_job_id=job_id,
            min_prob=0.5,
            band="high",
        ),
    )
    reused = reuse_segment(
        db,
        tenant_id=1,
        payload=AudienceReuseIn(
            name="复用-更严区间",
            target="churn",
            source_segment_id=first["id"],
            min_prob=0.85,
        ),
        operator="tester",
    )
    assert reused["source_job_id"] == job_id  # 溯源到原始预测任务
    assert reused["member_count"] == 1
    assert reused["members"][0]["subject_key"] == "u_1"
    assert reused["criteria"]["source_segment_id"] == first["id"]


def test_reuse_segment_missing_source_raises(db):
    with pytest.raises(AudienceServiceError):
        reuse_segment(
            db,
            tenant_id=1,
            payload=AudienceReuseIn(
                name="来源不存在",
                target="churn",
                source_segment_id=9999,
                min_prob=0.5,
            ),
        )


# ============================================================ 服务层：列表/详情/更新
def test_list_segments_with_filters(db):
    job_id = seed_job_with_results(db)
    create_segment(
        db,
        tenant_id=1,
        payload=AudienceSegmentIn(
            name="流失包A", target="churn", source_job_id=job_id, min_prob=0.6
        ),
    )
    create_segment(
        db,
        tenant_id=1,
        payload=AudienceSegmentIn(
            name="转化包B", target="conversion", source_job_id=job_id, min_prob=0.5
        ),
    )
    # 全量
    result = list_segments(db, tenant_id=1, page=1, size=10)
    assert result["total"] == 2
    assert len(result["items"]) == 2
    # 按目标过滤
    only_churn = list_segments(db, tenant_id=1, target="churn")
    assert only_churn["total"] == 1
    assert only_churn["items"][0]["name"] == "流失包A"
    # 按关键字过滤
    by_keyword = list_segments(db, tenant_id=1, keyword="转化")
    assert by_keyword["total"] == 1
    assert by_keyword["items"][0]["name"] == "转化包B"


def test_list_segments_rejects_invalid_status(db):
    with pytest.raises(AudienceServiceError):
        list_segments(db, tenant_id=1, status="bogus")


def test_get_segment_with_members(db):
    job_id = seed_job_with_results(db)
    segment = create_segment(
        db,
        tenant_id=1,
        payload=AudienceSegmentIn(
            name="详情包",
            target="churn",
            source_job_id=job_id,
            min_prob=0.4,
        ),
    )
    detail = get_segment(db, tenant_id=1, segment_id=segment["id"])
    assert detail is not None
    assert detail["id"] == segment["id"]
    assert len(detail["members"]) == 4  # u_1 / u_2 / u_3 / u_4
    # 成员按概率降序
    probs = [m["probability"] for m in detail["members"]]
    assert probs == sorted(probs, reverse=True)
    assert get_segment(db, tenant_id=1, segment_id=9999) is None


def test_update_segment_status_and_description(db):
    job_id = seed_job_with_results(db)
    segment = create_segment(
        db,
        tenant_id=1,
        payload=AudienceSegmentIn(
            name="状态流转包",
            target="churn",
            source_job_id=job_id,
            min_prob=0.5,
        ),
    )
    updated = update_segment(
        db, tenant_id=1, segment_id=segment["id"], status="active", description="已启用"
    )
    assert updated["status"] == "active"
    assert updated["description"] == "已启用"
    # 非法状态抛错
    with pytest.raises(AudienceServiceError):
        update_segment(db, tenant_id=1, segment_id=segment["id"], status="bogus")
    # 租户隔离：其他租户查不到
    assert update_segment(db, tenant_id=2, segment_id=segment["id"], status="ready") is None
