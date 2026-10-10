"""OS 内核 · 任务 SLA · 工作日历（可选增强）。

默认 SLA 按 24 小时绝对时间计时；传入 ``WorkingCalendar`` 后，创建时
截止时间按「工作时间段 + 节假日」展开计算，跳过下班时间与假期。

最小实现：单日工作时段 + 日期级节假日集合；跨日按工作时段滚动累计。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, tzinfo
from typing import Iterable, Optional


class WorkingCalendar:
    """按工作时间段展开时长的日历。

    示例：``WorkingCalendar(work_start_hour=9, work_end_hour=18, holidays=[date(2026,10,1)])``
    表示周一至周五 09:00-18:00 为工作时间，2026-10-01 放假。
    """

    def __init__(
        self,
        work_start_hour: int = 9,
        work_end_hour: int = 18,
        holidays: Optional[Iterable[date]] = None,
        weekend_off: bool = True,
        tz: Optional[tzinfo] = None,
    ) -> None:
        if not (0 <= work_start_hour < work_end_hour <= 24):
            raise ValueError("工作时间段非法: 需要 0 <= start < end <= 24")
        self.work_start_hour = work_start_hour
        self.work_end_hour = work_end_hour
        self.holidays = set(holidays or ())
        self.weekend_off = weekend_off
        self.tz = tz

    # ---- 判断 ----

    def is_working(self, dt: datetime) -> bool:
        """某时刻是否属于工作时间。"""
        d = dt.date()
        if d in self.holidays:
            return False
        if self.weekend_off and dt.weekday() >= 5:
            return False
        start = datetime.combine(d, time(self.work_start_hour), tzinfo=dt.tzinfo)
        end = datetime.combine(d, time(self.work_end_hour), tzinfo=dt.tzinfo)
        return start <= dt < end

    # ---- 展开计算 ----

    def add_working_minutes(self, start: datetime, minutes: int) -> datetime:
        """从 start 起，累计 minutes 个工作分钟，返回到达时刻（下班/假期跳过）。"""
        if minutes < 0:
            raise ValueError("minutes 必须为非负")
        remaining = int(minutes)
        cursor = start
        while remaining > 0:
            if not self.is_working(cursor):
                cursor = self._next_working_start(cursor)
                continue
            day_end = datetime.combine(
                cursor.date(),
                time(self.work_end_hour),
                tzinfo=cursor.tzinfo,
            )
            available = int((day_end - cursor).total_seconds() // 60)
            if available <= 0:
                cursor = self._next_working_start(cursor)
                continue
            if remaining <= available:
                return cursor + timedelta(minutes=remaining)
            remaining -= available
            cursor = self._next_working_start(day_end)
        return cursor

    def _next_working_start(self, dt: datetime) -> datetime:
        """下一个工作时段起点（当天未到上班时间则当天起，否则次日）。"""
        start = datetime.combine(dt.date(), time(self.work_start_hour), tzinfo=dt.tzinfo)
        if dt < start and self.is_working(start):
            return start
        day = dt.date() + timedelta(days=1)
        while True:
            candidate = datetime.combine(day, time(self.work_start_hour), tzinfo=dt.tzinfo)
            if candidate.date() not in self.holidays and not (
                self.weekend_off and candidate.weekday() >= 5
            ):
                return candidate
            day += timedelta(days=1)
