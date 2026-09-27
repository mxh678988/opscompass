"""采集调度模型：按计划从数据源自动采集数据并写入指标库。

两张表：
- oc_collect_task：采集任务定义（数据源、采集方式、映射配置、调度策略、执行统计）
- oc_collect_run ：每次执行（手动 / 调度）的运行记录与结果留痕
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 采集方式：
# - csv  读取服务器 data/raw 下的文件（复用数据接入解析链路，真实落库）
# - api  HTTP 拉取 JSON 接口（真实出网 + 真实落库）
# - sql  数据库直连采集（驱动未接入，仅做连通性探测 + 演练记录）
COLLECT_MODES = ("csv", "api", "sql")

# 调度策略：manual 仅手动触发 / interval 按固定间隔自动执行
SCHEDULE_TYPES = ("manual", "interval")

# 任务状态：enabled 启用 / paused 暂停
TASK_STATUSES = ("enabled", "paused")

# 运行状态：running / success 全部成功 / partial 部分成功 / failed 失败 / skipped 跳过
RUN_STATUSES = ("running", "success", "partial", "failed", "skipped")

# 触发方式：manual 手动 / schedule 调度
RUN_TRIGGERS = ("manual", "schedule")


class CollectTask(Base):
    """采集任务：数据源 + 采集方式 + 字段映射 + 调度计划。"""

    __tablename__ = "oc_collect_task"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_collect_task_tenant_code"),
        Index("ix_collect_task_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    code: Mapped[str] = mapped_column(String(64), comment="任务编码")
    name: Mapped[str] = mapped_column(String(128), comment="任务名称")
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_data_source.id", ondelete="SET NULL"),
        default=None,
        comment="关联数据源 ID",
    )
    collect_mode: Mapped[str] = mapped_column(
        String(16), default="csv", server_default="csv", comment="csv/api/sql"
    )
    target: Mapped[str] = mapped_column(
        String(512), comment="采集目标：文件名 / 接口 URL / 库表名"
    )
    mapping: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="字段映射（结构同数据接入 IngestMapping）"
    )
    extra_config: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="扩展配置：API 数据路径、请求头、HTTP 方法等"
    )
    schedule_type: Mapped[str] = mapped_column(
        String(16), default="manual", server_default="manual", comment="manual/interval"
    )
    interval_minutes: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="调度间隔（分钟，interval 模式）"
    )
    cron_expr: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, comment="Cron 表达式（预留，当前按 interval 生效）"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="enabled", server_default="enabled", index=True, comment="enabled/paused"
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="最近执行时间"
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="下次计划执行时间"
    )
    run_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="累计执行次数"
    )
    success_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="成功次数"
    )
    fail_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="失败次数"
    )
    last_status: Mapped[Optional[str]] = mapped_column(
        String(16), default=None, comment="最近一次运行状态"
    )
    remark: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CollectTask {self.code} {self.collect_mode} {self.status}>"


class CollectRun(Base):
    """采集运行记录：一次执行的结果与耗时留痕。"""

    __tablename__ = "oc_collect_run"
    __table_args__ = (
        Index("ix_collect_run_tenant_task", "tenant_id", "task_id"),
        Index("ix_collect_run_tenant_started", "tenant_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    task_id: Mapped[int] = mapped_column(
        ForeignKey("oc_collect_task.id", ondelete="CASCADE"), index=True, comment="采集任务 ID"
    )
    task_code: Mapped[str] = mapped_column(
        String(64), default="", server_default="", comment="任务编码快照"
    )
    collect_mode: Mapped[str] = mapped_column(
        String(16), default="csv", server_default="csv", comment="采集方式快照"
    )
    trigger: Mapped[str] = mapped_column(
        String(16), default="manual", server_default="manual", comment="manual/schedule"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="running", server_default="running", index=True, comment="运行状态"
    )
    rows_in: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="读取到的原始记录数"
    )
    rows_written: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="成功写入的指标值条数"
    )
    rows_failed: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="失败记录数"
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="执行耗时（毫秒）"
    )
    simulated: Mapped[bool] = mapped_column(
        default=False, server_default="false", comment="是否为演练执行（未真实采集）"
    )
    message: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="结果说明 / 失败原因")
    detail: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="执行细节：指标编码、样例、错误明细等"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="开始时间"
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="完成时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CollectRun {self.task_id} {self.status}>"
