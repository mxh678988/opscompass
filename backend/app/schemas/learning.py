"""P8 学习进化闭环请求/响应结构。"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class FeedbackIn(BaseModel):
    """登记一条决策反馈（采纳/效果回流）。"""

    insight_id: Optional[int] = Field(default=None, description="关联 AI 洞察 ID")
    action_item_id: Optional[int] = Field(default=None, description="关联处置单 ID")
    policy_code: str = Field(default="", max_length=64, description="策略编码，权重自调维度")
    action_type: str = Field(default="", max_length=64, description="动作类型，权重自调维度")
    data_level: str = Field(default="L1", max_length=16, description="数据分级 L1~L4")
    decision: str = Field(default="adopted", description="采纳结果 adopted/partial/rejected/ignored")
    outcome: str = Field(default="unknown", description="实际效果 success/neutral/fail/unknown")
    outcome_score: Optional[float] = Field(default=None, description="效果得分 0~100")
    effect_note: str = Field(default="", description="效果说明")
    remark: str = Field(default="", description="备注")
    applied: bool = Field(default=True, description="是否计入策略权重自调")


class FeedbackPatch(BaseModel):
    """补录/修正反馈的实际效果字段。"""

    decision: Optional[str] = None
    outcome: Optional[str] = None
    outcome_score: Optional[float] = None
    effect_note: Optional[str] = None
    remark: Optional[str] = None
    applied: Optional[bool] = None


class WeightAdjustIn(BaseModel):
    """策略权重自调参数。"""

    policy_code: Optional[str] = Field(default=None, max_length=64, description="不传则全量重算")
    action_type: Optional[str] = Field(default=None, max_length=64)
    min_samples: int = Field(default=5, ge=1, le=1000, description="低于该样本数保持基准权重")
    learning_rate: float = Field(default=0.5, gt=0, le=2, description="权重对成功率的敏感度")
    weight_floor: float = Field(default=0.2, gt=0, le=5, description="权重下限")
    weight_ceil: float = Field(default=3.0, gt=0, le=10, description="权重上限")
    remark: str = Field(default="", description="调整说明")

class CaseIn(BaseModel):
    """新建经验案例。"""

    title: str = Field(..., min_length=1, max_length=255, description="案例标题")
    category: str = Field(default="", max_length=64, description="案例分类")
    tags: Optional[list] = Field(default=None, description="标签数组")
    scenario: str = Field(default="", description="问题场景")
    action_taken: str = Field(default="", description="采取的动作")
    outcome: str = Field(default="", description="最终结果")
    outcome_score: Optional[float] = Field(default=None, description="结果得分 0~100")
    lesson: str = Field(default="", description="经验教训/可复用结论")
    source_insight_id: Optional[int] = None
    source_feedback_id: Optional[int] = None
    status: str = Field(default="draft", description="draft/verified/archived")


class CasePatch(BaseModel):
    """修改经验案例。"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = Field(default=None, max_length=64)
    tags: Optional[list] = None
    scenario: Optional[str] = None
    action_taken: Optional[str] = None
    outcome: Optional[str] = None
    outcome_score: Optional[float] = None
    lesson: Optional[str] = None
    status: Optional[str] = None


class CaseFromFeedbackIn(BaseModel):
    """由反馈一键沉淀为经验案例。"""

    feedback_id: int = Field(..., description="来源反馈 ID")
    title: Optional[str] = Field(default=None, max_length=255, description="不传则自动生成")
    category: Optional[str] = Field(default=None, max_length=64)
    lesson: str = Field(default="", description="经验教训")
    status: str = Field(default="draft", description="draft/verified")


class ExperimentIn(BaseModel):
    """新建 A/B 对照实验。"""

    name: str = Field(..., min_length=1, max_length=255, description="实验名称")
    code: Optional[str] = Field(default=None, max_length=64, description="不传则自动生成")
    hypothesis: str = Field(default="", description="实验假设")
    metric_code: str = Field(default="", max_length=64, description="对照指标编码")
    variant_a: str = Field(default="", max_length=128, description="方案 A 描述")
    variant_b: str = Field(default="", max_length=128, description="方案 B 描述")
    status: str = Field(default="draft", description="draft/running")


class ExperimentPatch(BaseModel):
    """修改实验。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    hypothesis: Optional[str] = None
    metric_code: Optional[str] = Field(default=None, max_length=64)
    variant_a: Optional[str] = Field(default=None, max_length=128)
    variant_b: Optional[str] = Field(default=None, max_length=128)
    status: Optional[str] = None


class ExperimentRecordIn(BaseModel):
    """登记一次对照样本。"""

    variant: str = Field(..., description="样本归属方案：a / b")
    result: float = Field(..., description="该样本指标值")
    remark: str = Field(default="", description="备注")


class ExperimentFinishIn(BaseModel):
    """结项并判定胜出方案（不传则按 lift 自动判定）。"""

    winner: Optional[str] = Field(default=None, description="a / b / none，不传自动判定")
    conclusion: str = Field(default="", description="实验结论")
    apply_weight: bool = Field(default=False, description="是否把结论写入策略权重调整说明")


class ListQuery(BaseModel):
    """通用列表查询参数（供服务层复用）。"""

    keyword: Optional[str] = None
    status: Optional[str] = None
    extra: Optional[dict] = Field(default=None, description="扩展过滤条件")
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=200)

