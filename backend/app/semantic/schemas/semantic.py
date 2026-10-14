"""语义层 API Schemas。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SemanticAskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500, description="自然语言问数问题")
    limit: int = Field(200, ge=1, le=1000, description="单指标返回行数上限")


class MetricRowOut(BaseModel):
    code: str
    name: str
    agg_func: Optional[str] = None
    unit: str = ""
    precision: Optional[int] = None
    source_label: str = ""
    dialect: str = ""
    execution_ms: int = 0
    fallback_reason: str = ""
    columns: list[str] = []
    rows: list[dict[str, Any]] = []


class IntentOut(BaseModel):
    metric_codes: list[str] = []
    granularity: str = "day"
    start: Optional[str] = None
    end: Optional[str] = None
    dims_filter: dict[str, Any] = {}
    reason: str = ""
    model: Optional[str] = None
    mode: str = "rule"
    fallback: bool = True


class SemanticAskResponse(BaseModel):
    question: str
    ok: bool
    error: Optional[str] = None
    intent: Optional[IntentOut] = None
    metrics: list[MetricRowOut] = []
    errors: list[str] = []


class SemanticCompileRequest(BaseModel):
    metric_code: str = Field(..., min_length=1, max_length=128)


class SemanticCompileResponse(BaseModel):
    ok: bool
    error: Optional[str] = None
    metric_code: str = ""
    mode: Optional[str] = None
    dialect: Optional[str] = None
    sql: Optional[str] = None
    params: dict[str, Any] = {}
