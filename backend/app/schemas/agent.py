"""M12 智能体编排请求/响应结构。"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentRunIn(BaseModel):
    """发起一次智能体编排运行（场景模板 → 绑定数据源 → 配置动作）。"""

    name: str = Field(..., min_length=1, max_length=200, description="运行名称")
    scenario: str = Field(default="custom", description="场景模板 churn_recall/conversion_promote/channel_roi/custom")
    datasource_bindings: Optional[dict[str, Any]] = Field(
        default=None, description="数据源绑定 {数据源 ID: 角色}"
    )
    action_config: Optional[dict[str, Any]] = Field(
        default=None, description="执行动作配置（模板参数 / 人群包 ID / 通知内容等）"
    )
    approval_required: bool = Field(default=True, description="是否强制人工确认闸门")
    created_by: str = Field(default="system", max_length=64, description="发起人")


class AgentRunPatch(BaseModel):
    """更新运行（人工确认/驳回）。"""

    status: Optional[str] = Field(default=None, description="awaiting_approval 后续状态：executing 确认 / rejected 驳回")
    approve_note: Optional[str] = Field(default=None, description="确认意见")
    approved_by: Optional[str] = Field(default=None, max_length=64, description="确认人")


class AgentActionIn(BaseModel):
    """手动登记执行动作（一般由 Action Agent 生成）。"""

    insight_id: Optional[int] = Field(default=None, description="来源洞察 ID")
    action_type: str = Field(default="create_task", description="create_task/create_segment/notify/plugin/record")
    payload: Optional[dict[str, Any]] = Field(default=None, description="动作配置载荷")
