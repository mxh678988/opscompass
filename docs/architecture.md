---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_27fba000b59f11f1a816525400cd780f
    ReservedCode1: e3x4YcQBrNGQMNiy3GpxM69FU6g0Yy/uj/pQwuEdmnhWCDkTgjJvnDdoOzsfrLfCoAnEJER5yJnQ0G2GB0FhM61IK0qsmOQHLINJDyudV0UDxRBbY7dpDTwW9jIaf9n/4roqhvfvbn3PD5ozOkL0dFyJFLLx12KCoam4A/rQvL3dMyWpePJbbLo3JEc=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_27fba000b59f11f1a816525400cd780f
    ReservedCode2: e3x4YcQBrNGQMNiy3GpxM69FU6g0Yy/uj/pQwuEdmnhWCDkTgjJvnDdoOzsfrLfCoAnEJER5yJnQ0G2GB0FhM61IK0qsmOQHLINJDyudV0UDxRBbY7dpDTwW9jIaf9n/4roqhvfvbn3PD5ozOkL0dFyJFLLx12KCoam4A/rQvL3dMyWpePJbbLo3JEc=
---

# 架构设计

> 适用产品：运营智脑（让数据自动做出最优决策）

## 1. 总体架构

```
┌──────────────┐     HTTP/JSON      ┌──────────────┐
│   前端 Vue3   │ ─────────────────▶ │ 后端 FastAPI  │
└──────────────┘                    └───────┬──────┘
                                            │
                        ┌───────────────────┼───────────────────┐
                        ▼                   ▼                   ▼
                 ┌────────────┐      ┌────────────┐      ┌────────────┐
                 │ PostgreSQL │      │   Redis    │      │  data/ 目录 │
                 │  主数据存储 │      │ 缓存/队列   │      │ 原始/加工数据│
                 └────────────┘      └────────────┘      └────────────┘
```

## 2. 分层约定（后端）

| 层 | 目录 | 职责 |
|---|---|---|
| 接口层 | `app/api/v1/endpoints` | 参数校验、响应组装，不含业务逻辑 |
| 服务层 | `app/services` | 业务编排、事务边界 |
| 数据层 | `app/crud` | 单表 CRUD 与查询构造 |
| 模型层 | `app/models` | ORM 定义 |
| 契约层 | `app/schemas` | Pydantic 请求/响应模型 |
| 基础设施 | `app/core` | 配置、日志、安全 |

依赖方向：接口层 → 服务层 → 数据层 → 模型层，禁止反向依赖。

## 3. 数据流

1. 原始数据落至 `data/raw/`（人工导入或采集脚本写入）。
2. 清洗与加工脚本输出至 `data/processed/`。
3. 加工结果入库（PostgreSQL），供指标接口查询。
4. 报表/导出结果写入 `data/exports/`。

## 4. 部署形态

- 开发：本地原生运行（`scripts/start_dev.ps1`）或 Docker Compose。
- 测试/生产：Docker Compose 启动四容器（postgres / redis / backend / frontend），前端经 Nginx 托管静态资源并反向代理 `/api`。

## 5. 环境变量

所有配置集中在根目录 `.env`，模板为 `.env.example`，后端通过 `pydantic-settings` 读取，前端通过 Vite `loadEnv` 读取。

## 6. 待办

- [x] 补充鉴权与权限模型（P0 RBAC + JWT + 审计已落地）
- [x] 运营参谋前端页（网站/网店/媒体库/自媒体/SEO-GEO，已落地）
- [x] 内置浏览器（P3）：站内预览与可控抓取（同域受控抓取 + SEO 体检，前端「站内预览」区块已落地，0.6.0）
- [x] UI 美化（P4）：设计令牌体系 + 全局基线 + 全页面样式改造（已落地，0.7.0）
- [x] 营销全渠道接入（P5）：渠道类型目录 + 平台授权（凭据 Fernet 加密存储）+ 投放任务编排 + 渠道事件留痕（已落地，0.8.0；真实平台 API 调用与投放数据回流待接入）
- [ ] 确定指标口径与数据字典
- [ ] 接入真实数据源与采集任务
- [x] 数字人一键生成（P6）：形象库 / 音色库 / 工作流模板 / 生成项目 / 任务五表 + 四阶段编排（script→voice→avatar→compose）+ 引擎探测与演练降级 + 前端页面（已落地，0.9.0）
- [x] 文档备齐（P7）：产品说明书 / 快速上手 / 部署手册 / 管理员手册 / 运维手册 / 安全白皮书 / 数据字典 / OpenAPI / 测试报告（已落地，0.9.0，功能冻结基线）
- [x] 学习进化闭环（P8）：决策反馈回流 / 策略权重自调 / 经验案例库 / A-B 对照实验 + 前端「学习进化」页（已落地，0.9.0）
- [x] AI 决策治理闭环（治理侧，changelog 0.10.0「P8」条目）：三级决策看板（仅用户本人 / 需用户授权 / 智能体自主）+ 处置单六类动作（审批 / 驳回 / 执行 / 分级调整 / 叫停 / 还原）+ 决策全过程追溯时间线；治理读接口数据库端分页与聚合 + Redis 短缓存（20s，写路径主动失效），治理专项索引 14 个（已落地，0.10.0）
- [x] 硬件检测与模型自动适配（P9）：`hardware_service`（WMI / nvidia-smi 探测）+ `model_hub_service`（VRAM 分档推荐与端点编排）+ 前端「模型中心」页（已落地，0.9.0）
- [x] 商业化中心（P10）：套餐 / 授权 / 订单 / 用量 / 事件五表 + 授权签发校验（HMAC-SHA256 离线可复核）+ 上架门槛清单，覆盖本地私有化 / SaaS 订阅 / 应用市场三种授权形态；后端验证 25/25 通过，前端六标签页（已落地，0.10.0）
- [x] 建立 CI 流程（`scripts/ci.ps1` 本地一键校验：版本一致性四源比对 / 后端 `compileall` + `pytest` / 运行实例与 `docs/openapi.json` 的路径契约比对 / 容器健康与运行版本生效 / 前端 `vue-tsc` + `vite build`，结果为退出码驱动，日志落 `temp/ci-logs/`；已落地，2026-09-29。托管式远程流水线（GitHub Actions 等）待仓库推送远端后补充）
*（内容由AI生成，仅供参考）*
