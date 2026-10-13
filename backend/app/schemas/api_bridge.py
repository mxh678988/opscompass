"""M13 API 申请助手请求/响应结构。"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ApiPlatformTemplateIn(BaseModel):
    """新增/编辑平台模板入参。"""

    name: str = Field(..., min_length=1, max_length=200, description="平台名称")
    apply_url: str = Field(..., min_length=1, max_length=500, description="申请地址")
    field_schema: Optional[dict[str, Any]] = Field(
        default=None, description="表单字段映射（JSON：字段名/标签/必填/选项等）"
    )
    requires_manual: bool = Field(
        default=False, description="是否需人工验证/付费/资质审核"
    )
    category: str = Field(
        default="other", description="分类 ecommerce/website/other"
    )
    enabled: bool = Field(default=True, description="是否启用")


class ApiPlatformTemplatePatch(BaseModel):
    """模板部分更新（启用/停用或局部修改）。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200, description="平台名称")
    apply_url: Optional[str] = Field(default=None, min_length=1, max_length=500, description="申请地址")
    field_schema: Optional[dict[str, Any]] = Field(default=None, description="表单字段映射")
    requires_manual: Optional[bool] = Field(default=None, description="是否需人工验证/付费/资质审核")
    category: Optional[str] = Field(default=None, description="分类 ecommerce/website/other")
    enabled: Optional[bool] = Field(default=None, description="是否启用")


class ApiApplyTaskIn(BaseModel):
    """创建 API 申请任务入参。

    password 为账号口令明文入参：服务层必须以 AES 加密后写入
    credentials_ref 密文引用，严禁明文密码落库。
    """

    platform_id: Optional[int] = Field(default=None, description="平台模板 ID")
    platform: str = Field(..., min_length=1, max_length=200, description="目标平台名称（模板缺失时直接填写）")
    account: str = Field(..., min_length=1, max_length=255, description="申请账号")
    password: str = Field(..., min_length=1, max_length=255, description="账号口令（服务层加密存储）")
    remark: Optional[str] = Field(default=None, max_length=2000, description="申请备注")
    created_by: str = Field(default="system", max_length=64, description="申请人")


class ApiApplyTaskPatch(BaseModel):
    """申请任务状态/进度更新。"""

    status: Optional[str] = Field(
        default=None, description="submitted/awaiting_manual/done/failed"
    )
    progress: Optional[int] = Field(default=None, ge=0, le=100, description="进度 0-100")
    result_message: Optional[str] = Field(default=None, description="结果消息")
    error: Optional[str] = Field(default=None, description="失败原因")
