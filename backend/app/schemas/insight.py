"""智能洞察中心（InsightCenter）请求/响应结构。

洞察中心聚合 M9/M11/M12 与既有指标/AI 分析能力，输出：
- 看板 AI 总结（dashboard summary）
- 异常波动识别与归因（anomaly）
- 可行动建议列表（suggestion，可一键转任务）
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class InsightCenterQuery(BaseModel):
    """洞察中心查询参数（时间范围 / 指标范围）。"""

    days: int = Field(default=7, ge=1, le=90, description="回溯天数")
    metric_codes: Optional[list[str]] = Field(default=None, description="限定指标编码，为空则全量")


class InsightToTaskIn(BaseModel):
    """洞察 → 一键转任务。"""

    insight_id: Optional[int] = Field(default=None, description="来源洞察 ID（AgentInsight / AiInsight）")
    title: str = Field(..., min_length=1, max_length=200, description="任务标题")
    description: Optional[str] = Field(default=None, description="任务描述")
    assignee: Optional[str] = Field(default=None, max_length=64, description="负责人")
    due_in_days: int = Field(default=7, ge=0, le=365, description="截止天数")
