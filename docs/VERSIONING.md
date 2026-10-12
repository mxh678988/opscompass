# 文档版本控制（A3）

> 适用产品：运营智脑（让数据自动做出最优决策）

## 1. 原则

- **文档与代码同源同提交**：一个功能合入，其 changelog / 设计 / 参考文档在同一提交内更新，禁止事后补账；
- **快照型文档随版本冻结**：`docs/openapi.json`、`docs/api-reference.md`、`docs/test-report.md` 属于发布快照，只允许随接口/版本变更一起提交，禁止手改；
- **人工文档分层**：`docs/api.md`（高层接口说明）为人工维护，与自动生成的 `api-reference.md` 并存，两者互补不冲突。

## 2. 多版本共存

同一文档存在历史版本需要追溯时，按以下约定：

```
docs/
├── RELEASES/                 # 历史版本快照（仅重大版本归档）
│   └── v0.10.1/
│       ├── api.md
│       └── test-report.md
├── deploy/RELEASE_NOTES_v0.10.1.md   # 发布说明按版本号命名
└── changelog.md              # 唯一变更流水账（[Unreleased] + 已发布版本）
```

- 日常迭代只更新 `docs/` 根下的现行文档与 `changelog.md`；
- 发布时把现行快照复制进 `docs/RELEASES/<version>/` 留档（可选，按项目需要）；
- 旧版文档仅供追溯，不在现行路径维护。

## 3. changelog 约定

- 开发中条目统一放 `[Unreleased]`；
- 发布时把 `[Unreleased]` 改写为版本号 + 日期，并新开空的 `[Unreleased]`；
- 条目按 `实现(vX.Y.Z 内核)` / `文档` / `修复` 分组，标注里程碑代号（S/D/A/M）。

## 4. 自动生成文档清单

| 文档 | 生成方式 | 校验方式 |
|---|---|---|
| `docs/openapi.json` | `python scripts/check_openapi.py` 失败时重新导出 | `check_openapi.py`（契约一致） |
| `docs/api-reference.md` | `python scripts/gen_api_docs.py` | `gen_api_docs.py --check` |

> 接口变更流程：改代码 → 重新导出 `docs/openapi.json` → 重新生成 `docs/api-reference.md` → 一并提交。

## 5. 文档 CI（A2）

- `python scripts/check_docs.py`：链接 / 引用完整性，全 PASS 才允许提交；
- `scripts/ci.ps1` 全量检查入口已并入 A1/A2 检查项。
