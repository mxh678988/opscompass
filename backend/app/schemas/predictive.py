"""M9 预测引擎请求/响应结构。"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class PredictionRunIn(BaseModel):
    """发起一次预测任务。"""

    name: str = Field(..., min_length=1, max_length=200, description="任务名称")
    target: str = Field(default="churn", description="预测目标 churn/conversion")
    subject_keys: list[str] = Field(
        default_factory=list, description="预测主体键列表（如用户 ID），为空则按特征自动生成"
    )
    features: Optional[dict[str, Any]] = Field(default=None, description="输入特征快照（key=主体键或全局特征）")
    mode: str = Field(default="local", description="模型路由模式 local/api/rule")
    threshold: Optional[float] = Field(default=None, ge=0, le=1, description="判定阈值")
    rule_fallback: bool = Field(default=True, description="本地模型不可用时是否允许规则兜底")
    source: str = Field(default="event_bus", description="任务来源标记（event_bus/batch/manual）")


class PredictionBatchIn(BaseModel):
    """批量预测：直接给主体列表。"""

    target: str = Field(default="churn", description="预测目标 churn/conversion")
    subjects: list[dict[str, Any]] = Field(..., min_length=1, description="主体列表 [{key, name?, features?}]")
    mode: str = Field(default="local", description="模型路由模式 local/api/rule")
    threshold: Optional[float] = Field(default=None, ge=0, le=1, description="判定阈值")
    rule_fallback: bool = Field(default=True, description="允许规则兜底")
