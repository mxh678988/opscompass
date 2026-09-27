"""P9 模型中心模型：模型接入端点（本地 Ollama / OpenAI 兼容云端）。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 接入类型
ENDPOINT_KINDS = ("local_ollama", "cloud_openai")
# 推荐分档（按显存）
VRAM_TIERS = ("cpu", "4g", "8g", "12g", "16g", "24g", "48g", "80g")


class AIModelEndpoint(Base):
    """模型接入端点配置。

    - kind=local_ollama：本地 Ollama 服务（默认 http://host.docker.internal:11434）
    - kind=cloud_openai：任意 OpenAI 兼容云端端点（DeepSeek / 通义 / Moonshot / vLLM 等）
    - api_key 以密文存储（app.core.crypto.encrypt），接口只回显脱敏提示
    """

    __tablename__ = "oc_ai_model_endpoint"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_oc_ai_model_endpoint_name"),
        Index("ix_oc_ai_model_endpoint_kind", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(64), comment="端点名称，租户内唯一")
    kind: Mapped[str] = mapped_column(
        String(32), comment="接入类型：local_ollama 本地 Ollama / cloud_openai OpenAI 兼容云端"
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(32), default=None, comment="供应商标识：ollama / deepseek / openai / custom 等"
    )
    base_url: Mapped[str] = mapped_column(String(255), comment="接口基址")
    model: Mapped[str] = mapped_column(String(128), comment="模型名，如 qwen2.5:7b")
    param_scale: Mapped[Optional[str]] = mapped_column(
        String(32), default=None, comment="参数量级标注，如 7B / 14B"
    )
    api_key_enc: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="云端 API Key 密文（Fernet）"
    )
    api_key_hint: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, comment="API Key 脱敏提示，如 sk-***abcd"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否启用"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否为当前生效端点（租户内至多一个）"
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(32), default="manual", comment="来源：manual 手工配置 / recommend 推荐一键接入"
    )
    remark: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="备注")
    last_test_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="最近一次连通性自检时间"
    )
    last_test_ok: Mapped[Optional[bool]] = mapped_column(
        Boolean, default=None, comment="最近一次自检结果"
    )
    last_test_latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer, default=None, comment="最近一次自检耗时（毫秒）"
    )
    last_test_message: Mapped[Optional[str]] = mapped_column(
        String(255), default=None, comment="最近一次自检说明"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
