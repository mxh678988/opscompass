"""数据源：请求 / 响应模型。"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DataSourceBase(BaseModel):
    code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    ds_type: str = Field(..., description="mysql/postgresql/clickhouse/hive/api/csv")
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    db_name: Optional[str] = None
    username: Optional[str] = None
    extra_config: Optional[dict[str, Any]] = None
    status: str = Field("enabled", description="enabled/disabled")


class DataSourceCreate(DataSourceBase):
    password: Optional[str] = Field(None, description="明文密码，落库前加密")


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    ds_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    db_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    extra_config: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class DataSourceOut(DataSourceBase):
    """对外输出，不含密码明文。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
