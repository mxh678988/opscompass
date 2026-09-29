"""AI 域模型：数据分级 / AI 分析 / 洞察建议 / 权限策略 / 处置单 / 审计。

设计要点：
- 数据分级：规则引擎先定级，AI 与人工可覆盖（ai/manual），结果统一落 oc_ai_data_level_record；
- AI 分析：一次分析一条 oc_ai_analysis，模型来源区分 api / local 两种模式；
- 洞察建议：分析产出若干 oc_ai_insight，携带严重度、置信度、建议动作；
- 权限处理：oc_ai_action_policy 定义「数据级别 × 执行者(ai/human) × 动作」的权限矩阵，
  oc_ai_action_item 是最终处置单：权限内由 AI 自动执行，超出权限转人工审批；
- 审计：所有 AI / 人工 动作全部落 oc_ai_audit_log，保证可追溯。
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# ---------------------------------------------------------------- 枚举常量
# 数据分级：L1 公开 / L2 内部 / L3 敏感 / L4 机密
DATA_LEVELS = ("L1", "L2", "L3", "L4")
DATA_LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
DATA_LEVEL_META = {
    "L1": {"name": "公开", "desc": "已聚合、可对外披露的指标数据"},
    "L2": {"name": "内部", "desc": "内部粒度数据，仅限内部使用"},
    "L3": {"name": "敏感", "desc": "含用户标识、连接凭据或经营敏感信息"},
    "L4": {"name": "机密", "desc": "含个人敏感信息或密钥，严格受控"},
}

# AI 模式：api 云端 API / local 本地模型
AI_MODES = ("api", "local")
# 分析范围
AI_SCOPES = ("overview", "compass", "metric", "quality", "ingest", "datasource", "mixed")
ANALYSIS_STATUSES = ("pending", "running", "success", "failed")

# 洞察分类与严重度
INSIGHT_CATEGORIES = ("anomaly", "trend", "opportunity", "risk", "quality")
INSIGHT_SEVERITIES = ("info", "warning", "critical")
SEVERITY_ORDER = {"info": 1, "warning": 2, "critical": 3}
INSIGHT_STATUSES = ("new", "routed", "resolved", "dismissed")

# 建议动作类型
ACTION_TYPES = ("notify", "inspect", "optimize", "remediate", "escalate", "record", "none")
# 执行者
ACTOR_TYPES = ("ai", "human", "system")
# 处置单状态（revoked：AI 决策被执行后又被用户撤销/叫停）
ACTION_STATUSES = ("pending", "auto_executed", "approved", "rejected", "executed", "failed", "revoked")

# 决策分级授权：三级决策权限边界
# user_only        仅用户本人决策：AI 只给建议，不产生任何自动执行动作
# user_authorized  需用户授权决策：AI 可生成处置方案，执行前须经用户授权
# agent_autonomous 智能体自主决策：低风险动作可由智能体自主执行，用户保留知情权与叫停权
DECISION_LEVELS = ("user_only", "user_authorized", "agent_autonomous")
DECISION_LEVEL_ORDER = {"user_only": 1, "user_authorized": 2, "agent_autonomous": 3}
DECISION_LEVEL_META = {
    "user_only": {
        "name": "仅用户本人决策",
        "desc": "AI 仅输出建议与依据，不发起任何自动执行动作，决策权完全在用户本人",
        "auto_execute": False,
    },
    "user_authorized": {
        "name": "需用户授权决策",
        "desc": "AI 生成处置方案并等待用户授权，授权通过后方可执行",
        "auto_execute": False,
    },
    "agent_autonomous": {
        "name": "智能体自主决策",
        "desc": "权限与风险范围内的低风险动作由智能体自主执行，用户保留知情权与一键叫停权",
        "auto_execute": True,
    },
}
# 决策分级来源
DECISION_SOURCES = ("policy", "manual", "rule")
# 定级来源
GRADE_SOURCES = ("rule", "manual", "ai")
# 分级对象类型
GRADE_OBJECT_TYPES = ("metric", "metric_value", "data_source", "import_task", "analysis", "tenant")


class AiDataLevelRule(Base):
    """数据分级规则：命中即定级，priority 越大越先匹配。"""

    __tablename__ = "oc_ai_data_level_rule"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_ai_level_rule_tenant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    code: Mapped[str] = mapped_column(String(64), comment="规则编码")
    name: Mapped[str] = mapped_column(String(128), comment="规则名称")
    object_type: Mapped[str] = mapped_column(
        String(32), default="metric", server_default="metric", comment="对象类型 metric/data_source/import_task/analysis/*"
    )
    field: Mapped[str] = mapped_column(
        String(64), default="code", server_default="code", comment="判定字段：code/name/description/granularity/type/status/has_credential"
    )
    operator: Mapped[str] = mapped_column(
        String(16),
        default="in",
        server_default="in",
        comment="运算符 eq/ne/in/contains/regex/gte/lte/exists",
    )
    threshold: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="阈值（数组或单值数组）")
    level: Mapped[str] = mapped_column(String(4), default="L2", server_default="L2", comment="命中后定级 L1-L4")
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100", comment="优先级，越大越先匹配")
    builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否系统内置规则"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", comment="是否启用")
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="规则说明")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiDataLevelRecord(Base):
    """数据分级结果：同一对象只保留一条最新定级。"""

    __tablename__ = "oc_ai_data_level_record"
    __table_args__ = (
        UniqueConstraint("tenant_id", "object_type", "object_id", name="uq_ai_level_record_object"),
        Index("ix_ai_level_record_level", "tenant_id", "level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    object_type: Mapped[str] = mapped_column(String(32), comment="对象类型")
    object_id: Mapped[int] = mapped_column(Integer, index=True, comment="对象 ID")
    object_code: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="对象编码/名称")
    level: Mapped[str] = mapped_column(String(4), comment="数据级别 L1-L4")
    source: Mapped[str] = mapped_column(
        String(16), default="rule", server_default="rule", comment="定级来源 rule 规则 / ai 模型 / manual 人工"
    )
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_ai_data_level_rule.id", ondelete="SET NULL"), default=None, comment="命中规则 ID"
    )
    rule_code: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="命中规则编码")
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), default=None, comment="AI 定级置信度")
    grader: Mapped[str] = mapped_column(
        String(64), default="rule-engine", server_default="rule-engine", comment="定级者"
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="定级依据")
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiAnalysis(Base):
    """AI 分析任务：一次分析一条记录，记录双模式模型与耗时。"""

    __tablename__ = "oc_ai_analysis"
    __table_args__ = (
        Index("ix_ai_analysis_tenant_time", "tenant_id", "created_at"),
        Index("ix_ai_analysis_scope", "scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    scope: Mapped[str] = mapped_column(
        String(32), default="overview", server_default="overview", comment="分析范围"
    )
    title: Mapped[str] = mapped_column(String(200), default="", server_default="", comment="分析标题")
    mode: Mapped[str] = mapped_column(String(16), default="local", server_default="local", comment="ai 模式 api/local")
    model: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="实际调用模型名")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending/running/success/failed"
    )
    granularity: Mapped[str] = mapped_column(String(16), default="day", server_default="day", comment="统计粒度")
    dim_key: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="拆解维度键")
    request_params: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="分析入参快照")
    input_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="送模型的指标快照")
    prompt_digest: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="提示词摘要（截断）")
    result_summary: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="模型总体结论")
    insight_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="产出洞察数")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="耗时(ms)")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="输入 token")
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="输出 token")
    error: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="失败原因")
    sim_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否演练/模拟模式（结论不作为真实决策依据）"
    )
    data_sources: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="结论引用的数据来源清单")
    evidence_metrics: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="结论依据的指标清单")
    credibility: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), default=None, comment="本次分析结论整体置信度 0-1"
    )
    created_by: Mapped[str] = mapped_column(
        String(64), default="system", server_default="system", comment="发起方"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None, comment="完成时间")


class AiInsight(Base):
    """AI 洞察与建议：分析产出的最小建议单元。"""

    __tablename__ = "oc_ai_insight"
    __table_args__ = (
        Index("ix_ai_insight_tenant_status", "tenant_id", "status"),
        Index("ix_ai_insight_tenant_decision", "tenant_id", "decision_level"),
        Index("ix_ai_insight_tenant_status_severity", "tenant_id", "status", "severity"),
        Index("ix_ai_insight_status_decision", "status", "decision_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    analysis_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_ai_analysis.id", ondelete="CASCADE"), default=None, index=True, comment="所属分析"
    )
    seq: Mapped[int] = mapped_column(Integer, default=1, server_default="1", comment="序号")
    category: Mapped[str] = mapped_column(
        String(24), default="anomaly", server_default="anomaly", comment="分类"
    )
    severity: Mapped[str] = mapped_column(String(16), default="info", server_default="info", comment="严重度")
    title: Mapped[str] = mapped_column(String(200), comment="洞察标题")
    detail: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="洞察详情")
    metric_codes: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="涉及指标编码")
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="数据依据")
    suggestion: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="AI 处置建议")
    action_type: Mapped[str] = mapped_column(
        String(16), default="record", server_default="record", comment="建议动作类型"
    )
    data_level: Mapped[str] = mapped_column(
        String(4), default="L2", server_default="L2", comment="所属数据级别"
    )
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), default=None, comment="置信度 0-1")
    data_sources: Mapped[Optional[list]] = mapped_column(
        JSON, default=None, comment="数据来源清单（指标表/导入任务/数据源）"
    )
    evidence_metrics: Mapped[Optional[list]] = mapped_column(
        JSON, default=None, comment="依据指标清单（编码 + 取值 + 环比）"
    )
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="结论生成时间"
    )
    sim_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否演练/模拟模式"
    )
    decision_level: Mapped[str] = mapped_column(
        String(24),
        default="user_authorized",
        server_default="user_authorized",
        comment="决策分级 user_only/user_authorized/agent_autonomous",
    )
    status: Mapped[str] = mapped_column(
        String(16), default="new", server_default="new", comment="new/routed/resolved/dismissed"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiActionPolicy(Base):
    """处置权限策略：数据级别 × 执行者 × 动作 → 是否需要复核/审批。"""

    __tablename__ = "oc_ai_action_policy"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_ai_policy_tenant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    code: Mapped[str] = mapped_column(String(64), comment="策略编码")
    name: Mapped[str] = mapped_column(String(128), comment="策略名称")
    data_level: Mapped[str] = mapped_column(String(4), comment="适用数据级别 L1-L4")
    actor: Mapped[str] = mapped_column(String(16), comment="执行者 ai / human")
    action_type: Mapped[str] = mapped_column(
        String(16), default="*", server_default="*", comment="适用动作类型，* 表示全部"
    )
    max_severity: Mapped[str] = mapped_column(
        String(16), default="warning", server_default="warning", comment="该策略允许处理的最大严重度"
    )
    allow: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", comment="是否允许处置")
    require_review: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否需人工复核"
    )
    require_approval: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否必须人工审批后才可执行"
    )
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100", comment="匹配优先级")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    builtin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", comment="系统内置")
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiActionItem(Base):
    """处置单：权限内 AI 自动执行，超出权限转人工待办。"""

    __tablename__ = "oc_ai_action_item"
    __table_args__ = (
        Index("ix_ai_action_tenant_status", "tenant_id", "status"),
        Index("ix_ai_action_tenant_decision", "tenant_id", "decision_level"),
        Index("ix_ai_action_tenant_status_handler", "tenant_id", "status", "handler"),
        Index("ix_ai_action_tenant_analysis", "tenant_id", "analysis_id"),
        Index("ix_ai_action_status_decision", "status", "decision_level"),
        Index("ix_ai_action_revoked", "revoked"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    insight_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_ai_insight.id", ondelete="SET NULL"), default=None, index=True, comment="来源洞察"
    )
    analysis_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_ai_analysis.id", ondelete="SET NULL"), default=None, comment="来源分析"
    )
    policy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_ai_action_policy.id", ondelete="SET NULL"), default=None, comment="命中策略"
    )
    title: Mapped[str] = mapped_column(String(200), comment="处置标题")
    action_type: Mapped[str] = mapped_column(String(16), default="record", server_default="record", comment="动作类型")
    data_level: Mapped[str] = mapped_column(String(4), default="L2", server_default="L2", comment="数据级别")
    severity: Mapped[str] = mapped_column(String(16), default="info", server_default="info", comment="严重度")
    decision_level: Mapped[str] = mapped_column(
        String(24),
        default="user_authorized",
        server_default="user_authorized",
        comment="决策分级 user_only 仅用户本人 / user_authorized 需用户授权 / agent_autonomous 智能体自主",
    )
    decision_source: Mapped[str] = mapped_column(
        String(16), default="policy", server_default="policy", comment="分级来源 policy/manual/rule"
    )
    sim_mode: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="是否来自演练/模拟模式的分析结论：为真时不得作为真实经营决策依据",
    )
    handler: Mapped[str] = mapped_column(
        String(16), default="human", server_default="human", comment="处置方：ai 自动 / human 人工"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        server_default="pending",
        comment="pending 待办 / auto_executed AI 已自动执行 / approved 已批准 / rejected 已驳回 / executed 已执行 / failed / revoked 已撤销叫停",
    )
    review_required: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否需人工复核"
    )
    assignee: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="责任人")
    decision_by: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="审批/处置人")
    decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    decision_note: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="审批意见")
    execution_result: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="执行结果说明")
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    revoked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否已被用户撤销/叫停"
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="撤销/叫停时间"
    )
    revoked_by: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="撤销/叫停操作人")
    revoke_reason: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="撤销/叫停原因")
    prev_status: Mapped[Optional[str]] = mapped_column(
        String(16), default=None, comment="撤销前的状态，用于回溯与还原"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiAuditLog(Base):
    """AI / 人工动作审计日志。"""

    __tablename__ = "oc_ai_audit_log"
    __table_args__ = (Index("ix_ai_audit_tenant_time", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    actor_type: Mapped[str] = mapped_column(
        String(16), default="system", server_default="system", comment="执行者类型 ai/human/system"
    )
    actor: Mapped[str] = mapped_column(String(64), default="system", server_default="system", comment="执行者")
    action: Mapped[str] = mapped_column(String(64), comment="动作，如 analyze/grade/auto_execute/approve/reject")
    object_type: Mapped[str] = mapped_column(String(32), default="", server_default="", comment="对象类型")
    object_id: Mapped[Optional[int]] = mapped_column(Integer, default=None, comment="对象 ID")
    from_state: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="原状态")
    to_state: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="新状态")
    detail: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="明细")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
