"""数字人一键生成模块：形象库 / 音色库 / 生成项目 / 阶段任务 / 工作流模板。

设计要点：
- 形象库 oc_dh_avatar：内置形象 + 照片驱动 + 克隆形象三类，统一登记封面与源文件；
- 音色库 oc_dh_voice：绑定具体 TTS 引擎与音色标识，供配音阶段直接引用；
- 项目 oc_dh_project：一次「一键生成」的业务载体，落口播稿、形象、音色、分辨率与成片；
- 阶段任务 oc_dh_task：脚本 -> 配音 -> 形象 -> 合成 四阶段的执行留痕，含进度与产物；
- 工作流模板 oc_dh_workflow：可复用的阶段编排（步骤 JSON），支持默认模板与启停。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# ---------------------------------------------------------------- 枚举常量
# 项目状态：草稿 / 脚本生成中 / 就绪待生成 / 渲染中 / 已完成 / 失败
DH_PROJECT_STATUSES = ("draft", "scripting", "ready", "rendering", "done", "failed")
# 生成阶段：脚本 -> 配音 -> 形象驱动 -> 合成成片
DH_STAGES = ("script", "voice", "avatar", "compose")
# 阶段状态
DH_TASK_STATUSES = ("pending", "running", "success", "failed", "skipped")
# 形象类型：内置预置 / 照片驱动 / 视频克隆
DH_AVATAR_TYPES = ("preset", "photo", "clone")
# TTS 引擎
DH_TTS_ENGINES = ("edge-tts", "gpt-sovits", "cosyvoice", "azure", "openai", "custom")
# 成片分辨率预设（竖版短视频优先）
DH_RESOLUTIONS = ("720x1280", "1080x1920", "1280x720", "1920x1080", "1024x1024")


class DhAvatar(Base):
    """数字人形象库：预置形象 / 照片驱动 / 视频克隆。"""

    __tablename__ = "oc_dh_avatar"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_dh_avatar_tenant_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(128), comment="形象名称")
    avatar_type: Mapped[str] = mapped_column(
        String(16), default="preset", server_default="preset", comment="preset|photo|clone"
    )
    gender: Mapped[str] = mapped_column(String(16), default="neutral", server_default="neutral", comment="male|female|neutral")
    style: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="风格标签，如 商务/国风/亲和")
    preview_url: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="封面预览地址")
    source_url: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="源素材（照片/视频）地址")
    engine: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="驱动引擎标识，如 sadtalker/wav2lip/heygem")
    status: Mapped[str] = mapped_column(String(16), default="ready", server_default="ready", comment="ready|training|failed")
    remark: Mapped[str] = mapped_column(Text, default="", server_default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DhVoice(Base):
    """音色库：绑定 TTS 引擎与音色标识。"""

    __tablename__ = "oc_dh_voice"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_dh_voice_tenant_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(128), comment="音色名称")
    engine: Mapped[str] = mapped_column(
        String(32), default="edge-tts", server_default="edge-tts", comment="TTS 引擎"
    )
    voice_id: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="引擎内音色标识")
    language: Mapped[str] = mapped_column(String(32), default="zh-CN", server_default="zh-CN", comment="语言")
    gender: Mapped[str] = mapped_column(String(16), default="neutral", server_default="neutral", comment="male|female|neutral")
    speed: Mapped[str] = mapped_column(String(16), default="1.0", server_default="1.0", comment="语速倍率")
    sample_url: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="试听样本地址")
    status: Mapped[str] = mapped_column(String(16), default="ready", server_default="ready", comment="ready|unavailable")
    remark: Mapped[str] = mapped_column(Text, default="", server_default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DhProject(Base):
    """数字人视频项目：一键生成的业务载体。"""

    __tablename__ = "oc_dh_project"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(255), comment="项目名称")
    topic: Mapped[str] = mapped_column(Text, default="", server_default="", comment="主题/选题")
    source_text: Mapped[str] = mapped_column(Text, default="", server_default="", comment="原始素材文案")
    script: Mapped[str] = mapped_column(Text, default="", server_default="", comment="定稿口播稿")
    segments: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="分镜段落数组")
    avatar_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_dh_avatar.id", ondelete="SET NULL"), index=True, comment="形象 ID"
    )
    voice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_dh_voice.id", ondelete="SET NULL"), index=True, comment="音色 ID"
    )
    workflow_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_dh_workflow.id", ondelete="SET NULL"), index=True, comment="工作流模板 ID"
    )
    resolution: Mapped[str] = mapped_column(String(16), default="720x1280", server_default="720x1280", comment="分辨率")
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="9:16", server_default="9:16", comment="画幅")
    duration_sec: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="目标时长（秒）")
    subtitle_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", comment="是否烧录字幕")
    bgm: Mapped[str] = mapped_column(String(255), default="", server_default="", comment="背景音乐标识")
    status: Mapped[str] = mapped_column(
        String(16), default="draft", server_default="draft", comment="draft|scripting|ready|rendering|done|failed"
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="整体进度 0-100")
    video_url: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="成片地址")
    audio_url: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="配音地址")
    cover_url: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="封面地址")
    simulated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", comment="是否演练产物")
    ai_model: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="脚本生成所用模型")
    error: Mapped[str] = mapped_column(Text, default="", server_default="", comment="失败原因")
    remark: Mapped[str] = mapped_column(Text, default="", server_default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tasks: Mapped[list["DhTask"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="DhTask.id"
    )


class DhTask(Base):
    """阶段任务：脚本 / 配音 / 形象驱动 / 合成，四阶段执行留痕。"""

    __tablename__ = "oc_dh_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    project_id: Mapped[int] = mapped_column(ForeignKey("oc_dh_project.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(16), comment="script|voice|avatar|compose")
    stage_name: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="阶段中文名")
    seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="阶段顺序")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending|running|success|failed|skipped"
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="阶段进度 0-100")
    engine: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="执行引擎")
    input_brief: Mapped[str] = mapped_column(Text, default="", server_default="", comment="阶段输入摘要")
    output_url: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="阶段产物地址")
    output_text: Mapped[str] = mapped_column(Text, default="", server_default="", comment="阶段产物文本（如口播稿）")
    message: Mapped[str] = mapped_column(Text, default="", server_default="", comment="执行说明/错误")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="耗时毫秒")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["DhProject"] = relationship(back_populates="tasks")


class DhWorkflow(Base):
    """数字人生成工作流模板：可复用的阶段编排。"""

    __tablename__ = "oc_dh_workflow"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_dh_workflow_tenant_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(128), comment="模板名称")
    description: Mapped[str] = mapped_column(Text, default="", server_default="", comment="模板说明")
    steps: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="阶段编排数组")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", comment="是否默认模板")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", comment="是否启用")
    run_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="累计执行次数")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
