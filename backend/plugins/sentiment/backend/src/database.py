"""舆情插件数据库模型（内核监督建表，M2 约束）。

插件不得自行建表：install 时由内核 ``provision_tables`` 读取本模块
``Base.metadata`` 统一执行 create_all。表统一 ``os_sentiment_`` 前缀。
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """舆情插件私有 ORM 基类。"""


class SentimentTask(Base):
    """舆情分析任务（MVP 最小示例表）。"""

    __tablename__ = "os_sentiment_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
