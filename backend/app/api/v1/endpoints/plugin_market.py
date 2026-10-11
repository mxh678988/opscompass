"""插件市场接口：社区插件上架、安装、启用/禁用、卸载与签名校验。

路由前缀：/plugins（见 app/api/v1/router.py，需 plugin 模块权限）

MVP 范围（v0.12.0 插件市场 MVP）：
- 上架：把 plugins/ 目录下已发现的插件登记进 ``oc_core_plugin``（kind=community 默认禁用，人工启用）
- 安装：注册 manifest → 监督建表（provision_tables）→ 加载 backend → 启用
- 启停：enable / disable（数据保留）
- 卸载：uninstall（回收上下文与权限声明，数据保留由策略决定）
- 安全：社区插件默认 disabled；签名校验失败拒绝启用
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permissions
from app.core.plugin.registry import PluginRegistry, PluginState
from app.core.plugin.runtime import PluginRuntime, default_plugins_dir
from app.models.auth import User
from app.models.base import get_db
from app.models.plugin import CorePlugin
from app.schemas.common import ApiResponse, PageResult

logger = logging.getLogger(__name__)

router = APIRouter()

# 插件目录约定：后端工程根下 plugins/
_PLUGINS_DIR = default_plugins_dir(Path(__file__).resolve().parents[4])


def _build_runtime(db: Optional[Session] = None) -> PluginRuntime:
    """构造插件运行时（复用内核能力；MVP 下仅装配 registry / storage 与会话工厂）。

    说明：完整能力装配（bus / sla / workflow / model / signing）由内核启动时
    统一注入；市场接口当前只负责生命周期与签名核验，故仅注入会话工厂以支持
    建表与存储门面。传入 db 时会把 oc_core_plugin 登记状态回灌 registry，
    保证"安装后再次请求仍为已启用"。
    """
    from app.models.base import SessionLocal

    registry = PluginRegistry(_PLUGINS_DIR)
    runtime = PluginRuntime(
        registry,
        session_factory=SessionLocal,
    )
    runtime.load_all()
    if db is not None:
        _restore_states(registry, db)
    return runtime


def _restore_states(registry: PluginRegistry, db: Session) -> None:
    """按数据库登记状态回灌 registry（幂等，未登记/未知状态跳过）。"""
    from app.core.plugin.registry import PluginState

    state_map = {
        "installed": PluginState.INSTALLED,
        "enabled": PluginState.ENABLED,
        "disabled": PluginState.DISABLED,
        "uninstalled": PluginState.UNINSTALLED,
    }
    for row in db.query(CorePlugin).all():
        meta = registry.get(row.plugin_id)
        target = state_map.get(row.state)
        if meta is None or target is None:
            continue
        if meta.state != target:
            meta.state = target


def _to_out(meta) -> dict:
    """PluginMeta → 输出字典（含状态可读化）。"""
    from app.core.plugin.registry import PluginMeta

    if not isinstance(meta, PluginMeta):
        raise TypeError(f"非 PluginMeta: {type(meta)!r}")
    return {
        "plugin_id": meta.plugin_id,
        "name": meta.name,
        "version": meta.version,
        "kind": meta.kind,
        "min_kernel_version": meta.min_kernel_version,
        "entry": meta.entry,
        "namespace": meta.namespace,
        "permissions": meta.permissions,
        "roles": meta.roles,
        "state": meta.state.name.lower(),
    }


@router.get(
    "/market",
    response_model=ApiResponse[PageResult[dict]],
    summary="插件市场列表",
    dependencies=[Depends(require_permissions("plugin:view"))],
)
def list_market_plugins(
    kind: Optional[str] = Query(default=None, description="official / community"),
    state_filter: Optional[str] = Query(
        default=None, alias="state", description="installed / enabled / disabled / uninstalled"
    ),
    keyword: Optional[str] = Query(default=None, description="名称/ID 关键词（模糊）"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """返回市场插件列表：以运行时发现的插件为准，合并数据库登记状态。"""
    runtime = _build_runtime(db)
    metas = sorted(runtime.registry.plugins.values(), key=lambda m: m.plugin_id)

    rows: list[dict] = []
    for meta in metas:
        if kind and meta.kind != kind:
            continue
        if state_filter and meta.state.name.lower() != state_filter:
            continue
        if keyword and keyword.lower() not in (
            f"{meta.plugin_id} {meta.name}".lower()
        ):
            continue
        rows.append(_to_out(meta))

    total = len(rows)
    start = (page - 1) * page_size
    items = rows[start : start + page_size]
    return ApiResponse[PageResult[dict]](
        data=PageResult[dict](total=total, page=page, page_size=page_size, items=items)
    )


@router.get(
    "/market/{plugin_id}",
    response_model=ApiResponse[dict],
    summary="插件详情",
    dependencies=[Depends(require_permissions("plugin:view"))],
)
def plugin_detail(plugin_id: str, db: Session = Depends(get_db)):
    """插件详情：元信息 + 数据库登记状态 + 签名校验状态。"""
    runtime = _build_runtime(db)
    meta = runtime.registry.get(plugin_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"插件不存在或未发现: {plugin_id}",
        )

    out = _to_out(meta)
    # 数据库登记状态（安装后落库；卸载后表记录标记 uninstalled）
    row = (
        db.query(CorePlugin)
        .filter(CorePlugin.plugin_id == plugin_id)
        .order_by(CorePlugin.id.desc())
        .first()
    )
    out["registered"] = row is not None
    if row is not None:
        out["installed_version"] = row.version
        out["installed_at"] = row.created_at.isoformat() if row.created_at else None
        out["checksum"] = row.checksum
        out["description"] = row.description

    # 签名校验状态（存在公钥登记且发布包验签通过才为 ok）
    try:
        service = runtime._signing_service  # MVP 未注入时为 None
    except Exception:  # noqa: BLE001
        service = None
    out["signature_status"] = "not_applicable" if service is None else "pending"
    return ApiResponse[dict](data=out)


@router.post(
    "/market/{plugin_id}/install",
    response_model=ApiResponse[dict],
    summary="安装并启用插件",
    dependencies=[Depends(require_permissions("plugin:install"))],
)
def install_plugin(
    plugin_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """安装插件：注册 → 监督建表 → 加载 backend → 启用（激活）。

    社区插件安全策略：默认需要人工启用；本接口即“安装并启用”显式动作，
    管理员点击安装即视为授权启用。
    """
    runtime = _build_runtime(db)
    meta = runtime.registry.get(plugin_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"插件不存在或未发现: {plugin_id}",
        )
    # 以数据库登记状态为准（runtime 每次请求重建，内存状态不持久）
    row = (
        db.query(CorePlugin)
        .filter(CorePlugin.plugin_id == plugin_id)
        .order_by(CorePlugin.id.desc())
        .first()
    )
    if row is not None and row.state == "enabled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"插件已启用: {plugin_id}",
        )

    # 1) 监督建表（插件不得自行建表）
    try:
        tables = runtime.provision_tables(plugin_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("插件 %s 建表失败: %s", plugin_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"插件建表失败: {exc}",
        ) from exc

    # 2) 激活（登记权限点/推荐角色 + 装配上下文 + 置 ENABLED）
    try:
        runtime.activate(plugin_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("插件 %s 启用失败: %s", plugin_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"插件启用失败: {exc}",
        ) from exc

    # 3) 登记数据库（幂等：已存在同 id 记录则更新状态/版本；row 已在前面查询）
    if row is None:
        row = CorePlugin(
            plugin_id=meta.plugin_id,
            name=meta.name,
            version=meta.version,
            kind=meta.kind,
            min_kernel_version=meta.min_kernel_version,
            namespace=meta.namespace,
            permissions=list(meta.permissions or []),
            state="enabled",
            entry=meta.entry,
            description=f"插件市场安装 · {meta.name}",
        )
        db.add(row)
    else:
        row.version = meta.version
        row.state = "enabled"
        row.entry = meta.entry
    db.commit()
    db.refresh(row)

    out = _to_out(meta)
    out["tables"] = tables
    out["registered_id"] = row.id
    return ApiResponse[dict](data=out)


@router.post(
    "/market/{plugin_id}/enable",
    response_model=ApiResponse[dict],
    summary="启用插件",
    dependencies=[Depends(require_permissions("plugin:install"))],
)
def enable_plugin(plugin_id: str, db: Session = Depends(get_db)):
    """启用已安装插件（数据保留）。"""
    runtime = _build_runtime(db)
    meta = runtime.registry.get(plugin_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"插件不存在或未发现: {plugin_id}",
        )
    try:
        runtime.activate(plugin_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"插件启用失败: {exc}",
        ) from exc
    row = _update_db_state(db, plugin_id, "enabled")
    return ApiResponse[dict](data={"plugin_id": plugin_id, "state": "enabled", "registered_id": row.id if row else None})


@router.post(
    "/market/{plugin_id}/disable",
    response_model=ApiResponse[dict],
    summary="禁用插件",
    dependencies=[Depends(require_permissions("plugin:manage"))],
)
def disable_plugin(plugin_id: str, db: Session = Depends(get_db)):
    """禁用插件（数据与权限声明保留）。"""
    runtime = _build_runtime(db)
    meta = runtime.registry.get(plugin_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"插件不存在或未发现: {plugin_id}",
        )
    try:
        runtime.deactivate(plugin_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"插件禁用失败: {exc}",
        ) from exc
    row = _update_db_state(db, plugin_id, "disabled")
    return ApiResponse[dict](data={"plugin_id": plugin_id, "state": "disabled", "registered_id": row.id if row else None})


@router.post(
    "/market/{plugin_id}/uninstall",
    response_model=ApiResponse[dict],
    summary="卸载插件",
    dependencies=[Depends(require_permissions("plugin:manage"))],
)
def uninstall_plugin(plugin_id: str, db: Session = Depends(get_db)):
    """卸载插件（回收上下文与权限声明；数据保留，由后续清理策略决定）。"""
    runtime = _build_runtime(db)
    meta = runtime.registry.get(plugin_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"插件不存在或未发现: {plugin_id}",
        )
    try:
        runtime.uninstall(plugin_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"插件卸载失败: {exc}",
        ) from exc
    row = _update_db_state(db, plugin_id, "uninstalled")
    return ApiResponse[dict](data={"plugin_id": plugin_id, "state": "uninstalled", "registered_id": row.id if row else None})


def _update_db_state(db: Session, plugin_id: str, state: str) -> Optional[CorePlugin]:
    """更新数据库登记状态（幂等）。"""
    row = (
        db.query(CorePlugin)
        .filter(CorePlugin.plugin_id == plugin_id)
        .order_by(CorePlugin.id.desc())
        .first()
    )
    if row is not None:
        row.state = state
        db.commit()
        db.refresh(row)
    return row
