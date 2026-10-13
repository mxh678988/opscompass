"""M11 企业知识库模型：知识文档与引用日志。

设计要点：
- oc_knowledge_doc 沉淀业务经验/SOP/洞察/策略/手册，供 Agent（M12）引用；
  类型 experience 经验 / sop 流程 / insight 洞察 / policy 策略 / manual 手册；
- 文档携带标签、适用场景、来源，便于检索与权限控制；
- oc_knowledge_ref_log 记录每次被 Agent/用户引用的轨迹，ref_count 累计热度，
  形成「知识沉淀 → 引用 → 反馈」的进化闭环。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 知识类型
KNOWLEDGE_TYPES = ("experience", "sop", "insight", "policy", "manual")
# 文档状态
KNOWLEDGE_STATUSES = ("draft", "published", "archived")
# 引用来源
REF_SOURCES = ("agent", "user", "system", "insight_center", "decision_studio")


class KnowledgeDoc(Base):
    """知识文档：业务经验 / SOP / 洞察 / 策略 / 手册。"""

    __tablename__ = "oc_knowledge_doc"
    __table_args__ = (
        Index("ix_knowledge_doc_tenant_type", "tenant_id", "doc_type"),
        Index("ix_knowledge_doc_tenant_status", "tenant_id", "status"),
        Index("ix_knowledge_doc_ref_count", "ref_count"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    title: Mapped[str] = mapped_column(String(200), comment="文档标题")
    doc_type: Mapped[str] = mapped_column(
        String(16), default="experience", server_default="experience", comment="类型 experience/sop/insight/policy/manual"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="published", server_default="published", comment="draft/published/archived"
    )
    content: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="正文内容")
    summary: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="摘要（供 Agent 快速引用）"
    )
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="标签列表")
    scenario: Mapped[Optional[str]] = mapped_column(
        String(200), default=None, comment="适用场景描述"
    )
    source: Mapped[str] = mapped_column(
        String(64), default="manual", server_default="manual", comment="来源 manual/insight/learning/agent"
    )
    ref_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="累计被引用次数（热度）"
    )
    author: Mapped[str] = mapped_column(
        String(64), default="system", server_default="system", comment="作者/沉淀者"
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="发布时间"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeRefLog(Base):
    """知识引用日志：记录 Agent/用户引用知识文档的轨迹。"""

    __tablename__ = "oc_knowledge_ref_log"
    __table_args__ = (
        Index("ix_knowledge_ref_log_doc", "doc_id", "created_at"),
        Index("ix_knowledge_ref_log_tenant_time", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    doc_id: Mapped[int] = mapped_column(
        ForeignKey("oc_knowledge_doc.id", ondelete="CASCADE"), index=True, comment="被引用文档"
    )
    source: Mapped[str] = mapped_column(
        String(32), default="agent", server_default="agent", comment="引用来源 agent/user/system/insight_center/decision_studio"
    )
    ref_key: Mapped[Optional[str]] = mapped_column(
        String(128), default=None, comment="引用方标识（Agent 名 / 任务 ID）"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="引用说明")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# 知识库状态
KB_STATUSES = ("active", "disabled")
# 知识库文件状态
KB_FILE_STATUSES = ("active", "removed")


class KnowledgeBase(Base):
    """知识库（虚拟视图）：挂载一批知识文档与文件，支撑检索问答。"""

    __tablename__ = "oc_knowledge_base"
    __table_args__ = (
        Index("ix_kb_tenant_status", "tenant_id", "status"),
        Index("ix_kb_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(100), comment="知识库名称")
    description: Mapped[Optional[str]] = mapped_column(String(500), default=None, comment="描述")
    config: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="配置（模型/top_k/标签等）")
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active", comment="active/disabled"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeBaseFile(Base):
    """知识库文件：上传到知识库的源文件（仅登记，磁盘落于 data/knowledge）。"""

    __tablename__ = "oc_knowledge_base_file"
    __table_args__ = (
        Index("ix_kb_file_base_status", "base_id", "status"),
        Index("ix_kb_file_tenant_time", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    base_id: Mapped[int] = mapped_column(
        ForeignKey("oc_knowledge_base.id", ondelete="CASCADE"), index=True, comment="所属知识库"
    )
    file_name: Mapped[str] = mapped_column(String(200), comment="原始文件名")
    file_path: Mapped[str] = mapped_column(String(600), comment="磁盘存储路径")
    file_type: Mapped[str] = mapped_column(String(16), default="other", comment="扩展名（小写）")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="文件大小")
    uploader: Mapped[str] = mapped_column(String(64), default="system", server_default="system", comment="上传者")
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active", comment="active/removed"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
