"""数据接入模型：一次文件导入的执行记录。"""

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 文件布局：wide 一行多指标（宽表） / long 一行一指标（长表）
LAYOUTS = ("wide", "long")

# 任务状态：pending 待执行 / running 执行中 / success 全部成功 / partial 部分成功 / failed 失败
TASK_STATUSES = ("pending", "running", "success", "partial", "failed")


class ImportTask(Base):
    """数据文件导入任务：留存文件信息、映射配置与执行结果。"""

    __tablename__ = "oc_import_task"
    __table_args__ = (Index("ix_import_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_data_source.id", ondelete="SET NULL"),
        default=None,
        comment="来源数据源 ID",
    )
    file_name: Mapped[str] = mapped_column(String(255), comment="原始文件名")
    file_path: Mapped[str] = mapped_column(String(512), comment="服务端落盘路径")
    file_size: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="文件字节数"
    )
    file_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default="", comment="文件内容 sha256"
    )
    layout: Mapped[str] = mapped_column(
        String(8), default="wide", server_default="wide", comment="wide 宽表 / long 长表"
    )
    granularity: Mapped[str] = mapped_column(
        String(16), default="day", server_default="day", comment="统计粒度"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        server_default="pending",
        index=True,
        comment="pending/running/success/partial/failed",
    )
    total_rows: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="文件总行数"
    )
    success_rows: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="成功解析的行数"
    )
    failed_rows: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="解析失败的行数"
    )
    skipped_rows: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="空值跳过的行数"
    )
    value_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="实际写入的指标值条数"
    )
    metric_codes: Mapped[Optional[list]] = mapped_column(
        JSON, default=None, comment="本次涉及的指标编码列表"
    )
    mapping: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="列映射配置（快照）"
    )
    error_detail: Mapped[Optional[list]] = mapped_column(
        JSON, default=None, comment="失败行明细（最多留存 100 条）"
    )
    error_msg: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="整体失败原因")
    elapsed_ms: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="执行耗时（毫秒）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="完成时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ImportTask {self.id} {self.file_name} {self.status}>"
