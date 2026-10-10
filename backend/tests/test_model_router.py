"""OS 内核 · 模型路由引擎（M6）测试。

覆盖：
- 能力声明 CRUD：upsert / get / 默认值 / 停用
- 路由决策：本地优先、敏感强制本地、云端降级、规则兜底、模型覆盖
- 全局降级开关：一键 rule
- 缓存：命中 / 过期 / skip_cache
- 计量：route_log_stats 汇总与过滤

无外部依赖（模型调用被 monkeypatch 打桩），直接执行：``pytest tests/test_model_router.py -v``。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.model_router.routing import (
    ModelRouterError,
    _call_model,
    get_capability,
    is_degraded,
    route_log_stats,
    route_model,
    set_global_degrade,
    upsert_capability,
)
from app.models.base import Base
from app.models.model_router import (
    CoreModelCache,
    CoreModelCapability,
    CoreModelRouteLog,
)

MODEL_ROUTER_TABLES = [
    CoreModelCapability.__table__,
    CoreModelRouteLog.__table__,
    CoreModelCache.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建模型路由所需表）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=MODEL_ROUTER_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _degrade_off():
    """每个用例结束恢复全局降级开关为关闭。"""
    yield
    set_global_degrade(False)


# ---- 模型调用打桩：local / api 成败可控 ----

class _StubResult:
    def __init__(self, mode, model, text="ok", duration_ms=5, prompt_tokens=1, completion_tokens=2):
        self.mode = mode
        self.model = model
        self.text = text
        self.duration_ms = duration_ms
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


def _stub_call_model(monkeypatch, *, local_ok=True, api_ok=True):
    calls = {"local": 0, "api": 0}

    def fake(capability, input, *, mode, model=None, temperature=None, max_tokens=None):
        calls[mode] += 1
        if mode == "local" and not local_ok:
            return {}, f"local unavailable: {mode}"
        if mode == "api" and not api_ok:
            return {}, f"api unavailable: {mode}"
        chosen = model or ("local-llama" if mode == "local" else "api-gpt")
        return ({"text": f"ok[{mode}]", "mode": mode, "model": chosen,
                 "latency_ms": 5, "prompt_tokens": 1, "completion_tokens": 2,
                 "total_tokens": 3}, None)

    monkeypatch.setattr("app.core.model_router.routing._call_model", fake)
    return calls


# ---- 能力声明 CRUD ----

class TestCapability:
    def test_upsert_get(self, db):
        upsert_capability(db, capability="test.cap", kind="llm",
                          description="测试", sensitive=True,
                          fallback_cloud=True, cost_cap=100,
                          cache_ttl_seconds=600)
        cap = get_capability(db, "test.cap")
        assert cap["capability"] == "test.cap"
        assert cap["kind"] == "llm"
        assert cap["sensitive"] is True
        assert cap["fallback_cloud"] is True
        assert cap["cost_cap"] == 100
        assert cap["cache_ttl_seconds"] == 600

    def test_upsert_update_existing(self, db):
        upsert_capability(db, capability="cap1", kind="llm", cache_ttl_seconds=100)
        upsert_capability(db, capability="cap1", kind="llm", cache_ttl_seconds=200)
        cap = get_capability(db, "cap1")
        assert cap["cache_ttl_seconds"] == 200

    def test_capability_not_found_defaults(self, db):
        cap = get_capability(db, "nonexistent")
        assert cap["capability"] == "nonexistent"
        assert cap["sensitive"] is False
        assert cap["fallback_cloud"] is False
        assert cap["cache_ttl_seconds"] == 0
        assert cap["enabled"] is True

    def test_defaults_zero_false(self, db):
        upsert_capability(db, capability="cap")
        cap = get_capability(db, "cap")
        assert cap["sensitive"] is False
        assert cap["fallback_cloud"] is False
        assert cap["cost_cap"] == 0
        assert cap["enabled"] is True

    def test_invalid_kind_rejected(self, db):
        with pytest.raises(ModelRouterError):
            upsert_capability(db, capability="bad", kind="unknown")

    def test_disabled_capability_blocks_route(self, db):
        upsert_capability(db, capability="off", enabled=False)
        with pytest.raises(ModelRouterError):
            route_model(db, "off", {"text": "x"}, tenant_id=1)


# ---- 路由决策 ----

class TestRouteModel:
    def test_local_preferred(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch)
        upsert_capability(db, capability="p", fallback_cloud=True)
        result = route_model(db, "p", {"text": "hi"}, tenant_id=1)
        assert result.mode == "local"
        assert result.model == "local-llama"
        assert result.cached is False
        assert result.fallback is False
        assert calls["api"] == 0

    def test_cloud_fallback_when_local_down(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch, local_ok=False)
        upsert_capability(db, capability="p", fallback_cloud=True)
        result = route_model(db, "p", {"text": "hi"}, tenant_id=1)
        assert result.mode == "api"
        assert result.model == "api-gpt"
        assert calls["local"] == 1
        assert calls["api"] == 1

    def test_rule_fallback_when_all_down(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch, local_ok=False, api_ok=False)
        upsert_capability(db, capability="p", fallback_cloud=True)
        result = route_model(db, "p", {"text": "hi"}, tenant_id=1)
        assert result.mode == "rule"
        assert result.fallback is True
        assert calls["local"] == 1
        assert calls["api"] == 1

    def test_no_cloud_when_fallback_disabled(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch, local_ok=False, api_ok=False)
        upsert_capability(db, capability="p", fallback_cloud=False)
        result = route_model(db, "p", {"text": "hi"}, tenant_id=1)
        assert result.mode == "rule"
        assert calls["api"] == 0

    def test_sensitive_forced_local(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch, local_ok=True)
        upsert_capability(db, capability="s", sensitive=True, fallback_cloud=True)
        result = route_model(db, "s", {"text": "secret"}, tenant_id=1)
        assert result.mode == "local"
        assert calls["api"] == 0

    def test_sensitive_blocks_cloud_even_when_local_down(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch, local_ok=False, api_ok=False)
        upsert_capability(db, capability="s", sensitive=True, fallback_cloud=True)
        result = route_model(db, "s", {"text": "secret"}, tenant_id=1)
        assert result.mode == "rule"
        assert calls["api"] == 0

    def test_force_local_param(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch, local_ok=False, api_ok=False)
        upsert_capability(db, capability="p", fallback_cloud=True)
        result = route_model(db, "p", {"text": "x"}, tenant_id=1, force_local=True)
        assert result.mode == "rule"
        assert calls["api"] == 0

    def test_global_degrade_skips_models(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch)
        set_global_degrade(True)
        upsert_capability(db, capability="p")
        result = route_model(db, "p", {"text": "x"}, tenant_id=1)
        assert result.mode == "rule"
        assert calls["local"] == 0
        assert calls["api"] == 0
        assert is_degraded() is True

    def test_model_override_passed_to_call(self, db, monkeypatch):
        seen = {}

        def fake(capability, input, *, mode, model=None, temperature=None, max_tokens=None):
            seen["model"] = model
            return ({"text": "ok", "mode": mode, "model": model,
                     "latency_ms": 5, "prompt_tokens": 1, "completion_tokens": 2,
                     "total_tokens": 3}, None)

        monkeypatch.setattr("app.core.model_router.routing._call_model", fake)
        upsert_capability(db, capability="p")
        result = route_model(db, "p", {"text": "x"}, tenant_id=1, model="override-7b")
        assert seen["model"] == "override-7b"
        assert result.model == "override-7b"


# ---- 缓存 ----

class TestCache:
    def test_cache_hit_after_first_route(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch)
        upsert_capability(db, capability="c", cache_ttl_seconds=300)
        r1 = route_model(db, "c", {"text": "same"}, tenant_id=1)
        r2 = route_model(db, "c", {"text": "same"}, tenant_id=1)
        assert r1.cached is False
        assert r2.cached is True
        assert r2.mode == r1.mode
        assert calls["local"] == 1

    def test_cache_skip_cache_param(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch)
        upsert_capability(db, capability="c", cache_ttl_seconds=300)
        route_model(db, "c", {"text": "same"}, tenant_id=1)
        route_model(db, "c", {"text": "same"}, tenant_id=1, skip_cache=True)
        assert calls["local"] == 2

    def test_cache_expired_re_routes(self, db, monkeypatch):
        calls = _stub_call_model(monkeypatch)
        upsert_capability(db, capability="c", cache_ttl_seconds=300)
        r1 = route_model(db, "c", {"text": "same"}, tenant_id=1)
        # 直接把过期时间拨回过去
        from app.models.model_router import CoreModelCache
        from sqlalchemy import select

        row = db.execute(select(CoreModelCache)).scalar_one()
        row.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        db.commit()
        r2 = route_model(db, "c", {"text": "same"}, tenant_id=1)
        assert r2.cached is False
        assert calls["local"] == 2

    def test_no_cache_when_ttl_zero(self, db, monkeypatch):
        upsert_capability(db, capability="c", cache_ttl_seconds=0)
        route_model(db, "c", {"text": "same"}, tenant_id=1)
        from sqlalchemy import select

        rows = db.execute(select(CoreModelCache)).scalars().all()
        assert len(rows) == 0


# ---- 计量 ----

class TestStats:
    def test_basic_stats(self, db, monkeypatch):
        _stub_call_model(monkeypatch)
        upsert_capability(db, capability="s", fallback_cloud=True)
        for i in range(3):
            route_model(db, "s", {"text": f"t{i}"}, tenant_id=1)
        stats = route_log_stats(db, capability="s")
        assert stats["total"] == 3
        assert stats["success"] == 3
        assert stats["by_mode"].get("local") == 3

    def test_stats_empty(self, db):
        stats = route_log_stats(db, capability="nonexistent")
        assert stats["total"] == 0

    def test_stats_tenant_filter(self, db, monkeypatch):
        _stub_call_model(monkeypatch)
        upsert_capability(db, capability="s")
        route_model(db, "s", {"text": "1"}, tenant_id=1)
        route_model(db, "s", {"text": "2"}, tenant_id=2)
        assert route_log_stats(db, tenant_id=1)["total"] == 1
        assert route_log_stats(db, tenant_id=2)["total"] == 1

    def test_stats_count_fallback(self, db, monkeypatch):
        _stub_call_model(monkeypatch, local_ok=False, api_ok=False)
        upsert_capability(db, capability="s", fallback_cloud=True)
        route_model(db, "s", {"text": "x"}, tenant_id=1)
        stats = route_log_stats(db, capability="s")
        assert stats["fallback_count"] == 1
        assert stats["by_mode"].get("rule") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
