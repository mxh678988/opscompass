"""M14 导入导出安全中心：请求/响应 schema。"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ImportRequest(BaseModel):
    """导入压缩包自动解压提取请求。"""

    source_path: str = Field(..., description="源压缩包绝对路径")
    target_dir: str = Field(..., description="解压目标目录（自动创建）")
    archive_type: str = Field(default="zip", description="压缩类型 zip/tar.gz")

    @field_validator("archive_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in ("zip", "tar.gz"):
            raise ValueError("仅支持 zip / tar.gz")
        return v


class ExportRequest(BaseModel):
    """导出压缩请求（加密为付费插件能力）。"""

    source_dir: str = Field(..., description="待导出目录绝对路径")
    target_name: str = Field(..., description="导出压缩包文件名（含 .zip）")
    encrypted: bool = Field(default=False, description="是否加密压缩（需付费插件）")
    password: Optional[str] = Field(default=None, description="加密密码（encrypted=True 时必填）")

    @field_validator("target_name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        if not v.endswith(".zip"):
            raise ValueError("导出文件名必须以 .zip 结尾")
        return v

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 4:
            raise ValueError("加密密码至少 4 位")
        return v


class ImportRecordOut(BaseModel):
    """导入记录响应。"""

    id: int
    tenant_id: int
    source_name: str
    archive_type: str
    target_dir: str
    extracted: bool
    file_count: int
    status: str
    error: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ExportRecordOut(BaseModel):
    """导出记录响应。"""

    id: int
    tenant_id: int
    target_name: str
    encrypted: bool
    plugin_required: bool
    file_count: int
    status: str
    target_path: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}
