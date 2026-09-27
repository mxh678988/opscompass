"""P8 学习进化域模型：决策反馈回流 / 策略权重自调 / 经验案例库 / A/B 对照实验。

闭环链路：AI 洞察 -> 处置单 -> 执行 -> 反馈回流(oc_learn_feedback)
-> 策略权重自调(oc_learn_policy_weight) -> 经验沉淀(oc_learn_case) -> A/B 对照择优。
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 决策采纳结果
DECISION_RESULTS = ("adopted", "partial", "rejected", "ignored")
# 实际效果
OUTCOME_RESULTS = ("success", "neutral", "fail", "unknown")
# 案例状态
CASE_STATUSES = ("draft", "verified", "archived")
# 实验状态
EXPERIMENT_STATUSES = ("draft", "running", "finished", "stopped")
# 实验胜出方
EXPERIMENT_WINNERS = ("a", "b", "none")

class LearnFeedback(Base):
    """决策反馈回流：记录 AI 建议被采纳与否及最终效果。"""

    __tablename__ = "oc_learn_feedback"
    __table_args__ = (
        Index("ix_oc_learn_feedback_tenant_policy", "tenant_id", "policy_code"),
        Index("ix_oc_learn_feedback_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    insight_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("oc_ai_insight.id", ondelete="SET NULL"), nullable=True
    )
    action_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("oc_ai_action_item.id", ondelete="SET NULL"), nullable=True
    )
    policy_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    data_level: Mapped[str] = mapped_column(String(16), nullable=False, default="L1")
    decision: Mapped[str] = mapped_column(String(16), nullable=False, default="adopted")
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    outcome_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    effect_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearnPolicyWeight(Base):
    """策略权重：按 policy_code + action_type 维度自调权重。"""

    __tablename__ = "oc_learn_policy_weight"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_code", "action_type", name="uq_oc_learn_policy_weight"),
        Index("ix_oc_learn_policy_weight_tenant", "tenant_id", "weight"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    policy_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    weight: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=1)
    base_weight: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=1)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    adopt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    avg_score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    last_adjusted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    adjust_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearnCase(Base):
    """经验案例库：沉淀可复用的决策经验。"""

    __tablename__ = "oc_learn_case"
    __table_args__ = (
        UniqueConstraint("tenant_id", "case_no", name="uq_oc_learn_case_no"),
        Index("ix_oc_learn_case_tenant_category", "tenant_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    case_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    scenario: Mapped[str] = mapped_column(Text, nullable=False, default="")
    action_taken: Mapped[str] = mapped_column(Text, nullable=False, default="")
    outcome: Mapped[str] = mapped_column(Text, nullable=False, default="")
    outcome_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    lesson: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_insight_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_feedback_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearnExperiment(Base):
    """A/B 对照实验：同场景下两套策略的对照择优。"""

    __tablename__ = "oc_learn_experiment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_oc_learn_experiment_code"),
        Index("ix_oc_learn_experiment_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    variant_a: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    variant_b: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    sample_a: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_b: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_a: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    result_b: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    lift: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    winner: Mapped[str] = mapped_column(String(8), nullable=False, default="none")
    conclusion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


__all__ = [
    "DECISION_RESULTS",
    "OUTCOME_RESULTS",
    "CASE_STATUSES",
    "EXPERIMENT_STATUSES",
    "EXPERIMENT_WINNERS",
    "LearnFeedback",
    "LearnPolicyWeight",
    "LearnCase",
    "LearnExperiment",
]
