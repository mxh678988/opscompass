"""OS 内核 · 插件签名密钥体系测试（M7）。

覆盖：
- 密钥生成：Ed25519 PEM 密钥对
- 发布包签名/验签：正常通过、无 .sig、算法/指纹不匹配、内容被篡改、签名无效
- 公钥注册表：登记、幂等、轮换、吊销、指纹查询
- SDK signing 门面：未装配分期提示、装配后转发
- 运行时装配：注入签名服务后 ctx.signing.verify_self() 可用

无外部依赖，直接执行：``pytest tests/test_plugin_signing.py -v``。
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.plugin.registry import PluginRegistry
from app.core.plugin.runtime import PluginRuntime
from app.core.plugin.signing import (
    PluginSigningService,
    VERIFY_FAILED,
    VERIFY_NO_SIGNATURE,
    VERIFY_OK,
    fingerprint_public_key,
    generate_keypair,
    sign_plugin_dir,
    verify_plugin_dir,
)
from app.models.base import Base
from app.models.plugin import CorePluginKey
from app.sdk.context import PluginNamespace, create_context
from app.sdk.exceptions import NotAvailableError

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
"""


@pytest.fixture()
def plugin_dir(tmp_path: Path) -> Path:
    """构造一个可签名的插件发布包目录。"""
    root = tmp_path / "sentiment"
    (root / "backend").mkdir(parents=True)
    (root / "backend" / "main.py").write_text("def register(ctx): pass\n", encoding="utf-8")
    (root / "plugin.yaml").write_text(GOOD_MANIFEST, encoding="utf-8")
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


# ---------------- 密钥生成与指纹 ----------------


def test_generate_keypair_returns_pem() -> None:
    private_pem, public_pem = generate_keypair()
    assert "PRIVATE KEY" in private_pem
    assert "PUBLIC KEY" in public_pem


def test_fingerprint_stable_and_unique() -> None:
    _, pub1 = generate_keypair()
    _, pub2 = generate_keypair()
    fp1 = fingerprint_public_key(pub1)
    assert fp1 == fingerprint_public_key(pub1)  # 同钥指纹稳定
    assert len(fp1) == 64
    assert fp1 != fingerprint_public_key(pub2)  # 异钥指纹不同


# ---------------- 签名与验签 ----------------


def test_sign_and_verify_ok(plugin_dir: Path) -> None:
    private_pem, public_pem = generate_keypair()
    sig_path = sign_plugin_dir(plugin_dir, private_pem)
    assert sig_path.name == ".sig"
    assert sig_path.exists()

    status, message = verify_plugin_dir(plugin_dir, public_pem)
    assert status == VERIFY_OK
    assert "签名有效" in message


def test_verify_missing_signature(plugin_dir: Path) -> None:
    _, public_pem = generate_keypair()
    status, message = verify_plugin_dir(plugin_dir, public_pem)
    assert status == VERIFY_NO_SIGNATURE
    assert ".sig" in message


def test_verify_wrong_key_fails(plugin_dir: Path) -> None:
    private_pem, _ = generate_keypair()
    _, other_public = generate_keypair()
    sign_plugin_dir(plugin_dir, private_pem)

    status, message = verify_plugin_dir(plugin_dir, other_public)
    assert status == VERIFY_FAILED
    assert "公钥指纹不匹配" in message


def test_verify_tampered_file_fails(plugin_dir: Path) -> None:
    private_pem, public_pem = generate_keypair()
    sign_plugin_dir(plugin_dir, private_pem)

    (plugin_dir / "backend" / "main.py").write_text("def register(ctx): raise\n", encoding="utf-8")
    status, message = verify_plugin_dir(plugin_dir, public_pem)
    assert status == VERIFY_FAILED
    assert "被篡改" in message


def test_verify_tampered_signature_fails(plugin_dir: Path) -> None:
    private_pem, public_pem = generate_keypair()
    sig_path = sign_plugin_dir(plugin_dir, private_pem)

    content = sig_path.read_text(encoding="utf-8")
    sig_path.write_text(content.replace("signature", "sigXX"), encoding="utf-8")
    status, message = verify_plugin_dir(plugin_dir, public_pem)
    assert status == VERIFY_FAILED
    assert "签名无效" in message


# ---------------- 公钥注册表服务 ----------------


def test_register_and_query_fingerprint(session_factory) -> None:
    _, public_pem = generate_keypair()
    service = PluginSigningService(session_factory)

    fp = service.register_public_key("sentiment", public_pem)
    assert service.get_fingerprint("sentiment") == fp
    assert service.get_public_key("sentiment") == public_pem
    assert service.get_fingerprint("missing") is None


def test_register_same_key_idempotent(session_factory) -> None:
    _, public_pem = generate_keypair()
    service = PluginSigningService(session_factory)
    fp1 = service.register_public_key("sentiment", public_pem)
    fp2 = service.register_public_key("sentiment", public_pem)
    assert fp1 == fp2


def test_register_key_rotation_revokes_old(session_factory) -> None:
    _, pub1 = generate_keypair()
    _, pub2 = generate_keypair()
    service = PluginSigningService(session_factory)

    old_fp = service.register_public_key("sentiment", pub1)
    new_fp = service.register_public_key("sentiment", pub2, reason="v2 release")
    assert new_fp != old_fp
    assert service.get_fingerprint("sentiment") == new_fp  # 旧钥已吊销


def test_revoke_key(session_factory) -> None:
    _, public_pem = generate_keypair()
    service = PluginSigningService(session_factory)
    service.register_public_key("sentiment", public_pem)

    assert service.revoke_key("sentiment", "leak") is True
    assert service.get_fingerprint("sentiment") is None
    assert service.revoke_key("sentiment", "again") is False


def test_verify_plugin_uses_registered_key(plugin_dir: Path, session_factory) -> None:
    private_pem, public_pem = generate_keypair()
    sign_plugin_dir(plugin_dir, private_pem)
    service = PluginSigningService(session_factory)
    service.register_public_key("sentiment", public_pem)

    status, _ = service.verify_plugin(plugin_dir, "sentiment")
    assert status == VERIFY_OK


def test_verify_plugin_without_key_fails(plugin_dir: Path, session_factory) -> None:
    service = PluginSigningService(session_factory)
    status, message = service.verify_plugin(plugin_dir, "sentiment")
    assert status == VERIFY_FAILED
    assert "未登记公钥" in message


def test_service_without_session_factory_raises() -> None:
    service = PluginSigningService(None)
    with pytest.raises(RuntimeError):
        service.get_fingerprint("sentiment")


# ---------------- SDK signing 门面 ----------------


def _context(**kwargs):
    ns = PluginNamespace(tables="os_sentiment_", events="sentiment.", permissions="sentiment:")
    return create_context(plugin_id="sentiment", plugin_version="0.1.0", namespace=ns, **kwargs)


def test_signing_facade_unavailable_reports_m7() -> None:
    ctx = _context()
    with pytest.raises(NotAvailableError) as e1:
        ctx.signing.verify_self()
    assert e1.value.planned_in == "M7 装配完成"
    with pytest.raises(NotAvailableError) as e2:
        ctx.signing.key_fingerprint()
    assert e2.value.planned_in == "M7 装配完成"


def test_signing_facade_forwards_to_callbacks() -> None:
    calls: list[str] = []

    def verify_fn() -> dict:
        calls.append("verify")
        return {"verified": True, "status": "ok", "message": "签名有效"}

    def key_query_fn():
        calls.append("query")
        return "fp123"

    ctx = _context(signing_verify_fn=verify_fn, signing_key_query_fn=key_query_fn)
    assert ctx.signing.verify_self()["verified"] is True
    assert ctx.signing.key_fingerprint() == "fp123"
    assert calls == ["verify", "query"]


# ---------------- 运行时装配 ----------------


def test_runtime_signature_assembly(plugin_dir: Path, session_factory) -> None:
    """注入签名服务后，ctx.signing.verify_self() 可按登记公钥验签发布包。"""
    private_pem, public_pem = generate_keypair()
    sign_plugin_dir(plugin_dir, private_pem)

    registry = PluginRegistry(plugin_dir.parent)
    registry.register("sentiment")
    service = PluginSigningService(session_factory)
    service.register_public_key("sentiment", public_pem)

    runtime = PluginRuntime(registry, signing_service=service)
    ctx = runtime.build_context("sentiment")

    result = ctx.signing.verify_self()
    assert result["verified"] is True
    assert result["status"] == VERIFY_OK
    assert ctx.signing.key_fingerprint() == fingerprint_public_key(public_pem)


def test_runtime_without_signing_service_reports_m7(plugin_dir: Path, session_factory) -> None:
    registry = PluginRegistry(plugin_dir.parent)
    registry.register("sentiment")

    runtime = PluginRuntime(registry)
    ctx = runtime.build_context("sentiment")

    with pytest.raises(NotAvailableError) as e:
        ctx.signing.verify_self()
    assert e.value.planned_in == "M7 装配完成"
