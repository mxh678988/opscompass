"""M10 人群包引擎请求/响应结构。"""

from typing import Optional

from pydantic import BaseModel, Field


class AudienceSegmentIn(BaseModel):
    """创建人群包：基于预测结果按概率区间圈选。"""

    name: str = Field(..., min_length=1, max_length=200, description="人群包名称")
    target: str = Field(default="churn", description="圈选目标 churn/conversion")
    source_job_id: Optional[int] = Field(default=None, description="来源预测任务 ID（复用预测结果）")
    min_prob: Optional[float] = Field(default=None, ge=0, le=1, description="概率下限（含）")
    max_prob: Optional[float] = Field(default=None, ge=0, le=1, description="概率上限（含）")
    band: Optional[str] = Field(default=None, description="概率档位 high/medium/low（可选）")
    description: Optional[str] = Field(default=None, max_length=500, description="说明")


class AudienceSegmentPatch(BaseModel):
    """修改人群包（状态流转 / 说明）。"""

    status: Optional[str] = Field(default=None, description="draft/ready/active/expired/failed")
    description: Optional[str] = Field(default=None, max_length=500, description="说明")


class AudienceMemberIn(BaseModel):
    """手动添加人群包成员（兼容无预测结果的圈选）。"""

    subject_key: str = Field(..., min_length=1, max_length=128, description="主体键")
    subject_name: Optional[str] = Field(default=None, max_length=128, description="主体名称")
    probability: float = Field(default=0.5, ge=0, le=1, description="概率")
    band: str = Field(default="medium", description="概率档位")


class AudienceReuseIn(BaseModel):
    """复用人群包：从既有包成员中按新区间/档位再圈选。"""

    name: str = Field(..., min_length=1, max_length=200, description="新人群包名称")
    target: str = Field(default="churn", description="圈选目标 churn/conversion")
    source_segment_id: int = Field(..., gt=0, description="来源人群包 ID")
    min_prob: Optional[float] = Field(default=None, ge=0, le=1, description="概率下限（含）")
    max_prob: Optional[float] = Field(default=None, ge=0, le=1, description="概率上限（含）")
    band: Optional[str] = Field(default=None, description="概率档位 high/medium/low（可选）")
    description: Optional[str] = Field(default=None, max_length=500, description="说明")
