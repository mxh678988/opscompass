"""M12 智能体编排模型：分析 Agent 与执行 Agent 的双 Agent 闭环。

设计要点：
- oc_agent_run 记录一次完整的智能体编排运行（场景模板 → 绑定数据源 → 执行动作）；
- oc_agent_insight 记录分析 Agent（Insight Agent）产出的诊断/洞察（只读不改）；
- oc_agent_action 记录执行 Agent（Action Agent）的动作：经人工确认闸门后执行，
  结果回写事件总线（result_published）；
- 状态机：run(pending → analyzing → awaiting_approval → executing → done/failed)，
  强制人工确认闸门：未经 approve 不得执行。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
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

# 运行状态
AGENT_RUN_STATUSES = (
    "pending",          # 已创建，等待分析
    "analyzing",        # 分析 Agent 执行中
    "awaiting_approval",  # 洞察产出，等待人工确认
    "executing",        # 已确认，执行 Agent 执行中
    "done",             # 完成
    "rejected",         # 人工驳回
    "failed",           # 失败
)
# 场景模板
AGENT_SCENARIOS = ("churn_recall", "conversion_promote", "channel_roi", "custom")
# 动作类型
AGENT_ACTION_TYPES = ("create_task", "create_segment", "notify", "plugin", "record")
# 洞察状态
AGENT_INSIGHT_STATUSES = ("new", "confirmed", "rejected", "executed")


class AgentRun(Base):
    """智能体编排运行：一次「分析 → 确认 → 执行 → 回写」闭环。"""

    __tablename__ = "oc_agent_run"
    __table_args__ = (
        Index("ix_agent_run_tenant_time", "tenant_id", "created_at"),
        Index("ix_agent_run_scenario_status", "scenario", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(200), comment="运行名称")
    scenario: Mapped[str] = mapped_column(
        String(32), default="custom", server_default="custom", comment="场景模板 churn_recall/conversion_promote/channel_roi/custom"
    )
    status: Mapped[str] = mapped_column(
        String(24),
        default="pending",
        server_default="pending",
        comment="pending/analyzing/awaiting_approval/executing/done/rejected/failed",
    )
    datasource_bindings: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="数据源绑定（数据源 ID → 角色）"
    )
    knowledge_refs: Mapped[Optional[list]] = mapped_column(
        JSON, default=None, comment="引用的知识库文档 ID 列表"
    )
    action_config: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="执行动作配置"
    )
    insight_agent: Mapped[str] = mapped_column(
        String(64), default="insight-agent", server_default="insight-agent", comment="分析 Agent 标识"
    )
    action_agent: Mapped[str] = mapped_column(
        String(64), default="action-agent", server_default="action-agent", comment="执行 Agent 标识"
    )
    approval_required: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否强制人工确认闸门"
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, comment="确认人"
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="确认时间"
    )
    approve_note: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="确认意见")
    result_summary: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="交付结果摘要"
    )
    result_published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="结果是否已回写事件总线"
    )
    result_event_id: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, comment="回写的事件 ID"
    )
    error: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="失败原因")
    created_by: Mapped[str] = mapped_column(
        String(64), default="system", server_default="system", comment="发起人"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="完成时间"
    )


class AgentInsight(Base):
    """分析 Agent 产出的洞察（只读诊断，不产生执行副作用）。"""

    __tablename__ = "oc_agent_insight"
    __table_args__ = (
        Index("ix_agent_insight_run", "run_id", "created_at"),
        Index("ix_agent_insight_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    run_id: Mapped[int] = mapped_column(
        ForeignKey("oc_agent_run.id", ondelete="CASCADE"), index=True, comment="所属运行"
    )
    seq: Mapped[int] = mapped_column(Integer, default=1, server_default="1", comment="序号")
    title: Mapped[str] = mapped_column(String(200), comment="洞察标题")
    detail: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="诊断详情")
    severity: Mapped[str] = mapped_column(
        String(16), default="info", server_default="info", comment="info/warning/critical"
    )
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="数据依据")
    suggestion: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="可行动建议")
    suggested_action_type: Mapped[str] = mapped_column(
        String(24), default="create_task", server_default="create_task", comment="建议动作类型"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="new", server_default="new", comment="new/confirmed/rejected/executed"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentAction(Base):
    """执行 Agent 的动作：经人工确认后执行，结果回写事件总线。"""

    __tablename__ = "oc_agent_action"
    __table_args__ = (
        Index("ix_agent_action_run", "run_id", "created_at"),
        Index("ix_agent_action_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    run_id: Mapped[int] = mapped_column(
        ForeignKey("oc_agent_run.id", ondelete="CASCADE"), index=True, comment="所属运行"
    )
    insight_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_agent_insight.id", ondelete="SET NULL"), default=None, comment="来源洞察"
    )
    action_type: Mapped[str] = mapped_column(
        String(24), default="create_task", server_default="create_task", comment="动作类型"
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="动作配置载荷")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending/approved/rejected/executed/failed"
    )
    executed_by: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, comment="执行者（Action Agent）"
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="执行时间"
    )
    result: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="执行结果")
    published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否已回写事件总线"
    )
    event_name: Mapped[Optional[str]] = mapped_column(
        String(128), default=None, comment="回写事件名"
    )
    error: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="失败原因")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
