"""统一身份治理 · 委派与代理、离职交接（M3）。

职责（对应设计文档 3.5「委派与代理」）：
1. 临时授权（委派）：把委托人自身权限的**子集**在限定时段内授予他人，到期/撤销自动失效；
2. 越权委托拦截：委派范围必须是委托人自身角色与权限的子集（超管除外），防止权限放大；
3. 一律留痕：委派创建/撤销/交接写入 ``oc_audit_log``（event_type=sensitive_operation）；
4. 离职交接：一次完成「角色转移 + 在途委派撤销 + 审计留痕」，不改动历史审计记录。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.identity.permissions import load_core_permissions
from app.core.security import collect_permission_codes
from app.models.auth import AuditLog, Permission, Role
from app.models.identity import CoreDelegation

# 单次委派最长时长（天）：禁止无期限临时授权
MAX_DELEGATION_DAYS = 90

# 审计事件类型（与 oc_audit_log 既有取值一致）
AUDIT_EVENT_SENSITIVE = "sensitive_operation"


class DelegationError(ValueError):
    """委派非法（自我委派、超范围授权、时间窗不合理等）。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite 读回的 naive 时间按 UTC 解释。"""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _audit(db: Session, *, action: str, user: Any = None, detail: str = "") -> None:
    db.add(
        AuditLog(
            tenant_id=getattr(user, "tenant_id", None),
            user_id=getattr(user, "id", None),
            username=getattr(user, "username", None),
            event_type=AUDIT_EVENT_SENSITIVE,
            action=action,
            status="success",
            detail=detail,
        )
    )


def own_role_codes(user: Any) -> set[str]:
    return {r.code for r in (getattr(user, "roles", None) or [])}


def own_permission_codes(user: Any) -> set[str]:
    """用户当前持有的权限码（超管为全部内核权限点）。"""
    if getattr(user, "is_superuser", False):
        return {d.code for d in load_core_permissions()}
    return collect_permission_codes(user)


def create_delegation(
    db: Session,
    *,
    delegator: Any,
    delegatee: Any,
    role_codes: Iterable[str] = (),
    permission_codes: Iterable[str] = (),
    reason: str = "",
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    created_by: Optional[Any] = None,
) -> CoreDelegation:
    """创建临时委派；范围必须是委托人自身权限子集。"""
    if delegator is None or delegatee is None:
        raise DelegationError("委托人与被委托人不能为空")
    if getattr(delegator, "id", None) == getattr(delegatee, "id", None):
        raise DelegationError("不允许委托给本人")

    start = _as_utc(start_at) or _utcnow()
    end = _as_utc(end_at)
    if end is None:
        raise DelegationError("必须指定委派失效时间（禁止无期限委派）")
    if end <= start:
        raise DelegationError("失效时间必须晚于生效时间")
    if end - start > timedelta(days=MAX_DELEGATION_DAYS):
        raise DelegationError(f"单次委派不得超过 {MAX_DELEGATION_DAYS} 天")

    roles = sorted({str(c) for c in role_codes or () if c})
    perms = sorted({str(c) for c in permission_codes or () if c})
    if not roles and not perms:
        raise DelegationError("委派范围为空：至少指定角色或权限点")

    if not getattr(delegator, "is_superuser", False):
        extra_roles = sorted(set(roles) - own_role_codes(delegator))
        if extra_roles:
            raise DelegationError(f"越权委托：委托人未持有角色 {extra_roles}")
        extra_perms = sorted(set(perms) - own_permission_codes(delegator))
        if extra_perms:
            raise DelegationError(f"越权委托：委托人未持有权限 {extra_perms}")

    delegation = CoreDelegation(
        delegator_id=delegator.id,
        delegatee_id=delegatee.id,
        scope_roles=roles,
        scope_permissions=perms,
        reason=reason or None,
        status="active",
        start_at=start,
        end_at=end,
        created_by=getattr(created_by, "id", None) or getattr(delegator, "id", None),
    )
    db.add(delegation)
    _audit(
        db,
        action="delegation.create",
        user=created_by or delegator,
        detail=(
            f"委托人={delegator.username} 被委托人={delegatee.username} "
            f"角色={roles} 权限={perms} 有效期=[{start.isoformat()}, {end.isoformat()}]"
        ),
    )
    db.commit()
    db.refresh(delegation)
    return delegation


def revoke_delegation(db: Session, delegation: CoreDelegation, *, revoked_by: Any = None) -> CoreDelegation:
    """撤销委派（立即失效）。"""
    if delegation.status != "active":
        raise DelegationError(f"仅 active 委派可撤销，当前状态: {delegation.status}")
    delegation.status = "revoked"
    delegation.revoked_at = _utcnow()
    delegation.revoked_by = getattr(revoked_by, "id", None)
    _audit(
        db,
        action="delegation.revoke",
        user=revoked_by,
        detail=f"撤销委派 #{delegation.id}（委托人={delegation.delegator_id} → 被委托人={delegation.delegatee_id}）",
    )
    db.commit()
    db.refresh(delegation)
    return delegation


def refresh_status(db: Session, *, now: Optional[datetime] = None) -> int:
    """把已过期的 active 委派批量置为 expired，返回条数。"""
    moment = _as_utc(now) or _utcnow()
    rows = (
        db.execute(select(CoreDelegation).where(CoreDelegation.status == "active"))
        .scalars()
        .all()
    )
    expired = 0
    for row in rows:
        if _as_utc(row.end_at) <= moment:
            row.status = "expired"
            expired += 1
    if expired:
        db.commit()
    return expired


def active_delegations(
    db: Session, delegatee_id: int, *, now: Optional[datetime] = None
) -> list[CoreDelegation]:
    """被委托人在当前时刻生效的委派列表。"""
    moment = _as_utc(now) or _utcnow()
    rows = (
        db.execute(
            select(CoreDelegation).where(
                CoreDelegation.delegatee_id == delegatee_id,
                CoreDelegation.status == "active",
            )
        )
        .scalars()
        .all()
    )
    return [r for r in rows if _as_utc(r.start_at) <= moment < _as_utc(r.end_at)]


def delegated_permissions(
    db: Session, delegatee_id: int, *, now: Optional[datetime] = None
) -> set[str]:
    """委派带来的权限码集合（角色码展开为权限码 + 显式权限码）。"""
    codes: set[str] = set()
    role_codes: set[str] = set()
    for delegation in active_delegations(db, delegatee_id, now=now):
        codes.update(str(c) for c in (delegation.scope_permissions or []))
        role_codes.update(str(c) for c in (delegation.scope_roles or []))
    if role_codes:
        rows = db.execute(select(Role).where(Role.code.in_(sorted(role_codes)))).scalars().all()
        for role in rows:
            codes.update(p.code for p in (role.permissions or []))
    return codes


def effective_permissions(db: Session, user: Any, *, now: Optional[datetime] = None) -> list[str]:
    """用户实际生效的权限码 = 自身角色权限 ∪ 在途委派权限。"""
    if user is None:
        return []
    if getattr(user, "is_superuser", False):
        return sorted(own_permission_codes(user))
    owned = set(collect_permission_codes(user))
    owned |= delegated_permissions(db, user.id, now=now)
    return sorted(owned)


def handover(
    db: Session,
    *,
    from_user: Any,
    to_user: Any,
    role_codes: Optional[Iterable[str]] = None,
    revoke_delegations: bool = True,
    reason: str = "",
    operator: Any = None,
) -> dict:
    """离职交接：角色转移 + 在途委派撤销，全程留痕。

    ``role_codes`` 为空表示转移其全部角色。
    """
    if from_user is None or to_user is None:
        raise DelegationError("交接双方不能为空")
    if from_user.id == to_user.id:
        raise DelegationError("交接双方不得为同一人")

    wanted = (
        sorted({str(c) for c in role_codes})
        if role_codes
        else sorted(own_role_codes(from_user))
    )
    rows = db.execute(select(Role).where(Role.code.in_(wanted))).scalars().all() if wanted else []
    found = {r.code: r for r in rows}
    missing = sorted(c for c in wanted if c not in found)

    owned = {r.code for r in (to_user.roles or [])}
    transferred = [found[c] for c in wanted if c in found and c not in owned]
    if transferred:
        to_user.roles = list(to_user.roles or []) + transferred

    revoked = 0
    if revoke_delegations:
        outgoing = (
            db.execute(
                select(CoreDelegation).where(
                    CoreDelegation.delegator_id == from_user.id,
                    CoreDelegation.status == "active",
                )
            )
            .scalars()
            .all()
        )
        moment = _utcnow()
        for row in outgoing:
            row.status = "revoked"
            row.revoked_at = moment
            row.revoked_by = getattr(operator, "id", None)
            revoked += 1

    _audit(
        db,
        action="identity.handover",
        user=operator or from_user,
        detail=(
            f"交接：{from_user.username} → {to_user.username} 角色={[r.code for r in transferred]} "
            f"缺失角色={missing} 撤销委派={revoked} 事由={reason or '未填写'}"
        ),
    )
    db.commit()
    return {
        "from_user": from_user.username,
        "to_user": to_user.username,
        "transferred_roles": [r.code for r in transferred],
        "missing_roles": missing,
        "revoked_delegations": revoked,
    }


def make_permission_authorizer(registry: Any, *, on_denied: Any = None):
    """构造内核鉴权回调（注入插件 SDK 的 ``auth`` 门面）。

    回调签名 ``authorize(perm_code, user=None, plugin_id=None) -> bool``：
    - 权限点必须已在注册中心登记，否则拒绝（插件不得使用未声明权限点）；
    - ``user`` 为空视为内核/后台任务调用，放行（由调用方保证可信）；
    - 否则按用户自身权限 + 在途委派权限判断；拒绝时可回调 ``on_denied`` 落审计。
    """

    def _authorize(perm_code: str, user: Any = None, plugin_id: Optional[str] = None) -> bool:
        if perm_code not in registry:
            raise PermissionError(f"权限点未注册，拒绝鉴权: {perm_code}")
        if user is None:
            return True
        if getattr(user, "is_superuser", False):
            return True
        owned = set(collect_permission_codes(user))
        for code in list(getattr(user, "delegated_permission_codes", None) or []):
            owned.add(str(code))
        if perm_code in owned:
            return True
        if on_denied is not None:
            on_denied(perm_code, user, plugin_id)
        return False

    return _authorize


__all__ = [
    "MAX_DELEGATION_DAYS",
    "DelegationError",
    "create_delegation",
    "revoke_delegation",
    "refresh_status",
    "active_delegations",
    "delegated_permissions",
    "effective_permissions",
    "handover",
    "make_permission_authorizer",
]
