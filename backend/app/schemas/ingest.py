"""数据接入：请求 / 响应模型。"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class IngestMapping(BaseModel):
    """文件列 → 指标的映射配置。

    - wide（宽表）：一行 = 一个时间点的多个指标，metric_columns 指定「指标编码 → 文件列名」
    - long（长表）：一行 = 一个时间点的一个指标，metric_column / value_column 指定编码列与数值列
    """

    layout: Literal["wide", "long"] = "wide"
    time_column: str = Field(..., max_length=128, description="时间列名")
    time_format: Optional[str] = Field(None, max_length=64, description="时间格式，如 %Y-%m-%d")
    granularity: str = Field("day", description="hour/day/week/month")
    # 宽表
    metric_columns: dict[str, str] = Field(
        default_factory=dict, description="指标编码 -> 文件列名（宽表）"
    )
    # 长表
    metric_column: Optional[str] = Field(None, max_length=128, description="指标编码所在列（长表）")
    value_column: Optional[str] = Field(None, max_length=128, description="指标值所在列（长表）")
    dim_columns: list[str] = Field(default_factory=list, description="维度列（长表）")
    # 通用
    auto_create_metric: bool = Field(False, description="指标不存在时按列名自动创建")
    auto_metric_status: str = Field("online", description="自动创建指标的初始状态")


class IngestPreviewIn(BaseModel):
    file_name: str = Field(..., max_length=255, description="已上传到 data/raw 的文件名")
    limit: int = Field(20, ge=1, le=200, description="预览行数")


class IngestPreviewOut(BaseModel):
    file_name: str
    columns: list[str] = Field(default_factory=list)
    total_rows: int = 0
    rows: list[dict[str, Any]] = Field(default_factory=list)
    suggested: dict[str, Any] = Field(default_factory=dict, description="建议的行映射配置")
    known_metrics: list[dict[str, Any]] = Field(
        default_factory=list, description="租户已有指标（code/name/unit）"
    )


class IngestRunIn(BaseModel):
    file_name: str = Field(..., max_length=255, description="已上传到 data/raw 的文件名")
    source_code: Optional[str] = Field(None, max_length=64, description="关联数据源编码")
    mapping: IngestMapping


class ImportTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    source_id: Optional[int] = None
    file_name: str
    file_path: str
    file_size: int = 0
    layout: str = "wide"
    granularity: str = "day"
    status: str = "pending"
    total_rows: int = 0
    success_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0
    value_count: int = 0
    metric_codes: Optional[list[Any]] = None
    mapping: Optional[dict[str, Any]] = None
    error_detail: Optional[list[Any]] = None
    error_msg: Optional[str] = None
    elapsed_ms: int = 0
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class UploadOut(BaseModel):
    file_name: str
    file_size: int
    file_hash: str
    saved_path: str
