"""数字人一键生成接口：形象库 / 音色库 / 生成项目 / 一键生成 / 工作流模板。

路由前缀 /digital-human（见 app/api/v1/router.py，需 digital_human 模块权限）：
- 读（总览、引擎状态、形象/音色/项目/工作流列表与详情）：digital_human:view
- 写（维护形象与音色、生成口播稿、一键生成、工作流增删改与执行）：digital_human:manage
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user
from app.models.auth import User
from app.models.base import get_db
from app.schemas.common import ApiResponse
from app.schemas.digital_human import (
    AvatarIn,
    AvatarPatch,
    GenerateIn,
    ProjectIn,
    ProjectPatch,
    ScriptIn,
    VoiceIn,
    VoicePatch,
    WorkflowIn,
    WorkflowPatch,
    WorkflowRunIn,
)
from app.services import digital_human_service as svc

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ============================================================ 总览 / 引擎
@router.get("/overview", response_model=ApiResponse[dict], summary="数字人总览（形象/音色/项目计数、成功率、引擎状态）")
def read_overview(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.stats_overview(db, tenant_id))


@router.get("/engines", response_model=ApiResponse[dict], summary="生成引擎可用性探测（脚本/配音/驱动/合成）")
def read_engines() -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.engine_status())


# ============================================================ 形象库
@router.get("/avatars", response_model=ApiResponse[dict], summary="形象库列表")
def list_avatars(
    keyword: str | None = Query(default=None, description="名称或风格关键字"),
    avatar_type: str | None = Query(default=None, description="preset|photo|clone"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.list_avatars(db, tenant_id, keyword, avatar_type, page, size))


@router.post("/avatars", response_model=ApiResponse[dict], summary="新建数字人形象")
def create_avatar(
    payload: AvatarIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.create_avatar(db, tenant_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="形象已创建")


@router.patch("/avatars/{avatar_id}", response_model=ApiResponse[dict], summary="修改数字人形象")
def update_avatar(
    avatar_id: int,
    payload: AvatarPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.update_avatar(db, tenant_id, avatar_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="形象已更新")


@router.delete("/avatars/{avatar_id}", response_model=ApiResponse[dict], summary="删除数字人形象")
def delete_avatar(
    avatar_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.delete_avatar(db, tenant_id, avatar_id)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="形象已删除")


# ============================================================ 音色库
@router.get("/voices", response_model=ApiResponse[dict], summary="音色库列表")
def list_voices(
    keyword: str | None = Query(default=None, description="音色名称关键字"),
    engine: str | None = Query(default=None, description="TTS 引擎"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.list_voices(db, tenant_id, keyword, engine, page, size))


@router.post("/voices", response_model=ApiResponse[dict], summary="新建音色")
def create_voice(
    payload: VoiceIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.create_voice(db, tenant_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="音色已创建")


@router.patch("/voices/{voice_id}", response_model=ApiResponse[dict], summary="修改音色")
def update_voice(
    voice_id: int,
    payload: VoicePatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.update_voice(db, tenant_id, voice_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="音色已更新")


@router.delete("/voices/{voice_id}", response_model=ApiResponse[dict], summary="删除音色")
def delete_voice(
    voice_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.delete_voice(db, tenant_id, voice_id)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="音色已删除")


# ============================================================ 生成项目
@router.get("/projects", response_model=ApiResponse[dict], summary="生成项目列表")
def list_projects(
    keyword: str | None = Query(default=None, description="项目名称或主题关键字"),
    status: str | None = Query(default=None, description="draft|scripting|ready|rendering|done|failed"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.list_projects(db, tenant_id, keyword, status, page, size))


@router.post("/projects", response_model=ApiResponse[dict], summary="新建生成项目（自动绑定默认工作流）")
def create_project(
    payload: ProjectIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.create_project(db, tenant_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="项目已创建")


@router.get("/projects/{project_id}", response_model=ApiResponse[dict], summary="项目详情（含四阶段任务留痕）")
def read_project(
    project_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    row = svc.get_project(db, tenant_id, project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ApiResponse[dict](data=svc.project_to_dict(row, with_tasks=True))


@router.patch("/projects/{project_id}", response_model=ApiResponse[dict], summary="修改项目 / 手工编辑口播稿")
def update_project(
    project_id: int,
    payload: ProjectPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.update_project(db, tenant_id, project_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="项目已更新")


@router.delete("/projects/{project_id}", response_model=ApiResponse[dict], summary="删除生成项目")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.delete_project(db, tenant_id, project_id)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="项目已删除")


@router.post("/projects/{project_id}/script", response_model=ApiResponse[dict], summary="生成/重写口播稿（含分镜）")
def generate_script(
    project_id: int,
    payload: ScriptIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.generate_script(db, tenant_id, project_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message=data.get("message", "口播稿已生成"))


@router.post("/projects/{project_id}/generate", response_model=ApiResponse[dict], summary="一键生成（脚本->配音->驱动->合成）")
def run_generation(
    project_id: int,
    payload: GenerateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.run_generation(db, tenant_id, project_id, payload, operator=user.username)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message=data.get("message", "一键生成完成"))


# ============================================================ 工作流模板
@router.get("/workflows", response_model=ApiResponse[dict], summary="工作流模板列表")
def list_workflows(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.list_workflows(db, tenant_id, page, size))


@router.post("/workflows", response_model=ApiResponse[dict], summary="新建工作流模板")
def create_workflow(
    payload: WorkflowIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.create_workflow(db, tenant_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="工作流已创建")


@router.patch("/workflows/{workflow_id}", response_model=ApiResponse[dict], summary="修改工作流模板")
def update_workflow(
    workflow_id: int,
    payload: WorkflowPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.update_workflow(db, tenant_id, workflow_id, payload)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="工作流已更新")


@router.delete("/workflows/{workflow_id}", response_model=ApiResponse[dict], summary="删除工作流模板（默认模板不可删）")
def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.delete_workflow(db, tenant_id, workflow_id)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="工作流已删除")


@router.post("/workflows/{workflow_id}/run", response_model=ApiResponse[dict], summary="按指定工作流执行一键生成")
def run_workflow(
    workflow_id: int,
    payload: WorkflowRunIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.run_workflow(db, tenant_id, workflow_id, payload, operator=user.username)
    except Exception as exc:  # pragma: no cover
        raise _fail(exc)
    return ApiResponse[dict](data=data, message=data.get("message", "工作流已执行"))
