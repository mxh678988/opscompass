"""RBAC 管理接口：用户、角色、权限。"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.core import security
from app.models.auth import Permission, Role, User
from app.models.base import get_db
from app.schemas.auth import (
    PermissionOut,
    ResetPasswordRequest,
    RoleCreate,
    RoleOut,
    RoleUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.schemas.common import ApiResponse, PageResult
from app.services import audit_service, auth_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================ 用户
@router.get(
    "/users",
    response_model=ApiResponse[PageResult[UserOut]],
    summary="用户列表",
    dependencies=[Depends(require_permissions("user:view"))],
)
def list_users(
    keyword: Optional[str] = Query(default=None, description="用户名/姓名/邮箱模糊匹配"),
    is_active: Optional[bool] = Query(default=None, description="启用状态"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    conditions = []
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            or_(
                User.username.ilike(like),
                User.full_name.ilike(like),
                User.email.ilike(like),
            )
        )
    if is_active is not None:
        conditions.append(User.is_active == is_active)

    base = select(User)
    count_stmt = select(func.count(User.id))
    for cond in conditions:
        base = base.where(cond)
        count_stmt = count_stmt.where(cond)

    total = int(db.execute(count_stmt).scalar() or 0)
    rows = (
        db.execute(
            base.order_by(User.id.asc()).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )
    return ApiResponse[PageResult[UserOut]](
        data=PageResult[UserOut](
            total=total,
            page=page,
            page_size=page_size,
            items=[auth_service.user_to_out(u) for u in rows],
        )
    )


@router.post(
    "/users",
    response_model=ApiResponse[UserOut],
    summary="新建用户",
    dependencies=[Depends(require_permissions("user:create"))],
)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if auth_service.get_user_by_username(db, payload.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"用户名已存在: {payload.username}"
        )
    err = security.validate_password_strength(payload.password)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    roles, missing = auth_service.get_roles_by_codes(db, payload.roles)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"角色不存在: {', '.join(missing)}"
        )

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        tenant_id=payload.tenant_id,
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
        hashed_password=security.hash_password(payload.password),
    )
    user.roles = roles
    db.add(user)
    db.commit()
    db.refresh(user)
    return ApiResponse[UserOut](data=auth_service.user_to_out(user))


@router.get(
    "/users/{user_id}",
    response_model=ApiResponse[UserOut],
    summary="用户详情",
    dependencies=[Depends(require_permissions("user:view"))],
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return ApiResponse[UserOut](data=auth_service.user_to_out(user))


@router.patch(
    "/users/{user_id}",
    response_model=ApiResponse[UserOut],
    summary="更新用户",
    dependencies=[Depends(require_permissions("user:update"))],
)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    data = payload.model_dump(exclude_unset=True)
    if "roles" in data:
        roles, missing = auth_service.get_roles_by_codes(db, data.pop("roles") or [])
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"角色不存在: {', '.join(missing)}",
            )
        user.roles = roles
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return ApiResponse[UserOut](data=auth_service.user_to_out(user))


@router.delete(
    "/users/{user_id}",
    response_model=ApiResponse[dict],
    summary="删除用户",
    dependencies=[Depends(require_permissions("user:delete"))],
)
def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_permissions("user:delete")),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录账号"
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.is_superuser:
        remain = int(
            db.execute(
                select(func.count(User.id)).where(User.is_superuser.is_(True))
            ).scalar()
            or 0
        )
        if remain <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除最后一个超级管理员"
            )
    username = user.username
    db.delete(user)
    db.commit()
    audit_service.log_sensitive_operation(
        db,
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=current_user.tenant_id,
        action=f"删除用户 {username}",
        status_code=200,
    )
    return ApiResponse[dict](data={"message": f"用户 {username} 已删除"})


@router.post(
    "/users/{user_id}/reset-password",
    response_model=ApiResponse[dict],
    summary="重置用户密码",
    dependencies=[Depends(require_permissions("user:reset_password"))],
)
def reset_user_password(
    user_id: int,
    payload: ResetPasswordRequest,
    request: Request,
    current_user: User = Depends(require_permissions("user:reset_password")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    err = auth_service.reset_password(db, user, payload.new_password)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    audit_service.log_sensitive_operation(
        db,
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=current_user.tenant_id,
        action=f"重置用户 {user.username} 的密码",
        status_code=200,
    )
    return ApiResponse[dict](data={"message": f"用户 {user.username} 密码已重置"})


# ============================================================ 角色
@router.get(
    "/roles",
    response_model=ApiResponse[list[RoleOut]],
    summary="角色列表",
    dependencies=[Depends(require_permissions("role:view"))],
)
def list_roles(db: Session = Depends(get_db)):
    rows = db.execute(select(Role).order_by(Role.id.asc())).scalars().all()
    return ApiResponse[list[RoleOut]](data=[auth_service.role_to_out(r) for r in rows])


@router.post(
    "/roles",
    response_model=ApiResponse[RoleOut],
    summary="新建角色",
    dependencies=[Depends(require_permissions("role:create"))],
)
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    exists = db.execute(select(Role).where(Role.code == payload.code)).scalars().first()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"角色编码已存在: {payload.code}"
        )
    role = Role(code=payload.code, name=payload.name, description=payload.description)
    db.add(role)
    db.commit()
    db.refresh(role)
    missing = auth_service.set_permissions(db, role, payload.permissions)
    if missing:
        logger.warning("角色 %s 存在未识别权限码: %s", role.code, missing)
    return ApiResponse[RoleOut](data=auth_service.role_to_out(role))


@router.patch(
    "/roles/{role_id}",
    response_model=ApiResponse[RoleOut],
    summary="更新角色",
    dependencies=[Depends(require_permissions("role:update"))],
)
def update_role(role_id: int, payload: RoleUpdate, db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    data = payload.model_dump(exclude_unset=True)
    if "permissions" in data:
        auth_service.set_permissions(db, role, data.pop("permissions") or [])
    for field, value in data.items():
        setattr(role, field, value)
    db.commit()
    db.refresh(role)
    return ApiResponse[RoleOut](data=auth_service.role_to_out(role))


@router.delete(
    "/roles/{role_id}",
    response_model=ApiResponse[dict],
    summary="删除角色",
    dependencies=[Depends(require_permissions("role:delete"))],
)
def delete_role(
    role_id: int,
    request: Request,
    current_user: User = Depends(require_permissions("role:delete")),
    db: Session = Depends(get_db),
):
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    if role.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="内置角色不允许删除"
        )
    code = role.code
    db.delete(role)
    db.commit()
    audit_service.log_sensitive_operation(
        db,
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=current_user.tenant_id,
        action=f"删除角色 {code}",
        status_code=200,
    )
    return ApiResponse[dict](data={"message": f"角色 {code} 已删除"})


# ============================================================ 权限
@router.get(
    "/permissions",
    response_model=ApiResponse[list[PermissionOut]],
    summary="权限点列表",
    dependencies=[Depends(require_permissions("role:view", "user:view"))],
)
def list_permissions(
    module: Optional[str] = Query(default=None, description="按模块筛选"),
    db: Session = Depends(get_db),
):
    stmt = select(Permission)
    if module:
        stmt = stmt.where(Permission.module == module)
    rows = db.execute(stmt.order_by(Permission.module.asc(), Permission.id.asc())).scalars().all()
    return ApiResponse[list[PermissionOut]](
        data=[PermissionOut.model_validate(p) for p in rows]
    )
