"""AI 能力：数据分级 / 分析洞察 / 权限处置 / 审计 的请求与响应模型。"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- 数据分级规则
class LevelRuleBase(BaseModel):
    code: str = Field(..., max_length=64, description="规则编码")
    name: str = Field(..., max_length=128, description="规则名称")
    object_type: str = Field("*", description="对象类型 metric/data_source/import_task/analysis/*")
    field: str = Field("code", max_length=64, description="判定字段")
    operator: str = Field("in", description="eq/ne/in/contains/regex/gte/lte/exists")
    threshold: Optional[list[Any]] = Field(None, description="阈值")
    level: str = Field("L2", description="命中后定级 L1-L4")
    priority: int = Field(100, description="优先级，越大越先匹配")
    enabled: bool = True
    description: Optional[str] = None


class LevelRuleCreate(LevelRuleBase):
    pass


class LevelRuleUpdate(BaseModel):
    name: Optional[str] = None
    object_type: Optional[str] = None
    field: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[list[Any]] = None
    level: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class LevelRuleOut(LevelRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    builtin: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LevelRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    object_type: str
    object_id: int
    object_code: str
    level: str
    source: str
    rule_code: Optional[str] = None
    confidence: Optional[float] = None
    grader: str
    reason: Optional[str] = None
    graded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GradeRunIn(BaseModel):
    """触发数据分级。"""

    object_types: list[str] = Field(
        default_factory=lambda: ["metric", "data_source", "import_task"], description="分级对象类型"
    )
    use_ai: bool = Field(False, description="是否使用 AI 辅助定级（否则仅规则引擎）")
    ai_limit: int = Field(20, ge=1, le=50, description="AI 定级的最大对象数")


class GradeRunOut(BaseModel):
    rule_engine: dict[str, Any] = Field(default_factory=dict)
    ai: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------- AI 分析
class AnalysisRunIn(BaseModel):
    scope: str = Field("overview", description="overview/compass/metric/quality/ingest/datasource/mixed")
    granularity: str = Field("day", description="hour/day/week/month")
    dim_key: Optional[str] = Field(None, description="拆解维度键")
    codes: Optional[list[str]] = Field(None, description="限定指标编码")
    title: Optional[str] = Field(None, max_length=200)
    mode: Optional[str] = Field(None, description="覆盖当前模式：api / local")
    model: Optional[str] = Field(None, description="覆盖模型名")
    max_insights: int = Field(8, ge=1, le=20)
    auto_route: bool = Field(True, description="是否自动按权限路由为处置单")


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    scope: str
    title: str
    mode: str
    model: str
    status: str
    granularity: str
    dim_key: Optional[str] = None
    result_summary: Optional[str] = None
    insight_count: int = 0
    duration_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: Optional[str] = None
    sim_mode: bool = Field(False, description="是否演练/模拟模式：结论不作为真实决策依据")
    data_sources: Optional[list[Any]] = Field(None, description="结论引用的数据来源清单")
    evidence_metrics: Optional[list[Any]] = Field(None, description="结论依据的指标清单")
    credibility: Optional[float] = Field(None, description="结论整体置信度 0-1")
    created_by: str = "system"
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    analysis_id: Optional[int] = None
    seq: int
    category: str
    severity: str
    title: str
    detail: Optional[str] = None
    metric_codes: Optional[list[str]] = None
    evidence: Optional[dict[str, Any]] = None
    suggestion: Optional[str] = None
    action_type: str
    data_level: str
    confidence: Optional[float] = None
    data_sources: Optional[list[Any]] = Field(None, description="数据来源清单（来源表/导入任务/数据源）")
    evidence_metrics: Optional[list[Any]] = Field(None, description="依据指标清单（编码/取值/环比）")
    generated_at: Optional[datetime] = Field(None, description="结论生成时间")
    sim_mode: bool = Field(False, description="是否演练/模拟模式")
    decision_level: str = Field("user_authorized", description="决策分级 user_only/user_authorized/agent_autonomous")
    status: str
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------- 权限策略
class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    name: str
    data_level: str
    actor: str
    action_type: str
    max_severity: str
    allow: bool
    require_review: bool
    require_approval: bool
    priority: int
    enabled: bool
    builtin: bool = False
    description: Optional[str] = None


class PolicyUpdate(BaseModel):
    allow: Optional[bool] = None
    require_review: Optional[bool] = None
    require_approval: Optional[bool] = None
    max_severity: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class PolicyDecideOut(BaseModel):
    data_level: str
    actor: str
    action_type: str
    severity: str = "info"
    allow: bool
    require_review: bool
    require_approval: bool
    policy_code: Optional[str] = None
    policy_name: Optional[str] = None
    reason: str = ""


# ---------------------------------------------------------------- 处置单
class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    insight_id: Optional[int] = None
    analysis_id: Optional[int] = None
    policy_id: Optional[int] = None
    title: str
    action_type: str
    data_level: str
    severity: str
    decision_level: str = Field("user_authorized", description="决策分级 user_only/user_authorized/agent_autonomous")
    decision_source: str = Field("policy", description="分级来源 policy/manual/rule")
    sim_mode: bool = Field(False, description="是否来自演练/模拟模式，界面须显性提示")
    handler: str
    status: str
    review_required: bool
    assignee: Optional[str] = None
    decision_by: Optional[str] = None
    decision_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    execution_result: Optional[str] = None
    executed_at: Optional[datetime] = None
    revoked: bool = Field(False, description="是否已被用户撤销/叫停")
    revoked_at: Optional[datetime] = Field(None, description="撤销/叫停时间")
    revoked_by: Optional[str] = Field(None, description="撤销/叫停操作人")
    revoke_reason: Optional[str] = Field(None, description="撤销/叫停原因")
    prev_status: Optional[str] = Field(None, description="撤销前状态，用于回溯")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ActionDecisionIn(BaseModel):
    """人工审批 / 执行入参。"""

    operator: str = Field("operator", max_length=64, description="操作人")
    note: Optional[str] = Field(None, description="审批意见")
    result: Optional[str] = Field(None, description="执行结果说明（execute 时使用）")


class ActionDecisionLevelIn(BaseModel):
    """调整处置单的决策分级（仅用户本人 / 需用户授权 / 智能体自主）。"""

    operator: str = Field("operator", max_length=64, description="操作人")
    decision_level: str = Field(..., description="user_only/user_authorized/agent_autonomous")
    note: Optional[str] = Field(None, description="调整说明")


class ActionRevokeIn(BaseModel):
    """一键撤销 / 叫停 AI 决策。"""

    operator: str = Field("operator", max_length=64, description="操作人")
    reason: Optional[str] = Field(None, description="撤销/叫停原因")


class DecisionLevelOut(BaseModel):
    """决策分级元数据。"""

    code: str
    name: str
    desc: str = ""
    order: int = 0
    auto_execute: bool = False
    need_approval: bool = False


class DecisionBoardOut(BaseModel):
    """决策分级授权看板：分级元数据 + 各级数量 + 待办/叫停概览。"""

    levels: list[DecisionLevelOut] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    revoked_total: int = 0
    pending_total: int = 0
    auto_executed_total: int = 0
    sim_mode_total: int = Field(0, description="演练/模拟模式产出的处置单数量")


class TraceItemOut(BaseModel):
    """决策全过程留痕的单条记录。"""

    seq: int
    at: Optional[datetime] = None
    actor_type: str = ""
    actor: str = ""
    action: str = ""
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    detail: Optional[str] = None


class DecisionTraceOut(BaseModel):
    """处置单全链路留痕（洞察 → 分级 → 处置 → 决策 → 叫停）。"""

    action: ActionOut
    trace: list[TraceItemOut] = Field(default_factory=list)


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    actor_type: str
    actor: str
    action: str
    object_type: str
    object_id: Optional[int] = None
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    detail: Optional[str] = None
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------- 配置与健康
class AiConfigOut(BaseModel):
    enabled: bool
    mode: str
    model: str
    base_url: str
    ready: bool
    modes: dict[str, Any]
    timeout: int
    max_tokens: int
    temperature: float
    probe: Optional[dict[str, Any]] = Field(None, description="实际探测结果（仅 probe=true 时返回）")
    level_meta: dict[str, Any] = Field(default_factory=dict)
    statistics: dict[str, Any] = Field(default_factory=dict)
