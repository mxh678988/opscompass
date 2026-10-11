"""插件市场接口测试（v0.12.0 MVP）。

覆盖：
1. 市场列表：运行时发现 sentiment 插件并返回元信息/状态
2. 详情：未发现插件 404；已发现插件返回元信息
3. 安装：建表 + 激活 + 数据库登记（CorePlugin）
4. 启停：enable / disable 状态流转
5. 卸载：uninstall 状态落库
6. 权限：无 plugin:view 权限访问被拒（401/403）
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import plugin_market
from app.main import app

REAL_PLUGIN_SRC = Path(__file__).resolve().parents[2] / "plugins" / "sentiment"


@pytest.fixture()
def patch_plugins_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把真实 sentiment 插件复制到临时目录并替换模块级 _PLUGINS_DIR。"""
    dest = tmp_path / "plugins"
    shutil.copytree(REAL_PLUGIN_SRC, dest / "sentiment")
    monkeypatch.setattr(plugin_market, "_PLUGINS_DIR", dest)
    return dest


@pytest.fixture()
def patch_session_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """内存库会话工厂替换 SessionLocal，并建登录/权限/插件登记所需表。

    注意：全量 Base.metadata.create_all 会因 PostgreSQL 专用 JSONB 列在
    sqlite 下无法编译而失败，因此只建 auth + plugin 相关表。
    """
    from app.models.auth import (  # noqa: F401
        AuditLog,
        Permission,
        Role,
        User,
    )
    from app.models.plugin import (  # noqa: F401
        CorePlugin,
        CorePluginConfig,
        CorePluginKey,
    )

    from app.models.tenant import Tenant  # noqa: F401

    from app.models.base import Base as ORMBase

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    # 只建这些表（按依赖顺序）
    for table in (
        "oc_tenant",
        "oc_user",
        "oc_role",
        "oc_permission",
        "oc_role_permission",
        "oc_user_role",
        "oc_audit_log",
        "oc_core_plugin",
        "oc_core_plugin_config",
        "oc_core_plugin_key",
    ):
        if table in ORMBase.metadata.tables:
            ORMBase.metadata.tables[table].create(engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr("app.models.base.SessionLocal", maker)
    yield


@pytest.fixture()
def client(patch_plugins_dir, patch_session_factory) -> TestClient:
    with TestClient(app) as c:
        yield c


def _login(client: TestClient) -> str:
    """登录并返回 access_token（测试环境 ensure_seed 已建超管）。"""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "OpsCompass@2026"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_market_list_finds_sentiment(client: TestClient) -> None:
    token = _login(client)
    resp = client.get("/api/v1/plugins/market", headers=_auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] >= 1
    ids = [item["plugin_id"] for item in data["items"]]
    assert "sentiment" in ids


def test_market_list_filter_kind(client: TestClient) -> None:
    token = _login(client)
    resp = client.get(
        "/api/v1/plugins/market?kind=official", headers=_auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    for item in resp.json()["data"]["items"]:
        assert item["kind"] == "official"


def test_market_detail_unknown_404(client: TestClient) -> None:
    token = _login(client)
    resp = client.get(
        "/api/v1/plugins/market/not_exist", headers=_auth_headers(token)
    )
    assert resp.status_code == 404, resp.text


def test_market_detail_known(client: TestClient) -> None:
    token = _login(client)
    resp = client.get(
        "/api/v1/plugins/market/sentiment", headers=_auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["plugin_id"] == "sentiment"
    assert data["state"] in ("installed", "enabled", "disabled")
    assert data["registered"] is not None


def test_install_enable_disable_uninstall(client: TestClient) -> None:
    token = _login(client)
    h = _auth_headers(token)

    # 安装（建表 + 激活）
    resp = client.post("/api/v1/plugins/market/sentiment/install", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["state"] == "enabled"
    assert data["tables"], "安装后应有插件表清单"
    assert "os_sentiment_" in data["tables"][0]

    # 重复安装冲突
    resp = client.post("/api/v1/plugins/market/sentiment/install", headers=h)
    assert resp.status_code == 409, resp.text

    # 禁用
    resp = client.post("/api/v1/plugins/market/sentiment/disable", headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["state"] == "disabled"

    # 启用
    resp = client.post("/api/v1/plugins/market/sentiment/enable", headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["state"] == "enabled"

    # 卸载
    resp = client.post("/api/v1/plugins/market/sentiment/uninstall", headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["state"] == "uninstalled"


def test_market_requires_permission(client: TestClient) -> None:
    """未登录访问应被拒（401）。"""
    resp = client.get("/api/v1/plugins/market")
    assert resp.status_code == 401, resp.text
