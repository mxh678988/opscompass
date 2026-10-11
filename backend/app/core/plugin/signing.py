"""插件签名密钥体系（M7）：Ed25519 签名、公钥注册、发布包验签。

设计要点：
- 签名算法：Ed25519（RFC 8032）。私钥仅存在于插件作者侧，内核只持有公钥，
  私钥泄漏不影响内核，吊销公钥即可止损；
- 发布包签名：对 plugin.yaml 与包内全部文件做规范化 SHA-256 哈希清单后整体签名，
  ``.sig`` 文件内嵌算法、公钥指纹、文件哈希清单与签名值，篡改任意文件即验签失败；
- 公钥管理：内核按 ``plugin_id`` 登记公钥（fingerprint 唯一），支持吊销与轮换；
  official 插件激活前强制验签，community 插件登记公钥后同样可验；
- 纯函数（generate/sign/verify/fingerprint）不依赖 DB，可在构建期或管理脚本中使用；
  ``PluginSigningService`` 依赖会话工厂读写 ``oc_core_plugin_key``。

范式与 M4-M6 一致：内核模块接收 ``db`` Session（由门面/运行时注入会话工厂），
单测以 SQLite 内存库 + 仅建所需表直接执行。
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.models.plugin import CorePluginKey

SIG_FILE_NAME = ".sig"
SIG_ALGO = "ed25519"

# 验签状态常量
VERIFY_OK = "ok"
VERIFY_FAILED = "failed"
VERIFY_NO_SIGNATURE = "no_signature"

# 公钥生命周期
KEY_STATE_ENABLED = "enabled"
KEY_STATE_REVOKED = "revoked"

# 打包时需要排除的目录/文件（版本控制、缓存、签名文件自身）
_EXCLUDE_PARTS = {".git", "__pycache__", ".pytest_cache", ".DS_Store", "node_modules"}


def generate_keypair() -> tuple[str, str]:
    """生成 Ed25519 密钥对，返回 (私钥 PEM, 公钥 PEM)。

    私钥以 PKCS8 + NoEncryption PEM 输出，调用方负责落盘与保管；
    公钥随插件包提交或经管理接口登记进内核。
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def _load_private_key(private_key_pem: str) -> ed25519.Ed25519PrivateKey:
    key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None
    )
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise TypeError("私钥不是 Ed25519 密钥")
    return key


def _load_public_key(public_key_pem: str) -> ed25519.Ed25519PublicKey:
    key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise TypeError("公钥不是 Ed25519 密钥")
    return key


def _public_pem_from_private(private_key_pem: str) -> str:
    return (
        _load_private_key(private_key_pem)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


def fingerprint_public_key(public_key_pem: str) -> str:
    """公钥指纹：SHA-256(SubjectPublicKeyInfo DER)，64 位十六进制。"""
    der = _load_public_key(public_key_pem).public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def _package_files(plugin_dir: Path) -> list[Path]:
    """包内文件清单（按相对路径字典序）：排除 .sig 与版本控制/缓存目录。"""
    files: list[Path] = []
    for p in sorted(plugin_dir.rglob("*")):
        if not p.is_file() or p.name == SIG_FILE_NAME:
            continue
        rel = p.relative_to(plugin_dir)
        if any(part in _EXCLUDE_PARTS for part in rel.parts):
            continue
        files.append(p)
    return files


def _file_hashes(plugin_dir: Path) -> dict[str, str]:
    """规范化文件哈希清单：相对路径（正斜杠）→ SHA-256。"""
    return {
        str(p.relative_to(plugin_dir)).replace("\\", "/"): hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
        for p in _package_files(plugin_dir)
    }


def _canonical_payload(files: dict[str, str]) -> bytes:
    """规范化的待签串：文件哈希清单按 key 排序的紧凑 JSON。"""
    return json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_plugin_dir(plugin_dir: Path, private_key_pem: str) -> Path:
    """对插件发布包签名，写出 ``.sig`` 文件，返回其路径。

    签名覆盖 plugin.yaml 与包内全部文件（哈希清单整体签名）；
    重复签名会覆盖旧 ``.sig``。
    """
    plugin_dir = Path(plugin_dir)
    if not (plugin_dir / "plugin.yaml").exists():
        raise FileNotFoundError(f"缺少 plugin.yaml: {plugin_dir}")
    files = _file_hashes(plugin_dir)
    payload = _canonical_payload(files)
    signature = _load_private_key(private_key_pem).sign(payload)
    sig_doc = {
        "algo": SIG_ALGO,
        "fingerprint": fingerprint_public_key(_public_pem_from_private(private_key_pem)),
        "files": files,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    sig_path = plugin_dir / SIG_FILE_NAME
    sig_path.write_text(
        json.dumps(sig_doc, indent=2, sort_keys=True), encoding="utf-8"
    )
    return sig_path


def verify_plugin_dir(plugin_dir: Path, public_key_pem: str) -> tuple[str, str]:
    """验签插件发布包，返回 (status, message)。

    status ∈ VERIFY_OK / VERIFY_FAILED / VERIFY_NO_SIGNATURE；
    校验顺序：.sig 存在 → 解析 → 算法/指纹匹配 → 签名有效 → 包内容与签名一致。
    """
    plugin_dir = Path(plugin_dir)
    sig_path = plugin_dir / SIG_FILE_NAME
    if not sig_path.exists():
        return VERIFY_NO_SIGNATURE, f"缺少签名文件 {SIG_FILE_NAME}"
    try:
        sig_doc = json.loads(sig_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return VERIFY_FAILED, f"{SIG_FILE_NAME} 解析失败"
    if not isinstance(sig_doc, dict):
        return VERIFY_FAILED, f"{SIG_FILE_NAME} 格式错误"
    if sig_doc.get("algo") != SIG_ALGO:
        return VERIFY_FAILED, f"签名算法不匹配: {sig_doc.get('algo')!r}"
    if str(sig_doc.get("fingerprint", "")) != fingerprint_public_key(public_key_pem):
        return VERIFY_FAILED, "公钥指纹不匹配"
    payload = _canonical_payload(sig_doc.get("files") or {})
    try:
        signature = base64.b64decode(str(sig_doc.get("signature", "")))
        _load_public_key(public_key_pem).verify(signature, payload)
    except (InvalidSignature, ValueError, TypeError):
        return VERIFY_FAILED, "签名无效"
    if _file_hashes(plugin_dir) != sig_doc.get("files"):
        return VERIFY_FAILED, "包内容与签名不一致（文件被篡改）"
    return VERIFY_OK, "签名有效"


class PluginSigningService:
    """插件签名服务：登记/吊销插件公钥，并按登记公钥验签发布包。

    依赖 ``session_factory`` 访问 ``oc_core_plugin_key``；未注入会话工厂时，
    登记/查询类操作抛 ``RuntimeError``（纯函数能力 generate/sign/verify 始终可用）。
    """

    def __init__(
        self, session_factory: Optional[Any] = None
    ) -> None:
        self._session_factory = session_factory

    def _db(self) -> Any:
        if self._session_factory is None:
            raise RuntimeError("签名服务未注入会话工厂，无法访问公钥注册表")
        return self._session_factory()

    # ---- 公钥管理 ----

    def register_public_key(
        self,
        plugin_id: str,
        public_key_pem: str,
        *,
        reason: Optional[str] = None,
    ) -> str:
        """登记/轮换插件公钥，返回指纹。

        同一插件已存在 enabled 公钥时：指纹相同则幂等返回；不同则吊销旧钥
        并登记新钥（轮换），``reason`` 记录轮换/覆盖原因。
        """
        fp = fingerprint_public_key(public_key_pem)
        db = self._db()
        try:
            row = (
                db.query(CorePluginKey)
                .filter_by(plugin_id=plugin_id, key_state=KEY_STATE_ENABLED)
                .first()
            )
            if row is not None:
                if row.fingerprint == fp:
                    return fp
                row.key_state = KEY_STATE_REVOKED
                row.revoked_at = datetime.now(timezone.utc)
                row.revoked_reason = reason or "key rotation"
            db.add(
                CorePluginKey(
                    plugin_id=plugin_id,
                    public_key=public_key_pem,
                    fingerprint=fp,
                    key_state=KEY_STATE_ENABLED,
                )
            )
            db.commit()
            return fp
        finally:
            db.close()

    def get_fingerprint(self, plugin_id: str) -> Optional[str]:
        """查询插件当前启用公钥的指纹；未登记返回 None。"""
        db = self._db()
        try:
            row = (
                db.query(CorePluginKey)
                .filter_by(plugin_id=plugin_id, key_state=KEY_STATE_ENABLED)
                .first()
            )
            return row.fingerprint if row is not None else None
        finally:
            db.close()

    def get_public_key(self, plugin_id: str) -> Optional[str]:
        """查询插件当前启用公钥 PEM；未登记返回 None。"""
        db = self._db()
        try:
            row = (
                db.query(CorePluginKey)
                .filter_by(plugin_id=plugin_id, key_state=KEY_STATE_ENABLED)
                .first()
            )
            return row.public_key if row is not None else None
        finally:
            db.close()

    def revoke_key(self, plugin_id: str, reason: str) -> bool:
        """吊销插件当前启用公钥，返回是否吊销成功（有 enabled 公钥才 True）。"""
        db = self._db()
        try:
            row = (
                db.query(CorePluginKey)
                .filter_by(plugin_id=plugin_id, key_state=KEY_STATE_ENABLED)
                .first()
            )
            if row is None:
                return False
            row.key_state = KEY_STATE_REVOKED
            row.revoked_at = datetime.now(timezone.utc)
            row.revoked_reason = reason
            db.commit()
            return True
        finally:
            db.close()

    # ---- 验签 ----

    def verify_plugin(self, plugin_dir: Path, plugin_id: str) -> tuple[str, str]:
        """按插件已登记公钥验签发布包；未登记公钥返回 failed 并说明。"""
        public_key_pem = self.get_public_key(plugin_id)
        if public_key_pem is None:
            return VERIFY_FAILED, f"插件 {plugin_id} 未登记公钥，无法验签"
        return verify_plugin_dir(plugin_dir, public_key_pem)
