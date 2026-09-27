"""P10 吊销接口探针（临时）。"""

import json
import urllib.error
import urllib.request
from urllib.parse import quote

from app.core.config import settings

BASE = "http://127.0.0.1:8000/api/v1"


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        return "ERR", repr(exc)


status, body = call(
    "POST",
    "/auth/login",
    {"username": settings.SECURITY_ADMIN_USERNAME, "password": settings.SECURITY_ADMIN_PASSWORD},
)
token = (json.loads(body).get("data") or {}).get("access_token") or (json.loads(body).get("data") or {}).get("token")
print("login:", status)

status, body = call("GET", "/commercial/licenses?page_size=5", token=token)
print("licenses:", status, body[:400])
items = ((json.loads(body).get("data") or {}).get("items")) or []
target = next((i for i in items if i.get("status") == "active"), items[0] if items else None)
print("target:", target and target.get("id"), target and target.get("status"))

if target:
    lid = target["id"]
    for label, url in (
        ("ascii-reason", f"/commercial/licenses/{lid}/revoke?reason=probe"),
        ("cn-reason", f"/commercial/licenses/{lid}/revoke?reason={quote('验证吊销')}"),
    ):
        status, body = call("POST", url, token=token)
        print(label, "->", status, body[:300])
