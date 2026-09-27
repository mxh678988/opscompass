"""采集调度：请求 / 响应模型。"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ingest import IngestMapping


class CollectTaskIn(BaseModel):
    """新建 / 编辑采集任务。

    mapping 与数据接入共用一套字段映射语义：
    - csv 模式：time_column / metric_columns 指向 CSV 的列名
    - api 模式：同名字段指向 JSON 记录的键名
    """

    code: str = Field(..., min_length=2, max_length=64, description="任务编码，租户内唯一")
    name: str = Field(..., min_length=1, max_length=128, description="任务名称")
    source_id: Optional[int] = Field(None, description="关联数据源 ID")
    collect_mode: Literal["csv", "api", "sql"] = Field("csv", description="采集方式")
    target: str = Field(..., min_length=1, max_length=512, description="文件名 / 接口 URL / 库表名")
    mapping: Optional[IngestMapping] = Field(None, description="字段映射配置")
    extra_config: dict[str, Any] = Field(
        default_factory=dict, description="扩展配置：data_path（API 数据路径）、method、headers 等"
    )
    schedule_type: Literal["manual", "interval"] = Field("manual", description="调度策略")
    interval_minutes: int = Field(0, ge=0, le=10080, description="调度间隔（分钟）")
    cron_expr: Optional[str] = Field(None, max_length=64, description="Cron 表达式（预留）")
    status: Literal["enabled", "paused"] = Field("enabled", description="任务状态")
    remark: Optional[str] = Field(None, max_length=500, description="备注")

    @field_validator("code")
    @classmethod
    def _code_pattern(cls, value: str) -> str:
        cleaned = value.strip()
        if not all(ch.isalnum() or ch in "_-" for ch in cleaned):
            raise ValueError("任务编码仅允许字母、数字、下划线与连字符")
        return cleaned

    @field_validator("interval_minutes")
    @classmethod
    def _interval_check(cls, value: int) -> int:
        if value and value < 1:
            raise ValueError("调度间隔至少 1 分钟")
        return value


class CollectTaskUpdateIn(BaseModel):
    """编辑采集任务（字段可选）。"""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    source_id: Optional[int] = None
    collect_mode: Optional[Literal["csv", "api", "sql"]] = None
    target: Optional[str] = Field(None, min_length=1, max_length=512)
    mapping: Optional[IngestMapping] = None
    extra_config: Optional[dict[str, Any]] = None
    schedule_type: Optional[Literal["manual", "interval"]] = None
    interval_minutes: Optional[int] = Field(None, ge=0, le=10080)
    cron_expr: Optional[str] = Field(None, max_length=64)
    status: Optional[Literal["enabled", "paused"]] = None
    remark: Optional[str] = Field(None, max_length=500)


class CollectTaskOut(BaseModel):
    """采集任务列表项。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    name: str
    source_id: Optional[int] = None
    source_name: str = ""
    source_type: str = ""
    collect_mode: str = "csv"
    target: str = ""
    mapping: Optional[dict[str, Any]] = None
    extra_config: Optional[dict[str, Any]] = None
    schedule_type: str = "manual"
    interval_minutes: int = 0
    cron_expr: Optional[str] = None
    status: str = "enabled"
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    run_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_status: Optional[str] = None
    remark: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CollectRunOut(BaseModel):
    """采集运行记录。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    task_id: int
    task_code: str = ""
    task_name: str = ""
    collect_mode: str = "csv"
    trigger: str = "manual"
    status: str = "running"
    rows_in: int = 0
    rows_written: int = 0
    rows_failed: int = 0
    duration_ms: int = 0
    simulated: bool = False
    message: str = ""
    detail: Optional[dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class CollectModeOut(BaseModel):
    """采集方式目录项。"""

    mode: str
    name: str
    target_label: str
    target_hint: str
    real_fetch: bool
    description: str


class CollectSourceOut(BaseModel):
    """可绑定的数据源（下拉选项）。"""

    id: int
    code: str
    name: str
    ds_type: str
    status: str


class CollectTrendPoint(BaseModel):
    """执行趋势点。"""

    day: str
    total: int = 0
    success: int = 0
    failed: int = 0


class CollectOverviewOut(BaseModel):
    """采集调度总览。"""

    total_tasks: int = 0
    enabled_tasks: int = 0
    paused_tasks: int = 0
    scheduled_tasks: int = 0
    due_tasks: int = 0
    total_runs: int = 0
    runs_24h: int = 0
    success_24h: int = 0
    failed_24h: int = 0
    success_rate_24h: float = 0.0
    rows_written_24h: int = 0
    total_rows_written: int = 0
    avg_duration_ms: int = 0
    mode_distribution: dict[str, int] = Field(default_factory=dict)
    status_distribution: dict[str, int] = Field(default_factory=dict)
    trend: list[CollectTrendPoint] = Field(default_factory=list)
    recent_runs: list[CollectRunOut] = Field(default_factory=list)
    scheduler_enabled: bool = False
