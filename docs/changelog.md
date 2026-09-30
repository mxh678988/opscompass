---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_2a1a44b9b59f11f183e7525400de85a5
    ReservedCode1: 3FzDa0fgRGfztHLiLOKADzKF3XL0jMpXxhLVPdw+A1CjQMbEzLDFCUNqQBvo06GWhexpJVID8MTugZlNVX4Z0FihO2dtbW7h/ZsKKQGz2iLJAmjT5W2354DP+71eSf8ySEkjhKc+7bMaajuDxjAv21u6/PgKX5Nx9iUP3qOgAEyuUYTYdl1/fD2J5tA=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_2a1a44b9b59f11f183e7525400de85a5
    ReservedCode2: 3FzDa0fgRGfztHLiLOKADzKF3XL0jMpXxhLVPdw+A1CjQMbEzLDFCUNqQBvo06GWhexpJVID8MTugZlNVX4Z0FihO2dtbW7h/ZsKKQGz2iLJAmjT5W2354DP+71eSf8ySEkjhKc+7bMaajuDxjAv21u6/PgKX5Nx9iUP3qOgAEyuUYTYdl1/fD2J5tA=
---

# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- **本地 CI 校验脚本**：新增 `scripts/ci.ps1`，一条命令完成升版 / 提交前校验——① 版本一致性（`config.APP_VERSION` / 前端 `package.json` / `docs/openapi.json` / `changelog` 四源比对）；② 后端 `compileall` 与 `pytest`（容器内执行，与运行环境同构）；③ 接口契约基线（运行实例 `/openapi.json` 与 `docs/openapi.json` 的路径集合逐条比对，不一致时输出差异文件）；④ 容器健康与运行版本生效（防止改版未重启）；⑤ 前端 `vue-tsc --noEmit` + `vite build`；⑥ 前端 `eslint`（未安装则跳过）。结果打印汇总并落盘 `temp/ci-logs/<时间戳>/`（含 `pytest.log`、`frontend-build.log`、`summary.json`），存在失败项时以退出码 1 结束，可直接挂接提交钩子或后续远程流水线。支持 `-SkipBackend` / `-SkipFrontend` / `-SkipRuntime` 按需裁剪。

- **前端 lint 基线落地**：新增 `frontend/.eslintrc.cjs`（`eslint:recommended` + `plugin:vue/vue3-essential` + `plugin:@typescript-eslint/recommended`；格式类规则交由 prettier 统一，避免双重标准），`devDependencies` 增补 `eslint@8.57.1` / `eslint-plugin-vue@9.32.0` / `@typescript-eslint/parser@8.26.0` / `@typescript-eslint/eslint-plugin@8.26.0`。`scripts/ci.ps1` 第 8 项「前端 lint」由长期 SKIP 转为 PASS，本地 CI 首次全绿（通过 9 / 失败 0 / 跳过 0）。基线条目口径为 0 error / 286 warning（warning 全部为 `@typescript-eslint/no-explicit-any`，作为类型债留待后续版本逐步收紧）。

### 验证

- **后端镜像重建实证（可选驱动免手工重装）**：`docker compose build backend` 重建后的镜像自带全部四类采集驱动（PostgreSQL / MySQL / ClickHouse / Hive），对 16 个关键模块做导入检查为 16/16 通过，重建后**无需再手工 pip 安装驱动**；重建全程非中断，运行中的 `opscompass-backend` 容器保持 healthy。附注：`pure-sasl` 的导入名是 `puresasl`（非 `pure_sasl`）。

### 修复

- **Hive 方言名修正（连接串畸形）**：`collect_service.SQL_SUPPORTED_TYPES` 中 Hive 的方言名误写为 `hive://`，而 `_build_sql_url` 已统一补 `://`，实际拼出 `hive://://user@host:10000/db` 畸形串——SQLAlchemy 解析为「主机为空 + 空口令」，PyHive 随即抛 `ValueError: Password should be set if and only if in LDAP or CUSTOM mode`，连接在参数校验阶段即失败，与目标库是否可达无关。现修正为 `hive`（与 PostgreSQL / MySQL / ClickHouse 三类对齐），并新增 `backend/tests/test_collect_sql.py`——50 条纯函数级用例（不连库、不出网、不落库）固化四类驱动分派、连接串拼装（含 Hive 空口令不拼 `user:@`、口令 URL 编码）、连接参数分派、表名白名单、SSRF 防护与调度排期基线；容器内 `python -m pytest -q tests` 由 2 passed 升至 **52 passed**。修正后同一场景（127.0.0.1:10000 无实例）的失败归因为真实网络层 `TTransportException: Could not connect to [('127.0.0.1', 10000)]`，Hive「失败降级」口径自洽；真实源端到端落库仍需 HiveServer2 实例方可补验。

- **依赖清单不可复现修复**：`backend/requirements.txt` 中原先写入 `pymysql==2.2.8`，该版本在 PyPI 上并不存在（PyMySQL 最新为 `1.2.3`）；而 `deploy/docker/Dockerfile.backend` 会执行 `pip install -r requirements.txt`，因此在干净环境下镜像构建必然失败，交付基线不具备可复现性。现改为 `pymysql==1.2.3`（与实际运行环境已验证版本一致）。为防回归，新增 `scripts/verify_requirements.py`——对清单内每个 pin 做 PyPI 存在性静态校验（只读联网，不安装、不改环境，离线环境下相关条目降级为 UNKNOWN 不计失败），并接入 `scripts/ci.ps1` 作为第 9 项「依赖清单可复现性」校验，在构建前拦截无效 pin；同时清理历史上误入版本库的两个临时验证脚本（`backend/_p0_verify_tmp.py`、`backend/_tmp_p9_check.py`）。

- **版本号单点化**：`/api/v1/system/info` 原先返回硬编码的 `0.1.0`，现与 FastAPI 文档统一改为读取 `settings.APP_VERSION`（定义于 `app/core/config.py`，当前 `0.10.0`）；此后升版只需修改该字段一处，避免版本号漏同步。

## [0.10.0] - 2026-09-29

### 新增

- **AI 决策治理闭环（P8）**：新增迁移 `d1a7b3c9e5f2`（治理三表补齐 13 列），`app/services/ai/governor.py` 的三级决策（仅用户本人决策 / 需用户授权决策 / 智能体自主决策）由后端贯通到界面；前端新增 `src/views/AiGovernance.vue` 与 `src/api/ai.ts` 类型封装，注册路由 `/ai-governance` 并在顶部导航新增「AI 治理」；页面含三级决策看板、处置单处置表（审批 / 驳回 / 执行 / 分级调整 / 叫停 / 还原）与决策全过程追溯时间线。
- **商业化中心（P10）后端**：新增 `app/api/v1/endpoints/commercial.py`（18 条路径，挂载 `/api/v1/commercial`）与 `app/services/commercial_service.py`；落库 5 张表（套餐 `oc_com_plan`、授权 `oc_com_license`、订单 `oc_com_order`、用量 `oc_com_usage`、事件 `oc_com_license_event`）；覆盖套餐 CRUD 与 `plans/seed` 预置、授权签发/激活/续期/吊销、`license/verify` 授权校验（返回 `valid` / `message` / 剩余天数）、订单创建/支付（支付后自动签发授权）/取消、用量登记与告警超额判定、总览 `overview`（含 `modes` 授权模式与 `launch_checklist` 上架门槛）、当前租户权益 `entitlement`；权限点 `commercial:view` / `commercial:manage`。后端验证 25/25 通过。
- **商业化中心前端**：新增 `src/api/commercial.ts`（封装 overview / entitlement / plans / licenses / orders / usage / license-verify / events 全部接口与严格类型）与 `src/views/CommercialCenter.vue`（六标签页：总览、套餐、授权、订单、用量、授权校验）；`router/index.ts` 注册懒加载路由 `/commercial`，`App.vue` 顶部导航新增「商业化」。

### 变更

- **数据库直连采集（sql 模式）驱动补齐至四类库**：`app/services/collect_service.py` 的 SQL 直连支持类型由 PostgreSQL / MySQL 扩展至 ClickHouse 与 Hive 共四类。ClickHouse 走 `clickhousedb+connect`（HTTP 8123），Hive 走 `hive://`（HiveServer2 Thrift 10000）；`_connect_args` 改为按数据源分派——ClickHouse 同时下发 `connect_timeout` 与 `send_receive_timeout`，Hive 有口令时以 `auth=LDAP` 认证、无口令时用默认 NOSASL 且空口令不再拼接 `user:@`（规避 PyHive「口令仅允许 LDAP/CUSTOM 模式」与「不接受 connect_timeout」两处硬校验，详见同期踩坑记录）。两类驱动均已 pin 入 `backend/requirements.txt`：`clickhouse-connect` / `clickhouse-sqlalchemy`，以及 `pyhive` / `thrift` / `thrift-sasl` / `pure-sasl` / `future`（以纯 Python 的 `pure-sasl` 替代需 C 编译的 `sasl`）。验证口径：ClickHouse 与 PostgreSQL、MySQL 均实测真实拉取落库（`simulated=false`）；Hive 因本机无 HiveServer2 实例，仅验证驱动可用性与失败降级——连接不可达时返回可预期业务错误并留失败运行记录，不抛 500，真实源端到端验证待具备实例后再补。同期清理版本库外残留的临时校验日志 `backend/_tmp_p9_check.log`（P9 阶段产物，已被 `.gitignore` 忽略）。
- `api/commercial.ts` 中 `createOrder` 的 `plan_id` 调整为可选（缺省时由后端取首个上架套餐）。
- **治理读接口性能优化**：`insights` / `actions` 列表改为数据库端分页（`limit` / `offset`，返回 `total` / `page` / `page_size`），`analyses/{id}` 详情改用数据库端 `analysis_id` 过滤，替代原「拉取近 200 条再内存过滤」；`decision_board` / `statistics` 改为数据库端聚合计数（`group_by` + `count`），不再全表载入内存。
- **索引补齐**：新增迁移 `p5_ai_gov_perf_idx`，补建 `ix_ai_insight_tenant_status_severity`、`ix_ai_action_tenant_status_handler`、`ix_ai_action_tenant_analysis`，并修正 `p4` 迁移 `downgrade` 中的索引名错误（`ix_ai_analysis_data_level` → `ix_ai_analysis_scope`）；全库 AI 相关索引达 14 个。
- **治理看板短缓存**：`decision_board` / `statistics` 接入 Redis 短 TTL 缓存（20 秒，复用 `app/storage/cache.py` 适配器，Redis 不可用时自动降级直连数据库），治理写路径（分级调整 / 审批 / 驳回 / 执行 / 叫停 / 还原）提交后主动失效；实测看板接口 410ms → ~50ms。
- `docs/product-manual.md` 对齐 2026 市场趋势（智能体定规、数据不出域、决策合规可追溯），功能页补充 AI 治理与商业化中心，能力规模刷新至 2026-09-29 实测值。
- **数据库直连采集（sql 模式）接入真实驱动**：`app/services/collect_service.py` 的 sql 采集由「TCP 探测演练」升级为 PostgreSQL / MySQL 受控 `SELECT` 真实落库（表名白名单、行数上限 5000、10 秒超时、示例行回传）；驱动缺失时按可预期错误返回而非 500；新增扩展配置 `limit`（1~5000）用于小批量试采；采集中心 `modes` 中 sql 的 `real_fetch` 置真，并注明 MySQL 需环境已安装 `pymysql`。

### 修复

- `CommercialCenter.vue` 修复 `prompt()` 返回 `string | null` 直接传入 `parseInt` / 字符串参数导致的严格类型报错（5 处 `parseInt(prompt(...) ?? '', 10)`）；用量表首列（指标标识）补齐 `min-width`，避免 `seats` / `api_calls` 等标识被截断。

## [0.9.0] - 2026-09-26

### 新增

- **数字人一键生成（P6）**：新增 `app/api/v1/endpoints/digital_human.py` 与 `app/services/digital_human_service.py`（865 行），挂载 `/api/v1/digital-human`，权限点 `digital_human:view` / `digital_human:manage`；新增 5 张表 `oc_dh_avatar`（形象库）、`oc_dh_voice`（音色库）、`oc_dh_workflow`（工作流模板）、`oc_dh_project`（生成项目）、`oc_dh_task`（任务与阶段状态）；内置默认工作流 `ensure_default_workflow`，四阶段编排 `script → voice → avatar → compose`，含生成引擎可用性探测与不可用时的演练降级。
- **前端**：新增 `src/views/DigitalHuman.vue`（1356 行）与 `src/api/digitalHuman.ts`，注册路由 `/digital-human` 并在顶部导航新增「数字人」；列表加载改用 `Promise.allSettled`，避免单接口故障拖垮整页。
- **P7 文档备齐（功能冻结基线）**：新增 `docs/product-manual.md`（产品说明书）、`docs/quick-start.md`（快速上手）、`docs/deployment-manual.md`（部署手册）、`docs/admin-manual.md`（管理员手册）、`docs/ops-manual.md`（运维手册）、`docs/security-whitepaper.md`（安全白皮书）、`docs/data-dictionary.md`（数据字典，59 张表 / 765 字段实时导出）、`docs/openapi.json`（OpenAPI 3.1 全量导出）、`docs/test-report.md`（测试报告）。

### 变更

- 文档版本统一为 **v0.9.0（功能冻结）**；`docs/api.md`、`docs/architecture.md`、`docs/data-model.md` 与代码库同步更新。

### 安全

- 数字人接口沿用模块级权限依赖（`require_module_access("digital_human")`），未认证访问返回 401；演示预览图外链域名已清空，避免第三方资源引用。
- 安全白皮书落地安全基线：JWT 认证、50 个 RBAC 权限点、登录失败锁定、IP 白名单、审计日志与分级安全日志（含 CRITICAL 告警镜像）。

### 验收

- 宿主机 `npm run build` 通过（`vue-tsc --noEmit` + `vite build`）。
- 数字人模块全链路复验通过：前端页面加载、形象/音色/工作流/项目/任务接口联通，四阶段编排与降级路径可用。
- 事实采集核对：OpenAPI 146 条路径 / 200 个操作 / 207 个 Schema；数据库 59 张表 / 765 字段；权限点 50 个；前端 13 个功能页面。

## [0.8.0] - 2026-09-24

### 新增

- **营销全渠道接入（P5）**：新增 `app/api/v1/endpoints/marketing.py` 并挂载 `/api/v1/marketing`（依赖 `require_module_access("marketing")`，权限点 `marketing:view/create/update/authorize/delete`，管理员默认授权）；新增 3 张表 `oc_marketing_channel`（渠道账号 + 凭据密文）、`oc_channel_campaign`（投放/分发任务）、`oc_channel_event`（渠道事件日志），`python -m app.init_db` 建表共 37 张。
- **渠道类型目录**：内置 14 类平台 —— 抖音、抖音小店、小红书、微信公众号、微信视频号、微信小程序、哔哩哔哩、快手、微博、知乎、淘宝/天猫、京东、拼多多、自有网站，逐类标注授权方式（OAuth / API Key / Cookie）与开放能力，并返回已接入 / 已授权计数。
- **接口**：`GET /channel-types`、`GET /overview`、`GET|POST /channels`、`PUT|DELETE /channels/{id}`、`POST /channels/{id}/authorize|revoke|sync`、`GET|POST /campaigns`、`PUT|DELETE /campaigns/{id}`、`POST /campaigns/{id}/execute`、`GET /events`。
- **前端**：新增 `src/views/MarketingCenter.vue` 与 `src/api/marketing.ts`，注册路由 `/marketing` 并在顶部导航新增「营销渠道」；页面含接入概览、渠道类型目录、渠道账号（新增 / 编辑 / 授权 / 撤销 / 同步 / 停用 / 删除）、投放任务（创建 / 执行 / 删除）、渠道事件五个区块，样式沿用 P4 设计令牌。

### 安全

- 平台凭据经 Fernet 对称加密落库，接口一律只回显脱敏串（如 `dy_******3456`），不回显明文；未携带 token 访问营销接口一律 401。
- `POST /campaigns/{id}/execute` 当前为本地编排演练（返回 `result.simulated=true`），不调用平台真实 API、不写入曝光 / 点击 / 转化数据。

### 修复

- **数据源页表单语义**：`DataSourceCenter.vue` 新建 / 编辑数据源区块由 `<div class="form">` 改为 `<form class="form" @submit.prevent="submit">`，提交按钮改 `type="submit"`、取消按钮改 `type="button"`，消除 Chrome `[DOM] Password field is not contained in a form` 提示（P4 遗留非阻塞项）。

### 验收

- 宿主机 `npm run build` 通过（`vue-tsc --noEmit` 类型检查 + `vite build`）。
- 浏览器端到端验收通过：导航「营销渠道」真实跳转 `/marketing`；接入概览 6 指标（已接入 3 / 已授权 2 / 未授权·过期 1 / 投放任务 1 / 渠道事件 7）、渠道类型 14 卡、渠道账号 3 行（凭据脱敏）、投放任务 1 行（已成功）、渠道事件 7 条，页面真实调用 `/api/v1/marketing/*` 且返回 200，console 无 JS 报错；`/data-sources` 表单提交成功（新建 id=2），form 相关提示消失。

## [0.7.0] - 2026-09-24

### 变更

- **UI 美化（P4 设计令牌体系）**：`src/styles/main.css` 扩充为完整设计令牌库与全局基线 —— 品牌色（`--color-primary` / `--color-success` / `--color-warning` / `--color-error`，各含 `light` / `border` 衍生）、文字三级（`--color-text` / `-secondary` / `-muted`）、背景三级（`--color-bg` / `-subtle` / `-hover`）、边框三级、阴影三级（`--shadow-sm` / `-md` / `-card`）、圆角五级（`--radius-sm` ~ `--radius-full`）、间距九级（`--space-1` ~ `--space-16`）、动画三级（`--transition-fast` / `-base` / `-slow`），并为表格、按钮、输入框（含聚焦光环）、滚动条、代码块、链接提供统一全局样式。
- **全页面样式令牌化**：`App.vue`（顶栏改用毛玻璃背景 + 56px 高度 + 导航 active 态 primary-light 底色）、`Login.vue`（多层径向渐变背景 + 输入框聚焦光环 + 提交按钮 hover 阴影）、`Dashboard.vue`、`Compass.vue`、`DataImport.vue`、`DataSourceCenter.vue`、`MetricCenter.vue`、`OpsCenter.vue`、`SecurityLog.vue`、`StorageCenter.vue` 共 10 个文件的样式由硬编码色值（`#2f6fed` / `#eee` / `#999` / `#333` 等）全部替换为设计令牌变量；页面容器统一 `max-width: 1400px` 居中，面板统一 `--radius-lg` 圆角与卡片 hover 阴影，并追加表格行 hover、按钮 hover、标签字重、指标卡 hover 等交互增强。
- **响应式**：`Dashboard` / `Compass` 补充 `max-width: 768px` / `480px` 断点适配。

### 验收

- 宿主机 `npm run build` 通过（125 modules，2.82s），dist 已更新。
- 浏览器逐页实测 8 个路由：页面渲染正常、无空白页或样式错乱；46 个设计令牌真实注入并驱动计算样式（实测 `body` 文字色解析为 `#1f2937`）；console 无 JS 报错。

## [0.6.0] - 2026-09-24

### 新增

- **内置浏览器（P3 后端）**：新增 `app/services/ai/site_crawler.py` 受控抓取服务，配套接口 `POST /api/v1/ops/websites/{website_id}/crawl`，支持按 `page_id` 或站点内相对 `path` 派生目标地址（前导 `/` 自动归一）；仅允许同域，拒绝内网与保留地址（10.x / 192.168.x / 169.254.x / 元数据地址）与 http/https 以外的协议，单次读取上限 512KB、超时 10s、不跟随跨域跳转；解析标题 / 描述 / H1·H2 / canonical / og:title / 正文字数，并输出 `ok|warn|error` 三级 SEO 诊断。

### 变更

- **运营参谋（P3 前端）**：页面行新增「站内预览」按钮，页面区块新增「站内预览（仅同域抓取）」入口（可留空抓站点首页或填写相对路径）；结果面板展示 HTTP 状态、耗时、字节数、最终地址与标题/描述/H1/正文字数，7 类诊断项以绿 / 橙 / 红三色标签呈现，并提供「新窗口打开」。

## [0.5.0] - 2026-09-24

### 新增

- **安全权限体系（P0）**：RBAC 角色权限 + JWT 鉴权 + 审计日志（新增 6 张表）；后端不提供注册接口，管理员凭据唯一来源为 `.env` 的 `SECURITY_ADMIN_USERNAME` / `SECURITY_ADMIN_PASSWORD`。
- **存储适配层（P2）**：多类型存储路由（关系型 / 时序 / 全文 / 缓存 / 文件）、时序分区表 `oc_ts_metric_point`、全文索引 `oc_doc_index`（PG `GIN` + `pg_trgm`）、缓存降级与跨存储一致性对账；接口挂载于 `/api/v1/storage/*`，前端新增「存储适配」页（引擎总览 / 路由识别 / 全文检索 / 一致性对账）。
- **安全日志分级通道**：新增 `app/core/security_log.py`，按 INFO / WARNING / CRITICAL 三级写入独立轮转日志（默认 `logs/security.log`），支持最低级别过滤与告警级别镜像主日志（含 WARNING 及以上可选镜像）；与审计库由 `audit_service.record` 单点联动，日志写入失败不影响主流程。新增接口 `GET /api/v1/audit/security-log/levels`（级别/事件字典 + 通道配置）与 `GET /api/v1/audit/security-log/entries`（按级别/事件/天数筛选 + 分级统计 + 最近高危），前端新增「安全日志」页（分级统计卡 / 通道配置 / 条目筛选 / 事件分布 / 高危事件）。
- **一键云部署**：新增 `deploy/deploy.sh`（环境与依赖自检、`.env` 与密钥生成补全、端口占用提示、镜像构建、容器健康检查、数据库迁移、部署摘要），配套 `deploy/nginx/nginx.https.conf` 与 `deploy/docker/docker-compose.https.yml` 支持 HTTPS（自签证书或自有证书）。

- **运营参谋（P2 前端）**：新增「运营参谋」页（前端 `api/ops.ts` 封装站点/页面/商品/SEO/GEO/媒体/自媒体/AI 分析全套接口），覆盖七区块——站点资产（新建/切换/发布/AI 开关与模式、SEO·GEO 评分）、页面与文章（创建、发布/转草稿、一键「AI 改写」按 SEO 关键词与语气生成内容）、商品管理（分转元展示）、SEO 与 GEO 任务（六类 SEO 任务 + 五类 GEO 任务执行与任务记录）、媒体库（登记/筛选/分级）、自媒体分发（AI 优化文案 / 智能排期 / 数据洞察）、AI 智能设置（七类配置开关与保存）；路由 `/ops` 与顶部导航「运营参谋」已接入。

### 修复

- **容器内路径解析**：`BASE_DIR` 兼容容器目录布局（容器内为 `/app`），修复日志与数据目录被解析到根路径（`/logs`、`/data`）导致日志未写入宿主挂载卷的问题。

## [0.4.0] - 2026-09-23

### 变更

- **品牌重塑（P1）**：对外展示品牌统一为「运营智脑」，Slogan 为「让数据自动做出最优决策」。覆盖前端应用标题与页面路由标题、顶部导航品牌区、登录页品牌标识与 Slogan、`index.html` 的 title/description 与 favicon 图标；后端 FastAPI 应用标题、OpenAPI 文档标题与健康检查接口品牌字段（新增 `slogan`）；同步 README、docs 各文档与部署说明。技术标识（项目目录名 `OpsCompass`、容器名、Python 包名、数据库名、`oc_` 表前缀）保持不变。

## [0.3.0] - 2026-09-22

### 新增

- **全景罗盘（Phase 1-4）**：新增 `GET /api/v1/metrics/compass`（全部上线指标的整体值 + 环比 + 维度拆解 + 趋势）与 `GET /api/v1/metrics/dim-keys`（已接入数据中出现过的维度键）；前端新增「全景罗盘」页面，支持粒度切换（日/周/月）与拆解维度切换，按维度取值展示数值、占比与环比条形对比。

## [0.2.0] - 2026-09-22

### 新增

- **数据接入（Phase 1-3）**：CSV/Excel 文件导入全链路 —— 上传、宽表/长表映射、清洗、指标值 upsert、导入任务查询；前端新增「数据导入」与「数据源」页面。
- **数据模型（Phase 1-1）**：新增多租户与指标中心共 7 张表 —— `oc_tenant`、`oc_data_source`、`oc_metric_category`、`oc_metric_dimension`、`oc_metric_dimension_rel`、`oc_metric`、`oc_metric_value`，统一按 `tenant_id` 隔离，唯一约束按 `(tenant_id, code)` 组合。
- **指标中心（Phase 1-2）**：指标定义 CRUD、指标值批量写入（同「时间+粒度+维度」覆盖）、指标值明细查询、指标趋势、指标总览（最新值 + 环比）。
- **数据源管理**：连接配置增删改查，密码经 Fernet 加密落库（`app/core/crypto.py`），接口不回显明文。
- **租户管理**：租户列表与创建。
- **前端**：总览页接入真实指标卡（数值 + 环比 + 迷你 sparkline + 主趋势图）；新增「指标中心」页面（指标列表、筛选、新建、上下线、删除）。
- **初始化与演示数据**：`app/init_db.py` 建表、`app/seed_demo.py` 写入 1 租户 / 1 数据源 / 4 指标 / 124 条指标值。
- **文档**：新增 `docs/data-model.md` 数据模型设计说明。

### 变更

- `GET /api/v1/metrics/overview` 响应由固定四字段（`gmv`/`orders`/`users`/`conversion_rate`）改为通用结构 `{ stat_date, items[] }`，支持任意上线指标动态扩展。

## [0.1.0] - 2026-09-21

### 新增

- 初始化项目骨架：`backend` / `frontend` / `data` / `docs` / `scripts` / `deploy` 目录结构。
- 后端 FastAPI 基础工程：配置加载、日志、安全工具、ORM 基类、统一响应结构与健康检查接口。
- 前端 Vue3 + Vite 基础工程：路由、状态管理、请求封装与总览页面骨架。
- Docker Compose 编排：PostgreSQL 16、Redis 7、后端、前端四服务。
- 环境变量模板 `.env.example`、`.gitignore`、`.editorconfig`。
- 开发脚本：`start_dev.ps1`、`init_db.py`、`backup.ps1`。
*（内容由AI生成，仅供参考）*
