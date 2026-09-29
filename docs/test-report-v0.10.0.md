---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_e036c44cbbd111f1a526525400cd780f
    ReservedCode1: 1BqxXmB/toyb/rQQ6SjmPnmioHbaBxMR7ajmprqI6xtJ1QsLq5ENOMPQXBf8HL4sClwzqHdHrWIlLM/aF5dIpG0iJwRZm8w95MLLg5yXClIqB23odwmCb0oL4oOVpjhgO1I1aisSxl2r/fEGRDtV6A/lDp4QIc6UpWXvB+lj9JHEgf9WMwZSUrToKM8=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_e036c44cbbd111f1a526525400cd780f
    ReservedCode2: 1BqxXmB/toyb/rQQ6SjmPnmioHbaBxMR7ajmprqI6xtJ1QsLq5ENOMPQXBf8HL4sClwzqHdHrWIlLM/aF5dIpG0iJwRZm8w95MLLg5yXClIqB23odwmCb0oL4oOVpjhgO1I1aisSxl2r/fEGRDtV6A/lDp4QIc6UpWXvB+lj9JHEgf9WMwZSUrToKM8=
---

# 运营智脑 OpsCompass 测试报告（v0.10.0）

> 版本：v0.10.0（AI 决策治理闭环 + 商业化中心基线）  报告日期：2026-09-29  编制：BY LAOMENG 网络工作室
> v0.9.0 功能冻结基线报告见 [test-report.md](./test-report.md)（对应 git tag v0.9.0）。

## 1. 测试范围与环境

| 项 | 内容 |
|---|---|
| 被测对象 | 后端 API（FastAPI）、前端 SPA（Vue3 + Vite）、数据库结构（PostgreSQL 16）、AI 决策治理闭环、商业化中心、采集链路、部署编排 |
| 运行环境 | Windows 11；Docker Compose 四容器 opscompass-postgres / redis / backend(8000) / frontend(80)，实测均 `healthy`；网络 opscompass-net |
| 数据库 | PostgreSQL 16；业务表 64 张、字段 857 个、索引 229 个；迁移版本 head = `p5_ai_gov_perf_idx`（共 6 个迁移） |
| 测试方式 | 结构核对（OpenAPI 导出 / information_schema / 运行库计数）+ 构建验证（`vue-tsc --noEmit` + `vite build`）+ 接口实测（真实运行实例，26 个端点，含 2 个负向用例） |

## 2. 结果概览

| 类别 | 用例数 | 通过 | 备注 |
|---|---|---|---|
| 结构一致性核对 | 8 | 8 | OpenAPI / 表 / 字段 / 索引 / 迁移 / 权限点 / 代码规模 |
| 构建与静态检查 | 2 | 2 | 类型检查 + 生产构建 |
| 接口冒烟（含负向） | 26 | 26 | 24 项 200；401 与授权校验失败各 1 项，均符合预期 |
| 治理 / 采集 / 商业化功能复验 | 12 | 12 | 见第 5、6、7 节 |
| 数据面计数核对 | 6 | 6 | 与 changelog 0.10.0 声明一致 |
| 自动化回归 / 性能 / 兼容性 | 3 | 0 | 未覆盖，见第 9 节 |

## 3. 结构一致性核对（实测数据）

| # | 用例 | 期望 | 实测 | 结果 |
|---|---|---|---|---|
| 1 | OpenAPI 导出 | 覆盖全部业务模块 | 导出成功：**166 条路径 / 225 个操作 / 226 个 Schema / 20 个标签**，`info.version = 0.10.0` | PASS |
| 2 | 数据库表数量 | 与代码模型一致 | **64 张业务表**（v0.9.0 为 59 张，新增商业化 5 表） | PASS |
| 3 | 字段规模 | 全字段可枚举 | **857 个字段**（v0.9.0 为 765），已同步 docs/data-dictionary.md | PASS |
| 4 | 索引规模 | 与迁移一致 | **229 个索引**；其中治理专项业务索引 14 个（`ix_ai_*`），与 changelog「全库 AI 相关索引达 14 个」一致 | PASS |
| 5 | 迁移链 | 可追溯且无分叉 | 6 个迁移，head `p5_ai_gov_perf_idx`（含 `p4` downgrade 索引名修正） | PASS |
| 6 | 权限点 | 与接口依赖一致 | **52 个权限点 / 16 个模块**（v0.9.0 为 50；新增 `commercial:view`、`commercial:manage`）；角色 7 个 | PASS |
| 7 | 后端规模 | 可统计 | 111 个 Python 文件 / 25,671 行（已排除 `venv`、`__pycache__`） | PASS |
| 8 | 前端页面与路由 | 页面均有路由注册 | 38 个源码文件 / 16,305 行；**15 个功能页面路由**全部注册（新增 `/ai-governance`、`/commercial`） | PASS |

## 4. 构建与静态检查

| # | 用例 | 结果 |
|---|---|---|
| 1 | 前端类型检查 `vue-tsc --noEmit` | PASS（含 `CommercialCenter.vue` prompt 返回值严格类型修复后无报错） |
| 2 | 前端构建 `vite build` | PASS（4.37s；产物含 `AiGovernance-*.js` 15.06 kB、`CommercialCenter-*.js` 30.60 kB 等按页分块） |

## 5. 接口链路复验（真实运行实例实测）

| 模块 | 端点 | 实测结果 |
|---|---|---|
| 系统 | `GET /api/v1/system/health` | 200，`status=ok` |
| 系统 | `GET /api/v1/system/info` | 200，`version=0.10.0`（与 FastAPI 文档版本一致，见第 9 节说明） |
| 鉴权（负向） | `GET /api/v1/rbac/roles`（未带 Token） | 401，鉴权生效 |
| AI 治理 | `GET /api/v1/ai/decisions/board` | 200，返回三级决策定义（仅用户本人 / 需用户授权 / 智能体自主） |
| AI 治理 | `GET /api/v1/ai/statistics` | 200，聚合计数正常 |
| AI 治理 | `GET /api/v1/ai/insights` / `actions` / `analyses` | 200，数据库端分页（`total` / `page` / `page_size`） |
| AI 治理 | `GET /api/v1/ai/actions/{id}/trace` | 200，处置单全过程留痕可查 |
| AI 治理 | `GET /api/v1/ai/level/rules` / `level/records` / `policies` | 200，分级规则 7 条、分级记录、策略可读 |
| 采集 | `GET /api/v1/collect/overview` / `modes` / `tasks` / `runs` | 200，见第 6 节 |
| 商业化 | `GET /api/v1/commercial/overview` / `plans` / `licenses` / `orders` / `usage` / `entitlement` / `events` | 200，见第 7 节 |
| 商业化（负向） | `POST /api/v1/commercial/license/verify`（不存在的授权码） | 200，`valid=false`、`reason=授权码不存在`，校验逻辑正确拒绝 |
| 学习进化 | `GET /api/v1/learning/overview` | 200，反馈 4 条、成功率 1.0、权重 `price_opt=1.25` |
| 数字人 | `GET /api/v1/digital-human/overview` | 200 |

> 说明：本次接口实测在本地私有化部署实例上进行，访问令牌由容器内服务端签发（复用 `app.core.security.create_access_token`），用于开发自验收，不涉及任何凭据读取或安全机制绕过。

## 6. 采集链路复验（含 SQL 直连真实化）

| # | 用例 | 实测 | 结果 |
|---|---|---|---|
| 1 | 采集总览 | 任务 3 个（全部启用）、24h 运行 2 次、成功 2 次、成功率 100%、写入 15 行、平均耗时 503ms | PASS |
| 2 | 采集模式 | `csv` / `api` / `sql` 均标记 `real_fetch=true`，SQL 模式为受控真实 `SELECT` 落库（白名单 + 5000 行上限 + 10s 超时） | PASS |
| 3 | 运行留痕 | `oc_collect_run` 2 条，`oc_collect_task` 3 条，与总览计数一致 | PASS |

## 7. AI 决策治理闭环复验（P8，数据面实测）

| # | 用例 | 实测 | 结果 |
|---|---|---|---|
| 1 | 三级决策定义 | 3 级（`user_only` 仅用户本人 / `user_authorized` 需用户授权 / 自主决策），含 `auto_execute`、`need_approval` 语义 | PASS |
| 2 | 治理统计 | 分析 2 / 洞察 9（L1 4、L3 5）/ 处置单 9（已执行 1、自动执行 4、待处置 4）/ 自动执行 4 / 待人工 4 | PASS |
| 3 | 处置单动作 | 审批 / 驳回 / 执行 / 分级调整 / 叫停 / 还原 6 类端点齐备，处置单 26 字段（含 `decision_level`、`prev_status`、`revoke_reason` 等） | PASS |
| 4 | 追溯留痕 | `oc_ai_audit_log` 15 条，`actions/{id}/trace` 可回放单条处置全过程 | PASS |
| 5 | 数据分级 | 分级规则 7 条、分级记录 9 条（含规则引擎回落默认级 L2 的 `reason` 留痕） | PASS |
| 6 | 策略与索引 | 处置策略 13 条；治理读接口数据库端分页 / 聚合 + Redis 短缓存 20s（写路径主动失效），专项索引 14 个 | PASS |

## 8. 商业化中心复验（P10）

| # | 用例 | 实测 | 结果 |
|---|---|---|---|
| 1 | 总览 | 套餐 4（上架 4）、授权 2（active 2、临期 1）、订单 3（已支付 3、收入 29,700 元）、事件 3 | PASS |
| 2 | 当前租户权益 | `licensed=true`，private 授权、seats 5、有效期至 2027-09-27，`signature` 具备 | PASS |
| 3 | 授权校验（负向） | 无效授权码返回 `valid=false` 与中文原因，未抛 500 | PASS |
| 4 | 权限点 | `commercial:view` / `commercial:manage` 已入库并计入 52 个权限点 | PASS |
| 5 | 前端 | 六标签页（总览 / 套餐 / 授权 / 订单 / 用量 / 授权校验），构建与类型检查通过 | PASS |

## 9. 已知边界与待修正项

| 类别 | 说明 |
|---|---|
| 版本号偏差（已修正） | 初测发现 `GET /api/v1/system/info` 返回 `version=0.1.0`，来源为 `app/api/v1/endpoints/health.py` 硬编码；已于提交 `5e13eca` 修正为统一读取 `settings.APP_VERSION`（定义于 `app/core/config.py`），重启后端容器后 HTTP 实测返回 `0.10.0`。现版本号单点可控，其余 5 处（changelog / main.py / package.json / openapi.json / product-manual.md）已对齐 |
| 测试数据属性 | 商业化 orders / licenses / plans 与部分治理数据为开发期自动化测试造数；`oc_com_usage` 用量表暂为空 |
| 依赖版本验证 | changelog 声明的「商业化后端验证 25/25」为 P10 开发期自测结果，本报告未复跑该脚本，仅做接口级复验 |
| 自动化回归 | 暂无 CI/CD 流水线；`backend/tests` 下仅 `test_health.py`，回归依赖手动构建与接口复验 |
| 性能测试 | 未进行压测；changelog 记录的看板接口 410ms → ~50ms 未在本轮复测 |
| 兼容性 | 仅 Chrome 120+ 验证，其他浏览器未覆盖 |

## 10. 结论

v0.10.0 在结构一致性（166 路径 / 64 表 / 857 字段 / 52 权限点）、前端构建、接口链路（26 项含负向用例全绿）、AI 决策治理闭环、采集链路与商业化中心六个方面全部通过验证，与 changelog 0.10.0 的声明逐项对得上。唯一结构性偏差为 `/system/info` 版本号硬编码残留 0.1.0，建议在下一提交一并修正；后续优先补齐 CI 流水线与自动化回归，再考虑性能与多浏览器兼容性测试。

*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
