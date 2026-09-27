---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_28ec9ce8b59f11f1a816525400cd780f
    ReservedCode1: 2xONaqp5xUlwGT5O1aV5zV+xxZzKhcfLAIcTW4lAOHAWeRFe2rlIRG8qUF1Mwu5eIvECgJHBcmzotyg9ELpKnsfFBYEUYp4Sp+n6PfLTyuNynDAA/RP+B+KoKnPZI7TmMzXOIjvrARNWV/jA7sVOf+O4R9k0mfX61LYu22yDxbh6CO73N9SOuIAGaoU=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_28ec9ce8b59f11f1a816525400cd780f
    ReservedCode2: 2xONaqp5xUlwGT5O1aV5zV+xxZzKhcfLAIcTW4lAOHAWeRFe2rlIRG8qUF1Mwu5eIvECgJHBcmzotyg9ELpKnsfFBYEUYp4Sp+n6PfLTyuNynDAA/RP+B+KoKnPZI7TmMzXOIjvrARNWV/jA7sVOf+O4R9k0mfX61LYu22yDxbh6CO73N9SOuIAGaoU=
---

# 接口说明

> 适用产品：运营智脑（让数据自动做出最优决策）

统一前缀：`/api/v1`
统一响应体：`{ "code": 0, "message": "ok", "data": {...} }`

在线文档：后端启动后访问 `http://localhost:8000/docs`（Swagger UI）或 `/redoc`。

## 系统

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/system/health` | 健康检查 |
| GET | `/api/v1/system/info` | 服务基础信息 |
| GET | `/health` | 根级健康检查（供容器探针使用） |

## 租户

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/tenants` | 租户列表 |
| POST | `/api/v1/tenants` | 新建租户（编码重复返回 409） |

## 数据源

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/datasources` | 数据源列表（`keyword` 模糊搜索 + 分页） |
| POST | `/api/v1/datasources` | 新建数据源（`password` 密文落库，不回显） |
| GET | `/api/v1/datasources/{code}` | 数据源详情 |
| PUT | `/api/v1/datasources/{code}` | 更新数据源（局部更新） |
| DELETE | `/api/v1/datasources/{code}` | 删除数据源 |

支持的 `ds_type`：`mysql` / `postgresql` / `clickhouse` / `hive` / `api` / `csv`。

## 指标中心

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/metrics/overview` | 指标总览（各指标最新值 + 环比） |
| GET | `/api/v1/metrics` | 指标列表（`keyword` / `status` / `category_id` + 分页） |
| POST | `/api/v1/metrics` | 新建指标（可同时绑定维度，编码重复返回 409） |
| GET | `/api/v1/metrics/{code}` | 指标详情 |
| PUT | `/api/v1/metrics/{code}` | 更新指标（局部更新） |
| DELETE | `/api/v1/metrics/{code}` | 删除指标（指标值级联删除） |
| POST | `/api/v1/metrics/{code}/values` | 批量写入指标值（同「时间+粒度+维度」覆盖） |
| GET | `/api/v1/metrics/{code}/values` | 指标值明细（`start` / `end` / `granularity` / `limit`） |
| GET | `/api/v1/metrics/{code}/trend` | 指标趋势（`start` / `end` / `granularity`） |
| GET | `/api/v1/metrics/dim-keys` | 已接入数据中出现过的维度键（供罗盘维度切换） |
| GET | `/api/v1/metrics/compass` | 全景罗盘（`granularity` / `dim_key` / `codes`：整体值 + 环比 + 维度拆解 + 趋势） |

指标定义字段详见 [`data-model.md`](./data-model.md#35-oc_metric-指标定义核心)。

### 示例：指标总览

请求：

```
GET /api/v1/metrics/overview?granularity=day
```

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "stat_date": "2026-09-22T00:00:00+08:00",
    "items": [
      {
        "code": "gmv",
        "name": "成交总额",
        "unit": "元",
        "precision": 2,
        "value": 2096374.03,
        "prev_value": 2125891.5,
        "delta_ratio": -0.0139,
        "stat_time": "2026-09-22T00:00:00+08:00",
        "has_data": true
      }
    ]
  }
}
```

- `delta_ratio` 为环比变化率，`0.12` 表示 +12%；无上期数据时为 `null`。
- `codes` 可选，多个指标编码以英文逗号分隔；不传返回全部 `online` 指标。

### 示例：写入指标值

请求：

```
POST /api/v1/metrics/gmv/values
```

```json
{
  "items": [
    { "stat_time": "2026-09-22T00:00:00", "granularity": "day", "dims": { "channel": "app" }, "value": 2096374.03 }
  ]
}
```

响应：

```json
{ "code": 0, "message": "ok", "data": { "code": "gmv", "affected": 1 } }
```

## 安全审计与安全日志

审计库（`oc_audit_log`）保存可检索的完整流水；安全日志分级通道写入独立轮转文件，二者由审计写入单点联动，日志失败不影响主流程。

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/audit/logs` | `audit:view` | 审计日志分页查询（事件类型 / 结果 / 操作人 / 关键词 / 时间范围） |
| GET | `/api/v1/audit/stats` | `audit:view` | 近 N 天审计统计 |
| GET | `/api/v1/audit/event-types` | `audit:view` | 审计事件类型枚举 |
| POST | `/api/v1/audit/purge` | `audit:export` | 按保留期清理过期审计日志（敏感操作，落审计） |
| GET | `/api/v1/audit/security-log/levels` | `audit:view` | 级别/事件字典 + 通道配置（最低记录级别、告警级别、镜像开关、文件元信息） |
| GET | `/api/v1/audit/security-log/entries` | `audit:view` | 安全日志条目（`level` / `event_type` / `days` / `limit`）+ 分级统计 + 最近 CRITICAL |

分级规则：INFO（登录成功、登出、敏感操作成功）、WARNING（登录失败、权限拒绝、令牌无效、修改密码）、CRITICAL（账号锁定、IP 白名单拦截、审计通道异常）。

## 存储适配

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/storage/overview` | 引擎能力矩阵 + 规模统计（含路由规则与样例识别） |
| POST | `/api/v1/storage/bootstrap` | 幂等初始化：受管目录 + 内置规则 + 时序分区 |
| GET | `/api/v1/storage/routing/rules` | 路由规则列表 |
| POST | `/api/v1/storage/routing/identify` | 识别数据类型并给出目标存储引擎 |
| GET | `/api/v1/storage/search` | 全文检索（`pg_trgm`，不可用时返回降级说明） |
| POST | `/api/v1/storage/search/reindex` | 重建全文索引 |
| POST | `/api/v1/storage/backfill` | 回填存量指标值到时序分区表 |
| POST | `/api/v1/storage/consistency/run` | 跨存储一致性对账（可选自动修复） |
| GET | `/api/v1/storage/consistency/recent` | 最近对账记录 |

存储适配接口统一要求 `storage` 模块访问权限；安全审计接口要求 `audit:view` / `audit:export` 权限。

## 运营参谋

网站/网店资产、页面与商品、SEO/GEO 任务、AI 智能设置、媒体库与自媒体分发；统一要求 `ops` 模块访问权限，数据按租户隔离。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/ops/websites` | 创建网站/网店（`site_type`：cms/shop/blog/landing/custom） |
| GET | `/api/v1/ops/websites` | 网站列表 |
| GET | `/api/v1/ops/websites/{website_id}` | 网站详情 |
| PUT | `/api/v1/ops/websites/{website_id}` | 更新网站（名称/状态/AI 开关与模式等） |
| DELETE | `/api/v1/ops/websites/{website_id}` | 删除网站 |
| POST | `/api/v1/ops/websites/{website_id}/pages` | 创建页面/文章（含 `content_level` 分级与 SEO 字段） |
| GET | `/api/v1/ops/websites/{website_id}/pages` | 页面列表 |
| GET | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 页面详情 |
| PUT | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 更新页面（含发布状态切换） |
| DELETE | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 删除页面 |
| POST | `/api/v1/ops/websites/{website_id}/products` | 创建商品（`price` 单位为分） |
| GET | `/api/v1/ops/websites/{website_id}/products` | 商品列表 |
| PUT | `/api/v1/ops/websites/{website_id}/products/{product_id}` | 更新商品 |
| DELETE | `/api/v1/ops/websites/{website_id}/products/{product_id}` | 删除商品 |
| POST | `/api/v1/ops/websites/{website_id}/seo` | 执行 SEO 任务（`task_type`：audit/generate_sitemap/generate_robots/content_audit/keyword_analysis/link_audit） |
| GET | `/api/v1/ops/websites/{website_id}/seo` | SEO 任务列表 |
| POST | `/api/v1/ops/websites/{website_id}/geo` | 执行 GEO 任务（`task_type`：content_optimize/schema_markup/ai_snippet/structured_data/local_seo） |
| GET | `/api/v1/ops/websites/{website_id}/geo` | GEO 任务列表 |
| POST | `/api/v1/ops/websites/{website_id}/ai-config` | 创建/更新 AI 配置（`setting_type`：seo_auto/content_auto/seo_tone/content_tone/publish_schedule/auto_sitemap/media_auto_tag/auto_meta） |
| GET | `/api/v1/ops/websites/{website_id}/ai-config` | AI 配置列表 |
| PUT | `/api/v1/ops/ai-configs/{config_id}` | 更新 AI 配置 |
| POST | `/api/v1/ops/websites/{website_id}/media` | 登记媒体（图片/视频/文档，支持 `tags`、`content_level`） |
| GET | `/api/v1/ops/websites/{website_id}/media` | 媒体列表 |
| GET | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 媒体详情 |
| PUT | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 更新媒体 |
| DELETE | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 删除媒体 |
| POST | `/api/v1/ops/websites/{website_id}/social` | 创建自媒体发布 |
| POST | `/api/v1/ops/websites/{website_id}/social/optimize` | AI 优化自媒体文案（`platform` / `content` / `tone` / `mode`） |
| POST | `/api/v1/ops/websites/{website_id}/social/schedule` | AI 智能安排发布时间（`platform` / `posts`） |
| POST | `/api/v1/ops/websites/{website_id}/social/analytics` | AI 分析自媒体数据（`platform`） |
| POST | `/api/v1/ops/websites/{website_id}/crawl` | 站内预览抓取与 SEO 体检（`page_id` 或 `path` 二选一，`path` 为站点内相对路径） |
| POST | `/api/v1/ops/ai/analyze` | AI 全面运营分析（`scope`：seo/geo/content/analytics） |
| POST | `/api/v1/ops/ai/generate-content` | AI 生成/改写页面内容（`page_id` / `content_type` / `keywords` / `tone` / `mode`） |

## 营销渠道（`/api/v1/marketing`，权限模块 `marketing`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/marketing/channel-types` | 渠道类型目录（14 类平台，含授权方式、开放能力、已接入 / 已授权计数） |
| GET | `/api/v1/marketing/overview` | 接入概览（渠道与任务计数、类型覆盖情况） |
| GET | `/api/v1/marketing/channels` | 渠道账号列表（支持 `channel_type` / `status` / `keyword` / 分页） |
| POST | `/api/v1/marketing/channels` | 新增渠道账号（可同传 `credential` 直接授权） |
| PUT | `/api/v1/marketing/channels/{channel_id}` | 编辑渠道账号 |
| DELETE | `/api/v1/marketing/channels/{channel_id}` | 删除渠道账号（级联删除其任务与事件） |
| POST | `/api/v1/marketing/channels/{channel_id}/authorize` | 写入凭据并授权（`credential` / `auth_type` / `expires_at` / `scopes`） |
| POST | `/api/v1/marketing/channels/{channel_id}/revoke` | 撤销授权并清除本地凭据 |
| POST | `/api/v1/marketing/channels/{channel_id}/sync` | 触发渠道数据同步（更新 `last_sync_at`） |
| GET | `/api/v1/marketing/campaigns` | 投放任务列表（支持 `channel_id` / `status` / 分页） |
| POST | `/api/v1/marketing/campaigns` | 创建投放任务（`campaign_type`：content_publish / ad_delivery / promotion / data_sync） |
| PUT | `/api/v1/marketing/campaigns/{campaign_id}` | 编辑投放任务 |
| DELETE | `/api/v1/marketing/campaigns/{campaign_id}` | 删除投放任务 |
| POST | `/api/v1/marketing/campaigns/{campaign_id}/execute` | 执行投放任务（当前为本地编排演练，`simulated=true`） |
| GET | `/api/v1/marketing/events` | 渠道事件日志（支持 `channel_id` / `limit`） |

凭据安全：平台 Token / Key 经 Fernet 对称加密后落库，接口只返回脱敏串（`credential_masked`），任何响应不含明文；未携带 token 访问一律 401。投放任务执行目前仅完成本地状态机与凭据校验，不调用平台真实 API。

SEO/GEO 任务与 AI 分析默认走本地模型（`mode=local`），执行结果与耗时落任务表（`status=success|failed`）；页面与媒体支持 `content_level`（L1~L4）数据分级。

站内预览（`/crawl`）是 P3 内置浏览器的后端能力：仅允许抓取站点自身同域地址，跨域、内网与保留地址（10.x / 192.168.x / 169.254.x / 元数据地址）一律拒绝，不支持 http/https 以外的协议；单次读取上限 512KB、超时 10s、不跟随跨域跳转。返回标题、描述、H1/H2、正文字数、canonical、og:title 与 `ok|warn|error` 三级 SEO 诊断。

## 商业化（`/api/v1/commercial`，权限模块 `commercial`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/commercial/overview` | 商业化总览（套餐 / 授权 / 订单 / 收入 / 用量告警 / 上架门槛清单） |
| GET | `/api/v1/commercial/plans` | 套餐列表 |
| POST | `/api/v1/commercial/plans` | 新建套餐 |
| POST | `/api/v1/commercial/plans/seed` | 重建内置套餐（社区版 / 专业版 / 旗舰版 / SaaS 订阅） |
| PATCH | `/api/v1/commercial/plans/{plan_id}` | 修改套餐 |
| DELETE | `/api/v1/commercial/plans/{plan_id}` | 删除套餐（已签发授权的套餐不可删） |
| GET | `/api/v1/commercial/licenses` | 授权列表 |
| POST | `/api/v1/commercial/licenses` | 签发授权证书（自动写入数字签名） |
| POST | `/api/v1/commercial/licenses/{license_id}/activate` | 激活授权（绑定机器码） |
| POST | `/api/v1/commercial/licenses/{license_id}/renew` | 续期授权并重算签名 |
| POST | `/api/v1/commercial/licenses/{license_id}/revoke` | 吊销授权 |
| POST | `/api/v1/commercial/license/verify` | 校验授权（签名 / 状态 / 有效期 / 机器码四重校验） |
| GET | `/api/v1/commercial/events` | 授权事件留痕（签发 / 激活 / 续期 / 吊销 / 校验失败） |
| GET | `/api/v1/commercial/orders` | 订单列表 |
| POST | `/api/v1/commercial/orders` | 创建订单 |
| POST | `/api/v1/commercial/orders/{order_id}/pay` | 订单支付（成功后自动签发授权） |
| POST | `/api/v1/commercial/orders/{order_id}/cancel` | 取消订单 |
| GET | `/api/v1/commercial/usage` | 用量列表（可按账期过滤） |
| POST | `/api/v1/commercial/usage` | 登记 / 更新用量（自动判定告警与超额） |
| GET | `/api/v1/commercial/entitlement` | 当前租户权益（生效授权 + 套餐限额 + 本月用量对账） |

权限与准入：整模块由 `require_module_access("commercial")` 统一把关，读写权限点 `commercial:view`（查询类）/ `commercial:manage`（签发 / 修改 / 删除类）；自动登记的两个权限点已随 P10 写入 `oc_permission`。

凭据与签名安全：授权证书签名使用 HMAC-SHA256，签名内容为授权码 / 套餐 / 主体 / 机器码 / 有效期等字段的规范化串，签名值随授权落库，任何响应不返回签名密钥；`license/verify` 支持离线复核，签名不匹配、状态非法、超期、机器码不符四类情况一律返回 `valid=false` 并写明 `message`，事件同步写入 `oc_com_license_event`。订单支付为本地状态机流转（支付成功后签发授权），不接第三方支付网关，不涉及真实扣款。

## 约定

- 新增业务域：在 `app/api/v1/endpoints/` 下新建模块，并在 `app/api/v1/router.py` 注册。
- 分页参数统一为 `page`（从 1 开始）与 `page_size`（默认 20）。
- 时间字段统一使用 ISO 8601 带时区格式。
*（内容由AI生成，仅供参考）*

## 接口全量索引（v0.10.0，自动生成）

> 由 `docs/openapi.json` 实时导出：共 220 个操作 / 161 条路径；215 个数据模型。接口契约以 OpenAPI 为准。
### ai（25）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/ai/config` | AI 配置与状态 |
| GET | `/api/v1/ai/statistics` | AI 治理概览 |
| POST | `/api/v1/ai/level/rules/seed` | 写入内置分级规则 |
| GET | `/api/v1/ai/level/rules` | 分级规则列表 |
| POST | `/api/v1/ai/level/rules` | 新建分级规则 |
| PUT | `/api/v1/ai/level/rules/{rule_id}` | 更新分级规则 |
| DELETE | `/api/v1/ai/level/rules/{rule_id}` | 删除分级规则 |
| POST | `/api/v1/ai/level/grade` | 触发数据分级 |
| GET | `/api/v1/ai/level/records` | 分级结果列表 |
| GET | `/api/v1/ai/level/object` | 单对象实时定级 |
| POST | `/api/v1/ai/analyze` | 发起 AI 分析 |
| GET | `/api/v1/ai/analyses` | 分析历史 |
| GET | `/api/v1/ai/analyses/{analysis_id}` | 分析详情 |
| GET | `/api/v1/ai/analyses/{analysis_id}/insights` | 分析洞察 |
| GET | `/api/v1/ai/insights` | 洞察列表 |
| POST | `/api/v1/ai/insights/route` | 批量路由洞察 |
| POST | `/api/v1/ai/policies/seed` | 写入内置权限策略 |
| GET | `/api/v1/ai/policies` | 权限策略列表 |
| PUT | `/api/v1/ai/policies/{policy_id}` | 更新权限策略 |
| GET | `/api/v1/ai/policies/decide` | 权限判定试算 |
| GET | `/api/v1/ai/actions` | 处置单列表 |
| POST | `/api/v1/ai/actions/{action_id}/approve` | 人工审批通过 |
| POST | `/api/v1/ai/actions/{action_id}/reject` | 人工驳回 |
| POST | `/api/v1/ai/actions/{action_id}/execute` | 人工执行处置 |
| GET | `/api/v1/ai/audit` | 审计日志 |

### audit（6）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/audit/logs` | 审计日志查询 |
| GET | `/api/v1/audit/stats` | 审计统计 |
| GET | `/api/v1/audit/event-types` | 审计事件类型 |
| POST | `/api/v1/audit/purge` | 清理过期审计日志 |
| GET | `/api/v1/audit/security-log/levels` | 安全日志分级字典 |
| GET | `/api/v1/audit/security-log/entries` | 安全日志分级查询 |

### auth（5）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 用户登录 |
| POST | `/api/v1/auth/logout` | 退出登录 |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| GET | `/api/v1/auth/profile` | 个人资料 |
| POST | `/api/v1/auth/password` | 修改密码 |

### collect/采集调度（12）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/collect/modes` | List Modes |
| GET | `/api/v1/collect/sources` | List Sources |
| GET | `/api/v1/collect/overview` | Overview |
| GET | `/api/v1/collect/tasks` | List Tasks |
| POST | `/api/v1/collect/tasks` | Create Task |
| GET | `/api/v1/collect/tasks/{task_id}` | Get Task |
| PUT | `/api/v1/collect/tasks/{task_id}` | Update Task |
| DELETE | `/api/v1/collect/tasks/{task_id}` | Delete Task |
| POST | `/api/v1/collect/tasks/{task_id}/run` | Run Task |
| POST | `/api/v1/collect/tasks/{task_id}/toggle` | Toggle Task |
| POST | `/api/v1/collect/scheduler/scan` | Scan Due |
| GET | `/api/v1/collect/runs` | List Runs |

### commercial/商业化（20）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/commercial/overview` | 商业化总览（含上架门槛清单） |
| POST | `/api/v1/commercial/plans/seed` | 重建内置套餐 |
| GET | `/api/v1/commercial/plans` | 套餐列表 |
| POST | `/api/v1/commercial/plans` | 新建套餐 |
| PATCH | `/api/v1/commercial/plans/{plan_id}` | 修改套餐 |
| DELETE | `/api/v1/commercial/plans/{plan_id}` | 删除套餐 |
| GET | `/api/v1/commercial/licenses` | 授权列表 |
| POST | `/api/v1/commercial/licenses` | 签发授权证书 |
| POST | `/api/v1/commercial/licenses/{license_id}/activate` | 激活授权（绑定机器码） |
| POST | `/api/v1/commercial/licenses/{license_id}/renew` | 续期授权 |
| POST | `/api/v1/commercial/licenses/{license_id}/revoke` | 吊销授权 |
| POST | `/api/v1/commercial/license/verify` | 校验授权（四重校验） |
| GET | `/api/v1/commercial/events` | 授权事件留痕 |
| GET | `/api/v1/commercial/orders` | 订单列表 |
| POST | `/api/v1/commercial/orders` | 创建订单 |
| POST | `/api/v1/commercial/orders/{order_id}/pay` | 订单支付（自动签发授权） |
| POST | `/api/v1/commercial/orders/{order_id}/cancel` | 取消订单 |
| GET | `/api/v1/commercial/usage` | 用量列表 |
| POST | `/api/v1/commercial/usage` | 登记 / 更新用量 |
| GET | `/api/v1/commercial/entitlement` | 当前租户权益 |

### datasources（5）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/datasources` | 数据源列表 |
| POST | `/api/v1/datasources` | 新建数据源 |
| GET | `/api/v1/datasources/{code}` | 数据源详情 |
| PUT | `/api/v1/datasources/{code}` | 更新数据源 |
| DELETE | `/api/v1/datasources/{code}` | 删除数据源 |

### digital-human（22）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/digital-human/overview` | 数字人总览（形象/音色/项目计数、成功率、引擎状态） |
| GET | `/api/v1/digital-human/engines` | 生成引擎可用性探测（脚本/配音/驱动/合成） |
| GET | `/api/v1/digital-human/avatars` | 形象库列表 |
| POST | `/api/v1/digital-human/avatars` | 新建数字人形象 |
| PATCH | `/api/v1/digital-human/avatars/{avatar_id}` | 修改数字人形象 |
| DELETE | `/api/v1/digital-human/avatars/{avatar_id}` | 删除数字人形象 |
| GET | `/api/v1/digital-human/voices` | 音色库列表 |
| POST | `/api/v1/digital-human/voices` | 新建音色 |
| PATCH | `/api/v1/digital-human/voices/{voice_id}` | 修改音色 |
| DELETE | `/api/v1/digital-human/voices/{voice_id}` | 删除音色 |
| GET | `/api/v1/digital-human/projects` | 生成项目列表 |
| POST | `/api/v1/digital-human/projects` | 新建生成项目（自动绑定默认工作流） |
| GET | `/api/v1/digital-human/projects/{project_id}` | 项目详情（含四阶段任务留痕） |
| PATCH | `/api/v1/digital-human/projects/{project_id}` | 修改项目 / 手工编辑口播稿 |
| DELETE | `/api/v1/digital-human/projects/{project_id}` | 删除生成项目 |
| POST | `/api/v1/digital-human/projects/{project_id}/script` | 生成/重写口播稿（含分镜） |
| POST | `/api/v1/digital-human/projects/{project_id}/generate` | 一键生成（脚本->配音->驱动->合成） |
| GET | `/api/v1/digital-human/workflows` | 工作流模板列表 |
| POST | `/api/v1/digital-human/workflows` | 新建工作流模板 |
| PATCH | `/api/v1/digital-human/workflows/{workflow_id}` | 修改工作流模板 |
| DELETE | `/api/v1/digital-human/workflows/{workflow_id}` | 删除工作流模板（默认模板不可删） |
| POST | `/api/v1/digital-human/workflows/{workflow_id}/run` | 按指定工作流执行一键生成 |

### ingest（7）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/ingest/upload` | 上传数据文件 |
| GET | `/api/v1/ingest/files` | 可导入文件清单 |
| POST | `/api/v1/ingest/samples/{file_name}/load` | 载入示例文件 |
| POST | `/api/v1/ingest/preview` | 预览文件结构 |
| POST | `/api/v1/ingest/run` | 执行导入 |
| GET | `/api/v1/ingest/tasks` | 导入任务列表 |
| GET | `/api/v1/ingest/tasks/{task_id}` | 导入任务详情 |

### learning（20）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/learning/overview` | 学习进化总览（采纳率/成功率/权重 Top/案例与实验计数） |
| POST | `/api/v1/learning/feedbacks` | 登记决策反馈（采纳与否 + 实际效果） |
| GET | `/api/v1/learning/feedbacks` | 反馈列表 |
| GET | `/api/v1/learning/feedbacks/{fid}` | 反馈详情 |
| PATCH | `/api/v1/learning/feedbacks/{fid}` | 补录/修正实际效果 |
| GET | `/api/v1/learning/weights` | 策略权重列表 |
| POST | `/api/v1/learning/weights/recompute` | 触发策略权重自调（可指定策略，不传则全量） |
| POST | `/api/v1/learning/cases` | 新建经验案例 |
| GET | `/api/v1/learning/cases` | 经验案例列表 |
| POST | `/api/v1/learning/cases/from-feedback` | 由反馈一键沉淀为经验案例 |
| GET | `/api/v1/learning/cases/{cid}` | 案例详情 |
| PATCH | `/api/v1/learning/cases/{cid}` | 修改案例 |
| POST | `/api/v1/learning/cases/{cid}/hit` | 标记案例被命中引用 |
| POST | `/api/v1/learning/cases/{cid}/archive` | 归档案例 |
| POST | `/api/v1/learning/experiments` | 新建 A/B 对照实验 |
| GET | `/api/v1/learning/experiments` | 实验列表 |
| GET | `/api/v1/learning/experiments/{eid}` | 实验详情 |
| PATCH | `/api/v1/learning/experiments/{eid}` | 修改实验 |
| POST | `/api/v1/learning/experiments/{eid}/samples` | 登记一次对照样本 |
| POST | `/api/v1/learning/experiments/{eid}/finish` | 结项并判定胜出方案 |

### marketing/营销渠道（15）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/marketing/channel-types` | 渠道类型目录 |
| GET | `/api/v1/marketing/overview` | 渠道接入概览 |
| POST | `/api/v1/marketing/channels` | 新增渠道账号 |
| GET | `/api/v1/marketing/channels` | 渠道列表 |
| PUT | `/api/v1/marketing/channels/{channel_id}` | 编辑渠道账号 |
| DELETE | `/api/v1/marketing/channels/{channel_id}` | 删除渠道账号 |
| POST | `/api/v1/marketing/channels/{channel_id}/authorize` | 写入凭据并授权 |
| POST | `/api/v1/marketing/channels/{channel_id}/revoke` | 撤销授权 |
| POST | `/api/v1/marketing/channels/{channel_id}/sync` | 触发渠道数据同步 |
| POST | `/api/v1/marketing/campaigns` | 创建投放任务 |
| GET | `/api/v1/marketing/campaigns` | 投放任务列表 |
| PUT | `/api/v1/marketing/campaigns/{campaign_id}` | 编辑投放任务 |
| DELETE | `/api/v1/marketing/campaigns/{campaign_id}` | 删除投放任务 |
| POST | `/api/v1/marketing/campaigns/{campaign_id}/execute` | 执行投放任务（本地演练） |
| GET | `/api/v1/marketing/events` | 渠道事件日志 |

### metrics（11）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/metrics/overview` | 指标总览 |
| GET | `/api/v1/metrics/dim-keys` | 可用维度键 |
| GET | `/api/v1/metrics/compass` | 全景罗盘 |
| GET | `/api/v1/metrics` | 指标列表 |
| POST | `/api/v1/metrics` | 新建指标 |
| GET | `/api/v1/metrics/{code}` | 指标详情 |
| PUT | `/api/v1/metrics/{code}` | 更新指标 |
| DELETE | `/api/v1/metrics/{code}` | 删除指标 |
| POST | `/api/v1/metrics/{code}/values` | 写入指标值（覆盖） |
| GET | `/api/v1/metrics/{code}/values` | 查询指标值明细 |
| GET | `/api/v1/metrics/{code}/trend` | 指标趋势 |

### model（13）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/model/hardware` | 本机硬件探测（CPU/内存/GPU 显存/磁盘/网络出口） |
| GET | `/api/v1/model/recommend` | 按显存分档推荐可跑的本地模型量级与接入后端 |
| GET | `/api/v1/model/overview` | 模型中心概览 |
| GET | `/api/v1/model/endpoints` | 接入端点列表 |
| POST | `/api/v1/model/endpoints` | 新增接入端点 |
| GET | `/api/v1/model/endpoints/{endpoint_id}` | 端点详情 |
| PUT | `/api/v1/model/endpoints/{endpoint_id}` | 修改接入端点 |
| DELETE | `/api/v1/model/endpoints/{endpoint_id}` | 删除接入端点 |
| POST | `/api/v1/model/test` | 连通性自检（支持未保存配置） |
| POST | `/api/v1/model/endpoints/{endpoint_id}/test` | 对已保存端点做连通性自检 |
| POST | `/api/v1/model/endpoints/{endpoint_id}/activate` | 设为当前生效端点 |
| POST | `/api/v1/model/endpoints/{endpoint_id}/sync-env` | 生效端点回写 .env 持久化 |
| POST | `/api/v1/model/apply` | 一键接入（落库 + 自检 + 生效） |

### ops/运营参谋（33）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/ops/websites` | 创建网站/网店 |
| GET | `/api/v1/ops/websites` | 网站列表 |
| GET | `/api/v1/ops/websites/{website_id}` | 网站详情 |
| PUT | `/api/v1/ops/websites/{website_id}` | 更新网站/网店 |
| DELETE | `/api/v1/ops/websites/{website_id}` | 删除网站/网店 |
| POST | `/api/v1/ops/websites/{website_id}/pages` | 创建页面/文章 |
| GET | `/api/v1/ops/websites/{website_id}/pages` | 页面列表 |
| GET | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 页面详情 |
| PUT | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 更新页面/文章 |
| DELETE | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 删除页面/文章 |
| POST | `/api/v1/ops/websites/{website_id}/crawl` | 站内预览与可控抓取 |
| POST | `/api/v1/ops/websites/{website_id}/products` | 创建商品 |
| GET | `/api/v1/ops/websites/{website_id}/products` | 商品列表 |
| PUT | `/api/v1/ops/websites/{website_id}/products/{product_id}` | 更新商品 |
| DELETE | `/api/v1/ops/websites/{website_id}/products/{product_id}` | 删除商品 |
| POST | `/api/v1/ops/websites/{website_id}/seo` | 执行 SEO 任务 |
| GET | `/api/v1/ops/websites/{website_id}/seo` | SEO 任务列表 |
| POST | `/api/v1/ops/websites/{website_id}/geo` | 执行 GEO 任务 |
| GET | `/api/v1/ops/websites/{website_id}/geo` | GEO 任务列表 |
| POST | `/api/v1/ops/websites/{website_id}/ai-config` | 创建/更新 AI 配置 |
| GET | `/api/v1/ops/websites/{website_id}/ai-config` | AI 配置列表 |
| PUT | `/api/v1/ops/ai-configs/{config_id}` | 更新 AI 配置 |
| POST | `/api/v1/ops/websites/{website_id}/media` | 上传媒体 |
| GET | `/api/v1/ops/websites/{website_id}/media` | 媒体列表 |
| GET | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 媒体详情 |
| PUT | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 更新媒体 |
| DELETE | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 删除媒体 |
| POST | `/api/v1/ops/websites/{website_id}/social` | 创建自媒体发布 |
| POST | `/api/v1/ops/websites/{website_id}/social/optimize` | AI 优化自媒体内容 |
| POST | `/api/v1/ops/websites/{website_id}/social/schedule` | AI 智能安排发布时间 |
| POST | `/api/v1/ops/websites/{website_id}/social/analytics` | AI 分析自媒体数据 |
| POST | `/api/v1/ops/ai/analyze` | AI 全面运营分析 |
| POST | `/api/v1/ops/ai/generate-content` | AI 生成/改写内容 |

### rbac（11）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/rbac/users` | 用户列表 |
| POST | `/api/v1/rbac/users` | 新建用户 |
| GET | `/api/v1/rbac/users/{user_id}` | 用户详情 |
| PATCH | `/api/v1/rbac/users/{user_id}` | 更新用户 |
| DELETE | `/api/v1/rbac/users/{user_id}` | 删除用户 |
| POST | `/api/v1/rbac/users/{user_id}/reset-password` | 重置用户密码 |
| GET | `/api/v1/rbac/roles` | 角色列表 |
| POST | `/api/v1/rbac/roles` | 新建角色 |
| PATCH | `/api/v1/rbac/roles/{role_id}` | 更新角色 |
| DELETE | `/api/v1/rbac/roles/{role_id}` | 删除角色 |
| GET | `/api/v1/rbac/permissions` | 权限点列表 |

### storage（9）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/storage/overview` | 存储适配层总览 |
| POST | `/api/v1/storage/bootstrap` | 幂等初始化存储适配层 |
| GET | `/api/v1/storage/routing/rules` | 路由规则列表 |
| POST | `/api/v1/storage/routing/identify` | 识别数据类型并给出目标存储引擎 |
| GET | `/api/v1/storage/search` | 全文检索 |
| POST | `/api/v1/storage/search/reindex` | 重建全文检索索引 |
| POST | `/api/v1/storage/backfill` | 回填存量指标值到时序分区表 |
| POST | `/api/v1/storage/consistency/run` | 执行跨存储一致性对账 |
| GET | `/api/v1/storage/consistency/recent` | 最近对账记录 |

### system（4）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/system/health` | Health |
| GET | `/api/v1/system/info` | Info |
| GET | `/api/v1/system/security-overview` | 安全配置概览 |
| GET | `/health` | Health |

### tenants（2）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/tenants` | 租户列表 |
| POST | `/api/v1/tenants` | 新建租户 |

