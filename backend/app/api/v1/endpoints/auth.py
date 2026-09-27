"""认证接口：登录、登出、当前用户信息、修改密码。"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import security
from app.models.auth import User
from app.models.base import get_db
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    TokenOut,
    UserOut,
)
from app.schemas.common import ApiResponse
from app.services import audit_service, auth_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=ApiResponse[TokenOut], summary="用户登录")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """账号密码登录，成功后返回 JWT 访问令牌。"""
    user, reason = auth_service.authenticate(db, payload.username, payload.password)
    if user is None:
        audit_service.log_login_failed(db, payload.username, reason, request=request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=reason,
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = security.create_access_token(user.id)
    audit_service.log_login_success(db, user, request=request)
    data = TokenOut(
        access_token=token,
        token_type="bearer",
        expires_in=security.token_expires_in(),
        user=auth_service.user_to_out(user),
    )
    return ApiResponse[TokenOut](data=data)


@router.post("/logout", response_model=ApiResponse[dict], summary="退出登录")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """登出（JWT 无状态，仅记录审计日志并由前端清除令牌）。"""
    audit_service.log_logout(db, current_user, request=request)
    return ApiResponse[dict](data={"message": "已退出登录"})


@router.get("/me", response_model=ApiResponse[dict], summary="当前用户信息")
def me(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """返回当前登录用户信息与权限码。"""
    request.state.user_id = current_user.id
    request.state.username = current_user.username
    request.state.tenant_id = current_user.tenant_id
    data = {
        "user": auth_service.user_to_out(current_user).model_dump(mode="json"),
        "permissions": auth_service.user_permission_codes(current_user),
    }
    return ApiResponse[dict](data=data)


@router.get("/profile", response_model=ApiResponse[UserOut], summary="个人资料")
def profile(current_user: User = Depends(get_current_user)):
    """返回当前用户基础资料。"""
    return ApiResponse[UserOut](data=auth_service.user_to_out(current_user))


@router.post("/password", response_model=ApiResponse[dict], summary="修改密码")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改当前用户密码。"""
    err = auth_service.change_password(
        db, current_user, payload.old_password, payload.new_password
    )
    if err:
        audit_service.record(
            db,
            audit_service.EVENT_PASSWORD_CHANGE,
            user_id=current_user.id,
            username=current_user.username,
            tenant_id=current_user.tenant_id,
            action="修改密码失败",
            status="failure",
            status_code=400,
            request=request,
            detail=err,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    audit_service.record(
        db,
        audit_service.EVENT_PASSWORD_CHANGE,
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=current_user.tenant_id,
        action="修改密码成功",
        status="success",
        status_code=200,
        request=request,
    )
    return ApiResponse[dict](data={"message": "密码修改成功，请重新登录"})
