"""P9 模型中心服务：模型接入端点管理 + 连通性自检 + 按显存分档的模型推荐。

- 端点：本地 Ollama（local_ollama）/ OpenAI 兼容云端（cloud_openai），租户内隔离、Key 密文落库。
- 自检：本地走 /api/tags 与 /api/version；云端走 /models，失败回退最小对话请求，自动纠偏 /v1 前缀。
- 推荐：结合硬件探测（显存 / 内存）给出可跑的本地模型量级与接入后端，探测不可用时降级为保守结论。
- 生效：激活端点后可同步运行配置（内存 + 可选 .env），无需重启容器即可让新端点对后续调用生效。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, settings
from app.core.crypto import decrypt, encrypt
from app.models.model_hub import AIModelEndpoint, ENDPOINT_KINDS
from app.services import hardware_service

# ---------------------------------------------------------------- 常量
_VRAM_TIERS: list[dict[str, Any]] = [
    {"key": "cpu", "label": "无独显 / 仅 CPU 推理", "min_gb": 0, "max_gb": 0},
    {"key": "4g", "label": "4GB 显存（入门独显）", "min_gb": 4, "max_gb": 6},
    {"key": "8g", "label": "8GB 显存（主流独显）", "min_gb": 6, "max_gb": 10},
    {"key": "12g", "label": "12GB 显存", "min_gb": 10, "max_gb": 14},
    {"key": "16g", "label": "16GB 显存", "min_gb": 14, "max_gb": 20},
    {"key": "24g", "label": "24GB 显存（RTX 4090 / A10 级）", "min_gb": 20, "max_gb": 32},
    {"key": "48g", "label": "48GB 显存（A6000 / 双卡）", "min_gb": 32, "max_gb": 56},
    {"key": "80g", "label": "80GB 显存（A100 / H100 级）", "min_gb": 56, "max_gb": 1024},
]

# 本地可跑模型目录：vram_gb 为 Q4 量化下建议的最低保底显存（含上下文与 KV Cache 余量）
_MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "key": "qwen2.5-0.5b",
        "display": "Qwen2.5 0.5B（极轻量）",
        "params": "0.5B",
        "quant": "Q4_K_M",
        "vram_gb": 1.5,
        "ram_gb": 4,
        "ctx": "8K",
        "ollama_tag": "qwen2.5:0.5b",
        "fit_note": "仅适合意图分类 / 关键词抽取等轻任务",
    },
    {
        "key": "qwen2.5-1.5b",
        "display": "Qwen2.5 1.5B",
        "params": "1.5B",
        "quant": "Q4_K_M",
        "vram_gb": 2.5,
        "ram_gb": 6,
        "ctx": "16K",
        "ollama_tag": "qwen2.5:1.5b",
        "fit_note": "轻量摘要 / 标签生成，质量有限",
    },
    {
        "key": "qwen2.5-3b",
        "display": "Qwen2.5 3B",
        "params": "3B",
        "quant": "Q4_K_M",
        "vram_gb": 4,
        "ram_gb": 8,
        "ctx": "32K",
        "ollama_tag": "qwen2.5:3b",
        "fit_note": "CPU 可跑（较慢），适合日报摘要与简单问答",
    },
    {
        "key": "llama3.1-8b",
        "display": "Llama 3.1 8B",
        "params": "8B",
        "quant": "Q4_K_M",
        "vram_gb": 6.5,
        "ram_gb": 16,
        "ctx": "32K",
        "ollama_tag": "llama3.1:8b",
        "fit_note": "通用对话与文案能力均衡",
    },
    {
        "key": "qwen2.5-7b",
        "display": "Qwen2.5 7B（推荐主力）",
        "params": "7B",
        "quant": "Q4_K_M",
        "vram_gb": 6.5,
        "ram_gb": 16,
        "ctx": "32K",
        "ollama_tag": "qwen2.5:7b",
        "fit_note": "中文运营分析与报告撰写的主力档，性价比最高",
    },
    {
        "key": "qwen2.5-14b",
        "display": "Qwen2.5 14B",
        "params": "14B",
        "quant": "Q4_K_M",
        "vram_gb": 11,
        "ram_gb": 32,
        "ctx": "32K",
        "ollama_tag": "qwen2.5:14b",
        "fit_note": "长文分析与多步推理明显增强",
    },
    {
        "key": "qwen2.5-32b",
        "display": "Qwen2.5 32B",
        "params": "32B",
        "quant": "Q4_K_M",
        "vram_gb": 22,
        "ram_gb": 64,
        "ctx": "32K",
        "ollama_tag": "qwen2.5:32b",
        "fit_note": "接近云端中小模型的开源本地质量",
    },
    {
        "key": "llama3.3-70b",
        "display": "Llama 3.3 70B",
        "params": "70B",
        "quant": "Q4_K_M",
        "vram_gb": 48,
        "ram_gb": 128,
        "ctx": "32K",
        "ollama_tag": "llama3.3:70b",
        "fit_note": "本地可用的大模型档，需 48G 以上显存或多卡",
    },
]

# 云端 OpenAI 兼容预设（一键接入可选）
CLOUD_PRESETS: list[dict[str, Any]] = [
    {
        "key": "deepseek",
        "label": "DeepSeek（性价比首选）",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "scale": "云端大模型",
    },
    {
        "key": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "scale": "云端大模型",
    },
    {
        "key": "moonshot",
        "label": "Moonshot / Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "scale": "云端大模型",
    },
    {
        "key": "dashscope",
        "label": "阿里云百炼（通义千问）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "scale": "云端大模型",
    },
]

KIND_LABELS = {"local_ollama": "本地 Ollama", "cloud_openai": "OpenAI 兼容云端"}
PROVIDER_BY_KIND = {"local_ollama": "ollama", "cloud_openai": "custom"}


class ModelHubError(ValueError):
    """模型中心业务异常（参数/状态不合法）。"""


# ---------------------------------------------------------------- 工具
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mask(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}***{key[-4:]}"


def normalize_base_url(kind: str, base_url: str) -> str:
    """规范化接口基址：本地去掉误填的 /v1；云端统一去掉结尾斜杠。"""
    url = (base_url or "").strip().rstrip("/")
    if kind == "local_ollama" and url.endswith("/v1"):
        url = url[: -len("/v1")]
    return url


def _candidate_bases(kind: str, base_url: str) -> list[str]:
    """自检时尝试的候选基址（云端自动纠偏 /v1 前缀）。"""
    base = normalize_base_url(kind, base_url)
    if kind == "local_ollama":
        return [base]
    bases = [base]
    if not base.endswith("/v1"):
        bases.append(f"{base}/v1")
    return bases


def _httpx_client(timeout: float) -> httpx.Client:
    kwargs: dict[str, Any] = {"timeout": timeout}
    if settings.AI_PROXY:
        kwargs["proxy"] = settings.AI_PROXY
    return httpx.Client(**kwargs)


def default_config(kind: str) -> dict[str, str]:
    """某类接入的系统默认地址与模型（一键接入时兜底）。"""
    if kind == "local_ollama":
        base = settings.MODEL_HUB_LOCAL_DEFAULT_URL or settings.AI_LOCAL_BASE_URL
        return {"base_url": base, "model": settings.AI_LOCAL_MODEL, "provider": "ollama"}
    base = settings.MODEL_HUB_CLOUD_DEFAULT_URL or settings.AI_API_BASE_URL
    return {"base_url": base, "model": settings.AI_API_MODEL, "provider": "custom"}


# ---------------------------------------------------------------- 序列化
def serialize(row: AIModelEndpoint, active_id: Optional[int] = None) -> dict[str, Any]:
    """对外输出（绝不回显密文/明文 Key）。"""
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "name": row.name,
        "kind": row.kind,
        "kind_label": KIND_LABELS.get(row.kind, row.kind),
        "provider": row.provider,
        "base_url": row.base_url,
        "model": row.model,
        "param_scale": row.param_scale,
        "has_api_key": bool(row.api_key_enc),
        "api_key_hint": row.api_key_hint,
        "enabled": bool(row.enabled),
        "is_active": bool(row.is_active),
        "is_effective": (active_id is not None and row.id == active_id),
        "source": row.source,
        "remark": row.remark,
        "last_test_at": row.last_test_at.isoformat() if row.last_test_at else None,
        "last_test_ok": row.last_test_ok,
        "last_test_latency_ms": row.last_test_latency_ms,
        "last_test_message": row.last_test_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def resolve_api_key(row: AIModelEndpoint, override: Optional[str] = None) -> Optional[str]:
    """取端点 Key：优先请求传入的明文，其次解密落库密文。"""
    if override:
        return override.strip()
    if row.api_key_enc:
        return decrypt(row.api_key_enc) or None
    return None


def get_endpoint(db: Session, tenant_id: int, endpoint_id: int) -> AIModelEndpoint:
    row = db.get(AIModelEndpoint, endpoint_id)
    if row is None or row.tenant_id != tenant_id:
        raise ModelHubError(f"端点不存在：id={endpoint_id}")
    return row


def active_endpoint(db: Session, tenant_id: int, enabled_only: bool = True) -> Optional[AIModelEndpoint]:
    stmt = select(AIModelEndpoint).where(
        AIModelEndpoint.tenant_id == tenant_id, AIModelEndpoint.is_active.is_(True)
    )
    if enabled_only:
        stmt = stmt.where(AIModelEndpoint.enabled.is_(True))
    return db.execute(stmt.order_by(AIModelEndpoint.id.desc())).scalars().first()


def list_endpoints(db: Session, tenant_id: int) -> list[AIModelEndpoint]:
    stmt = (
        select(AIModelEndpoint)
        .where(AIModelEndpoint.tenant_id == tenant_id)
        .order_by(AIModelEndpoint.is_active.desc(), AIModelEndpoint.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def _clear_active(db: Session, tenant_id: int, keep_id: Optional[int] = None) -> None:
    """保证租户内至多一个生效端点。"""
    for row in list_endpoints(db, tenant_id):
        if row.is_active and row.id != keep_id:
            row.is_active = False


def _validate_kind(kind: str) -> str:
    k = (kind or "").strip().lower()
    if k not in ENDPOINT_KINDS:
        raise ModelHubError(f"接入类型不合法：{kind}（可选 {' / '.join(ENDPOINT_KINDS)}）")
    return k


# ---------------------------------------------------------------- 连通性自检
def _local_probe(base_url: str, model: Optional[str], api_key: Optional[str]) -> dict[str, Any]:
    """本地 Ollama 自检：/api/version + /api/tags 模型清单。"""
    base = normalize_base_url("local_ollama", base_url)
    steps: list[dict[str, Any]] = []
    started = time.perf_counter()

    version: Optional[str] = None
    try:
        with _httpx_client(min(settings.AI_TIMEOUT, 8)) as client:
            resp = client.get(f"{base}/api/version")
            if resp.status_code == 200:
                version = (resp.json() or {}).get("version")
                steps.append({"step": "GET /api/version", "ok": True, "detail": f"版本 {version}"})
            else:
                steps.append(
                    {"step": "GET /api/version", "ok": False, "detail": f"HTTP {resp.status_code}"}
                )
    except Exception as exc:  # noqa: BLE001
        steps.append({"step": "GET /api/version", "ok": False, "detail": str(exc)})

    models: list[str] = []
    try:
        with _httpx_client(min(settings.AI_TIMEOUT, 8)) as client:
            resp = client.get(f"{base}/api/tags")
            resp.raise_for_status()
            data = resp.json() or {}
            models = [str(m.get("name") or "") for m in (data.get("models") or []) if m.get("name")]
            steps.append(
                {"step": "GET /api/tags", "ok": True, "detail": f"发现 {len(models)} 个已拉取模型"}
            )
    except Exception as exc:  # noqa: BLE001
        latency = int((time.perf_counter() - started) * 1000)
        return {
            "ok": False,
            "kind": "local_ollama",
            "checked_url": base,
            "model": model,
            "latency_ms": latency,
            "models": [],
            "version": version,
            "model_available": None,
            "message": f"本地模型服务不可达：{exc}。请确认 Ollama 已启动（ollama serve），"
            f"容器内访问宿主机需使用 host.docker.internal",
            "steps": steps,
        }

    latency = int((time.perf_counter() - started) * 1000)
    available: Optional[bool] = None
    if model:
        available = any(
            n == model or n.split(":")[0] == model.split(":")[0] for n in models
        )
    if not models:
        message = "服务可达，但尚未拉取任何模型，请先执行 ollama pull <模型名>"
        ok = False
    elif model and available is False:
        message = f"服务可达但未找到模型 {model}；可用：{', '.join(models[:8])}"
        ok = False
    else:
        message = "本地模型服务就绪" + (f"（模型 {model} 可用）" if model else "")
        ok = True

    return {
        "ok": ok,
        "kind": "local_ollama",
        "checked_url": base,
        "model": model,
        "latency_ms": latency,
        "models": models[:50],
        "version": version,
        "model_available": available,
        "message": message,
        "steps": steps,
    }


def _cloud_probe(
    base_url: str, model: Optional[str], api_key: Optional[str]
) -> dict[str, Any]:
    """云端 OpenAI 兼容自检：/models 探活，失败回退最小对话请求。"""
    steps: list[dict[str, Any]] = []
    started = time.perf_counter()
    last_error = ""
    resolved: Optional[str] = None
    models: list[str] = []

    if not api_key:
        return {
            "ok": False,
            "kind": "cloud_openai",
            "checked_url": normalize_base_url("cloud_openai", base_url),
            "model": model,
            "latency_ms": 0,
            "models": [],
            "model_available": None,
            "message": "未提供 API Key，无法访问云端端点",
            "steps": steps,
        }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for candidate in _candidate_bases("cloud_openai", base_url):
        try:
            with _httpx_client(min(settings.AI_TIMEOUT, 10)) as client:
                resp = client.get(f"{candidate}/models", headers=headers)
            if resp.status_code == 200:
                data = resp.json() or {}
                models = [
                    str(m.get("id") or "")
                    for m in (data.get("data") or [])
                    if isinstance(m, dict) and m.get("id")
                ]
                resolved = candidate
                steps.append(
                    {
                        "step": f"GET {candidate}/models",
                        "ok": True,
                        "detail": f"返回 {len(models)} 个模型",
                    }
                )
                break
            last_error = f"HTTP {resp.status_code}：{resp.text[:180]}"
            steps.append({"step": f"GET {candidate}/models", "ok": False, "detail": last_error})
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            steps.append({"step": f"GET {candidate}/models", "ok": False, "detail": last_error})

    # /models 不可用时退化为最小对话请求（部分兼容端点未实现 /models）
    if resolved is None and model:
        for candidate in _candidate_bases("cloud_openai", base_url):
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                }
                with _httpx_client(min(settings.AI_TIMEOUT, 20)) as client:
                    resp = client.post(
                        f"{candidate}/chat/completions", json=payload, headers=headers
                    )
                if resp.status_code == 200:
                    resolved = candidate
                    steps.append(
                        {
                            "step": f"POST {candidate}/chat/completions",
                            "ok": True,
                            "detail": "最小对话请求成功",
                        }
                    )
                    break
                last_error = f"HTTP {resp.status_code}：{resp.text[:180]}"
                steps.append(
                    {
                        "step": f"POST {candidate}/chat/completions",
                        "ok": False,
                        "detail": last_error,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                steps.append(
                    {
                        "step": f"POST {candidate}/chat/completions",
                        "ok": False,
                        "detail": last_error,
                    }
                )

    latency = int((time.perf_counter() - started) * 1000)
    available = None
    if models and model:
        available = any(m == model or m.split(":")[0] == model.split(":")[0] for m in models)

    if resolved:
        if model and available is False:
            message = f"端点可达，但模型列表中未找到 {model}（可用：{', '.join(models[:8]) or '未返回'}）"
            ok = False
        else:
            message = f"云端端点连通正常（{resolved}）"
            ok = True
    else:
        ok = False
        message = f"云端端点不可达：{last_error or '未知错误'}。请核对基址与 API Key（常见基址形如 https://api.deepseek.com/v1）"

    return {
        "ok": ok,
        "kind": "cloud_openai",
        "checked_url": resolved or normalize_base_url("cloud_openai", base_url),
        "model": model,
        "latency_ms": latency,
        "models": models[:50],
        "model_available": available,
        "message": message,
        "steps": steps,
    }


def test_endpoint(
    db: Optional[Session] = None,
    tenant_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    kind: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    persist: bool = True,
) -> dict[str, Any]:
    """连通性自检；命中已保存端点时回写最近自检结果。"""
    row: Optional[AIModelEndpoint] = None
    if endpoint_id is not None:
        if db is None or tenant_id is None:
            raise ModelHubError("按 id 自检需要租户上下文")
        row = get_endpoint(db, tenant_id, endpoint_id)

    resolved_kind = _validate_kind(kind or (row.kind if row else "local_ollama"))
    resolved_base = normalize_base_url(
        resolved_kind,
        base_url or (row.base_url if row else "") or default_config(resolved_kind)["base_url"],
    )
    resolved_model = (model or (row.model if row else "") or "").strip() or None
    resolved_key = api_key.strip() if api_key else (resolve_api_key(row) if row else None)

    if resolved_kind == "local_ollama":
        result = _local_probe(resolved_base, resolved_model, resolved_key)
    else:
        result = _cloud_probe(resolved_base, resolved_model, resolved_key)

    result.update(
        {
            "endpoint_id": row.id if row else None,
            "endpoint_name": row.name if row else None,
            "tested_at": _now().isoformat(timespec="seconds"),
            "suggested_base_url": result.get("checked_url"),
        }
    )

    if persist and row is not None and db is not None:
        row.last_test_at = _now()
        row.last_test_ok = bool(result["ok"])
        row.last_test_latency_ms = result.get("latency_ms")
        row.last_test_message = str(result.get("message") or "")[:255]
        # 自检发现基址需要纠偏（如补 /v1）时自动更新，减少手工排错
        if result["ok"] and result.get("checked_url") and result["checked_url"] != row.base_url:
            row.base_url = result["checked_url"]
            result["base_url_updated"] = row.base_url
        db.commit()
    return result


# ---------------------------------------------------------------- 推荐引擎
def _pick_tier(vram_gb: Optional[float], has_gpu: bool, vram_accurate: bool) -> dict[str, Any]:
    if not has_gpu:
        return {**_VRAM_TIERS[0], "uncertain": False, "reason": "未探测到独立 GPU，按 CPU 推理档推荐"}
    if vram_gb is None or not vram_accurate:
        return {
            **_VRAM_TIERS[2],
            "uncertain": True,
            "reason": "显存未能精确探测，按 8GB 档保守推荐（可用宿主机 nvidia-smi 复核）",
        }
    for tier in _VRAM_TIERS[1:]:
        if tier["min_gb"] <= vram_gb < tier["max_gb"]:
            return {**tier, "uncertain": False, "reason": f"实测显存 {vram_gb}GB 落在该档"}
    return {**_VRAM_TIERS[-1], "uncertain": False, "reason": f"实测显存 {vram_gb}GB"}


def _fit_label(need: float, budget: float) -> str:
    if budget <= 0:
        return "不可用"
    ratio = need / budget
    if ratio <= 0.75:
        return "充裕"
    if ratio <= 0.95:
        return "合适"
    return "偏紧"


def recommend(probe_result: dict[str, Any]) -> dict[str, Any]:
    """基于硬件探测结果给出模型量级推荐与接入建议。"""
    gpu_info = probe_result.get("gpu_vram") or {}
    vram_total_mb = gpu_info.get("total_mb")
    vram_gb = round(vram_total_mb / 1024, 1) if vram_total_mb else None
    gpus = probe_result.get("gpus") or []
    has_gpu = bool(gpus)
    vram_accurate = bool(gpu_info.get("accurate"))

    memory = probe_result.get("memory") or {}
    ram_gb = round(memory["total_mb"] / 1024, 1) if memory.get("total_mb") else None
    cpu = probe_result.get("cpu") or {}
    cores = cpu.get("physical_cores") or cpu.get("logical_cores")

    tier = _pick_tier(vram_gb, has_gpu, vram_accurate)
    budget = float(vram_gb) if has_gpu and vram_gb else 0.0

    # CPU 档：显存视为 0，但可用内存可支撑小模型 CPU 推理
    if not has_gpu:
        cpu_budget = ram_gb or 0
        candidates = [
            m for m in _MODEL_CATALOG if m["key"] in ("qwen2.5-0.5b", "qwen2.5-1.5b", "qwen2.5-3b")
        ]
        items = []
        for m in candidates:
            if cpu_budget and m["ram_gb"] > cpu_budget:
                continue
            items.append(
                {
                    "key": m["key"],
                    "display": m["display"],
                    "params": m["params"],
                    "quant": m["quant"],
                    "vram_required_gb": m["vram_gb"],
                    "ram_required_gb": m["ram_gb"],
                    "context": m["ctx"],
                    "fit": _fit_label(m["ram_gb"], cpu_budget) if cpu_budget else "未知",
                    "note": m["fit_note"],
                    "local": {"kind": "local_ollama", "model": m["ollama_tag"]},
                }
            )
        if not items:
            items = [
                {
                    "key": "qwen2.5-0.5b",
                    "display": "Qwen2.5 0.5B（极轻量）",
                    "params": "0.5B",
                    "quant": "Q4_K_M",
                    "vram_required_gb": 1.5,
                    "ram_required_gb": 4,
                    "context": "8K",
                    "fit": "未知",
                    "note": "内存信息不足，按最小模型保守推荐",
                    "local": {"kind": "local_ollama", "model": "qwen2.5:0.5b"},
                }
            ]
        items.sort(key=lambda x: x["vram_required_gb"], reverse=True)
    else:
        fitting = [m for m in _MODEL_CATALOG if m["vram_gb"] <= budget]
        if not fitting:
            fitting = [m for m in _MODEL_CATALOG if m["key"] == "qwen2.5-1.5b"]
        fitting.sort(key=lambda m: m["vram_gb"], reverse=True)
        items = []
        for m in fitting[:3]:
            items.append(
                {
                    "key": m["key"],
                    "display": m["display"],
                    "params": m["params"],
                    "quant": m["quant"],
                    "vram_required_gb": m["vram_gb"],
                    "ram_required_gb": m["ram_gb"],
                    "context": m["ctx"],
                    "fit": _fit_label(m["vram_gb"], budget),
                    "note": m["fit_note"],
                    "local": {"kind": "local_ollama", "model": m["ollama_tag"]},
                }
            )

    primary = items[0] if items else None

    # 云端兜底建议：本地档位不足（CPU 档 / 显存偏紧 / 显存未知）时优先云端
    need_cloud = (not has_gpu) or (not vram_accurate) or (budget and budget < 12)
    cloud = {
        "recommended": bool(need_cloud),
        "reason": (
            "本机算力有限或显存未精确识别，复杂运营分析建议走云端 OpenAI 兼容端点"
            if need_cloud
            else "本机显存充足，可本地为主、云端兜底"
        ),
        "presets": CLOUD_PRESETS,
    }

    rationale_parts = [tier["reason"]]
    if ram_gb:
        rationale_parts.append(f"物理内存 {ram_gb}GB")
    if cores:
        rationale_parts.append(f"物理核 {cores}")
    if gpus:
        gpu_names = "、".join(str(g.get("name")) for g in gpus[:2])
        rationale_parts.append(f"GPU：{gpu_names}")

    degradations = [
        d for d in (probe_result.get("degradations") or []) if d.get("item") in ("gpu", "memory", "host_snapshot")
    ]

    return {
        "generated_at": _now().isoformat(timespec="seconds"),
        "hardware_summary": {
            "has_gpu": has_gpu,
            "gpu_count": len(gpus),
            "vram_total_gb": vram_gb,
            "vram_accurate": vram_accurate,
            "ram_total_gb": ram_gb,
            "cpu_cores": cores,
        },
        "tier": {
            "key": tier["key"],
            "label": tier["label"],
            "uncertain": tier.get("uncertain", False),
        },
        "tier_range_gb": {"min": tier["min_gb"], "max": tier["max_gb"]},
        "rationale": "；".join(rationale_parts),
        "primary": primary,
        "items": items,
        "cloud": cloud,
        "degradations": degradations,
        "local_defaults": default_config("local_ollama"),
    }


def hardware_and_recommend(refresh: bool = True) -> dict[str, Any]:
    """硬件探测 + 推荐（推荐结果同时带回原始探测摘要）。"""
    probe_result = hardware_service.probe()
    return {
        "probe": probe_result,
        "recommendation": recommend(probe_result),
    }


# ---------------------------------------------------------------- 端点 CRUD
def create_endpoint(db: Session, tenant_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    kind = _validate_kind(payload.get("kind"))
    name = (payload.get("name") or "").strip()
    if not name:
        raise ModelHubError("端点名称不能为空")
    exists = db.execute(
        select(AIModelEndpoint).where(
            AIModelEndpoint.tenant_id == tenant_id, AIModelEndpoint.name == name
        )
    ).scalars().first()
    if exists:
        raise ModelHubError(f"端点名称已存在：{name}")

    api_key = (payload.get("api_key") or "").strip()
    row = AIModelEndpoint(
        tenant_id=tenant_id,
        name=name,
        kind=kind,
        provider=(payload.get("provider") or PROVIDER_BY_KIND.get(kind)) or None,
        base_url=normalize_base_url(kind, payload.get("base_url") or default_config(kind)["base_url"]),
        model=(payload.get("model") or default_config(kind)["model"]).strip(),
        param_scale=payload.get("param_scale"),
        api_key_enc=encrypt(api_key) if api_key else None,
        api_key_hint=_mask(api_key),
        enabled=bool(payload.get("enabled", True)),
        is_active=bool(payload.get("is_active", False)),
        source=payload.get("source") or "manual",
        remark=payload.get("remark"),
    )
    if not row.base_url or not row.model:
        raise ModelHubError("接口基址与模型名不能为空")
    db.add(row)
    db.flush()
    if row.is_active:
        _clear_active(db, tenant_id, keep_id=row.id)
    db.commit()
    db.refresh(row)
    if row.is_active:
        sync_runtime(row)
    return serialize(row, active_id=(row.id if row.is_active else None))


def update_endpoint(
    db: Session, tenant_id: int, endpoint_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    row = get_endpoint(db, tenant_id, endpoint_id)
    fields = payload

    if "name" in fields and fields["name"]:
        new_name = fields["name"].strip()
        if new_name != row.name:
            dup = db.execute(
                select(AIModelEndpoint).where(
                    AIModelEndpoint.tenant_id == tenant_id, AIModelEndpoint.name == new_name
                )
            ).scalars().first()
            if dup:
                raise ModelHubError(f"端点名称已存在：{new_name}")
            row.name = new_name
    if "kind" in fields and fields["kind"]:
        row.kind = _validate_kind(fields["kind"])
    if "base_url" in fields and fields["base_url"]:
        row.base_url = normalize_base_url(row.kind, fields["base_url"])
    if "model" in fields and fields["model"]:
        row.model = fields["model"].strip()
    if "provider" in fields:
        row.provider = fields["provider"]
    if "param_scale" in fields:
        row.param_scale = fields["param_scale"]
    if "remark" in fields:
        row.remark = fields["remark"]
    if "enabled" in fields and fields["enabled"] is not None:
        row.enabled = bool(fields["enabled"])
    if "api_key" in fields and fields["api_key"] is not None:
        key = fields["api_key"].strip()
        row.api_key_enc = encrypt(key) if key else None
        row.api_key_hint = _mask(key)
    if "is_active" in fields and fields["is_active"] is not None:
        row.is_active = bool(fields["is_active"])
    if not row.base_url or not row.model:
        raise ModelHubError("接口基址与模型名不能为空")

    db.flush()
    if row.is_active:
        _clear_active(db, tenant_id, keep_id=row.id)
    db.commit()
    db.refresh(row)
    if row.is_active:
        sync_runtime(row)
    return serialize(row, active_id=(row.id if row.is_active else None))


def delete_endpoint(db: Session, tenant_id: int, endpoint_id: int) -> dict[str, Any]:
    row = get_endpoint(db, tenant_id, endpoint_id)
    was_active = bool(row.is_active)
    snapshot = serialize(row)
    db.delete(row)
    db.commit()
    if was_active:
        fallback = list_endpoints(db, tenant_id)
        if fallback:
            fallback[0].is_active = True
            db.commit()
            sync_runtime(fallback[0])
    return {"deleted": snapshot, "active_endpoint_id": (active_endpoint(db, tenant_id).id if active_endpoint(db, tenant_id) else None)}


def activate_endpoint(db: Session, tenant_id: int, endpoint_id: int) -> dict[str, Any]:
    row = get_endpoint(db, tenant_id, endpoint_id)
    if not row.enabled:
        raise ModelHubError("该端点已停用，启用后才能设为当前生效端点")
    row.is_active = True
    _clear_active(db, tenant_id, keep_id=row.id)
    db.commit()
    db.refresh(row)
    runtime = sync_runtime(row)
    return {"endpoint": serialize(row, active_id=row.id), "runtime": runtime}


# ---------------------------------------------------------------- 一键接入
def apply_endpoint(db: Session, tenant_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """一键接入：按档位落库端点（同名则更新），可选立刻自检与激活。"""
    mode = (payload.get("mode") or "local").strip().lower()
    kind = "local_ollama" if mode in ("local", "local_ollama") else "cloud_openai"
    defaults = default_config(kind)

    base_url = normalize_base_url(kind, payload.get("base_url") or defaults["base_url"])
    model = (payload.get("model") or defaults["model"]).strip()
    api_key = (payload.get("api_key") or "").strip()
    name = (payload.get("name") or "").strip() or (
        f"本地 Ollama · {model}" if kind == "local_ollama" else f"云端端点 · {model}"
    )
    if not base_url or not model:
        raise ModelHubError("接口基址与模型名不能为空")
    if kind == "cloud_openai" and not api_key:
        existing = db.execute(
            select(AIModelEndpoint).where(
                AIModelEndpoint.tenant_id == tenant_id, AIModelEndpoint.name == name
            )
        ).scalars().first()
        if existing is None or not existing.api_key_enc:
            raise ModelHubError("云端模式需提供 API Key（仅存密文，不回显明文）")

    existing = db.execute(
        select(AIModelEndpoint).where(
            AIModelEndpoint.tenant_id == tenant_id, AIModelEndpoint.name == name
        )
    ).scalars().first()

    if existing is None:
        row = AIModelEndpoint(
            tenant_id=tenant_id,
            name=name,
            kind=kind,
            provider=defaults["provider"],
            base_url=base_url,
            model=model,
            param_scale=payload.get("param_scale"),
            api_key_enc=encrypt(api_key) if api_key else None,
            api_key_hint=_mask(api_key),
            enabled=True,
            is_active=bool(payload.get("activate", True)),
            source="recommend",
            remark="由模型中心「一键接入」生成",
        )
        db.add(row)
    else:
        row = existing
        row.kind = kind
        row.base_url = base_url
        row.model = model
        row.param_scale = payload.get("param_scale") or row.param_scale
        if api_key:
            row.api_key_enc = encrypt(api_key)
            row.api_key_hint = _mask(api_key)
        if payload.get("activate", True):
            row.is_active = True
        row.source = "recommend"
        db.flush()

    db.flush()
    if row.is_active:
        _clear_active(db, tenant_id, keep_id=row.id)
    db.commit()
    db.refresh(row)

    test_result: Optional[dict[str, Any]] = None
    if payload.get("verify", True):
        test_result = test_endpoint(db=db, tenant_id=tenant_id, endpoint_id=row.id)
    if row.is_active:
        sync_runtime(row)

    return {
        "endpoint": serialize(row, active_id=(row.id if row.is_active else None)),
        "test": test_result,
        "runtime": runtime_snapshot(),
    }


# ---------------------------------------------------------------- 运行配置同步
def runtime_snapshot() -> dict[str, Any]:
    """当前进程内的 AI 运行配置（实际被 LLMClient 读取的即这份）。"""
    return {
        "ai_enabled": settings.AI_ENABLED,
        "ai_mode": settings.ai_mode,
        "base_url": settings.ai_base_url,
        "model": settings.ai_model,
        "api_key_configured": bool(settings.AI_API_KEY),
        "api_key_hint": _mask(settings.AI_API_KEY),
        "ai_ready": settings.ai_ready,
    }


def update_env_file(updates: dict[str, str]) -> dict[str, Any]:
    """更新 .env 中指定的键（保留其它行与注释）；失败时返回原因而不抛异常。"""
    env_path = BASE_DIR / ".env"
    result: dict[str, Any] = {"path": str(env_path), "updated": [], "ok": False}
    if not env_path.exists():
        result["message"] = f"未找到 .env：{env_path}，仅已更新进程内运行配置（重启后失效）"
        return result
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        result["message"] = f"读取 .env 失败：{exc}"
        return result

    remaining = dict(updates)
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                new_lines.append(f"{key}={remaining.pop(key)}")
                result["updated"].append(key)
                continue
        new_lines.append(line)
    for key, value in remaining.items():
        new_lines.append(f"{key}={value}")
        result["updated"].append(key)

    try:
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        result["ok"] = True
        result["message"] = f"已更新 .env 中 {len(result['updated'])} 项配置"
    except OSError as exc:
        result["message"] = f"写入 .env 失败：{exc}"
    return result


def sync_runtime(row: AIModelEndpoint, apply_to_env: bool = False) -> dict[str, Any]:
    """把生效端点写入进程内运行配置（立即对后续模型调用生效），可选持久化到 .env。"""
    key = resolve_api_key(row)
    updates_for_env: dict[str, str] = {}
    if row.kind == "local_ollama":
        settings.AI_MODE = "local"
        settings.AI_LOCAL_BASE_URL = row.base_url
        settings.AI_LOCAL_MODEL = row.model
        updates_for_env = {
            "AI_MODE": "local",
            "AI_LOCAL_BASE_URL": row.base_url,
            "AI_LOCAL_MODEL": row.model,
        }
    else:
        settings.AI_MODE = "api"
        settings.AI_API_BASE_URL = row.base_url
        settings.AI_API_MODEL = row.model
        if key:
            settings.AI_API_KEY = key
        updates_for_env = {
            "AI_MODE": "api",
            "AI_API_BASE_URL": row.base_url,
            "AI_API_MODEL": row.model,
        }
        if key:
            updates_for_env["AI_API_KEY"] = key
    settings.AI_ENABLED = True

    payload: dict[str, Any] = {
        "applied": True,
        "endpoint_id": row.id,
        "endpoint_name": row.name,
        "kind": row.kind,
        "runtime": runtime_snapshot(),
        "note": "已写入进程内运行配置，后续模型调用立即生效；容器重启后以 .env 为准",
    }
    if apply_to_env:
        payload["env"] = update_env_file(updates_for_env)
    return payload


def sync_endpoint_to_env(
    db: Session, tenant_id: int, endpoint_id: Optional[int], apply_to_env: bool = True
) -> dict[str, Any]:
    row = get_endpoint(db, tenant_id, endpoint_id) if endpoint_id else active_endpoint(db, tenant_id)
    if row is None:
        raise ModelHubError("尚未配置生效端点，无法同步运行配置")
    return sync_runtime(row, apply_to_env=apply_to_env)


# ---------------------------------------------------------------- 概览
def overview(db: Session, tenant_id: int) -> dict[str, Any]:
    """模型中心概览：生效端点、端点统计、可选本机模型。"""
    rows = list_endpoints(db, tenant_id)
    active = active_endpoint(db, tenant_id)
    active_id = active.id if active else None
    return {
        "active_endpoint": serialize(active, active_id=active_id) if active else None,
        "active_endpoint_id": active_id,
        "runtime": runtime_snapshot(),
        "stats": {
            "total": len(rows),
            "enabled": sum(1 for r in rows if r.enabled),
            "local": sum(1 for r in rows if r.kind == "local_ollama"),
            "cloud": sum(1 for r in rows if r.kind == "cloud_openai"),
            "tested": sum(1 for r in rows if r.last_test_at is not None),
            "test_ok": sum(1 for r in rows if r.last_test_ok),
        },
        "endpoints": [serialize(r, active_id=active_id) for r in rows],
        "kinds": [
            {"key": "local_ollama", "label": KIND_LABELS["local_ollama"]},
            {"key": "cloud_openai", "label": KIND_LABELS["cloud_openai"]},
        ],
        "cloud_presets": CLOUD_PRESETS,
        "local_defaults": default_config("local_ollama"),
        "env_path": str(BASE_DIR / ".env"),
    }
