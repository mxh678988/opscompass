"""存储适配层与一致性对账的请求/响应模型。"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RouteIdentifyIn(BaseModel):
    """数据源类型识别请求。"""

    ds_type: Optional[str] = Field(default=None, description="数据源类型 mysql/postgresql/clickhouse/hive/api/csv")
    file_ext: Optional[str] = Field(default=None, description="文件后缀，如 csv/xlsx/log")
    content: Optional[str] = Field(default=None, description="内容特征描述，用于关键词识别")


class RouteIdentifyOut(BaseModel):
    data_kind: str
    engine: str
    label: str = ""
    matched: bool = False
    reason: str = ""
    rule_id: Optional[int] = None
    inputs: dict = Field(default_factory=dict)


class RouteRuleIn(BaseModel):
    """自定义路由规则。"""

    name: str = Field(min_length=1, max_length=128)
    match_field: str = Field(description="ds_type / file_ext / content_hint")
    match_value: str = Field(min_length=1, max_length=128)
    data_kind: str = Field(description="relational / timeseries / fulltext / cache / file")
    engine: Optional[str] = None
    priority: int = 100
    enabled: bool = True
    remark: Optional[str] = None


class RouteRuleOut(BaseModel):
    id: int
    tenant_id: Optional[int] = None
    name: str
    match_field: str
    match_value: str
    data_kind: str
    engine: str
    priority: int
    enabled: bool
    remark: Optional[str] = None


class ConsistencyCheckIn(BaseModel):
    """一致性对账请求。"""

    scopes: list[str] = Field(default_factory=lambda: ["metric_ts", "search_index", "files"])
    auto_repair: bool = Field(default=False, description="是否自动修复可修复差异（仅指标值/检索索引）")


class ConsistencyCheckOut(BaseModel):
    id: Optional[int] = None
    scope: str
    status: str
    checked: int = 0
    matched: int = 0
    missing: int = 0
    extra: int = 0
    mismatched: int = 0
    repaired: int = 0
    auto_repair: bool = False
    operator: Optional[str] = None
    created_at: Optional[datetime] = None


class DocSearchIn(BaseModel):
    """全文检索请求。"""

    q: str = Field(min_length=1, description="检索关键词")
    doc_type: Optional[str] = Field(default=None, description="限定文档类型 metric/datasource/category")
    limit: int = Field(default=20, ge=1, le=100)


class DocIndexIn(BaseModel):
    """单条检索文档写入。"""

    doc_type: str
    doc_id: str
    title: str = ""
    content: Optional[str] = None
    keywords: Optional[str] = None
    url: Optional[str] = None
    payload: Optional[dict] = None


class TsQueryIn(BaseModel):
    """时序指标查询请求。"""

    metric_code: Optional[str] = None
    metric_id: Optional[int] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    granularity: Optional[str] = None
    bucket: Optional[str] = Field(default=None, description="聚合时间桶 hour/day/week/month")
    agg: str = Field(default="sum", description="聚合方式 sum/avg/max/min/count")
    limit: int = Field(default=200, ge=1, le=2000)


class CacheIn(BaseModel):
    """热点数据缓存写入。"""

    key_parts: list[str] = Field(description="缓存键片段（自动拼接命名空间与租户）")
    value: Any
    ttl: Optional[int] = Field(default=None, ge=1, le=86400)
