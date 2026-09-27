"""日志配置。"""

import logging
import sys
from pathlib import Path

from app.core.config import BASE_DIR, settings


def setup_logging() -> None:
    """初始化全局日志：控制台 + 文件双通道。"""
    log_dir = Path(settings.LOG_DIR)
    if not log_dir.is_absolute():
        log_dir = BASE_DIR / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    handlers.append(logging.FileHandler(log_dir / "app.log", encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )

    # 安全日志分级通道（独立文件 logs/security.log，不向 root 冒泡避免重复）
    from app.core.security_log import ensure_logger

    ensure_logger()
