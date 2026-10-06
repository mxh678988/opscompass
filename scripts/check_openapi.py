"""接口契约基线校验（离线，与 scripts/ci.ps1 第 4 项等价）。

不依赖运行中的服务与 Docker：直接在进程内构建 FastAPI 应用的 OpenAPI 文档，
与仓库快照 ``docs/openapi.json`` 逐条比对路径集合与版本号，把"改了接口但没更新
快照"的漂移拦在提交之前。

比对规则：
  - 路径集合与快照完全一致（实例新增 / 快照多余均视为失败）；
  - info.version 与快照一致。

退出码：0 一致；1 不一致（差异明细打印到标准输出）；2 环境依赖缺失。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
SNAPSHOT = BASE_DIR / "docs" / "openapi.json"

sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.main import app
except ModuleNotFoundError as exc:  # pragma: no cover - 依赖未安装时的明确提示
    print(f"[FAIL] 后端依赖缺失，无法构建 OpenAPI：{exc}")
    print("       请先执行：pip install -r backend/requirements.txt")
    sys.exit(2)


def main() -> int:
    if not SNAPSHOT.is_file():
        print(f"[FAIL] 未找到快照 {SNAPSHOT.relative_to(BASE_DIR)}")
        return 1

    live = app.openapi()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    live_paths = set(live.get("paths", {}))
    snap_paths = set(snapshot.get("paths", {}))

    added = sorted(live_paths - snap_paths)
    removed = sorted(snap_paths - live_paths)

    live_ver = str(live.get("info", {}).get("version", ""))
    snap_ver = str(snapshot.get("info", {}).get("version", ""))

    print("接口契约基线校验")
    print(f"  实例路径 {len(live_paths)} 条 / 快照路径 {len(snap_paths)} 条")
    print(f"  实例版本 {live_ver} / 快照版本 {snap_ver}")

    if added or removed:
        if added:
            print(f"[FAIL] 实例新增（快照未更新）{len(added)} 条：")
            for path in added:
                print(f"        + {path}")
        if removed:
            print(f"[FAIL] 快照多余（实例已移除）{len(removed)} 条：")
            for path in removed:
                print(f"        - {path}")
        print("       如为预期变更，请重新导出 docs/openapi.json 后一并提交。")
        return 1

    if live_ver != snap_ver:
        print(f"[FAIL] 版本不一致：实例 {live_ver} / 快照 {snap_ver}")
        return 1

    print(f"[PASS] 路径 {len(live_paths)} 条与 docs/openapi.json 完全一致（v{live_ver}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
