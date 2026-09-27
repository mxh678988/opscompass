"""指标中心：请求 / 响应模型。"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- 维度
class DimensionBase(BaseModel):
    code: str = Field(..., max_length=64, description="维度编码")
    name: str = Field(..., max_length=128, description="维度名称")
    dim_type: str = Field("enum", description="enum / datetime / number")
    source_field: Optional[str] = Field(None, max_length=128)
    value_scope: Optional[list[Any]] = None


class DimensionCreate(DimensionBase):
    pass


class DimensionOut(DimensionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------- 指标
class MetricBase(BaseModel):
    code: str = Field(..., max_length=64, description="指标编码，如 gmv")
    name: str = Field(..., max_length=128, description="指标名称")
    description: Optional[str] = Field(None, description="口径说明")
    metric_type: str = Field("atomic", description="atomic 原子 / derived 派生")
    agg_func: str = Field("sum", description="sum/avg/count/count_distinct/max/min/ratio")
    formula: Optional[str] = Field(None, description="派生指标表达式")
    unit: str = Field("", max_length=16, description="单位")
    precision: int = Field(2, ge=0, le=6, description="小数位")
    granularity: str = Field("day", description="hour/day/week/month")
    owner: Optional[str] = Field(None, max_length=64)
    tags: Optional[list[str]] = None
    category_id: Optional[int] = None
    source_id: Optional[int] = None
    status: str = Field("draft", description="draft/online/offline")


class MetricCreate(MetricBase):
    dimensions: list[DimensionCreate] = Field(default_factory=list, description="绑定的维度")


class MetricUpdate(BaseModel):
    """局部更新，未传字段保持不变。"""

    name: Optional[str] = None
    description: Optional[str] = None
    metric_type: Optional[str] = None
    agg_func: Optional[str] = None
    formula: Optional[str] = None
    unit: Optional[str] = None
    precision: Optional[int] = Field(None, ge=0, le=6)
    granularity: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[list[str]] = None
    category_id: Optional[int] = None
    source_id: Optional[int] = None
    status: Optional[str] = None


class MetricOut(MetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    dimensions: list[DimensionOut] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------- 指标值
class MetricValueIn(BaseModel):
    stat_time: datetime = Field(..., description="统计时间点，如 2026-09-01T00:00:00")
    granularity: str = Field("day", description="hour/day/week/month")
    dims: Optional[dict[str, Any]] = Field(None, description='维度组合，如 {"channel": "app"}')
    value: float = Field(..., description="指标值")


class MetricValueBatchIn(BaseModel):
    items: list[MetricValueIn] = Field(..., min_length=1, max_length=5000)


class MetricValueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_id: int
    stat_time: datetime
    granularity: str
    dims: Optional[dict[str, Any]] = None
    value: float


class TrendPoint(BaseModel):
    stat_time: datetime
    value: float


class TrendOut(BaseModel):
    code: str
    granularity: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    points: list[TrendPoint] = Field(default_factory=list)


class OverviewItem(BaseModel):
    """总览卡片：当前值 + 环比。"""

    code: str
    name: str
    unit: str = ""
    precision: int = 2
    value: float = 0.0
    prev_value: Optional[float] = None
    delta_ratio: Optional[float] = Field(None, description="环比变化率，如 0.12 表示 +12%")
    stat_time: Optional[datetime] = None
    has_data: bool = False


class OverviewOut(BaseModel):
    stat_date: Optional[datetime] = None
    items: list[OverviewItem] = Field(default_factory=list)


# ---------------------------------------------------------------- 全景罗盘
class BreakdownItem(BaseModel):
    """维度拆解项：某维度取值下的指标值。"""

    dim_value: str
    value: float = 0.0
    prev_value: Optional[float] = None
    delta_ratio: Optional[float] = Field(None, description="环比变化率")
    share: Optional[float] = Field(None, description="占该指标各维度值合计的比例")


class CompassMetric(BaseModel):
    """全景罗盘单指标：整体口径 + 维度拆解 + 趋势。"""

    code: str
    name: str
    unit: str = ""
    precision: int = 2
    has_data: bool = False
    value: float = 0.0
    prev_value: Optional[float] = None
    delta_ratio: Optional[float] = None
    stat_time: Optional[datetime] = None
    breakdown: list[BreakdownItem] = Field(default_factory=list)
    trend: list[TrendPoint] = Field(default_factory=list)


class CompassOut(BaseModel):
    """全景罗盘响应：一次返回全部上线指标的全局视图。"""

    granularity: str = "day"
    dim_key: Optional[str] = Field(None, description="当前拆解维度键，未指定为 None")
    dim_name: Optional[str] = Field(None, description="拆解维度名称")
    available_dim_keys: list[str] = Field(default_factory=list, description="已接入数据中出现过的维度键")
    dim_values: list[str] = Field(default_factory=list)
    latest_stat: Optional[datetime] = None
    items: list[CompassMetric] = Field(default_factory=list)
