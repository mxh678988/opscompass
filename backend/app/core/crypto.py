"""敏感字段加解密：数据源密码等以密文落库。"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    """由 SECRET_KEY 派生出稳定的对称密钥。"""
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plain: str) -> str:
    """明文 -> 密文（URL 安全的 base64 字符串）。"""
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """密文 -> 明文；密文非法时返回空串，不抛出。"""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
