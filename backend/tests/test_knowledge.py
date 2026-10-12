"""M11 企业知识库测试。

覆盖：
- 校验：create_doc 非法类型/状态/来源抛错
- CRUD：create_doc 字段落库、get_doc、list_docs 分页过滤
  （keyword/doc_type/status/scenario）、update_doc 部分更新与状态流转、
  delete_doc 删除与租户隔离
- 检索：search_docs 仅返回已发布、关键词/类型/场景过滤、热度优先排序、limit
- 引用：register_refs 累计 ref_count、写引用日志、缺失统计、全部缺失抛错、
  非法来源抛错、租户隔离

无外部依赖，直接执行：``pytest tests/test_knowledge.py -v``。
"""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.knowledge import (
    KnowledgeDoc,
    KnowledgeRefLog,
)
from app.schemas.knowledge import (
    KnowledgeDocIn,
    KnowledgeDocPatch,
    KnowledgeQueryIn,
    KnowledgeRefIn,
)
from app.services.knowledge_service import (
    KnowledgeServiceError,
    create_doc,
    delete_doc,
    get_doc,
    list_docs,
    register_refs,
    search_docs,
    update_doc,
)

KNOWLEDGE_TABLES = [
    KnowledgeDoc.__table__,
    KnowledgeRefLog.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建知识库所需表，避开 JSONB）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=KNOWLEDGE_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def seed_docs(db, tenant_id: int = 1) -> dict[str, int]:
    """沉淀一组知识文档，返回 {名称: doc_id}。

    - SOP-结算流程（published, sop）
    - 洞察-流失分析（published, insight）
    - 经验-大促备货（draft, experience）
    - 策略-会员召回（published, policy, 场景 电商）
    """
    docs = {
        "sop": KnowledgeDocIn(
            title="结算流程SOP",
            doc_type="sop",
            status="published",
            content="对账→审核→打款→回执",
            summary="资金结算标准步骤",
            tags=["结算", "财务"],
            scenario="财务",
            source="manual",
            author="张财务",
        ),
        "insight": KnowledgeDocIn(
            title="流失用户洞察",
            doc_type="insight",
            status="published",
            content="高价值用户流失前登录频次下降",
            summary="流失前兆：登录频次下降",
            tags=["流失", "洞察"],
            scenario="用户运营",
            source="insight",
            author="分析师",
        ),
        "draft": KnowledgeDocIn(
            title="大促备货经验",
            doc_type="experience",
            status="draft",
            content="峰值备货按 1.5 倍余量",
            summary="备货余量参考",
            tags=["大促"],
            scenario="供应链",
            source="learning",
            author="运营",
        ),
        "policy": KnowledgeDocIn(
            title="会员召回策略",
            doc_type="policy",
            status="published",
            content="流失 30 天以上用户发券召回",
            summary="召回券策略",
            tags=["会员", "召回"],
            scenario="电商",
            source="manual",
            author="策略组",
        ),
    }
    ids: dict[str, int] = {}
    for key, payload in docs.items():
        data = create_doc(db, tenant_id, payload, operator="tester")
        ids[key] = data["id"]
    return ids


# ============================================================ 校验
def test_create_doc_rejects_invalid_doc_type(db):
    with pytest.raises(KnowledgeServiceError):
        create_doc(
            db,
            1,
            KnowledgeDocIn(title="非法类型", doc_type="magic"),
        )


def test_create_doc_rejects_invalid_status(db):
    with pytest.raises(KnowledgeServiceError):
        create_doc(
            db,
            1,
            KnowledgeDocIn(title="非法状态", status="deleted"),
        )


def test_create_doc_rejects_invalid_source(db):
    with pytest.raises(KnowledgeServiceError):
        create_doc(
            db,
            1,
            KnowledgeDocIn(title="非法来源", source="wiki"),
        )


# ============================================================ CRUD
def test_create_doc_fields(db):
    data = create_doc(
        db,
        1,
        KnowledgeDocIn(
            title="结算流程SOP",
            doc_type="sop",
            status="published",
            content="对账→审核→打款→回执",
            summary="资金结算标准步骤",
            tags=["结算"],
            scenario="财务",
            source="manual",
            author="张财务",
        ),
        operator="tester",
    )
    assert data["title"] == "结算流程SOP"
    assert data["doc_type"] == "sop"
    assert data["status"] == "published"
    assert data["source"] == "manual"
    assert data["ref_count"] == 0
    assert data["published_at"] is not None   # 发布即打点
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
    assert data["tenant_id"] == 1


def test_create_doc_draft_has_no_published_at(db):
    data = create_doc(
        db,
        1,
        KnowledgeDocIn(title="草稿文档", status="draft"),
    )
    assert data["status"] == "draft"
    assert data["published_at"] is None


def test_get_doc(db):
    ids = seed_docs(db)
    detail = get_doc(db, 1, ids["sop"])
    assert detail is not None
    assert detail["title"] == "结算流程SOP"
    assert get_doc(db, 1, 9999) is None
    assert get_doc(db, 2, ids["sop"]) is None  # 租户隔离


def test_list_docs_pagination_and_filters(db):
    seed_docs(db)
    # 全量
    result = list_docs(db, 1, page=1, size=10)
    assert result["total"] == 4
    assert len(result["items"]) == 4
    # 按类型过滤
    only_sop = list_docs(db, 1, doc_type="sop")
    assert only_sop["total"] == 1
    assert only_sop["items"][0]["title"] == "结算流程SOP"
    # 按状态过滤
    only_published = list_docs(db, 1, status="published")
    assert only_published["total"] == 3
    # 按关键词过滤（标题命中）
    by_keyword = list_docs(db, 1, keyword="洞察")
    assert by_keyword["total"] == 1
    assert by_keyword["items"][0]["doc_type"] == "insight"
    # 按场景过滤
    by_scenario = list_docs(db, 1, scenario="电商")
    assert by_scenario["total"] == 1
    assert by_scenario["items"][0]["title"] == "会员召回策略"
    # 组合过滤 + 分页
    combo = list_docs(db, 1, doc_type="insight", status="published", keyword="流失", page=1, size=5)
    assert combo["total"] == 1
    # 非法类型/状态抛错
    with pytest.raises(KnowledgeServiceError):
        list_docs(db, 1, doc_type="magic")
    with pytest.raises(KnowledgeServiceError):
        list_docs(db, 1, status="bogus")


def test_update_doc_partial_and_status_flow(db):
    ids = seed_docs(db)
    updated = update_doc(
        db,
        1,
        ids["draft"],
        KnowledgeDocPatch(title="大促备货经验V2", status="published", scenario="供应链/大促"),
    )
    assert updated["title"] == "大促备货经验V2"
    assert updated["status"] == "published"
    assert updated["published_at"] is not None  # 发布时打点
    assert updated["scenario"] == "供应链/大促"
    # 已发布再改不重复打点（仍保留首次发布时间）
    again = update_doc(db, 1, ids["draft"], KnowledgeDocPatch(summary="更稳的备货参考"))
    assert again["published_at"] == updated["published_at"]
    # 非法状态抛错
    with pytest.raises(KnowledgeServiceError):
        update_doc(db, 1, ids["draft"], KnowledgeDocPatch(status="deleted"))
    # 非法类型抛错
    with pytest.raises(KnowledgeServiceError):
        update_doc(db, 1, ids["draft"], KnowledgeDocPatch(doc_type="magic"))
    # 不存在返回 None
    assert update_doc(db, 1, 9999, KnowledgeDocPatch(title="x")) is None
    # 租户隔离
    assert update_doc(db, 2, ids["draft"], KnowledgeDocPatch(title="x")) is None


def test_delete_doc(db):
    ids = seed_docs(db)
    assert delete_doc(db, 1, ids["insight"]) is True
    assert get_doc(db, 1, ids["insight"]) is None
    # 再删返回 False
    assert delete_doc(db, 1, ids["insight"]) is False
    # 租户隔离：其他租户不能删
    assert delete_doc(db, 2, ids["sop"]) is False
    assert get_doc(db, 1, ids["sop"]) is not None


# ============================================================ 检索（Agent 引用入口）
def test_search_docs_only_published(db):
    ids = seed_docs(db)
    result = search_docs(db, 1, KnowledgeQueryIn(keyword="", limit=50))
    # 4 条里 3 条 published，draft 不返回
    assert result["total"] == 3
    titles = {item["title"] for item in result["items"]}
    assert "大促备货经验" not in titles


def test_search_docs_keyword_and_type_and_scenario(db):
    seed_docs(db)
    by_keyword = search_docs(db, 1, KnowledgeQueryIn(keyword="结算", limit=50))
    assert by_keyword["total"] == 1
    assert by_keyword["items"][0]["title"] == "结算流程SOP"
    by_type = search_docs(db, 1, KnowledgeQueryIn(doc_type="policy", limit=50))
    assert by_type["total"] == 1
    assert by_type["items"][0]["title"] == "会员召回策略"
    by_scenario = search_docs(db, 1, KnowledgeQueryIn(scenario="用户运营", limit=50))
    assert by_scenario["total"] == 1
    # 非法类型抛错
    with pytest.raises(KnowledgeServiceError):
        search_docs(db, 1, KnowledgeQueryIn(doc_type="magic"))


def test_search_docs_hot_first_and_limit(db):
    ids = seed_docs(db)
    # 分两次登记：SOP 累计 2 次、洞察 1 次，形成热度差
    register_refs(
        db,
        1,
        KnowledgeRefIn(doc_ids=[ids["sop"]], source="agent", ref_key="job-1"),
    )
    register_refs(
        db,
        1,
        KnowledgeRefIn(doc_ids=[ids["sop"], ids["insight"]], source="agent", ref_key="job-2"),
    )
    result = search_docs(db, 1, KnowledgeQueryIn(keyword="", limit=50))
    # 热度优先：sop(2) > insight(1) > policy(0)
    order = [item["title"] for item in result["items"]]
    assert order.index("结算流程SOP") < order.index("流失用户洞察") < order.index("会员召回策略")
    # limit 截断
    limited = search_docs(db, 1, KnowledgeQueryIn(keyword="", limit=2))
    assert len(limited["items"]) == 2
    assert limited["items"][0]["title"] == "结算流程SOP"


# ============================================================ 引用热度
def test_register_refs_increments_count_and_writes_log(db):
    ids = seed_docs(db)
    result = register_refs(
        db,
        1,
        KnowledgeRefIn(
            doc_ids=[ids["sop"], ids["insight"]],
            source="agent",
            ref_key="job-1",
            note="Agent 引用",
        ),
    )
    assert result["referenced"] == 2
    assert result["missing"] == []
    detail = get_doc(db, 1, ids["sop"])
    assert detail["ref_count"] == 1
    # 引用日志落库
    log_count = db.scalar(
        select(func.count()).select_from(KnowledgeRefLog).where(
            KnowledgeRefLog.doc_id == ids["sop"]
        )
    )
    assert log_count == 1
    # 再次引用累计
    register_refs(db, 1, KnowledgeRefIn(doc_ids=[ids["sop"]], source="decision_studio"))
    assert get_doc(db, 1, ids["sop"])["ref_count"] == 2


def test_register_refs_deduplicates_and_counts_missing(db):
    ids = seed_docs(db)
    result = register_refs(
        db,
        1,
        KnowledgeRefIn(doc_ids=[ids["sop"], ids["sop"], 9999, ids["insight"]]),
    )
    assert result["referenced"] == 2      # 去重后 sop + insight
    assert result["missing"] == [9999]
    assert get_doc(db, 1, ids["sop"])["ref_count"] == 1
    assert get_doc(db, 1, ids["insight"])["ref_count"] == 1


def test_register_refs_all_missing_raises(db):
    with pytest.raises(KnowledgeServiceError):
        register_refs(db, 1, KnowledgeRefIn(doc_ids=[8888, 9999]))


def test_register_refs_rejects_invalid_source(db):
    ids = seed_docs(db)
    with pytest.raises(KnowledgeServiceError):
        register_refs(db, 1, KnowledgeRefIn(doc_ids=[ids["sop"]], source="chatbot"))


def test_register_refs_tenant_isolation(db):
    ids = seed_docs(db)
    # 租户 2 引用租户 1 的文档 → 全部缺失
    with pytest.raises(KnowledgeServiceError):
        register_refs(db, 2, KnowledgeRefIn(doc_ids=[ids["sop"]]))
    # 热度未被污染
    assert get_doc(db, 1, ids["sop"])["ref_count"] == 0
