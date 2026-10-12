"""OS 内核 · 插件运行时与 SDK 测试（M2）。

覆盖：
- 清单校验：合法清单、非法 id/entry、命名空间冲突、内核版本门槛
- 注册表：发现 → 注册 → 启用/禁用/卸载，非法状态转换拦截
- SDK 门面：事件命名空间越界、表前缀越界、配置分区隔离、未落地能力分期提示
- 运行时：能力装配、声明收集、坏插件不阻断好插件
- S3 强制验签：官方插件启用前验签，失败拒绝（403 语义），社区插件不强制

无外部依赖，直接执行：``pytest tests/test_plugin_runtime.py -v``。
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.plugin.manifest_validator import validate_manifest
from app.core.plugin.registry import PluginRegistry, PluginState
from app.core.plugin.runtime import PluginRuntime
from app.core.plugin.signing import (
    PluginSigningService,
    PluginVerificationError,
    generate_keypair,
    sign_plugin_dir,
)
from app.models.base import Base
from app.models.plugin import CorePluginKey
from app.sdk.context import PluginNamespace, create_context
from app.sdk.exceptions import NamespaceViolation, NotAvailableError

GOOD_MANIFEST = """\
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
events:
  publish:
    - sentiment.task.created
  subscribe:
    - core.metric.written
"""

OFFICIAL_MANIFEST = """\
id: official_guard
name: 官方守门插件
version: 0.1.0
kind: official
min_kernel_version: 0.11.0
entry: main:register
namespace:
  tables: os_guard_
  events: "guard."
  permissions: "guard:"
"""

BROKEN_MANIFEST = """\
id: Core_Bad
version: 0.1
entry: not-an-entry
namespace:
  tables: bad_prefix_
  events: bad_event
"""


@pytest.fixture()
def plugins_dir(tmp_path: Path) -> Path:
    """构造含一个合法插件、一个非法插件的插件目录。"""
    root = tmp_path / "plugins"
    (root / "sentiment").mkdir(parents=True)
    (root / "sentiment" / "plugin.yaml").write_text(GOOD_MANIFEST, encoding="utf-8")
    (root / "broken").mkdir(parents=True)
    (root / "broken" / "plugin.yaml").write_text(BROKEN_MANIFEST, encoding="utf-8")
    return root


@pytest.fixture()
def official_plugin_dir(tmp_path: Path) -> Path:
    """构造一个可签名的官方插件发布包目录（kind=official）。"""
    root = tmp_path / "official_guard"
    (root / "backend").mkdir(parents=True)
    (root / "backend" / "main.py").write_text("def register(ctx): pass\n", encoding="utf-8")
    (root / "plugin.yaml").write_text(OFFICIAL_MANIFEST, encoding="utf-8")
    return root


@pytest.fixture()
def session_factory():
    """SQLite 内存库 + 仅建公钥注册表。"""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[CorePluginKey.__table__])
    maker = sessionmaker(bind=engine)
    return maker


class StubBus:
    """测试用事件总线。"""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []
        self.subscribed: list[str] = []

    def publish(self, name: str, payload: dict, **kwargs) -> str:
        self.published.append((name, payload))
        return f"evt-{len(self.published)}"

    def subscribe(self, name: str, handler, **kwargs):
        self.subscribed.append(name)
        return handler


class DictConfigStore:
    """测试用配置存储（内存字典）。"""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], object] = {}

    def get(self, plugin_id: str, key: str, default=None):
        return self._data.get((plugin_id, key), default)

    def set(self, plugin_id: str, key: str, value) -> None:
        self._data[(plugin_id, key)] = value

    def all(self, plugin_id: str) -> dict:
        return {k: v for (pid, k), v in self._data.items() if pid == plugin_id}


# ---------------- 清单校验 ----------------


def test_manifest_valid(plugins_dir: Path) -> None:
    result = validate_manifest(plugins_dir / "sentiment" / "plugin.yaml")
    assert result.valid, [e.detail for e in result.errors]


def test_manifest_invalid_fields(plugins_dir: Path) -> None:
    result = validate_manifest(plugins_dir / "broken" / "plugin.yaml")
    assert not result.valid
    fields = {e.field for e in result.errors}
    assert "id" in fields
    assert "version" in fields
    assert "entry" in fields
    assert "namespace.tables" in fields
    assert "namespace.events" in fields


def test_manifest_namespace_conflict(plugins_dir: Path) -> None:
    result = validate_manifest(
        plugins_dir / "sentiment" / "plugin.yaml",
        existing_table_prefixes={"os_sentiment_"},
        existing_event_prefixes={"sentiment."},
    )
    assert not result.valid
    details = " ".join(e.detail for e in result.errors)
    assert "已被占用" in details


def test_manifest_min_kernel_version(plugins_dir: Path) -> None:
    result = validate_manifest(
        plugins_dir / "sentiment" / "plugin.yaml", kernel_version="0.10.0"
    )
    assert not result.valid
    assert any(e.field == "min_kernel_version" for e in result.errors)


# ---------------- 注册表与生命周期 ----------------


def test_registry_discover_and_lifecycle(plugins_dir: Path) -> None:
    registry = PluginRegistry(plugins_dir)
    assert registry.discover() == ["sentiment"]  # broken 被过滤

    meta = registry.register("sentiment")
    assert meta.state is PluginState.INSTALLED
    assert meta.namespace["tables"] == "os_sentiment_"

    registry.enable("sentiment")
    assert registry.get("sentiment").state is PluginState.ENABLED

    registry.disable("sentiment")
    assert registry.get("sentiment").state is PluginState.DISABLED

    registry.enable("sentiment")
    registry.uninstall("sentiment")
    assert registry.get("sentiment") is None


def test_registry_invalid_transitions(plugins_dir: Path) -> None:
    registry = PluginRegistry(plugins_dir)
    registry.register("sentiment")

    with pytest.raises(RuntimeError):
        registry.disable("sentiment")  # installed 不能直接禁用

    registry.enable("sentiment")
    with pytest.raises(RuntimeError):
        registry.enable("sentiment")  # 重复启用

    with pytest.raises(KeyError):
        registry.enable("not-exist")


def test_registry_reports_manifest_errors(plugins_dir: Path) -> None:
    registry = PluginRegistry(plugins_dir)
    registry.discover()
    assert "broken" in registry.errors
    with pytest.raises(RuntimeError):
        registry.register("broken")


# ---------------- SDK 门面 ----------------


def _context(**kwargs):
    ns = PluginNamespace(tables="os_sentiment_", events="sentiment.", permissions="sentiment:")
    return create_context(plugin_id="sentiment", plugin_version="0.1.0", namespace=ns, **kwargs)


def test_bus_facade_guards_namespace() -> None:
    stub = StubBus()
    ctx = _context(publish_fn=stub.publish, subscribe_fn=stub.subscribe)

    event_id = ctx.bus.publish("sentiment.task.created", {"id": 1})
    assert event_id == "evt-1"
    assert stub.published[0][0] == "sentiment.task.created"

    ctx.bus.subscribe("core.metric.written", lambda e: None)
    ctx.bus.subscribe("sentiment.task.created", lambda e: None)
    assert stub.subscribed == ["core.metric.written", "sentiment.task.created"]

    with pytest.raises(NamespaceViolation):
        ctx.bus.publish("billing.invoice.created")
    with pytest.raises(NamespaceViolation):
        ctx.bus.subscribe("billing.invoice.created", lambda e: None)


def test_db_facade_guards_table() -> None:
    ctx = _context()
    ctx.db.assert_table("os_sentiment_task")  # 合法
    with pytest.raises(NamespaceViolation):
        ctx.db.assert_table("oc_user")  # 内核/业务表


def test_config_facade_partition() -> None:
    store = DictConfigStore()
    store.set("billing", "token", "secret")

    ctx = _context(config_store=store)
    assert ctx.config.get("token") is None  # 插件间配置隔离
    ctx.config.set("token", "sentiment-token")
    assert ctx.config.get("token") == "sentiment-token"
    assert ctx.config.all() == {"token": "sentiment-token"}


def test_unavailable_capabilities_report_phase() -> None:
    ctx = _context()
    # M3 已落地鉴权门面：内核未注入鉴权回调时仍显式报错，插件不得以为已受控
    with pytest.raises(NotAvailableError) as e1:
        ctx.auth.require("sentiment:task:create")
    assert e1.value.planned_in == "M3 装配完成"

    with pytest.raises(NotAvailableError) as e2:
        ctx.task.create("复核预警")
    assert e2.value.planned_in == "M4 装配完成"

    with pytest.raises(NotAvailableError) as e3:
        ctx.model.run("emotion.classify", {"text": "x"})
    assert e3.value.planned_in == "M6 装配完成"


def test_declarations_and_log() -> None:
    ctx = _context()
    ctx.log.info("插件就绪")  # 不抛异常即通过
    ctx.job.register("collect", "*/10 * * * *", lambda: None)
    ctx.ui.register_menu("/sentiment", "舆情监测", "radar")
    ctx.ui.register_route("/sentiment/list", "SentimentList")

    decl = ctx.declarations()
    assert decl["jobs"][0]["id"] == "collect"
    assert decl["menus"][0]["path"] == "/sentiment"
    assert decl["routes"][0]["component"] == "SentimentList"


# ---------------- 运行时装配 ----------------


def test_runtime_activate_assigns_capabilities(plugins_dir: Path) -> None:
    registry = PluginRegistry(plugins_dir)
    stub_bus = StubBus()
    store = DictConfigStore()
    runtime = PluginRuntime(registry, bus=stub_bus, config_store=store)

    assert runtime.load_all() == ["sentiment"]

    ctx = runtime.activate("sentiment")
    assert runtime.active_plugins == ["sentiment"]

    # 事件走内核总线，命名空间校验由 SDK 门面把关
    ctx.bus.publish("sentiment.task.created", {"id": 9})
    assert stub_bus.published[-1][0] == "sentiment.task.created"

    # 配置落到同一分区
    ctx.config.set("threshold", 0.8)
    assert store.get("sentiment", "threshold") == 0.8

    runtime.deactivate("sentiment")
    assert runtime.active_plugins == []
    assert runtime.context("sentiment") is None


def test_runtime_broken_plugin_does_not_block(plugins_dir: Path) -> None:
    registry = PluginRegistry(plugins_dir)
    runtime = PluginRuntime(registry, bus=StubBus(), config_store=DictConfigStore())

    assert runtime.load_all() == ["sentiment"]


# ---------------- S3 官方插件强制验签 ----------------


def test_activate_official_plugin_requires_signature_service(
    official_plugin_dir: Path,
) -> None:
    """官方插件启用时未装配签名服务：拒绝启用（403 语义），绝不降级放行。"""
    registry = PluginRegistry(official_plugin_dir.parent)
    registry.register("official_guard")
    runtime = PluginRuntime(registry, bus=StubBus(), config_store=DictConfigStore())

    with pytest.raises(PluginVerificationError) as e:
        runtime.activate("official_guard")
    assert "未装配签名服务" in str(e.value)
    assert runtime.active_plugins == []  # 未被启用


def test_activate_official_plugin_unregistered_key_rejected(
    official_plugin_dir: Path, session_factory
) -> None:
    """官方插件已签名但公钥未登记：验签失败，拒绝启用。"""
    private_pem, _ = generate_keypair()
    sign_plugin_dir(official_plugin_dir, private_pem)

    registry = PluginRegistry(official_plugin_dir.parent)
    registry.register("official_guard")
    service = PluginSigningService(session_factory)  # 未登记任何公钥
    runtime = PluginRuntime(
        registry, bus=StubBus(), config_store=DictConfigStore(), signing_service=service
    )

    with pytest.raises(PluginVerificationError) as e:
        runtime.activate("official_guard")
    assert "验签失败" in str(e.value)
    assert "未登记公钥" in str(e.value)
    assert runtime.active_plugins == []


def test_activate_official_plugin_unsigned_rejected(
    official_plugin_dir: Path, session_factory
) -> None:
    """官方插件未签名（无 .sig）：拒绝启用。"""
    private_pem, public_pem = generate_keypair()
    # 故意不调用 sign_plugin_dir —— 无 .sig
    service = PluginSigningService(session_factory)
    service.register_public_key("official_guard", public_pem)

    registry = PluginRegistry(official_plugin_dir.parent)
    registry.register("official_guard")
    runtime = PluginRuntime(
        registry, bus=StubBus(), config_store=DictConfigStore(), signing_service=service
    )

    with pytest.raises(PluginVerificationError) as e:
        runtime.activate("official_guard")
    assert "验签失败" in str(e.value)
    assert runtime.active_plugins == []


def test_activate_official_plugin_signed_ok(
    official_plugin_dir: Path, session_factory
) -> None:
    """官方插件签名有效且公钥已登记：正常启用。"""
    private_pem, public_pem = generate_keypair()
    sign_plugin_dir(official_plugin_dir, private_pem)
    service = PluginSigningService(session_factory)
    service.register_public_key("official_guard", public_pem)

    registry = PluginRegistry(official_plugin_dir.parent)
    registry.register("official_guard")
    runtime = PluginRuntime(
        registry, bus=StubBus(), config_store=DictConfigStore(), signing_service=service
    )

    ctx = runtime.activate("official_guard")
    assert runtime.active_plugins == ["official_guard"]
    assert ctx is not None


def test_activate_official_plugin_tampered_rejected(
    official_plugin_dir: Path, session_factory
) -> None:
    """官方插件签名后内容被篡改：验签失败，拒绝启用。"""
    private_pem, public_pem = generate_keypair()
    sign_plugin_dir(official_plugin_dir, private_pem)
    service = PluginSigningService(session_factory)
    service.register_public_key("official_guard", public_pem)

    # 签名后篡改 backend 源码
    (official_plugin_dir / "backend" / "main.py").write_text(
        "def register(ctx): raise RuntimeError('tampered')\n", encoding="utf-8"
    )

    registry = PluginRegistry(official_plugin_dir.parent)
    registry.register("official_guard")
    runtime = PluginRuntime(
        registry, bus=StubBus(), config_store=DictConfigStore(), signing_service=service
    )

    with pytest.raises(PluginVerificationError) as e:
        runtime.activate("official_guard")
    assert "验签失败" in str(e.value)
    assert runtime.active_plugins == []


def test_activate_community_plugin_not_forced(plugins_dir: Path) -> None:
    """社区插件不强制验签：未装配签名服务也能正常启用（原有行为保持）。"""
    registry = PluginRegistry(plugins_dir)
    registry.register("sentiment")
    runtime = PluginRuntime(registry, bus=StubBus(), config_store=DictConfigStore())

    runtime.activate("sentiment")  # 不应抛 PluginVerificationError
    assert runtime.active_plugins == ["sentiment"]


def test_model_facade_assembled_forwards_to_router() -> None:
    """M6 模型路由装配：注入 router + session_factory 后 run/declare/stats 转发内核。"""
    calls: list[str] = []

    class FakeRouter:
        def route_model(self, db, capability, input, **opts):
            calls.append(f"route_model:{capability}")
            assert db is not None
            return {"mode": "local", "model": "llama", "text": "ok"}

        def upsert_capability(self, db, **opts):
            calls.append(f"upsert:{opts['capability']}")
            return object()

        def route_log_stats(self, db, **opts):
            calls.append("stats")
            return {"total": 0}

        def is_degraded(self):
            calls.append("is_degraded")
            return False

    closed = []

    def session_factory():
        class _S:
            def close(self):
                closed.append(1)

        return _S()

    runtime = PluginRuntime(
        PluginRegistry(Path(".")),
        session_factory=session_factory,
        model_router=FakeRouter(),
    )
    ctx = create_context(
        plugin_id="sentiment",
        plugin_version="0.1.0",
        session_factory=session_factory,
        model_router=FakeRouter(),
    )
    res = ctx.model.run("emotion.classify", {"text": "x"}, tenant_id=1)
    assert res["mode"] == "local"
    assert calls[0] == "route_model:emotion.classify"
    ctx.model.declare(capability="emotion.classify", sensitive=False)
    assert calls[1] == "upsert:emotion.classify"
    assert ctx.model.stats(capability="emotion.classify") == {"total": 0}
    assert ctx.model.is_degraded() is False
    assert len(closed) == 3  # run/declare/stats 各自打开并关闭会话
    assert "broken" not in runtime.registry.plugins
