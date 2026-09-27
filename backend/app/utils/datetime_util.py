"""日期时间工具。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def now() -> datetime:
    """返回带时区的当前时间。"""
    return datetime.now(ZoneInfo(settings.TIMEZONE))


def format_dt(dt: datetime) -> str:
    """格式化时间为中文可读形式（避免 strftime 中的中文格式串）。"""
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日 {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"
