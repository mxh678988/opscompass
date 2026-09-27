"""健康检查接口测试。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/api/v1/system/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
