"""OS 内核模型：事件总线（持久化队列 / 死信 / 订阅位点）。

设计要点：
- 事件表本身承担持久化队列职责，不引入外部消息中间件，单机可跑；
- 消费采用「领取 + 租约」模型，工作者崩溃后超时事件可被重新领取，投递语义为
  「至少一次」，消费方按 ``event_id`` 自行幂等；
- 重试采用指数退避，超过最大次数的事件转入死信表，支持排查与重放；
- 订阅位点表留档消费进度，用于新增订阅方补数（回放）与积压观测。

所有表统一 ``oc_core_`` 前缀，与既有 ``oc_`` 业务表隔离，升级/回退互不影响。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 事件 ID 列类型：生产（PostgreSQL）为 BIGINT；SQLite 下退化为 INTEGER，
# 以保证单测内存库中主键可自增（SQLite 仅 INTEGER PRIMARY KEY 具备 rowid 自增语义）。
ID_TYPE = BigInteger().with_variant(Integer, "sqlite")

# 事件投递状态：pending 待投递 / processing 投递中（持租约）/ done 已完成 / dead 已转死信
EVENT_STATUSES = ("pending", "processing", "done", "dead")

# 事件名命名规范：<域>.<对象>.<动作>，内核事件前缀 core.
EVENT_NAME_PREFIX_CORE = "core."


class CoreEvent(Base):
    """内核事件（持久化队列中的一条待投递消息）。"""

    __tablename__ = "oc_core_event"
    __table_args__ = (
        # 派发扫描主索引：按状态 + 可投递时间 + 自增序
        Index("ix_core_event_dispatch", "status", "available_at", "id"),
        # 按事件名回溯（调试、补数、订阅方对齐）
        Index("ix_core_event_name", "event_name", "id"),
        # 分区键内保序：同一 (分区键, 事件名) 按 id 顺序消费
        Index("ix_core_event_partition", "partition_key", "id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, comment="事件全局唯一 ID（消费方幂等键）"
    )
    event_name: Mapped[str] = mapped_column(
        String(128), index=True, comment="事件名，规范：<域>.<对象>.<动作>"
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, comment="事件载荷（JSON）")
    trace_id: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, index=True, comment="链路追踪 ID"
    )
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, default=None, index=True, comment="租户 ID，null 表示内核级事件"
    )
    partition_key: Mapped[Optional[str]] = mapped_column(
        String(128),
        default=None,
        comment="分区键（如同租户 + 同聚合根），同键内保序",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        server_default="pending",
        comment="状态：pending/processing/done/dead",
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="已投递尝试次数"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5", comment="最大投递次数，超出转死信"
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="可投递时间（重试退避后推迟）",
    )
    locked_by: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, comment="当前领取者标识"
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="领取时间（租约起算点）"
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="最近一次投递失败原因"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="事件发生时间",
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="完成时间"
    )


class CoreEventDead(Base):
    """死信：超过最大投递次数仍失败的事件，留档供排查与重放。"""

    __tablename__ = "oc_core_event_dead"
    __table_args__ = (Index("ix_core_event_dead_time", "failed_at", "id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), index=True, comment="原事件 ID")
    event_name: Mapped[str] = mapped_column(String(128), index=True, comment="原事件名")
    payload: Mapped[dict] = mapped_column(JSON, default=dict, comment="原事件载荷")
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="链路追踪 ID")
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, default=None, comment="租户 ID")
    attempts: Mapped[int] = mapped_column(Integer, default=0, comment="累计尝试次数")
    last_error: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="最终失败原因")
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="转入死信时间"
    )
    replayed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否已重放"
    )
    replayed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="重放时间"
    )


class CoreEventCursor(Base):
    """订阅位点：记录某订阅方已消费到的事件 ID，用于补数与积压观测。"""

    __tablename__ = "oc_core_event_cursor"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscriber: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, comment="订阅方标识（插件 ID 或内核模块名）"
    )
    event_name: Mapped[str] = mapped_column(String(128), comment="订阅的事件名（支持前缀通配）")
    last_event_id: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", comment="已消费的最大事件自增 ID"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
