"""P9 模型中心请求/响应结构。"""

from typing import Optional

from pydantic import BaseModel, Field


class EndpointIn(BaseModel):
    """新建模型接入端点。"""

    name: str = Field(..., min_length=1, max_length=64, description="端点名称，租户内唯一")
    kind: str = Field(..., description="接入类型：local_ollama / cloud_openai")
    base_url: str = Field(..., min_length=1, max_length=255, description="接口基址")
    model: str = Field(..., min_length=1, max_length=128, description="模型名，如 qwen2.5:7b")
    api_key: Optional[str] = Field(default=None, description="云端 API Key，落库前加密")
    param_scale: Optional[str] = Field(default=None, max_length=32, description="参数量级，如 7B")
    provider: Optional[str] = Field(default=None, max_length=32, description="供应商标识")
    enabled: bool = Field(default=True, description="是否启用")
    is_active: bool = Field(default=False, description="是否设为当前生效端点")
    source: Optional[str] = Field(default="manual", description="来源：manual / recommend")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class EndpointPatch(BaseModel):
    """修改模型接入端点（仅提交需要变更的字段）。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    kind: Optional[str] = Field(default=None, description="接入类型：local_ollama / cloud_openai")
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=255)
    model: Optional[str] = Field(default=None, min_length=1, max_length=128)
    api_key: Optional[str] = Field(default=None, description="传空串表示清空已存 Key")
    param_scale: Optional[str] = Field(default=None, max_length=32)
    provider: Optional[str] = Field(default=None, max_length=32)
    enabled: Optional[bool] = None
    is_active: Optional[bool] = None
    remark: Optional[str] = Field(default=None, max_length=255)


class EndpointTestIn(BaseModel):
    """连通性自检（可传已保存端点 id，也可直传未保存配置）。"""

    id: Optional[int] = Field(default=None, description="已保存端点 ID")
    kind: str = Field(default="local_ollama", description="接入类型")
    base_url: Optional[str] = Field(default=None, description="不传则用端点/系统默认值")
    model: Optional[str] = None
    api_key: Optional[str] = None


class ApplyIn(BaseModel):
    """一键接入：把（推荐档位或自定义）配置设为当前生效端点并落库。"""

    mode: str = Field(default="local", description="local=本地 Ollama；cloud=OpenAI 兼容云端")
    name: Optional[str] = Field(default=None, max_length=64, description="不传则自动生成")
    base_url: Optional[str] = Field(default=None, max_length=255, description="不传则用系统配置默认值")
    model: Optional[str] = Field(default=None, max_length=128, description="不传则用系统配置默认值")
    param_scale: Optional[str] = Field(default=None, max_length=32, description="该模型量级，如 7B")
    api_key: Optional[str] = Field(default=None, description="云端模式必填（若未配置过）")
    verify: bool = Field(default=True, description="落库后是否立即做连通性自检")
    activate: bool = Field(default=True, description="是否设为当前生效端点")


class SyncIn(BaseModel):
    """把当前生效端点回写系统运行配置（.env 的 AI_MODE / AI_LOCAL_* / AI_API_*）。"""

    id: Optional[int] = Field(default=None, description="不传则用当前生效端点")
    apply_to_env: bool = Field(default=True, description="是否把改动写入 .env 持久化")
