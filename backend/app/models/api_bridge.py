"""M13 API 申请助手模型：平台模板 / 申请任务。

设计要点：
- oc_api_platform_template 描述外部平台接入模板（名称 / 申请地址 / 表单字段映射 /
  是否需人工验证 / 分类 / 启用状态），供申请任务创建时渲染表单与走流程；
- oc_api_apply_task 记录一次 API 申请任务（目标平台 / 状态 / 凭据密文引用 /
  进度 / 结果消息 / 失败原因 / 申请人），credentials_ref 仅保存 AES 密文引用，
  严禁明文密码入库；
- 状态机：pending -> submitted -> awaiting_manual -> done/failed，
  需人工验证/付费/资质审核的平台提交后进入 awaiting_manual 等待用户介入。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
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

# 平台分类
API_PLATFORM_CATEGORIES = ("ecommerce", "website", "other")
# 申请任务状态
API_TASK_STATUSES = (
    "pending",           # 已创建，等待提交
    "submitted",         # 已提交平台
    "awaiting_manual",   # 需人工验证/付费/资质审核，等待用户介入
    "done",              # 申请成功，凭据可用
    "failed",            # 申请失败
)
# 平台模板启用状态（布尔 enabled）


class ApiPlatformTemplate(Base):
    """外部平台 API 申请模板。"""

    __tablename__ = "oc_api_platform_template"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="平台名称")
    apply_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="申请地址")
    field_schema: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="表单字段映射（JSON：字段名/标签/必填/选项等）"
    )
    requires_manual: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否需人工验证/付费/资质审核"
    )
    category: Mapped[str] = mapped_column(
        String(16), default="other", server_default="other", comment="分类 ecommerce/website/other"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否启用"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class ApiApplyTask(Base):
    """API 申请任务。"""

    __tablename__ = "oc_api_apply_task"
    __table_args__ = (
        Index("ix_api_task_tenant_time", "tenant_id", "created_at"),
        Index("ix_api_task_platform_status", "platform", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="租户 ID")
    platform_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="平台模板 ID（oc_api_platform_template.id）"
    )
    platform: Mapped[str] = mapped_column(String(200), nullable=False, comment="目标平台名称（冗余快照）")
    status: Mapped[str] = mapped_column(
        String(24), default="pending", server_default="pending", comment="pending/submitted/awaiting_manual/done/failed"
    )
    credentials_ref: Mapped[Optional[str]] = mapped_column(
        String(2048), nullable=True, comment="凭据密文引用（AES 加密后引用，严禁明文）"
    )
    account: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="", comment="申请账号（用于列表脱敏展示）"
    )
    progress: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="进度（0-100）"
    )
    result_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="结果消息（成功说明/待办事项）"
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="失败原因"
    )
    created_by: Mapped[str] = mapped_column(
        String(64), default="system", server_default="system", comment="申请人"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="结束时间（done/failed）"
    )
