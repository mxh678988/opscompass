"""M12 智能体编排接口：分析 Agent 与执行 Agent 的双 Agent 闭环。

路由前缀 /agents（注册见 app/api/v1/router.py，需 agent 模块权限）：
- 读操作（列表 / 详情）：agent:view
- 写操作（创建运行 / 分析 / 动作登记 / 完成 / 失败）：agent:create / agent:update
- 人工确认闸门（approve / reject）：agent:update
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user
from app.models.auth import User
from app.models.base import get_db
from app.schemas.agent import AgentActionIn, AgentRunIn, AgentRunPatch
from app.schemas.common import ApiResponse
from app.services import agent_service as svc

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/runs", response_model=ApiResponse[dict], summary="创建智能体编排运行")
def create_run(
    payload: AgentRunIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.create_run(db, tenant_id, payload)
    except svc.AgentServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="智能体运行已创建")


@router.get("/runs", response_model=ApiResponse[dict], summary="运行列表（分页过滤）")
def list_runs(
    status: str | None = Query(default=None, description="限定运行状态"),
    scenario: str | None = Query(default=None, description="限定场景模板"),
    keyword: str | None = Query(default=None, description="关键词（名称/结果摘要）"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.list_runs(
            db,
            tenant_id,
            status=status,
            scenario=scenario,
            keyword=keyword,
            page=page,
            size=size,
        )
    except svc.AgentServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data)


@router.get("/runs/{run_id}", response_model=ApiResponse[dict], summary="运行详情（含洞察与动作）")
def read_run(
    run_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    data = svc.get_run(db, tenant_id, run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="运行不存在或不属于当前租户")
    return ApiResponse[dict](data=data)


@router.post("/runs/{run_id}/analyze", response_model=ApiResponse[dict], summary="执行分析并产出洞察")
def analyze_run(
    run_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.analyze_run(
            db,
            tenant_id,
            run_id,
            insight_agent=user.username,
        )
    except svc.AgentServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="分析完成，洞察已产出")


@router.patch("/runs/{run_id}", response_model=ApiResponse[dict], summary="人工确认闸门（approve/reject）")
def patch_run(
    run_id: int,
    payload: AgentRunPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.patch_run(db, tenant_id, run_id, payload, operator=user.username)
    except svc.AgentServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="运行状态已更新")


@router.post("/runs/{run_id}/actions", response_model=ApiResponse[dict], summary="登记执行动作（执行 Agent 落地）")
def record_action(
    run_id: int,
    payload: AgentActionIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.record_action(db, tenant_id, run_id, payload, operator=user.username)
    except svc.AgentServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="执行动作已登记并回写事件总线")


@router.post("/runs/{run_id}/complete", response_model=ApiResponse[dict], summary="完成运行并回写结果事件")
def complete_run(
    run_id: int,
    result_summary: str | None = Query(default=None, description="交付结果摘要"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.complete_run(db, tenant_id, run_id, result_summary=result_summary)
    except svc.AgentServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="运行已完成，结果已回写事件总线")


@router.post("/runs/{run_id}/fail", response_model=ApiResponse[dict], summary="标记运行失败")
def fail_run(
    run_id: int,
    error: str = Query(default="执行失败", description="失败原因"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.fail_run(db, tenant_id, run_id, error=error)
    except svc.AgentServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="运行已标记失败")
