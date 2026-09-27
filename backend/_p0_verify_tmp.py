"""P0 RBAC 安全体系临时验证脚本（验证后删除，不属于交付物）。"""

import json
import urllib.error
import urllib.request

from app.core.config import settings

BASE = "http://127.0.0.1:8000"
out = []


def req(method, path, data=None, token=None):
    r = urllib.request.Request(BASE + path, method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
        r.data = json.dumps(data).encode()
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:  # noqa: BLE001
        return -1, repr(e)


s, b = req("GET", "/health")
out.append("health -> %s %s" % (s, b[:100]))

s, b = req("GET", "/api/v1/tenants")
out.append("tenants_no_token -> %s %s" % (s, b[:160]))

s, b = req("GET", "/api/v1/audit/logs")
out.append("audit_no_token -> %s %s" % (s, b[:160]))

s, b = req(
    "POST",
    "/api/v1/auth/login",
    {"username": settings.SECURITY_ADMIN_USERNAME, "password": settings.SECURITY_ADMIN_PASSWORD},
)
out.append("login_admin -> %s %s" % (s, b[:260]))

token = None
if s == 200:
    token = json.loads(b)["data"]["access_token"]

if token:
    s, b = req("GET", "/api/v1/tenants", token=token)
    out.append("tenants_with_token -> %s %s" % (s, b[:200]))
    s, b = req("GET", "/api/v1/auth/me", token=token)
    perms = len(json.loads(b)["data"]["permissions"]) if s == 200 else -1
    out.append("me -> %s permission_count=%s" % (s, perms))
    s, b = req("GET", "/api/v1/system/info", token=token)
    out.append("system_info -> %s %s" % (s, b[:160]))
    s, b = req("GET", "/api/v1/system/security-overview", token=token)
    out.append("security_overview -> %s %s" % (s, b[:500]))
    s, b = req("GET", "/api/v1/audit/logs?page_size=5", token=token)
    out.append("audit_logs -> %s %s" % (s, b[:300]))
    s, b = req("GET", "/api/v1/audit/stats", token=token)
    out.append("audit_stats -> %s %s" % (s, b[:300]))
    s, b = req("GET", "/api/v1/rbac/permissions", token=token)
    out.append("rbac_permissions -> %s %s" % (s, b[:160]))

s, b = req("GET", "/api/v1/rbac/roles")
out.append("roles_no_token -> %s %s" % (s, b[:160]))

print("\n".join(out))
