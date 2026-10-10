"""OS 内核模型：工作流引擎（M5）。

设计要点（对应 docs/os-kernel-design.md 3.2）：
- 流程定义：YAML/JSON DSL（task / branch / parallel / wait / retry），本模块
  只承载运行态，定义解析与校验在 ``app/core/workflow/dsl.py``；
- 执行模型：状态机驱动，实例与步骤全部落库，中断后可续跑；
- 幂等：步骤以 ``instance_id + seq`` 为唯一键（数据库唯一约束 + 引擎检查），
  重复推进不会产生重复副作用；
- 人工节点：``wait`` 类型步骤生成待办等人认领/审批，可设超时兜底分支；
- 补偿：失败支持按 ``compensate`` 动作回滚已执行步骤，无补偿则标记人工介入。

所有表统一 ``oc_core_`` 前缀，与既有 ``oc_`` 业务表隔离，升级/回退互不影响。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
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
from app.models.kernel import ID_TYPE

# 实例状态：created 已创建未启动 / running 推进中 / waiting 存在人工节点 /
# paused 已暂停 / completed 已完成 / failed 已失败 / cancelled 已取消
WORKFLOW_STATUSES = ("created", "running", "waiting", "paused", "completed", "failed", "cancelled")

# 步骤状态：pending 待执行 / running 执行中 / waiting 等待人工或事件 /
# completed 已完成 / failed 已失败 / skipped 已跳过
WORKFLOW_STEP_STATUSES = ("pending", "running", "waiting", "completed", "failed", "skipped")

# 节点类型（与 DSL 对齐）
WORKFLOW_NODE_TYPES = ("task", "branch", "parallel", "wait", "retry")


class CoreWorkflowInstance(Base):
    """工作流实例：一次流程执行的运行态容器。"""

    __tablename__ = "oc_core_workflow_instance"
    __table_args__ = (
        # 按定义 + 状态检索（管理台/调度侧）
        Index("ix_core_wf_def_status", "def_key", "status", "id"),
        # 按创建时间回溯
        Index("ix_core_wf_created", "created_at"),
        # 按执行者/发起人查询（审计、看板）
        Index("ix_core_wf_creator", "created_by"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    def_key: Mapped[str] = mapped_column(
        String(128), index=True, comment="流程定义键（如 sentiment_analysis_workflow）"
    )
    title: Mapped[str] = mapped_column(
        String(200), comment="实例标题（业务侧描述）"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="created", server_default="created", comment="状态"
    )

    # 上下文：业务侧传入的初始数据（JSON）
    context: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="初始上下文数据（JSON）"
    )

    # 执行追踪
    current_step: Mapped[Optional[int]] = mapped_column(
        Integer, comment="当前步骤序号"
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), comment="开始执行时间"
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), comment="结束时间（完成/失败/取消）"
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text, comment="失败原因"
    )

    # 创建者
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, comment="创建者用户 ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(timezone=True), server_default=func.now(timezone=True)
    )


class CoreWorkflowStep(Base):
    """工作流步骤：实例中的单个执行节点。"""

    __tablename__ = "oc_core_workflow_step"
    __table_args__ = (
        # 幂等键：实例 + 步骤序号
        UniqueConstraint("instance_id", "seq"),
        # 按实例 + 状态检索（进度查询、续跑）
        Index("ix_core_wf_step_inst_status", "instance_id", "status", "seq"),
        # 按人工节点 + 状态检索（待办列表）
        Index("ix_core_wf_step_waiting", "status", "seq"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("oc_core_workflow_instance.id"), index=True
    )
    seq: Mapped[int] = mapped_column(
        Integer, comment="步骤序号（从 0 开始）"
    )
    node_type: Mapped[str] = mapped_column(
        String(16), comment="节点类型"
    )
    name: Mapped[str] = mapped_column(
        String(128), comment="步骤名称"
    )
    config: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="步骤配置（task/handler/compensate/timeout 等）"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="状态"
    )
    payload: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="执行结果或上下文数据"
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text, comment="错误信息"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
