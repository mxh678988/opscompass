"""安全工具：密码哈希、JWT 签发校验、角色/权限判定。"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
# bcrypt 单次只处理前 72 字节
BCRYPT_MAX_BYTES = 72


# ------------------------------------------------------------ 密码
def hash_password(password: str) -> str:
    """生成密码哈希（bcrypt，cost=12）。"""
    raw = (password or "").encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:BCRYPT_MAX_BYTES], hashed.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> Optional[str]:
    """基础强度校验，返回错误信息；通过则返回 None。"""
    min_len = settings.SECURITY_PASSWORD_MIN_LENGTH
    if not password or len(password) < min_len:
        return f"密码长度不得少于 {min_len} 位"
    kinds = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if kinds < 2:
        return "密码需包含大写字母、小写字母、数字、符号中的至少两类"
    return None


# ------------------------------------------------------------ JWT
def create_access_token(
    subject: str,
    expires_minutes: Optional[int] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """生成访问令牌。subject 传用户 ID；extra_claims 可携带非敏感声明。"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "iss": settings.PROJECT_NAME,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解析访问令牌，失败抛 jose.JWTError。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def try_decode_access_token(token: str) -> Optional[dict]:
    """宽容解析：失败返回 None（用于审计等非鉴权场景）。"""
    try:
        return decode_access_token(token)
    except JWTError:
        return None


def token_expires_in() -> int:
    """令牌有效期（秒）。"""
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


# ------------------------------------------------------- 角色 / 权限
def has_role(user: Any, role_codes: Iterable[str]) -> bool:
    """判断用户是否拥有指定角色之一（超管直接通过）。"""
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    owned = {r.code for r in (getattr(user, "roles", None) or [])}
    return bool(owned & set(role_codes))


def collect_permission_codes(user: Any) -> set:
    """汇总用户经由角色获得的权限码。"""
    if user is None:
        return set()
    codes = set()
    for role in getattr(user, "roles", None) or []:
        for perm in getattr(role, "permissions", None) or []:
            codes.add(perm.code)
    return codes


def has_permission(user: Any, permission_codes: Iterable[str]) -> bool:
    """判断用户是否拥有指定权限之一（超管直接通过）。"""
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    return bool(collect_permission_codes(user) & set(permission_codes))
