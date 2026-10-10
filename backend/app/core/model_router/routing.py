"""M6 模型路由引擎：能力声明 → 路由决策 → 降级/兜底 → 计量/缓存。

核心 API（函数式，接收 db Session）：
    route_model(db, capability, input, *, tenant_id, sensitive=False,
                force_local=False, model=None, temperature=None, max_tokens=None,
                skip_cache=False) -> ModelRouteResult

路由策略（对应 docs/os-kernel-design.md 3.6）：
    1. 查询能力声明（未登记则按默认规则：不敏感 / 不降级 / 不缓存）；
    2. 敏感数据强制本地，禁止出网（白名单配置控制）；
    3. 本地优先 → 本地不可用且允许降级 → 云端 → 全不可用走规则兜底；
    4. 降级开关（全局）打开时，直接走规则兜底，跳过一切模型调用；
    5. 相同输入指纹命中缓存直接返回（cost_cap/cache_ttl 控制）；
    6. 每次决策与调用结果写入计量表 oc_core_model_route_log。
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.model_router import (
    CAPABILITY_KINDS,
    ROUTE_MODES,
    CoreModelCache,
    CoreModelCapability,
    CoreModelRouteLog,
)

# 全局降级开关（对应设计文档 3.6 降级开关：一键全局降级到规则引擎）
MODEL_ROUTER_DEGRADE_ALL = False


class ModelRouterError(RuntimeError):
    """模型路由异常（能力未登记 / 参数非法 / 全链不可用且不允许兜底）。"""


@dataclass
class ModelRouteResult:
    """模型路由结果（与 LLMResult 对齐，另附路由元信息）。"""

    text: str
    mode: str  # local / api / rule
    model: Optional[str] = None
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    fallback: bool = False
    rule_fallback: bool = False
    cached: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """naive datetime 对齐为 UTC aware（SQLite 回读无时区）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fp(capability: str, input: Any) -> str:
    """输入指纹：capability + 输入内容规范化哈希。"""
    raw = json.dumps(
        {"c": capability, "i": input}, sort_keys=True, ensure_ascii=False, default=str
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _default_capability(capability: str) -> dict[str, Any]:
    """能力未登记时的默认路由规则（保守：不敏感 / 不降级 / 不缓存 / 不限成本）。"""
    return {
        "id": None,
        "capability": capability,
        "kind": "llm",
        "description": None,
        "sensitive": False,
        "fallback_cloud": False,
        "cost_cap": 0,
        "cache_ttl_seconds": 0,
        "enabled": True,
    }


def get_capability(db: Session, capability: str) -> dict[str, Any]:
    """查询能力声明；未登记时返回保守默认规则。"""
    row = db.execute(
        select(CoreModelCapability).where(CoreModelCapability.capability == capability)
    ).scalar_one_or_none()
    if row is None:
        return _default_capability(capability)
    return {
        "id": row.id,
        "capability": row.capability,
        "kind": row.kind,
        "description": row.description,
        "sensitive": row.sensitive,
        "fallback_cloud": row.fallback_cloud,
        "cost_cap": row.cost_cap,
        "cache_ttl_seconds": row.cache_ttl_seconds,
        "enabled": row.enabled,
    }


def upsert_capability(
    db: Session,
    *,
    capability: str,
    kind: str = "llm",
    description: Optional[str] = None,
    sensitive: bool = False,
    fallback_cloud: bool = False,
    cost_cap: int = 0,
    cache_ttl_seconds: int = 300,
    enabled: bool = True,
) -> CoreModelCapability:
    """登记/更新能力声明（供插件清单装载或运维配置）。"""
    if kind not in CAPABILITY_KINDS:
        raise ModelRouterError(f"非法能力类型: {kind}，可选 {CAPABILITY_KINDS}")
    row = db.execute(
        select(CoreModelCapability).where(CoreModelCapability.capability == capability)
    ).scalar_one_or_none()
    if row is None:
        row = CoreModelCapability(
            capability=capability,
            kind=kind,
            description=description,
            sensitive=sensitive,
            fallback_cloud=fallback_cloud,
            cost_cap=cost_cap,
            cache_ttl_seconds=cache_ttl_seconds,
            enabled=enabled,
        )
        db.add(row)
    else:
        row.kind = kind
        row.description = description
        row.sensitive = sensitive
        row.fallback_cloud = fallback_cloud
        row.cost_cap = cost_cap
        row.cache_ttl_seconds = cache_ttl_seconds
        row.enabled = enabled
    db.flush()
    return row


def set_global_degrade(degrade_all: bool) -> None:
    """一键全局降级开关（进程内生效；运维在故障时快速止损）。"""
    global MODEL_ROUTER_DEGRADE_ALL
    MODEL_ROUTER_DEGRADE_ALL = bool(degrade_all)


def is_degraded() -> bool:
    return MODEL_ROUTER_DEGRADE_ALL


# ------------------------------------------------------------ 缓存
def _cache_get(db: Session, tenant_id: int, fingerprint: str) -> Optional[CoreModelCache]:
    row = db.execute(
        select(CoreModelCache).where(
            CoreModelCache.tenant_id == tenant_id,
            CoreModelCache.fingerprint == fingerprint,
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at is not None and _as_utc(row.expires_at) < _utcnow():
        db.delete(row)
        db.flush()
        return None
    return row


def _cache_put(
    db: Session,
    tenant_id: int,
    fingerprint: str,
    capability: str,
    mode: str,
    model: Optional[str],
    result: dict[str, Any],
    ttl_seconds: int,
) -> None:
    expires_at = _utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None
    db.add(
        CoreModelCache(
            tenant_id=tenant_id,
            fingerprint=fingerprint,
            capability=capability,
            mode=mode,
            model=model,
            result=result,
            expires_at=expires_at,
        )
    )
    db.flush()


def _log_call(
    db: Session,
    *,
    tenant_id: int,
    capability: str,
    mode: str,
    model: Optional[str],
    sensitive: bool,
    ok: bool,
    fallback: bool,
    cached: bool,
    latency_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    error: Optional[str] = None,
) -> None:
    total = prompt_tokens + completion_tokens
    db.add(
        CoreModelRouteLog(
            tenant_id=tenant_id,
            capability=capability,
            mode=mode,
            model=model,
            sensitive=sensitive,
            ok=ok,
            fallback=fallback,
            cached=cached,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            error=error,
        )
    )
    db.flush()


# ------------------------------------------------------------ 模型调用
def _call_model(
    capability: str,
    input: Any,
    *,
    mode: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> tuple[dict[str, Any], Optional[str]]:
    """实际调用模型（local/api 双模式），返回 (result, error)。"""
    from app.services.ai.llm_client import LLMClient, LLMError

    try:
        client = LLMClient(mode=mode, model=model)
        messages = [
            {"role": "system", "content": f"你是运营智脑（OpsCompass）的{capability}能力执行器，只输出结构化结果。"},
            {"role": "user", "content": str(input)},
        ]
        res = client.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        result = {
            "text": res.text,
            "mode": res.mode,
            "model": res.model,
            "latency_ms": res.duration_ms,
            "prompt_tokens": res.prompt_tokens,
            "completion_tokens": res.completion_tokens,
            "total_tokens": res.prompt_tokens + res.completion_tokens,
        }
        return result, None
    except LLMError as exc:
        return {}, str(exc)
    except Exception as exc:  # noqa: BLE001
        return {}, f"模型调用异常: {exc}"


def _rule_fallback(capability: str, input: Any) -> dict[str, Any]:
    """规则兜底：不调用任何模型，返回结构化兜底结果（业务不报错）。"""
    return {
        "text": f"[规则兜底] 能力 {capability} 暂不可用，已按规则引擎返回空结果。",
        "mode": "rule",
        "model": None,
        "latency_ms": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "fallback": True,
        "rule_fallback": True,
    }


def route_model(
    db: Session,
    capability: str,
    input: Any,
    *,
    tenant_id: int = 1,
    sensitive: bool = False,
    force_local: bool = False,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    skip_cache: bool = False,
) -> ModelRouteResult:
    """模型路由入口：按能力声明与降级策略选择调用链，并记录计量。

    返回结果恒为 ModelRouteResult；全链不可用且不允许兜底时抛 ModelRouterError
    （业务可捕获后自行处理，避免静默吞错）。
    """
    started = time.perf_counter()
    cap = get_capability(db, capability)
    if not cap["enabled"]:
        raise ModelRouterError(f"能力已停用: {capability}")

    # 敏感数据强制本地：入参显式 sensitive=True 或能力声明敏感
    effective_sensitive = sensitive or cap["sensitive"]
    # 数据分级红线：敏感数据禁止降级云端（白名单控制）
    allow_cloud = cap["fallback_cloud"] and not effective_sensitive

    # 全局降级开关：直接走规则兜底
    if MODEL_ROUTER_DEGRADE_ALL:
        result = _rule_fallback(capability, input)
        _log_call(
            db,
            tenant_id=tenant_id,
            capability=capability,
            mode="rule",
            model=None,
            sensitive=effective_sensitive,
            ok=True,
            fallback=True,
            cached=False,
            latency_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
            error=None,
        )
        db.commit()
        return ModelRouteResult(**result)

    # 缓存命中
    fingerprint = _fp(capability, input)
    if not skip_cache and cap["cache_ttl_seconds"] > 0:
        cached = _cache_get(db, tenant_id, fingerprint)
        if cached is not None:
            _log_call(
                db,
                tenant_id=tenant_id,
                capability=capability,
                mode=cached.mode,
                model=cached.model,
                sensitive=effective_sensitive,
                ok=True,
                fallback=False,
                cached=True,
                latency_ms=0,
                prompt_tokens=0,
                completion_tokens=0,
                error=None,
            )
            db.commit()
            raw = cached.result or {}
            return ModelRouteResult(
                text=raw.get("text", ""),
                mode=cached.mode,
                model=cached.model,
                latency_ms=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                fallback=False,
                cached=True,
                raw=raw,
            )

    # 路由链：本地优先
    chain_modes: list[str] = []
    if force_local or effective_sensitive:
        chain_modes = ["local"]
    else:
        chain_modes = ["local"]
        if allow_cloud:
            chain_modes.append("api")

    last_error: Optional[str] = None
    last_result: Optional[dict[str, Any]] = None
    for mode in chain_modes:
        result, err = _call_model(
            capability,
            input,
            mode=mode,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if err is None:
            last_result = result
            last_error = None
            break
        last_error = err

    # 全链不可用：走规则兜底（不抛错，业务不报错）
    if last_result is None:
        result = _rule_fallback(capability, input)
        _log_call(
            db,
            tenant_id=tenant_id,
            capability=capability,
            mode="rule",
            model=None,
            sensitive=effective_sensitive,
            ok=True,
            fallback=True,
            cached=False,
            latency_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
            error=last_error,
        )
        db.commit()
        return ModelRouteResult(**result)

    # 成功：写缓存 + 计量
    if not skip_cache and cap["cache_ttl_seconds"] > 0:
        _cache_put(
            db,
            tenant_id,
            fingerprint,
            capability,
            last_result["mode"],
            last_result["model"],
            last_result,
            cap["cache_ttl_seconds"],
        )
    _log_call(
        db,
        tenant_id=tenant_id,
        capability=capability,
        mode=last_result["mode"],
        model=last_result["model"],
        sensitive=effective_sensitive,
        ok=True,
        fallback=False,
        cached=False,
        latency_ms=last_result["latency_ms"],
        prompt_tokens=last_result["prompt_tokens"],
        completion_tokens=last_result["completion_tokens"],
        error=None,
    )
    db.commit()
    return ModelRouteResult(**last_result)


# ------------------------------------------------------------ 计量查询
def route_log_stats(
    db: Session,
    *,
    tenant_id: Optional[int] = None,
    capability: Optional[str] = None,
    since: Optional[datetime] = None,
    limit_days: int = 7,
) -> dict[str, Any]:
    """调用计量汇总：总量、成功率、降级率、缓存命中率、耗时与 tokens 聚合。"""
    stmt = select(CoreModelRouteLog)
    if tenant_id is not None:
        stmt = stmt.where(CoreModelRouteLog.tenant_id == tenant_id)
    if capability:
        stmt = stmt.where(CoreModelRouteLog.capability == capability)
    if since is not None:
        stmt = stmt.where(CoreModelRouteLog.created_at >= since)
    else:
        stmt = stmt.where(
            CoreModelRouteLog.created_at >= _utcnow() - timedelta(days=limit_days)
        )
    rows = db.execute(stmt).scalars().all()

    total = len(rows)
    if total == 0:
        return {
            "total": 0,
            "success": 0,
            "success_rate": 0.0,
            "fallback_count": 0,
            "fallback_rate": 0.0,
            "cache_hit_count": 0,
            "cache_hit_rate": 0.0,
            "avg_latency_ms": 0,
            "total_tokens": 0,
            "by_mode": {},
        }
    ok_count = sum(1 for r in rows if r.ok)
    fallback_count = sum(1 for r in rows if r.fallback)
    cache_hit_count = sum(1 for r in rows if r.cached)
    avg_latency = sum(r.latency_ms for r in rows) // total
    total_tokens = sum(r.total_tokens for r in rows)
    by_mode: dict[str, int] = {}
    for r in rows:
        by_mode[r.mode] = by_mode.get(r.mode, 0) + 1

    return {
        "total": total,
        "success": ok_count,
        "success_rate": round(ok_count / total, 4),
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / total, 4),
        "cache_hit_count": cache_hit_count,
        "cache_hit_rate": round(cache_hit_count / total, 4),
        "avg_latency_ms": avg_latency,
        "total_tokens": total_tokens,
        "by_mode": by_mode,
    }
