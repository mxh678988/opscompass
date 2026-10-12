"""M10 人群包服务：圈选编排 / 复用 / 列表与详情查询 / 落库。

链路：端点 -> create_segment（从预测结果或既有包圈选）-> core.audience 校验
区间与筛选条件 -> 写入 oc_audience_segment + oc_audience_member。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audience import (
    AudienceEngineError,
    in_probability_range,
    matches_band,
    normalize_range,
    validate_band,
    validate_filters,
    validate_target,
)
from app.models.audience import (
    SEGMENT_STATUSES,
    SEGMENT_TARGETS,
    AudienceMember,
    AudienceSegment,
)
from app.models.predictive import PredictionResult
from app.schemas.audience import AudienceMemberIn, AudienceReuseIn, AudienceSegmentIn


class AudienceServiceError(RuntimeError):
    """人群包服务业务异常（参数 / 状态非法）。"""


def _now() -> datetime:
    return datetime.now()


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _check_segment_status(status: str) -> None:
    if status not in SEGMENT_STATUSES:
        raise AudienceServiceError(
            f"不支持的人群包状态: {status}（可选 {' / '.join(SEGMENT_STATUSES)}）"
        )


def _derive_band(probability: float, low: float = 0.3334, high: float = 0.6667) -> str:
    if probability >= high:
        return "high"
    if probability <= low:
        return "low"
    return "medium"


def _candidates_from_job(
    db: Session,
    tenant_id: int,
    *,
    source_job_id: int,
    target: str,
    lo: Optional[float],
    hi: Optional[float],
    band: Optional[str],
) -> list[PredictionResult]:
    """从预测结果表圈选候选主体。"""
    conditions = [
        PredictionResult.tenant_id == tenant_id,
        PredictionResult.job_id == source_job_id,
        PredictionResult.target == target,
    ]
    rows = (
        db.execute(
            select(PredictionResult)
            .where(*conditions)
            .order_by(PredictionResult.probability.desc(), PredictionResult.id.asc())
        )
        .scalars()
        .all()
    )
    return [
        r
        for r in rows
        if in_probability_range(r.probability, lo, hi) and matches_band(r.band, band)
    ]


def _candidates_from_segment(
    db: Session,
    tenant_id: int,
    *,
    source_segment_id: int,
    lo: Optional[float],
    hi: Optional[float],
    band: Optional[str],
) -> list[AudienceMember]:
    """从既有包成员表圈选候选主体（复用场景）。"""
    conditions = [
        AudienceMember.tenant_id == tenant_id,
        AudienceMember.segment_id == source_segment_id,
    ]
    rows = (
        db.execute(
            select(AudienceMember)
            .where(*conditions)
            .order_by(AudienceMember.probability.desc(), AudienceMember.id.asc())
        )
        .scalars()
        .all()
    )
    return [
        m
        for m in rows
        if in_probability_range(m.probability, lo, hi) and matches_band(m.band, band)
    ]


def _members_from_manual(
    tenant_id: int, segment_id: int, entries: list[AudienceMemberIn]
) -> list[AudienceMember]:
    seen: set[str] = set()
    members: list[AudienceMember] = []
    for e in entries:
        if e.subject_key in seen:
            continue
        seen.add(e.subject_key)
        members.append(
            AudienceMember(
                tenant_id=tenant_id,
                segment_id=segment_id,
                subject_key=e.subject_key,
                subject_name=e.subject_name,
                probability=e.probability,
                band=e.band or _derive_band(e.probability),
            )
        )
    return members


def create_segment(
    db: Session,
    tenant_id: int,
    payload: AudienceSegmentIn,
    operator: str = "system",
) -> dict[str, Any]:
    """创建人群包：按概率区间/档位从预测结果圈选并落库。"""
    try:
        validate_target(payload.target)
        lo, hi = normalize_range(payload.min_prob, payload.max_prob)
        validate_band(payload.band)
        validate_filters(
            source_job_id=payload.source_job_id,
            min_prob=payload.min_prob,
            max_prob=payload.max_prob,
            band=payload.band,
        )
    except AudienceEngineError as exc:
        raise AudienceServiceError(str(exc))

    # 圈选候选：来自预测任务（M9 联动）
    candidates = _candidates_from_job(
        db,
        tenant_id,
        source_job_id=payload.source_job_id,
        target=payload.target,
        lo=lo,
        hi=hi,
        band=payload.band,
    )
    segment = AudienceSegment(
        tenant_id=tenant_id,
        name=payload.name,
        target=payload.target,
        status="ready",
        source_job_id=payload.source_job_id,
        min_prob=lo,
        max_prob=hi,
        band=payload.band,
        member_count=0,
        criteria={
            "target": payload.target,
            "source_job_id": payload.source_job_id,
            "min_prob": lo,
            "max_prob": hi,
            "band": payload.band,
        },
        description=payload.description,
        created_by=operator,
    )
    db.add(segment)
    db.flush()

    members: list[AudienceMember] = []
    for c in candidates:
        members.append(
            AudienceMember(
                tenant_id=tenant_id,
                segment_id=segment.id,
                subject_key=c.subject_key,
                subject_name=c.subject_name,
                probability=c.probability,
                band=c.band,
                source_result_id=c.id,
            )
        )
    if members:
        db.add_all(members)
    segment.member_count = len(members)
    db.commit()
    return segment_to_dict(segment, members=[member_to_dict(m) for m in members])


def reuse_segment(
    db: Session,
    tenant_id: int,
    payload: AudienceReuseIn,
    operator: str = "system",
) -> dict[str, Any]:
    """复用人群包：从既有包成员中按新区间/档位再圈选。"""
    try:
        validate_target(payload.target)
        lo, hi = normalize_range(payload.min_prob, payload.max_prob)
        validate_band(payload.band)
        validate_filters(
            source_segment_id=payload.source_segment_id,
            min_prob=payload.min_prob,
            max_prob=payload.max_prob,
            band=payload.band,
        )
    except AudienceEngineError as exc:
        raise AudienceServiceError(str(exc))

    source = db.scalar(
        select(AudienceSegment).where(
            AudienceSegment.id == payload.source_segment_id,
            AudienceSegment.tenant_id == tenant_id,
        )
    )
    if source is None:
        raise AudienceServiceError("来源人群包不存在或不属于当前租户")

    candidates = _candidates_from_segment(
        db,
        tenant_id,
        source_segment_id=payload.source_segment_id,
        lo=lo,
        hi=hi,
        band=payload.band,
    )
    segment = AudienceSegment(
        tenant_id=tenant_id,
        name=payload.name,
        target=payload.target,
        status="ready",
        source_job_id=source.source_job_id,
        min_prob=lo,
        max_prob=hi,
        band=payload.band,
        member_count=0,
        criteria={
            "target": payload.target,
            "source_segment_id": payload.source_segment_id,
            "source_job_id": source.source_job_id,
            "min_prob": lo,
            "max_prob": hi,
            "band": payload.band,
        },
        description=payload.description,
        created_by=operator,
    )
    db.add(segment)
    db.flush()

    members: list[AudienceMember] = []
    for c in candidates:
        members.append(
            AudienceMember(
                tenant_id=tenant_id,
                segment_id=segment.id,
                subject_key=c.subject_key,
                subject_name=c.subject_name,
                probability=c.probability,
                band=c.band,
                source_result_id=c.source_result_id,
            )
        )
    if members:
        db.add_all(members)
    segment.member_count = len(members)
    db.commit()
    return segment_to_dict(segment, members=[member_to_dict(m) for m in members])


def list_segments(
    db: Session,
    tenant_id: int,
    *,
    keyword: Optional[str] = None,
    target: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    if target is not None:
        try:
            validate_target(target)
        except AudienceEngineError as exc:
            raise AudienceServiceError(str(exc))
    if status is not None:
        _check_segment_status(status)
    page = max(1, int(page or 1))
    size = min(200, max(1, int(size or 20)))
    conditions = [AudienceSegment.tenant_id == tenant_id]
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            or_(AudienceSegment.name.like(like), AudienceSegment.created_by.like(like))
        )
    if target:
        conditions.append(AudienceSegment.target == target)
    if status:
        conditions.append(AudienceSegment.status == status)

    total = (
        db.scalar(select(func.count()).select_from(AudienceSegment).where(*conditions)) or 0
    )
    rows = (
        db.execute(
            select(AudienceSegment)
            .where(*conditions)
            .order_by(AudienceSegment.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return {
        "total": int(total),
        "page": page,
        "page_size": size,
        "items": [segment_to_dict(s) for s in rows],
    }


def get_segment(
    db: Session, tenant_id: int, segment_id: int
) -> Optional[dict[str, Any]]:
    segment = db.scalar(
        select(AudienceSegment).where(
            AudienceSegment.id == segment_id, AudienceSegment.tenant_id == tenant_id
        )
    )
    if segment is None:
        return None
    members = (
        db.execute(
            select(AudienceMember)
            .where(AudienceMember.segment_id == segment.id)
            .order_by(AudienceMember.probability.desc(), AudienceMember.id.asc())
        )
        .scalars()
        .all()
    )
    return segment_to_dict(segment, members=[member_to_dict(m) for m in members])


def update_segment(
    db: Session,
    tenant_id: int,
    segment_id: int,
    *,
    status: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    segment = db.scalar(
        select(AudienceSegment).where(
            AudienceSegment.id == segment_id, AudienceSegment.tenant_id == tenant_id
        )
    )
    if segment is None:
        return None
    if status is not None:
        _check_segment_status(status)
        segment.status = status
    if description is not None:
        segment.description = description
    db.commit()
    return segment_to_dict(segment)


def segment_to_dict(
    segment: AudienceSegment, members: Optional[list[dict]] = None
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": segment.id,
        "tenant_id": segment.tenant_id,
        "name": segment.name,
        "target": segment.target,
        "status": segment.status,
        "source_job_id": segment.source_job_id,
        "min_prob": _f(segment.min_prob) if segment.min_prob is not None else None,
        "max_prob": _f(segment.max_prob) if segment.max_prob is not None else None,
        "band": segment.band,
        "member_count": int(segment.member_count or 0),
        "criteria": segment.criteria,
        "description": segment.description,
        "created_by": segment.created_by,
        "created_at": segment.created_at.isoformat() if segment.created_at else None,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }
    if members is not None:
        data["members"] = members
    return data


def member_to_dict(row: AudienceMember) -> dict[str, Any]:
    return {
        "id": row.id,
        "segment_id": row.segment_id,
        "subject_key": row.subject_key,
        "subject_name": row.subject_name,
        "probability": _f(row.probability),
        "band": row.band,
        "source_result_id": row.source_result_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
