"""P8 学习进化闭环接口：反馈回流 / 策略权重自调 / 经验案例库 / A-B 对照实验。

路由前缀 /learning（见 app/api/v1/router.py，需 learning 模块权限）：
- 读（总览、反馈列表与详情、权重列表、案例列表与详情、实验列表与详情）：learning:view
- 写（登记反馈、补录效果、重算权重、新建/修改案例、新建/修改/采样/结项实验）：learning:manage
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user
from app.models.auth import User
from app.models.base import get_db
from app.schemas.common import ApiResponse
from app.schemas.learning import (
    CaseFromFeedbackIn,
    CaseIn,
    CasePatch,
    ExperimentFinishIn,
    ExperimentIn,
    ExperimentPatch,
    ExperimentRecordIn,
    FeedbackIn,
    FeedbackPatch,
    WeightAdjustIn,
)
from app.services import learning_service as svc

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/overview", response_model=ApiResponse[dict], summary="学习进化总览（采纳率/成功率/权重 Top/案例与实验计数）")
def read_overview(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.stats_overview(db, tenant_id))


# ============================================================ 反馈回流
@router.post("/feedbacks", response_model=ApiResponse[dict], summary="登记决策反馈（采纳与否 + 实际效果）")
def create_feedback(
    payload: FeedbackIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.record_feedback(db, tenant_id, payload, operator=user.username)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="反馈已登记")


@router.get("/feedbacks", response_model=ApiResponse[dict], summary="反馈列表")
def list_feedbacks(
    keyword: str | None = Query(default=None, description="策略编码/动作类型/说明关键字"),
    decision: str | None = Query(default=None, description="adopted/partial/rejected/ignored"),
    outcome: str | None = Query(default=None, description="success/neutral/fail/unknown"),
    policy_code: str | None = Query(default=None, description="策略编码"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    data = svc.list_feedbacks(
        db, tenant_id, keyword=keyword, decision=decision, outcome=outcome,
        policy_code=policy_code, page=page, size=size,
    )
    return ApiResponse[dict](data=data)


@router.get("/feedbacks/{fid}", response_model=ApiResponse[dict], summary="反馈详情")
def get_feedback(
    fid: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    row = svc.get_feedback(db, tenant_id, fid)
    if row is None:
        raise HTTPException(status_code=404, detail="反馈记录不存在")
    return ApiResponse[dict](data=svc.feedback_to_dict(row))


@router.patch("/feedbacks/{fid}", response_model=ApiResponse[dict], summary="补录/修正实际效果")
def patch_feedback(
    fid: int,
    payload: FeedbackPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.patch_feedback(db, tenant_id, fid, payload)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="反馈已更新")

# ============================================================ 策略权重自调
@router.get("/weights", response_model=ApiResponse[dict], summary="策略权重列表")
def list_weights(
    keyword: str | None = Query(default=None, description="策略编码/名称关键字"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.list_weights(db, tenant_id, keyword=keyword, page=page, size=size))


@router.post("/weights/recompute", response_model=ApiResponse[dict], summary="触发策略权重自调（可指定策略，不传则全量）")
def recompute_weights(
    payload: WeightAdjustIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    data = svc.recompute_weights(
        db,
        tenant_id,
        policy_code=payload.policy_code,
        action_type=payload.action_type,
        min_samples=payload.min_samples,
        learning_rate=payload.learning_rate,
        weight_floor=payload.weight_floor,
        weight_ceil=payload.weight_ceil,
        remark=payload.remark,
    )
    return ApiResponse[dict](data=data, message=f"已重算 {data['updated']} 条策略权重")


# ============================================================ 经验案例库
@router.post("/cases", response_model=ApiResponse[dict], summary="新建经验案例")
def create_case(
    payload: CaseIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.create_case(db, tenant_id, payload, operator=user.username)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="案例已创建")


@router.get("/cases", response_model=ApiResponse[dict], summary="经验案例列表")
def list_cases(
    keyword: str | None = Query(default=None, description="标题/编号/场景/经验关键字"),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None, description="draft/verified/archived"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    data = svc.list_cases(
        db, tenant_id, keyword=keyword, category=category, status=status, page=page, size=size
    )
    return ApiResponse[dict](data=data)


@router.post("/cases/from-feedback", response_model=ApiResponse[dict], summary="由反馈一键沉淀为经验案例")
def case_from_feedback(
    payload: CaseFromFeedbackIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.case_from_feedback(db, tenant_id, payload, operator=user.username)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="案例已沉淀")


@router.get("/cases/{cid}", response_model=ApiResponse[dict], summary="案例详情")
def get_case(
    cid: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    row = svc.get_case(db, tenant_id, cid)
    if row is None:
        raise HTTPException(status_code=404, detail="案例不存在")
    return ApiResponse[dict](data=svc.case_to_dict(row))


@router.patch("/cases/{cid}", response_model=ApiResponse[dict], summary="修改案例")
def patch_case(
    cid: int,
    payload: CasePatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.patch_case(db, tenant_id, cid, payload)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="案例已更新")


@router.post("/cases/{cid}/hit", response_model=ApiResponse[dict], summary="标记案例被命中引用")
def hit_case(
    cid: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.hit_case(db, tenant_id, cid)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="命中已记录")


@router.post("/cases/{cid}/archive", response_model=ApiResponse[dict], summary="归档案例")
def archive_case(
    cid: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.archive_case(db, tenant_id, cid)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="案例已归档")

# ============================================================ A/B 对照实验
@router.post("/experiments", response_model=ApiResponse[dict], summary="新建 A/B 对照实验")
def create_experiment(
    payload: ExperimentIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.create_experiment(db, tenant_id, payload, operator=user.username)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="实验已创建")


@router.get("/experiments", response_model=ApiResponse[dict], summary="实验列表")
def list_experiments(
    keyword: str | None = Query(default=None, description="实验名称/编号关键字"),
    status: str | None = Query(default=None, description="draft/running/finished/stopped"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    data = svc.list_experiments(db, tenant_id, keyword=keyword, status=status, page=page, size=size)
    return ApiResponse[dict](data=data)


@router.get("/experiments/{eid}", response_model=ApiResponse[dict], summary="实验详情")
def get_experiment(
    eid: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    row = svc.get_experiment(db, tenant_id, eid)
    if row is None:
        raise HTTPException(status_code=404, detail="实验不存在")
    return ApiResponse[dict](data=svc.experiment_to_dict(row))


@router.patch("/experiments/{eid}", response_model=ApiResponse[dict], summary="修改实验")
def patch_experiment(
    eid: int,
    payload: ExperimentPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.patch_experiment(db, tenant_id, eid, payload)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="实验已更新")


@router.post("/experiments/{eid}/samples", response_model=ApiResponse[dict], summary="登记一次对照样本")
def record_sample(
    eid: int,
    payload: ExperimentRecordIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.record_sample(db, tenant_id, eid, payload)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="样本已登记")


@router.post("/experiments/{eid}/finish", response_model=ApiResponse[dict], summary="结项并判定胜出方案")
def finish_experiment(
    eid: int,
    payload: ExperimentFinishIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.finish_experiment(db, tenant_id, eid, payload)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="实验已结项")
