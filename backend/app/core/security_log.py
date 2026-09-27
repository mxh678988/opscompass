"""安全日志分级：把安全事件按严重度分级写入独立日志文件，并支持高危告警镜像。

分级定义：
- INFO      常规安全动作（登录成功、登出、写操作成功）
- WARNING   可疑行为（登录失败、权限拒绝、写操作失败、令牌无效）
- CRITICAL  高危事件（账号锁定、IP 白名单拦截、越权、审计通道异常）

文件行格式固定，便于按级别/事件解析统计：
    2026-09-24 20:11:00 | CRITICAL | ip_blocked | user=- | ip=1.2.3.4 | path=/api/v1/x | status_code=403 | detail=...

与审计库的关系：审计日志（oc_audit_log）负责可检索的完整流水；本模块负责
「分级 + 独立通道 + 告警」，两者由 audit_service.record 单点联动，互不阻塞。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from app.core.config import BASE_DIR, settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------ 级别定义
LEVEL_INFO = "INFO"
LEVEL_WARNING = "WARNING"
LEVEL_CRITICAL = "CRITICAL"
LEVELS: tuple[str, ...] = (LEVEL_INFO, LEVEL_WARNING, LEVEL_CRITICAL)
LEVEL_ORDER: dict[str, int] = {LEVEL_INFO: 10, LEVEL_WARNING: 20, LEVEL_CRITICAL: 30}
LEVEL_DESCRIPTIONS: dict[str, str] = {
    LEVEL_INFO: "常规安全动作：登录成功、登出、写操作成功。",
    LEVEL_WARNING: "可疑行为：登录失败、权限/令牌被拒、写操作失败。",
    LEVEL_CRITICAL: "高危事件：账号锁定、IP 白名单拦截、审计通道异常。",
}

# 事件类型 → 默认级别（resolve_level 可依上下文升级）
EVENT_BASE_LEVEL: dict[str, str] = {
    "login_success": LEVEL_INFO,
    "logout": LEVEL_INFO,
    "sensitive_operation": LEVEL_INFO,
    "password_change": LEVEL_WARNING,
    "login_failed": LEVEL_WARNING,
    "access_denied": LEVEL_WARNING,
    "token_invalid": LEVEL_WARNING,
    "login_locked": LEVEL_CRITICAL,
    "ip_blocked": LEVEL_CRITICAL,
    "audit_failure": LEVEL_CRITICAL,
}

EVENT_LABELS: dict[str, str] = {
    "login_success": "登录成功",
    "login_failed": "登录失败",
    "logout": "登出",
    "password_change": "修改密码",
    "access_denied": "访问被拒绝",
    "sensitive_operation": "敏感操作",
    "token_invalid": "令牌无效",
    "login_locked": "账号锁定",
    "ip_blocked": "IP 白名单拦截",
    "audit_failure": "审计通道异常",
}

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r" \| (?P<level>[A-Z]+)"
    r" \| (?P<event>[A-Za-z_]+)"
    r" \| (?P<rest>.*)$"
)
_DETAIL_MAX = 800
_LOGGER_NAME = "opscompass.security"
_ALERT_LOGGER_NAME = "opscompass.security.alert"

_logger: Optional[logging.Logger] = None


# ------------------------------------------------------------ 路径与级别
def log_file_path() -> Path:
    """安全日志文件绝对路径（相对路径按 LOG_DIR 解析）。"""
    path = Path(settings.SECURITY_LOG_FILE)
    if path.is_absolute():
        return path
    base = Path(settings.LOG_DIR)
    if not base.is_absolute():
        base = BASE_DIR / base
    return base / path


def normalize_level(level: Optional[str], default: str = LEVEL_INFO) -> str:
    """规范化级别字符串，非法值回落默认。"""
    if not level:
        return default
    value = str(level).strip().upper()
    return value if value in LEVEL_ORDER else default


def min_level() -> str:
    """生效的最低记录级别（低于该级别不写文件）。"""
    return normalize_level(settings.SECURITY_LOG_MIN_LEVEL, LEVEL_INFO)


def alert_level() -> str:
    """触发主日志告警镜像的级别。"""
    return normalize_level(settings.SECURITY_LOG_ALERT_LEVEL, LEVEL_CRITICAL)


def resolve_level(
    event_type: str,
    *,
    status: str = "success",
    status_code: Optional[int] = None,
    reason: Optional[str] = None,
) -> str:
    """按事件类型与上下文判定级别（含升级规则）。"""
    level = EVENT_BASE_LEVEL.get(event_type, LEVEL_INFO)
    text = (reason or "").lower()

    if event_type == "login_failed":
        if status_code == 423 or "锁定" in (reason or "") or "locked" in text:
            level = LEVEL_CRITICAL
    elif event_type == "access_denied":
        if "白名单" in (reason or "") or "allowlist" in text or "forbidden_ip" in text:
            level = LEVEL_CRITICAL
        elif status_code is not None and status_code >= 401:
            level = LEVEL_WARNING
    elif event_type == "sensitive_operation":
        if status_code is not None and status_code >= 500:
            level = LEVEL_CRITICAL
        elif status != "success" or (status_code is not None and status_code >= 400):
            level = LEVEL_WARNING
    elif event_type == "password_change":
        level = LEVEL_WARNING

    return level


# ------------------------------------------------------------ 文件通道
def ensure_logger() -> logging.Logger:
    """确保安全日志 logger 就绪（进程内幂等，独立文件通道，不向 root 冒泡）。"""
    global _logger
    if _logger is not None:
        return _logger

    handler_logger = logging.getLogger(_LOGGER_NAME)
    handler_logger.setLevel(logging.INFO)
    handler_logger.propagate = False
    if not handler_logger.handlers:
        try:
            path = log_file_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                path,
                maxBytes=int(settings.SECURITY_LOG_MAX_BYTES),
                backupCount=int(settings.SECURITY_LOG_BACKUP_COUNT),
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            handler_logger.addHandler(handler)
        except Exception:  # pragma: no cover - 文件通道不可用时不应影响业务
            logger.exception("安全日志文件通道初始化失败: %s", log_file_path())
    _logger = handler_logger
    return _logger


def _stringify(value: Any, limit: int = _DETAIL_MAX) -> str:
    """把字段值压成单行文本，保证行格式可解析。"""
    if value is None:
        return "-"
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:  # pragma: no cover
            value = str(value)
    text = value.replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return "-"
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def format_line(
    level: str,
    event_type: str,
    *,
    username: Optional[str] = None,
    user_id: Optional[Any] = None,
    tenant_id: Optional[Any] = None,
    ip: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = None,
    status: Optional[str] = None,
    detail: Any = None,
    extra: Optional[dict] = None,
) -> str:
    """组装一行安全日志。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = [
        f"user={_stringify(username if username else user_id)}",
        f"ip={_stringify(ip)}",
        f"method={_stringify(method)}",
        f"path={_stringify(path)}",
        f"status={_stringify(status)}",
        f"status_code={_stringify(status_code)}",
        f"tenant_id={_stringify(tenant_id)}",
        f"detail={_stringify(detail)}",
    ]
    if extra:
        for key, value in extra.items():
            fields.append(f"{key}={_stringify(value)}")
    return f"{ts} | {level} | {event_type} | " + " | ".join(fields)


def emit(
    event_type: str,
    *,
    level: Optional[str] = None,
    username: Optional[str] = None,
    user_id: Optional[Any] = None,
    tenant_id: Optional[Any] = None,
    ip: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = None,
    status: str = "success",
    detail: Any = None,
    extra: Optional[dict] = None,
) -> Optional[str]:
    """写入一条分级安全日志；返回实际级别（被过滤时返回 None）。失败不抛出。"""
    if not settings.SECURITY_LOG_ENABLED:
        return None
    try:
        reason = detail if isinstance(detail, str) else None
        actual = normalize_level(
            level
            or resolve_level(
                event_type, status=status, status_code=status_code, reason=reason
            )
        )
        if LEVEL_ORDER[actual] < LEVEL_ORDER[min_level()]:
            return None

        line = format_line(
            actual,
            event_type,
            username=username,
            user_id=user_id,
            tenant_id=tenant_id,
            ip=ip,
            method=method,
            path=path,
            status_code=status_code,
            status=status,
            detail=detail,
            extra=extra,
        )
        ensure_logger().info(line)

        # 主日志镜像：达到告警级别无条件镜像；开关开启时 WARNING 及以上一并镜像
        threshold = alert_level()
        mirror = LEVEL_ORDER[actual] >= LEVEL_ORDER[threshold] or (
            settings.SECURITY_LOG_MIRROR_TO_MAIN
            and LEVEL_ORDER[actual] >= LEVEL_ORDER[LEVEL_WARNING]
        )
        if mirror:
            alert_logger = logging.getLogger(_ALERT_LOGGER_NAME)
            if LEVEL_ORDER[actual] >= LEVEL_ORDER[LEVEL_CRITICAL]:
                alert_logger.critical(line)
            else:
                alert_logger.warning(line)
        return actual
    except Exception:  # pragma: no cover - 日志失败不影响主流程
        logger.exception("写入安全分级日志失败: event=%s", event_type)
        return None


def classified(event_type: str, **kwargs: Any) -> Optional[str]:
    """emit 的语义化别名：自动分级后写入。"""
    return emit(event_type, **kwargs)


# ------------------------------------------------------------ 读取与统计
def _parse_line(line: str) -> Optional[dict]:
    match = _LINE_RE.match(line)
    if not match:
        return None
    fields: dict[str, str] = {}
    for chunk in (match.group("rest") or "").split(" | "):
        if "=" in chunk:
            key, _, value = chunk.partition("=")
            fields[key.strip()] = value.strip()
    return {
        "time": match.group("ts"),
        "level": match.group("level"),
        "event": match.group("event"),
        "event_label": EVENT_LABELS.get(match.group("event"), match.group("event")),
        "username": None if fields.get("user") in (None, "-") else fields["user"],
        "ip": None if fields.get("ip") in (None, "-") else fields["ip"],
        "method": None if fields.get("method") in (None, "-") else fields["method"],
        "path": None if fields.get("path") in (None, "-") else fields["path"],
        "status": None if fields.get("status") in (None, "-") else fields["status"],
        "status_code": fields.get("status_code"),
        "detail": None if fields.get("detail") in (None, "-") else fields["detail"],
    }


def _read_lines() -> list[str]:
    """读取当前安全日志文件（含最近备份，按轮转顺序）。"""
    path = log_file_path()
    files = [path] + [
        Path(f"{path}.{i}") for i in range(1, 2)  # 最近一个备份，避免大文件反复读取
    ]
    lines: list[str] = []
    for item in reversed(files):  # 备份在前，当前在后，保证时间顺序
        if not item.exists():
            continue
        try:
            lines.extend(item.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:  # pragma: no cover
            logger.exception("读取安全日志失败: %s", item)
    return lines


def recent(
    *,
    limit: int = 20,
    level: Optional[str] = None,
    event_type: Optional[str] = None,
    days: Optional[int] = None,
) -> list[dict]:
    """倒序返回最近的安全日志条目（可按级别/事件/天数过滤）。"""
    level = normalize_level(level, "") if level else None
    since = datetime.now() - timedelta(days=days) if days else None
    matched: list[dict] = []
    for raw in _read_lines():
        item = _parse_line(raw)
        if not item:
            continue
        if level and item["level"] != level:
            continue
        if event_type and item["event"] != event_type:
            continue
        if since is not None:
            try:
                if datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S") < since:
                    continue
            except ValueError:
                continue
        matched.append(item)
    limit = max(1, min(limit, 500))
    return list(reversed(matched[-limit:]))


def stats(days: int = 7) -> dict:
    """近 N 天安全日志统计：分级计数、按事件计数、最近 CRITICAL。"""
    since = datetime.now() - timedelta(days=max(1, days))
    by_level = {level: 0 for level in LEVELS}
    by_event: dict[str, int] = {}
    total = 0
    criticals: list[dict] = []
    for raw in _read_lines():
        item = _parse_line(raw)
        if not item:
            continue
        try:
            if datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S") < since:
                continue
        except ValueError:
            continue
        total += 1
        by_level[item["level"]] = by_level.get(item["level"], 0) + 1
        by_event[item["event"]] = by_event.get(item["event"], 0) + 1
        if item["level"] == LEVEL_CRITICAL:
            criticals.append(item)

    return {
        "days": days,
        "total": total,
        "by_level": by_level,
        "by_event": by_event,
        "latest_critical": list(reversed(criticals[-10:])),
        "file": file_meta(),
        "config": {
            "enabled": settings.SECURITY_LOG_ENABLED,
            "min_level": min_level(),
            "alert_level": alert_level(),
            "mirror_to_main": settings.SECURITY_LOG_MIRROR_TO_MAIN,
        },
    }


def file_meta() -> dict:
    """安全日志文件元信息（路径、大小、轮转策略）。"""
    path = log_file_path()
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "max_bytes": int(settings.SECURITY_LOG_MAX_BYTES),
        "backup_count": int(settings.SECURITY_LOG_BACKUP_COUNT),
    }


def catalog() -> dict:
    """级别与事件字典，供前端展示筛选器与说明。"""
    return {
        "levels": [
            {
                "value": level,
                "label": LEVEL_DESCRIPTIONS[level].split("：", 1)[0],
                "description": LEVEL_DESCRIPTIONS[level],
                "order": LEVEL_ORDER[level],
            }
            for level in LEVELS
        ],
        "events": [
            {
                "value": event,
                "label": EVENT_LABELS.get(event, event),
                "default_level": default_level,
            }
            for event, default_level in EVENT_BASE_LEVEL.items()
        ],
        "config": {
            "enabled": settings.SECURITY_LOG_ENABLED,
            "min_level": min_level(),
            "alert_level": alert_level(),
            "mirror_to_main": settings.SECURITY_LOG_MIRROR_TO_MAIN,
            "file": file_meta(),
        },
    }
