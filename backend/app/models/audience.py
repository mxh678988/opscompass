"""M10 人群包引擎模型：人群包与成员。

设计要点：
- oc_audience_segment 记录一次圈选任务：基于预测结果（M9）按概率区间圈选，
  支持 min_prob/max_prob 区间、圈选主体数量与生成策略；
- source_job_id 记录来源预测任务，支持人群包复用与追溯；
- oc_audience_member 保存圈选出的成员（subject_key + 概率 + 区间），
  同一人群包内 subject_key 唯一，便于下游任务（召回/触达）直接引用。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 人群包状态
SEGMENT_STATUSES = ("draft", "ready", "active", "expired", "failed")
# 圈选目标（与预测目标对齐）
SEGMENT_TARGETS = ("churn", "conversion")


class AudienceSegment(Base):
    """人群包：一次概率区间圈选的结果集合。"""

    __tablename__ = "oc_audience_segment"
    __table_args__ = (
        Index("ix_audience_segment_tenant_time", "tenant_id", "created_at"),
        Index("ix_audience_segment_target_status", "target", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(200), comment="人群包名称")
    target: Mapped[str] = mapped_column(
        String(16), default="churn", server_default="churn", comment="圈选目标 churn/conversion"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="ready", server_default="ready", comment="draft/ready/active/expired/failed"
    )
    source_job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_prediction_job.id", ondelete="SET NULL"),
        default=None,
        index=True,
        comment="来源预测任务 ID（复用入口）",
    )
    min_prob: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 5), default=None, comment="圈选概率下限（含）"
    )
    max_prob: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 5), default=None, comment="圈选概率上限（含）"
    )
    band: Mapped[Optional[str]] = mapped_column(
        String(16), default=None, comment="概率档位 high/medium/low（可选圈选条件）"
    )
    member_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="成员数")
    criteria: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="圈选条件快照")
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="说明")
    created_by: Mapped[str] = mapped_column(
        String(64), default="system", server_default="system", comment="创建者"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AudienceMember(Base):
    """人群包成员：圈选出的主体及其概率。"""

    __tablename__ = "oc_audience_member"
    __table_args__ = (
        UniqueConstraint("segment_id", "subject_key", name="uq_audience_member_segment_subject"),
        Index("ix_audience_member_segment_prob", "segment_id", "probability"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    segment_id: Mapped[int] = mapped_column(
        ForeignKey("oc_audience_segment.id", ondelete="CASCADE"), index=True, comment="所属人群包"
    )
    subject_key: Mapped[str] = mapped_column(
        String(128), comment="主体键（用户 ID / 会员号）"
    )
    subject_name: Mapped[Optional[str]] = mapped_column(
        String(128), default=None, comment="主体名称"
    )
    probability: Mapped[float] = mapped_column(
        Numeric(6, 5), default=0.5, server_default="0.5", comment="预测概率"
    )
    band: Mapped[str] = mapped_column(
        String(16), default="medium", server_default="medium", comment="概率档位"
    )
    source_result_id: Mapped[Optional[int]] = mapped_column(
        Integer, default=None, comment="来源预测结果 ID"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
