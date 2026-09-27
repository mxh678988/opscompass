"""P9 临时自检脚本（运行后删除）：导入校验 + 路由清单 + 硬件探测/推荐 smoke。"""
import json
import traceback

report = {"steps": []}


def step(name, fn):
    try:
        report["steps"].append({"name": name, "ok": True, "detail": fn()})
    except Exception as exc:  # noqa: BLE001
        report["steps"].append(
            {"name": name, "ok": False, "error": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()}
        )


step("import_router", lambda: len(__import__("app.api.v1.router", fromlist=["api_router"]).api_router.routes))


def _model_paths():
    from app.api.v1.router import api_router

    return sorted({r.path for r in api_router.routes if "/model" in getattr(r, "path", "")})


step("model_routes", _model_paths)

step("import_models", lambda: __import__("app.models", fromlist=["x"]).AIModelEndpoint.__tablename__)


def _probe():
    from app.services import hardware_service

    data = hardware_service.probe()
    return {
        "probed_at": data.get("probed_at"),
        "env_platform": (data.get("environment") or {}).get("platform"),
        "cpu_model": (data.get("cpu") or {}).get("model"),
        "cpu_physical_cores": (data.get("cpu") or {}).get("physical_cores"),
        "mem_total_mb": (data.get("memory") or {}).get("total_mb"),
        "disks": len(data.get("disks") or []),
        "gpus": len(data.get("gpus") or []),
        "gpu_vram_total_mb": (data.get("gpu_vram") or {}).get("total_mb"),
        "net_egress_ip": (data.get("network") or {}).get("egress_ip"),
        "degradation_items": [d.get("item") for d in (data.get("degradations") or [])],
    }


step("probe", _probe)


def _recommend():
    from app.services import hardware_service, model_hub_service

    probe_result = hardware_service.probe()
    rec = model_hub_service.recommend(probe_result)
    return {
        "keys": sorted(rec.keys()),
        "tier_label": (rec.get("tier") or {}).get("label"),
        "tier_key": (rec.get("tier") or {}).get("key"),
        "top_models": [m.get("name") for m in (rec.get("local_models") or [])[:4]],
        "backends": [b.get("kind") for b in (rec.get("backends") or [])],
    }


step("recommend", _recommend)

print(json.dumps(report, ensure_ascii=False, indent=2)[:6000])
