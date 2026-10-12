"""M9 预测引擎模型：预测任务与预测结果。

设计要点：
- oc_prediction_job 记录一次预测任务：目标（churn 流失 / conversion 转化）、
  模型路由模式（local 本地模型优先 / api 云端 / rule 规则兜底）；
- oc_prediction_result 保存每个主体的预测输出：概率、置信度、概率区间档位
  （high/medium/low），供人群包引擎（M10）圈选复用；
- 模型路由遵循「本地优先、规则兜底」：本地模型不可用时降级为规则打分，
  所有结果显式携带 mode / model / confidence 便于追溯与可解释性展示。
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

# 预测目标：churn 流失 / conversion 转化
PREDICTION_TARGETS = ("churn", "conversion")
# 模型路由模式：local 本地模型 / api 云端 API / rule 规则兜底
PREDICTION_MODES = ("local", "api", "rule")
# 概率区间档位：high/medium/low
PREDICTION_BANDS = ("high", "medium", "low")
# 任务状态
PREDICTION_STATUSES = ("pending", "running", "success", "failed")


class PredictionJob(Base):
    """预测任务：一次流失/转化概率预测。"""

    __tablename__ = "oc_prediction_job"
    __table_args__ = (
        Index("ix_prediction_job_tenant_time", "tenant_id", "created_at"),
        Index("ix_prediction_job_target_status", "target", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    name: Mapped[str] = mapped_column(String(200), comment="任务名称")
    target: Mapped[str] = mapped_column(
        String(16), default="churn", server_default="churn", comment="预测目标 churn/conversion"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending/running/success/failed"
    )
    mode: Mapped[str] = mapped_column(
        String(16), default="local", server_default="local", comment="模型路由模式 local/api/rule"
    )
    model: Mapped[str] = mapped_column(
        String(128), default="", server_default="", comment="实际使用的模型名"
    )
    source: Mapped[str] = mapped_column(
        String(64), default="event_bus", server_default="event_bus", comment="输入数据来源"
    )
    input_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="输入特征快照")
    feature_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="特征数")
    subject_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="预测主体数")
    threshold: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), default=None, comment="判定阈值（如 0.5）"
    )
    rule_fallback_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="是否触发了规则兜底",
    )
    error: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="失败原因")
    created_by: Mapped[str] = mapped_column(
        String(64), default="system", server_default="system", comment="发起方"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="完成时间"
    )


class PredictionResult(Base):
    """预测结果：每个主体的概率输出与可解释信息。"""

    __tablename__ = "oc_prediction_result"
    __table_args__ = (
        UniqueConstraint("job_id", "subject_key", name="uq_prediction_result_job_subject"),
        Index("ix_prediction_result_job_band", "job_id", "band"),
        Index("ix_prediction_result_job_prob", "job_id", "probability"),
        Index("ix_prediction_result_tenant_target", "tenant_id", "target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    job_id: Mapped[int] = mapped_column(
        ForeignKey("oc_prediction_job.id", ondelete="CASCADE"), index=True, comment="所属预测任务"
    )
    target: Mapped[str] = mapped_column(String(16), comment="预测目标 churn/conversion")
    subject_key: Mapped[str] = mapped_column(
        String(128), comment="预测主体键（如用户 ID / 会员号）"
    )
    subject_name: Mapped[Optional[str]] = mapped_column(
        String(128), default=None, comment="主体名称（便于展示）"
    )
    probability: Mapped[float] = mapped_column(
        Numeric(6, 5), default=0.5, server_default="0.5", comment="预测概率 0-1"
    )
    band: Mapped[str] = mapped_column(
        String(16), default="medium", server_default="medium", comment="概率档位 high/medium/low"
    )
    mode: Mapped[str] = mapped_column(
        String(16), default="rule", server_default="rule", comment="本次预测模式 local/api/rule"
    )
    model: Mapped[str] = mapped_column(
        String(128), default="", server_default="", comment="本次使用的模型名"
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), default=None, comment="置信度 0-1"
    )
    features: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="使用的特征")
    reasons: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="可解释理由列表")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
