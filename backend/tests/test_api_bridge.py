"""M13 API 申请助手测试。

覆盖：
- 模板 CRUD：创建/更新/列表过滤/详情/删除、非法分类抛错、租户隔离
- 申请任务：创建任务密码 AES 加密落库（库中不含明文密码）、账号脱敏、
  状态机流转 pending→submitted→awaiting_manual→done/failed、
  非法流转与终态不可变、requires_manual 平台创建后自动 submitted、租户隔离

无外部依赖，直接执行：``pytest tests/test_api_bridge.py -v``。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.api_bridge import (
    ApiApplyTask,
    ApiPlatformTemplate,
)
from app.models.base import Base
from app.schemas.api_bridge import (
    ApiApplyTaskIn,
    ApiApplyTaskPatch,
    ApiPlatformTemplateIn,
    ApiPlatformTemplatePatch,
)
from app.services.api_bridge_service import (
    ApiBridgeServiceError,
    create_apply_task,
    create_template,
    delete_template,
    get_task,
    get_template,
    list_tasks,
    list_templates,
    update_apply_task,
    update_template,
)

BRIDGE_TABLES = [
    ApiPlatformTemplate.__table__,
    ApiApplyTask.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建 API 申请助手所需表）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=BRIDGE_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _tpl_in(name="某电商平台", category="ecommerce", requires_manual=False):
    return ApiPlatformTemplateIn(
        name=name,
        apply_url="https://open.example.com/apply",
        field_schema={"fields": [{"name": "app_name", "label": "应用名称", "required": True}]},
        requires_manual=requires_manual,
        category=category,
    )


def _task_in(platform_id, account="user@example.com", password="secret-pwd-123"):
    return ApiApplyTaskIn(
        platform_id=platform_id,
        platform="某电商平台",
        account=account,
        password=password,
    )


# ---------------------------------------------------------------- 模板 CRUD

def test_create_template(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    assert tpl.id > 0
    assert tpl.name == "某电商平台"
    assert tpl.category == "ecommerce"
    assert tpl.enabled is True


def test_create_template_invalid_category(db):
    payload = _tpl_in(category="bogus")
    with pytest.raises(ApiBridgeServiceError):
        create_template(db, tenant_id=1, payload=payload)


def test_update_template(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    patch = ApiPlatformTemplatePatch(enabled=False, name="新平台名")
    upd = update_template(db, tenant_id=1, template_id=tpl.id, payload=patch)
    assert upd.enabled is False
    assert upd.name == "新平台名"


def test_update_template_not_found(db):
    with pytest.raises(ApiBridgeServiceError):
        update_template(db, tenant_id=1, template_id=999, payload=ApiPlatformTemplatePatch(enabled=False))


def test_update_template_tenant_isolation(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    with pytest.raises(ApiBridgeServiceError):
        update_template(db, tenant_id=2, template_id=tpl.id, payload=ApiPlatformTemplatePatch(enabled=False))


def test_list_templates_filter(db):
    create_template(db, tenant_id=1, payload=_tpl_in(name="A电商", category="ecommerce"))
    create_template(db, tenant_id=1, payload=_tpl_in(name="B官网", category="website"))
    create_template(db, tenant_id=2, payload=_tpl_in(name="C其他租户", category="other"))
    data = list_templates(db, tenant_id=1)
    assert data["total"] == 2
    data = list_templates(db, tenant_id=1, category="website")
    assert data["total"] == 1
    assert data["items"][0].name == "B官网"
    data = list_templates(db, tenant_id=1, keyword="电商")
    assert data["total"] == 1


def test_get_template(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    got = get_template(db, tenant_id=1, template_id=tpl.id)
    assert got.name == tpl.name


def test_get_template_tenant_isolation(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    with pytest.raises(ApiBridgeServiceError):
        get_template(db, tenant_id=2, template_id=tpl.id)


def test_delete_template(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    delete_template(db, tenant_id=1, template_id=tpl.id)
    with pytest.raises(ApiBridgeServiceError):
        get_template(db, tenant_id=1, template_id=tpl.id)


# ---------------------------------------------------------------- 申请任务

def test_create_apply_task_password_encrypted(db):
    """创建任务后库中 credentials_ref 为密文，不得出现明文密码。"""
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    task = create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id), operator="alice")
    assert task.id > 0
    assert task.status == "pending"
    assert task.account == "user@example.com"
    # credentials_ref 是密文，不应包含明文密码
    assert "secret-pwd-123" not in task.credentials_ref
    rows = db.query(ApiApplyTask).all()
    for row in rows:
        assert "secret-pwd-123" not in (row.credentials_ref or "")


def test_create_apply_task_without_template(db):
    """无模板时直接按平台名创建。"""
    task = create_apply_task(
        db, tenant_id=1, payload=ApiApplyTaskIn(platform="某平台", account="a@b.com", password="pwd")
    )
    assert task.platform == "某平台"
    assert task.platform_id is None
    assert task.status == "pending"


def test_create_apply_task_disabled_template(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    update_template(db, tenant_id=1, template_id=tpl.id, payload=ApiPlatformTemplatePatch(enabled=False))
    with pytest.raises(ApiBridgeServiceError):
        create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id))


def test_create_apply_task_requires_manual_auto_submitted(db):
    """requires_manual 平台创建后自动 submitted，等待人工介入。"""
    tpl = create_template(db, tenant_id=1, payload=_tpl_in(requires_manual=True))
    task = create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id))
    assert task.status == "submitted"
    assert task.progress == 40


def test_apply_task_state_machine(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    task = create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id))
    # pending -> submitted
    task = update_apply_task(
        db, tenant_id=1, task_id=task.id,
        payload=ApiApplyTaskPatch(status="submitted", progress=50, result_message="已提交平台"),
    )
    assert task.status == "submitted"
    # submitted -> awaiting_manual
    task = update_apply_task(
        db, tenant_id=1, task_id=task.id, payload=ApiApplyTaskPatch(status="awaiting_manual")
    )
    assert task.status == "awaiting_manual"
    # awaiting_manual -> done
    task = update_apply_task(
        db, tenant_id=1, task_id=task.id,
        payload=ApiApplyTaskPatch(status="done", result_message="API 已发放"),
    )
    assert task.status == "done"
    assert task.finished_at is not None


def test_apply_task_invalid_transition(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    task = create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id))
    # pending 不能直接跳到 done
    with pytest.raises(ApiBridgeServiceError):
        update_apply_task(db, tenant_id=1, task_id=task.id, payload=ApiApplyTaskPatch(status="done"))


def test_apply_task_terminal_state_immutable(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    task = create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id))
    update_apply_task(db, tenant_id=1, task_id=task.id, payload=ApiApplyTaskPatch(status="failed", error="资质不符"))
    with pytest.raises(ApiBridgeServiceError):
        update_apply_task(db, tenant_id=1, task_id=task.id, payload=ApiApplyTaskPatch(status="done"))


def test_apply_task_invalid_status(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    task = create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id))
    with pytest.raises(ApiBridgeServiceError):
        update_apply_task(db, tenant_id=1, task_id=task.id, payload=ApiApplyTaskPatch(status="bogus"))


def test_list_tasks_masked(db):
    """列表返回脱敏账号，且不含 credentials_ref 字段。"""
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id, account="longaccount@example.com"))
    data = list_tasks(db, tenant_id=1)
    assert data["total"] == 1
    item = data["items"][0]
    assert item["account_masked"].startswith("lon")
    assert item["account_masked"].endswith("***")
    assert "credentials_ref" not in item


def test_list_tasks_filter_by_status(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id))
    create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id, account="x@y.com"))
    data = list_tasks(db, tenant_id=1, status="pending")
    assert data["total"] == 2
    # 全部置 done 后再过滤
    for row in db.query(ApiApplyTask).all():
        row.status = "done"
    db.commit()
    data = list_tasks(db, tenant_id=1, status="pending")
    assert data["total"] == 0
    data = list_tasks(db, tenant_id=1, status="done")
    assert data["total"] == 2


def test_get_task_tenant_isolation(db):
    tpl = create_template(db, tenant_id=1, payload=_tpl_in())
    task = create_apply_task(db, tenant_id=1, payload=_task_in(tpl.id))
    with pytest.raises(ApiBridgeServiceError):
        get_task(db, tenant_id=2, task_id=task.id)
