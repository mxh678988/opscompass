"""M8 全链路验证：内核加载插件 backend → 注入引擎 → 监督建表 → 门面调用。

覆盖链路：
1. 清单校验：entry 声明合法且被 registry 解析
2. 内核加载：PluginRuntime.load_backend 按 entry 动态加载插件 backend，
   register(runtime) 把 create_for_plugin 注入内核
3. 监督建表：provision_tables 在插件自有 metadata 上 create_all 12 张表
4. 门面调用：activate 后 ctx.sentiment.* 经内核会话工厂真实落库
5. 签名 + storage 门面：注入签名服务后 verify 可用；storage 自动装配读写
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.plugin.registry import PluginRegistry
from app.core.plugin.runtime import PluginRuntime

REAL_PLUGIN_SRC = Path(__file__).resolve().parents[2] / "plugins" / "sentiment"


@pytest.fixture()
def plugins_dir(tmp_path: Path) -> Path:
    """把真实 sentiment 插件复制到临时目录，测试不污染项目仓库。"""
    dest = tmp_path / "plugins"
    shutil.copytree(REAL_PLUGIN_SRC, dest / "sentiment")
    return dest


@pytest.fixture()
def session_factory() -> object:
    """sqlite 内存库会话工厂：单连接复用，供插件表与门面调用共用。"""
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def factory():
        return maker()

    return factory


def _runtime(plugins_dir: Path, session_factory, **kwargs) -> PluginRuntime:
    registry = PluginRegistry(plugins_dir)
    runtime = PluginRuntime(registry, session_factory=session_factory, **kwargs)
    return runtime


def test_manifest_entry_declared_and_parsed(plugins_dir: Path) -> None:
    """清单 entry 声明合法，registry 解析后 meta.entry 就绪。"""
    registry = PluginRegistry(plugins_dir)
    assert registry.discover() == ["sentiment"]
    meta = registry.register("sentiment")
    assert meta.entry == "backend.src.main:register"


def test_load_backend_injects_sentiment_engine(plugins_dir: Path, session_factory) -> None:
    """内核按 entry 加载插件 backend，register 注入引擎成功。"""
    runtime = _runtime(plugins_dir, session_factory)
    runtime.load_all()

    assert runtime._sentiment_engine is None
    mod = runtime.load_backend("sentiment")
    assert mod is not None
    assert runtime._sentiment_engine is not None  # 已由 register 注入

    # 幂等：二次加载复用缓存，不重复执行注册
    assert runtime.load_backend("sentiment") is mod


def test_provision_tables_creates_12_plugin_tables(plugins_dir: Path, session_factory) -> None:
    """内核监督建表：12 张 os_sentiment_* 表全部落库。"""
    runtime = _runtime(plugins_dir, session_factory)
    runtime.load_all()
    runtime.load_backend("sentiment")

    tables = runtime.provision_tables("sentiment")
    assert len(tables) == 12
    assert all(t.startswith("os_sentiment_") for t in tables)
    assert "os_sentiment_topic" in tables
    assert "os_sentiment_alert" in tables
    assert "os_sentiment_report" in tables


def test_full_chain_sentiment_facade_persists(plugins_dir: Path, session_factory) -> None:
    """全链路：注册→加载→建表→激活→ctx.sentiment 门面真实落库。"""
    runtime = _runtime(plugins_dir, session_factory)
    runtime.load_all()
    runtime.load_backend("sentiment")
    runtime.provision_tables("sentiment")

    ctx = runtime.activate("sentiment")
    assert runtime.active_plugins == ["sentiment"]

    # 建主题 → 建数据源 → 模拟采集 → 情感分析
    topic = ctx.sentiment.create_topic(
        name="新品上市", keywords=["新品", "上市"], brand_entities=["LAOMENG"]
    )
    topic_id = topic["id"]
    assert topic_id

    source = ctx.sentiment.create_source(
        topic_id=topic_id, source_type="weibo", endpoint="https://api.weibo.com"
    )
    source_id = source["id"]
    assert source_id

    collected = ctx.sentiment.monitor(
        topic_id=topic_id,
        source_id=source_id,
        texts=["新品上市很好用，推荐！", "这次新品太差了，失望。"],
    )
    assert collected.get("inserted", 0) >= 2, collected

    item_id = collected["item_ids"][0]
    analyzed = ctx.sentiment.analyze(item_id=item_id)
    assert analyzed.get("item_id") == item_id
    assert analyzed.get("polarity") in {"positive", "negative", "neutral"}

    analytics = ctx.sentiment.get_analytics(topic_id=topic_id, period="7d")
    assert analytics.get("topic_id") == topic_id

    runtime.deactivate("sentiment")
    assert runtime.active_plugins == []


def test_signing_and_storage_facades(plugins_dir: Path, session_factory) -> None:
    """签名门面注入后 verify 可用；storage 门面自动装配读写可用。"""
    class FakeSigningService:
        def verify_plugin(self, plugin_dir, plugin_id):
            return "ok", "指纹一致"

        def get_fingerprint(self, plugin_id):
            return "fp-sha256-abc123"

    runtime = _runtime(plugins_dir, session_factory, signing_service=FakeSigningService())
    runtime.load_all()
    runtime.load_backend("sentiment")
    runtime.provision_tables("sentiment")

    ctx = runtime.activate("sentiment")

    verify = ctx.signing.verify_self()
    assert verify["verified"] is True
    assert ctx.signing.key_fingerprint() == "fp-sha256-abc123"

    # storage 门面：registry.plugins_dir 存在时自动装配（M5）
    path = "reports/daily.md"
    ctx.storage.save(path=path, data="# 舆情日报")
    assert ctx.storage.read(path=path) == "# 舆情日报"
    assert "reports/daily.md" in [p for p in ctx.storage.list(prefix="reports")]
    ctx.storage.delete(path=path)
    with pytest.raises(FileNotFoundError):
        ctx.storage.read(path=path)


def test_missing_session_factory_blocks_provision(plugins_dir: Path) -> None:
    """未注入 session_factory 时建表被内核拒绝。"""
    registry = PluginRegistry(plugins_dir)
    runtime = PluginRuntime(registry)
    runtime.load_all()
    runtime.load_backend("sentiment")
    with pytest.raises(RuntimeError, match="session_factory"):
        runtime.provision_tables("sentiment")
