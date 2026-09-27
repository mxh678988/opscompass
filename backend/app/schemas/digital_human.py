"""数字人一键生成请求/响应结构。"""

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- 形象库
class AvatarIn(BaseModel):
    """新建数字人形象。"""

    name: str = Field(..., min_length=1, max_length=128, description="形象名称")
    avatar_type: str = Field(default="preset", description="preset|photo|clone")
    gender: str = Field(default="neutral", description="male|female|neutral")
    style: str = Field(default="", max_length=64, description="风格标签")
    preview_url: str = Field(default="", max_length=512, description="封面预览地址")
    source_url: str = Field(default="", max_length=512, description="源素材地址")
    engine: str = Field(default="", max_length=64, description="驱动引擎标识")
    status: str = Field(default="ready", description="ready|training|failed")
    remark: str = Field(default="", description="备注")


class AvatarPatch(BaseModel):
    """修改数字人形象。"""

    name: Optional[str] = Field(default=None, max_length=128)
    avatar_type: Optional[str] = None
    gender: Optional[str] = None
    style: Optional[str] = Field(default=None, max_length=64)
    preview_url: Optional[str] = Field(default=None, max_length=512)
    source_url: Optional[str] = Field(default=None, max_length=512)
    engine: Optional[str] = Field(default=None, max_length=64)
    status: Optional[str] = None
    remark: Optional[str] = None


# ---------------------------------------------------------------- 音色库
class VoiceIn(BaseModel):
    """新建音色。"""

    name: str = Field(..., min_length=1, max_length=128, description="音色名称")
    engine: str = Field(default="edge-tts", description="TTS 引擎")
    voice_id: str = Field(default="", max_length=128, description="引擎内音色标识")
    language: str = Field(default="zh-CN", max_length=32)
    gender: str = Field(default="neutral", description="male|female|neutral")
    speed: str = Field(default="1.0", max_length=16, description="语速倍率")
    sample_url: str = Field(default="", max_length=512)
    status: str = Field(default="ready", description="ready|unavailable")
    remark: str = Field(default="")


class VoicePatch(BaseModel):
    """修改音色。"""

    name: Optional[str] = Field(default=None, max_length=128)
    engine: Optional[str] = None
    voice_id: Optional[str] = Field(default=None, max_length=128)
    language: Optional[str] = Field(default=None, max_length=32)
    gender: Optional[str] = None
    speed: Optional[str] = Field(default=None, max_length=16)
    sample_url: Optional[str] = Field(default=None, max_length=512)
    status: Optional[str] = None
    remark: Optional[str] = None


# ---------------------------------------------------------------- 项目
class ProjectIn(BaseModel):
    """新建数字人项目。"""

    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    topic: str = Field(default="", description="主题/选题")
    source_text: str = Field(default="", description="原始素材文案")
    avatar_id: Optional[int] = Field(default=None, description="形象 ID")
    voice_id: Optional[int] = Field(default=None, description="音色 ID")
    workflow_id: Optional[int] = Field(default=None, description="工作流模板 ID")
    resolution: str = Field(default="720x1280", description="分辨率")
    aspect_ratio: str = Field(default="9:16", description="画幅")
    duration_sec: int = Field(default=0, ge=0, le=3600, description="目标时长（秒）")
    subtitle_enabled: bool = Field(default=True, description="是否烧录字幕")
    bgm: str = Field(default="", max_length=255, description="背景音乐")
    remark: str = Field(default="")


class ProjectPatch(BaseModel):
    """修改数字人项目。"""

    name: Optional[str] = Field(default=None, max_length=255)
    topic: Optional[str] = None
    source_text: Optional[str] = None
    script: Optional[str] = None
    segments: Optional[list] = None
    avatar_id: Optional[int] = None
    voice_id: Optional[int] = None
    workflow_id: Optional[int] = None
    resolution: Optional[str] = None
    aspect_ratio: Optional[str] = None
    duration_sec: Optional[int] = Field(default=None, ge=0, le=3600)
    subtitle_enabled: Optional[bool] = None
    bgm: Optional[str] = Field(default=None, max_length=255)
    remark: Optional[str] = None


class ScriptIn(BaseModel):
    """口播稿生成参数。"""

    topic: Optional[str] = Field(default=None, description="覆盖项目主题")
    source_text: Optional[str] = Field(default=None, description="覆盖原始素材")
    tone: str = Field(default="专业亲和", max_length=64, description="口吻风格")
    segment_count: int = Field(default=4, ge=1, le=12, description="分镜段落数")
    target_sec: int = Field(default=60, ge=10, le=900, description="目标时长（秒）")
    style: str = Field(default="", max_length=128, description="内容方向，如 中华传统文化")
    keywords: list[str] = Field(default_factory=list, description="必须覆盖的关键词")
    rewrite: bool = Field(default=True, description="是否允许在已有脚本上重写")


class GenerateIn(BaseModel):
    """一键生成参数。"""

    force: bool = Field(default=False, description="已有脚本时是否强制重新生成脚本")
    skip_script: bool = Field(default=False, description="跳过脚本阶段（使用已有定稿）")
    engine_preference: dict[str, str] = Field(
        default_factory=dict, description="阶段引擎偏好，如 {'voice': 'edge-tts'}"
    )
    remark: str = Field(default="", description="本次生成备注")


# ---------------------------------------------------------------- 工作流模板
class WorkflowIn(BaseModel):
    """新建工作流模板。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="")
    steps: list = Field(default_factory=list, description="阶段编排数组")
    is_default: bool = Field(default=False)
    enabled: bool = Field(default=True)


class WorkflowPatch(BaseModel):
    """修改工作流模板。"""

    name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = None
    steps: Optional[list] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None


class WorkflowRunIn(BaseModel):
    """按模板执行工作流。"""

    project_id: int = Field(..., ge=1, description="目标项目 ID")
    engine_preference: dict[str, str] = Field(default_factory=dict)
