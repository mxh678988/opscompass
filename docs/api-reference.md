# 运营智脑（自动生成）

> 适用产品：运营智脑（让数据自动做出最优决策）
>
> 源快照：`docs/openapi.json`（v0.12.0）｜ 生成时间：2026-10-12 10:57 中国标准时间
> 统一前缀：`/api/v1` ｜ 在线文档：`http://localhost:8000/docs`（Swagger UI）
> **本文件由脚本自动生成，禁止手改**；接口变更后运行 `python scripts/gen_api_docs.py`。

共 144 条路径。

## ai

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/ai/actions` | 处置单列表 |
| POST | `/api/v1/ai/actions/{action_id}/approve` | 人工审批通过 |
| PUT | `/api/v1/ai/actions/{action_id}/decision-level` | 调整决策分级 |
| POST | `/api/v1/ai/actions/{action_id}/execute` | 人工执行处置 |
| POST | `/api/v1/ai/actions/{action_id}/reject` | 人工驳回 |
| POST | `/api/v1/ai/actions/{action_id}/restore` | 还原叫停决策 |
| POST | `/api/v1/ai/actions/{action_id}/revoke` | 一键叫停/撤销 |
| GET | `/api/v1/ai/actions/{action_id}/trace` | 决策全过程追溯 |
| GET | `/api/v1/ai/analyses` | 分析历史 |
| GET | `/api/v1/ai/analyses/{analysis_id}` | 分析详情 |
| GET | `/api/v1/ai/analyses/{analysis_id}/insights` | 分析洞察 |
| POST | `/api/v1/ai/analyze` | 发起 AI 分析 |
| GET | `/api/v1/ai/audit` | 审计日志 |
| GET | `/api/v1/ai/config` | AI 配置与状态 |
| GET | `/api/v1/ai/decisions/board` | 决策分级授权看板 |
| GET | `/api/v1/ai/insights` | 洞察列表 |
| POST | `/api/v1/ai/insights/route` | 批量路由洞察 |
| POST | `/api/v1/ai/level/grade` | 触发数据分级 |
| GET | `/api/v1/ai/level/object` | 单对象实时定级 |
| GET | `/api/v1/ai/level/records` | 分级结果列表 |
| GET | `/api/v1/ai/level/rules` | 分级规则列表 |
| POST | `/api/v1/ai/level/rules` | 新建分级规则 |
| POST | `/api/v1/ai/level/rules/seed` | 写入内置分级规则 |
| PUT | `/api/v1/ai/level/rules/{rule_id}` | 更新分级规则 |
| DELETE | `/api/v1/ai/level/rules/{rule_id}` | 删除分级规则 |
| GET | `/api/v1/ai/policies` | 权限策略列表 |
| GET | `/api/v1/ai/policies/decide` | 权限判定试算 |
| POST | `/api/v1/ai/policies/seed` | 写入内置权限策略 |
| PUT | `/api/v1/ai/policies/{policy_id}` | 更新权限策略 |
| GET | `/api/v1/ai/statistics` | AI 治理概览 |

### GET `/api/v1/ai/actions`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `status` | query | 否 | object | pending/auto_executed/approved/rejected/executed/failed |
| `handler` | query | 否 | object | ai / human |
| `data_level` | query | 否 | object | L1-L4 |
| `limit` | query | 否 | integer |  |
| `offset` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_ActionOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/actions/{action_id}/approve`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `action_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ActionDecisionIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ActionOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ai/actions/{action_id}/decision-level`

把处置单在 仅用户决策 / 需用户授权 / 智能体自主 三级之间调整，来源记为 manual。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `action_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ActionDecisionLevelIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ActionOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/actions/{action_id}/execute`

登记式执行：记录处置结论与结果并留痕，不对生产数据做破坏性变更。

需审批的处置单必须先 approve 再 execute。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `action_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ActionDecisionIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ActionOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/actions/{action_id}/reject`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `action_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ActionDecisionIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ActionOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/actions/{action_id}/restore`

还原被误叫停的决策，回到撤销前状态。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `action_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ActionDecisionIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ActionOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/actions/{action_id}/revoke`

用户一键叫停 AI 决策：立即失效、停止引用并全过程留痕。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `action_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ActionRevokeIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ActionOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/actions/{action_id}/trace`

单条处置单全链路留痕：洞察生成 → 分级路由 → 审批/执行 → 撤销/还原。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `action_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_DecisionTraceOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/analyses`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `limit` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_AnalysisOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/analyses/{analysis_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `analysis_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/analyses/{analysis_id}/insights`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `analysis_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_InsightOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/analyze`

采集数据快照 → 调用模型（api/local）→ 产出洞察建议 → 按权限自动路由处置单。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AnalysisRunIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/audit`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `limit` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_AuditOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/config`

展示 AI 双模式（api 云端 / local 本地）配置、当前模式与实际可用性。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `probe` | query | 否 | boolean | 是否实际探测模型可用性 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_AiConfigOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/decisions/board`

三级决策授权概览：各级数量、待办、已叫停、自主执行与演练模式计数。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_DecisionBoardOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/insights`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `status` | query | 否 | object | new/routed/resolved/dismissed |
| `severity` | query | 否 | object | info/warning/critical |
| `limit` | query | 否 | integer |  |
| `offset` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_InsightOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/insights/route`

把所有未路由洞察按权限矩阵生成处置单（权限内 AI 自动执行，其余转人工）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/level/grade`

规则引擎批量定级；use_ai=true 时额外调用大模型给出定级建议。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`GradeRunIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_GradeRunOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/level/object`

按规则实时判定单个对象的级别，并返回命中的规则与依据。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `object_type` | query | 是 | string | 对象类型：metric/metric_value/data_source/import_task/analysis/tenant |
| `object_id` | query | 是 | integer | 对象 ID |
| `persist` | query | 否 | boolean | 是否把结果写入分级记录 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/level/records`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `object_type` | query | 否 | object | metric/data_source/import_task |
| `level` | query | 否 | object | L1-L4 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_LevelRecordOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/level/rules`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_LevelRuleOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/level/rules`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`LevelRuleCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_LevelRuleOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/level/rules/seed`

幂等写入系统内置分级规则（已存在则跳过）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ai/level/rules/{rule_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `rule_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`LevelRuleUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_LevelRuleOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ai/level/rules/{rule_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `rule_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/policies`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_PolicyOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/policies/decide`

给定「数据级别 × 执行者 × 动作 × 严重度」试算是否放行、是否需复核/审批。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `data_level` | query | 是 | string | L1-L4 |
| `actor` | query | 否 | string | ai / human |
| `action_type` | query | 否 | string | 动作类型 |
| `severity` | query | 否 | string | info/warning/critical |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PolicyDecideOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ai/policies/seed`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ai/policies/{policy_id}`

调整策略的放行/复核/审批开关（配置变更，仅影响后续判定）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `policy_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`PolicyUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PolicyOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ai/statistics`

洞察 / 处置单 / AI 自动处置与人工待办的数量统计。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## audit

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/audit/event-types` | 审计事件类型 |
| GET | `/api/v1/audit/logs` | 审计日志查询 |
| POST | `/api/v1/audit/purge` | 清理过期审计日志 |
| GET | `/api/v1/audit/security-log/entries` | 安全日志分级查询 |
| GET | `/api/v1/audit/security-log/levels` | 安全日志分级字典 |
| GET | `/api/v1/audit/stats` | 审计统计 |

### GET `/api/v1/audit/event-types`

返回可用的事件类型枚举，供前端筛选器使用。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_str__` |

### GET `/api/v1/audit/logs`

分页查询审计日志，默认按时间倒序。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `event_type` | query | 否 | object | 事件类型 |
| `status` | query | 否 | object | 结果：success / failure |
| `username` | query | 否 | object | 操作人用户名（模糊） |
| `keyword` | query | 否 | object | 路径/动作/详情/IP 关键词 |
| `start_time` | query | 否 | object | 起始时间 ISO8601 |
| `end_time` | query | 否 | object | 结束时间 ISO8601 |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_AuditLogOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/audit/purge`

按 SECURITY_AUDIT_RETENTION_DAYS 清理历史日志（敏感操作）。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### GET `/api/v1/audit/security-log/entries`

按级别/事件筛选安全日志条目，并返回分级统计与最近高危事件。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `level` | query | 否 | object | 级别：INFO / WARNING / CRITICAL |
| `event_type` | query | 否 | object | 事件类型 |
| `days` | query | 否 | integer | 统计近 N 天 |
| `limit` | query | 否 | integer | 返回条数 |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/audit/security-log/levels`

返回级别定义、事件默认级别与当前分级配置，供前端筛选与说明展示。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### GET `/api/v1/audit/stats`

近 N 天审计概览：总量、按事件类型、按结果分布。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `days` | query | 否 | integer | 统计最近 N 天 |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_AuditStatsOut_` |
| 422 | Validation Error | `HTTPValidationError` |

## auth

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 用户登录 |
| POST | `/api/v1/auth/logout` | 退出登录 |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| POST | `/api/v1/auth/password` | 修改密码 |
| GET | `/api/v1/auth/profile` | 个人资料 |

### POST `/api/v1/auth/login`

账号密码登录，成功后返回 JWT 访问令牌。

**请求参数**

无

**请求体**

`LoginRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_TokenOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/auth/logout`

登出（JWT 无状态，仅记录审计日志并由前端清除令牌）。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### GET `/api/v1/auth/me`

返回当前登录用户信息与权限码。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### POST `/api/v1/auth/password`

修改当前用户密码。

**请求参数**

无

**请求体**

`PasswordChangeRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/auth/profile`

返回当前用户基础资料。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_UserOut_` |

## collect

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/collect/modes` | List Modes |
| GET | `/api/v1/collect/overview` | Overview |
| GET | `/api/v1/collect/runs` | List Runs |
| POST | `/api/v1/collect/scheduler/scan` | Scan Due |
| GET | `/api/v1/collect/sources` | List Sources |
| GET | `/api/v1/collect/tasks` | List Tasks |
| POST | `/api/v1/collect/tasks` | Create Task |
| GET | `/api/v1/collect/tasks/{task_id}` | Get Task |
| PUT | `/api/v1/collect/tasks/{task_id}` | Update Task |
| DELETE | `/api/v1/collect/tasks/{task_id}` | Delete Task |
| POST | `/api/v1/collect/tasks/{task_id}/run` | Run Task |
| POST | `/api/v1/collect/tasks/{task_id}/toggle` | Toggle Task |

### GET `/api/v1/collect/modes`

采集方式目录：三种方式的能力与目标格式说明。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_CollectModeOut__` |

### GET `/api/v1/collect/overview`

采集调度总览：任务态势、近 24 小时运行质量、执行趋势与最近记录。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectOverviewOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/collect/runs`

运行记录（可按任务、状态筛选）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `task_id` | query | 否 | object |  |
| `status` | query | 否 | object |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_CollectRunOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/collect/scheduler/scan`

立即扫描并执行到期任务（手动兜底调度，便于无后台线程环境使用）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/collect/sources`

可绑定的数据源下拉项。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_CollectSourceOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/collect/tasks`

采集任务列表（支持状态 / 方式 / 关键词筛选）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `status` | query | 否 | object | enabled/paused |
| `collect_mode` | query | 否 | object | csv/api/sql |
| `keyword` | query | 否 | object |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_CollectTaskOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/collect/tasks`

新建采集任务（interval 模式自动排期下次执行时间）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CollectTaskIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/collect/tasks/{task_id}`

采集任务详情。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/collect/tasks/{task_id}`

编辑采集任务（编码不可改；改动调度策略会重排下次执行时间）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CollectTaskUpdateIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/collect/tasks/{task_id}`

删除采集任务（运行记录随任务级联清理）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/collect/tasks/{task_id}/run`

手动执行一次采集，返回本次运行记录。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectRunOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/collect/tasks/{task_id}/toggle`

启用 / 暂停任务；启用时重排下次执行时间。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

## datasources

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/datasources` | 数据源列表 |
| POST | `/api/v1/datasources` | 新建数据源 |
| GET | `/api/v1/datasources/{code}` | 数据源详情 |
| PUT | `/api/v1/datasources/{code}` | 更新数据源 |
| DELETE | `/api/v1/datasources/{code}` | 删除数据源 |

### GET `/api/v1/datasources`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `keyword` | query | 否 | object |  |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_DataSourceOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/datasources`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`DataSourceCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_DataSourceOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/datasources/{code}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_DataSourceOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/datasources/{code}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`DataSourceUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_DataSourceOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/datasources/{code}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## ingest

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/ingest/files` | 可导入文件清单 |
| POST | `/api/v1/ingest/preview` | 预览文件结构 |
| POST | `/api/v1/ingest/run` | 执行导入 |
| POST | `/api/v1/ingest/samples/{file_name}/load` | 载入示例文件 |
| GET | `/api/v1/ingest/tasks` | 导入任务列表 |
| GET | `/api/v1/ingest/tasks/{task_id}` | 导入任务详情 |
| POST | `/api/v1/ingest/upload` | 上传数据文件 |

### GET `/api/v1/ingest/files`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ingest/preview`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`IngestPreviewIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_IngestPreviewOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ingest/run`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`IngestRunIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ImportTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ingest/samples/{file_name}/load`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `file_name` | path | 是 | string |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_UploadOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ingest/tasks`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_ImportTaskOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ingest/tasks/{task_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ImportTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ingest/upload`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`Body_upload_file_api_v1_ingest_upload_post`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_UploadOut_` |
| 422 | Validation Error | `HTTPValidationError` |

## learning

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/learning/cases` | 新建经验案例 |
| GET | `/api/v1/learning/cases` | 经验案例列表 |
| POST | `/api/v1/learning/cases/from-feedback` | 由反馈一键沉淀为经验案例 |
| GET | `/api/v1/learning/cases/{cid}` | 案例详情 |
| PATCH | `/api/v1/learning/cases/{cid}` | 修改案例 |
| POST | `/api/v1/learning/cases/{cid}/archive` | 归档案例 |
| POST | `/api/v1/learning/cases/{cid}/hit` | 标记案例被命中引用 |
| POST | `/api/v1/learning/experiments` | 新建 A/B 对照实验 |
| GET | `/api/v1/learning/experiments` | 实验列表 |
| GET | `/api/v1/learning/experiments/{eid}` | 实验详情 |
| PATCH | `/api/v1/learning/experiments/{eid}` | 修改实验 |
| POST | `/api/v1/learning/experiments/{eid}/finish` | 结项并判定胜出方案 |
| POST | `/api/v1/learning/experiments/{eid}/samples` | 登记一次对照样本 |
| POST | `/api/v1/learning/feedbacks` | 登记决策反馈（采纳与否 + 实际效果） |
| GET | `/api/v1/learning/feedbacks` | 反馈列表 |
| GET | `/api/v1/learning/feedbacks/{fid}` | 反馈详情 |
| PATCH | `/api/v1/learning/feedbacks/{fid}` | 补录/修正实际效果 |
| GET | `/api/v1/learning/overview` | 学习进化总览（采纳率/成功率/权重 Top/案例与实验计数） |
| GET | `/api/v1/learning/weights` | 策略权重列表 |
| POST | `/api/v1/learning/weights/recompute` | 触发策略权重自调（可指定策略，不传则全量） |

### POST `/api/v1/learning/cases`

**请求参数**

无

**请求体**

`CaseIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/learning/cases`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `keyword` | query | 否 | object | 标题/编号/场景/经验关键字 |
| `category` | query | 否 | object |  |
| `status` | query | 否 | object | draft/verified/archived |
| `page` | query | 否 | integer |  |
| `size` | query | 否 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/learning/cases/from-feedback`

**请求参数**

无

**请求体**

`CaseFromFeedbackIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/learning/cases/{cid}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `cid` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### PATCH `/api/v1/learning/cases/{cid}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `cid` | path | 是 | integer |  |

**请求体**

`CasePatch`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/learning/cases/{cid}/archive`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `cid` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/learning/cases/{cid}/hit`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `cid` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/learning/experiments`

**请求参数**

无

**请求体**

`ExperimentIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/learning/experiments`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `keyword` | query | 否 | object | 实验名称/编号关键字 |
| `status` | query | 否 | object | draft/running/finished/stopped |
| `page` | query | 否 | integer |  |
| `size` | query | 否 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/learning/experiments/{eid}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `eid` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### PATCH `/api/v1/learning/experiments/{eid}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `eid` | path | 是 | integer |  |

**请求体**

`ExperimentPatch`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/learning/experiments/{eid}/finish`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `eid` | path | 是 | integer |  |

**请求体**

`ExperimentFinishIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/learning/experiments/{eid}/samples`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `eid` | path | 是 | integer |  |

**请求体**

`ExperimentRecordIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/learning/feedbacks`

**请求参数**

无

**请求体**

`FeedbackIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/learning/feedbacks`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `keyword` | query | 否 | object | 策略编码/动作类型/说明关键字 |
| `decision` | query | 否 | object | adopted/partial/rejected/ignored |
| `outcome` | query | 否 | object | success/neutral/fail/unknown |
| `policy_code` | query | 否 | object | 策略编码 |
| `page` | query | 否 | integer |  |
| `size` | query | 否 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/learning/feedbacks/{fid}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `fid` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### PATCH `/api/v1/learning/feedbacks/{fid}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `fid` | path | 是 | integer |  |

**请求体**

`FeedbackPatch`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/learning/overview`

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### GET `/api/v1/learning/weights`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `keyword` | query | 否 | object | 策略编码/名称关键字 |
| `page` | query | 否 | integer |  |
| `size` | query | 否 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/learning/weights/recompute`

**请求参数**

无

**请求体**

`WeightAdjustIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## marketing

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/marketing/campaigns` | 创建投放任务 |
| GET | `/api/v1/marketing/campaigns` | 投放任务列表 |
| PUT | `/api/v1/marketing/campaigns/{campaign_id}` | 编辑投放任务 |
| DELETE | `/api/v1/marketing/campaigns/{campaign_id}` | 删除投放任务 |
| POST | `/api/v1/marketing/campaigns/{campaign_id}/execute` | 执行投放任务（本地演练） |
| GET | `/api/v1/marketing/channel-types` | 渠道类型目录 |
| POST | `/api/v1/marketing/channels` | 新增渠道账号 |
| GET | `/api/v1/marketing/channels` | 渠道列表 |
| PUT | `/api/v1/marketing/channels/{channel_id}` | 编辑渠道账号 |
| DELETE | `/api/v1/marketing/channels/{channel_id}` | 删除渠道账号 |
| POST | `/api/v1/marketing/channels/{channel_id}/authorize` | 写入凭据并授权 |
| POST | `/api/v1/marketing/channels/{channel_id}/revoke` | 撤销授权 |
| POST | `/api/v1/marketing/channels/{channel_id}/sync` | 触发渠道数据同步 |
| GET | `/api/v1/marketing/events` | 渠道事件日志 |
| GET | `/api/v1/marketing/overview` | 渠道接入概览 |

### POST `/api/v1/marketing/campaigns`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CampaignCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ChannelCampaignOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/campaigns`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | query | 否 | object | 按渠道筛选 |
| `status` | query | 否 | object | 按状态筛选 |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_ChannelCampaignOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/marketing/campaigns/{campaign_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `campaign_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CampaignUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ChannelCampaignOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/marketing/campaigns/{campaign_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `campaign_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/campaigns/{campaign_id}/execute`

执行投放编排。

当前版本为接入骨架：仅校验渠道授权状态并记录演练结果（simulated=true），
未调用任何平台真实 API，因此不写入曝光/点击/转化等平台回传指标。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `campaign_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ChannelCampaignOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/channel-types`

返回可接入的平台类型、授权方式与能力，并统计本租户已接入/已授权数量。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_ChannelTypeOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/channels`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ChannelCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/channels`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_type` | query | 否 | object | 按平台类型筛选 |
| `status` | query | 否 | object | 按授权状态筛选 |
| `keyword` | query | 否 | object | 名称/账号模糊匹配 |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_MarketingChannelOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/marketing/channels/{channel_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ChannelUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/marketing/channels/{channel_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/channels/{channel_id}/authorize`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AuthorizePayload`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/channels/{channel_id}/revoke`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/channels/{channel_id}/sync`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/events`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | query | 否 | object | 按渠道筛选 |
| `limit` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_ChannelEventOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/overview`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingOverviewOut_` |
| 422 | Validation Error | `HTTPValidationError` |

## metrics

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/metrics` | 指标列表 |
| POST | `/api/v1/metrics` | 新建指标 |
| GET | `/api/v1/metrics/compass` | 全景罗盘 |
| GET | `/api/v1/metrics/dim-keys` | 可用维度键 |
| GET | `/api/v1/metrics/overview` | 指标总览 |
| GET | `/api/v1/metrics/{code}` | 指标详情 |
| PUT | `/api/v1/metrics/{code}` | 更新指标 |
| DELETE | `/api/v1/metrics/{code}` | 删除指标 |
| GET | `/api/v1/metrics/{code}/trend` | 指标趋势 |
| POST | `/api/v1/metrics/{code}/values` | 写入指标值（覆盖） |
| GET | `/api/v1/metrics/{code}/values` | 查询指标值明细 |

### GET `/api/v1/metrics`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `keyword` | query | 否 | object | 按编码/名称模糊搜索 |
| `status` | query | 否 | object | draft/online/offline |
| `category_id` | query | 否 | object |  |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_MetricOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/metrics`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`MetricCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MetricOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/metrics/compass`

全景罗盘：全部上线指标的整体值、环比、趋势，叠加维度拆解与占比。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `granularity` | query | 否 | string | 统计粒度 hour/day/week/month |
| `dim_key` | query | 否 | object | 拆解维度键，如 channel；不传只返回整体口径 |
| `codes` | query | 否 | object | 指标编码，多个用逗号分隔；不传返回全部上线指标 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CompassOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/metrics/dim-keys`

返回已接入数据中出现过的维度键，供全景罗盘维度切换使用。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_str__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/metrics/overview`

返回各指标最新值及环比，供首页指标卡消费。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `granularity` | query | 否 | string | 统计粒度 hour/day/week/month |
| `codes` | query | 否 | object | 指标编码，多个用逗号分隔；不传返回全部上线指标 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_OverviewOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/metrics/{code}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MetricOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/metrics/{code}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`MetricUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MetricOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/metrics/{code}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/metrics/{code}/trend`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `start` | query | 否 | object | 开始时间，ISO8601 |
| `end` | query | 否 | object | 结束时间，ISO8601 |
| `granularity` | query | 否 | string | 统计粒度 hour/day/week/month |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_TrendOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/metrics/{code}/values`

批量写入。同一「时间+粒度+维度」重复写入即为覆盖。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`MetricValueBatchIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/metrics/{code}/values`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `code` | path | 是 | string |  |
| `start` | query | 否 | object | 开始时间，ISO8601 |
| `end` | query | 否 | object | 结束时间，ISO8601 |
| `granularity` | query | 否 | object | 统计粒度 |
| `limit` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_MetricValueOut__` |
| 422 | Validation Error | `HTTPValidationError` |

## model

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/model/apply` | 一键接入（落库 + 自检 + 生效） |
| GET | `/api/v1/model/endpoints` | 接入端点列表 |
| POST | `/api/v1/model/endpoints` | 新增接入端点 |
| GET | `/api/v1/model/endpoints/{endpoint_id}` | 端点详情 |
| PUT | `/api/v1/model/endpoints/{endpoint_id}` | 修改接入端点 |
| DELETE | `/api/v1/model/endpoints/{endpoint_id}` | 删除接入端点 |
| POST | `/api/v1/model/endpoints/{endpoint_id}/activate` | 设为当前生效端点 |
| POST | `/api/v1/model/endpoints/{endpoint_id}/sync-env` | 生效端点回写 .env 持久化 |
| POST | `/api/v1/model/endpoints/{endpoint_id}/test` | 对已保存端点做连通性自检 |
| GET | `/api/v1/model/hardware` | 本机硬件探测（CPU/内存/GPU 显存/磁盘/网络出口） |
| GET | `/api/v1/model/overview` | 模型中心概览 |
| GET | `/api/v1/model/recommend` | 按显存分档推荐可跑的本地模型量级与接入后端 |
| POST | `/api/v1/model/test` | 连通性自检（支持未保存配置） |

### POST `/api/v1/model/apply`

**请求参数**

无

**请求体**

`ApplyIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/model/endpoints`

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### POST `/api/v1/model/endpoints`

**请求参数**

无

**请求体**

`EndpointIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/model/endpoints/{endpoint_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `endpoint_id` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/model/endpoints/{endpoint_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `endpoint_id` | path | 是 | integer |  |

**请求体**

`EndpointPatch`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/model/endpoints/{endpoint_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `endpoint_id` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/model/endpoints/{endpoint_id}/activate`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `endpoint_id` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/model/endpoints/{endpoint_id}/sync-env`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `endpoint_id` | path | 是 | integer |  |

**请求体**

`SyncIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/model/endpoints/{endpoint_id}/test`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `endpoint_id` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/model/hardware`

CPU / 内存 / GPU 与显存 / 磁盘 / 网络出口；探测不可用时返回降级原因。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `refresh` | query | 否 | boolean | 是否重新探测；false 时优先复用宿主机快照 |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/model/overview`

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### GET `/api/v1/model/recommend`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `include_hardware` | query | 否 | boolean | 是否附带回硬件探测原始结果 |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/model/test`

**请求参数**

无

**请求体**

`EndpointTestIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## ops

| 方法 | 路径 | 说明 |
|---|---|---|
| PUT | `/api/v1/ops/ai-configs/{config_id}` | 更新 AI 配置 |
| POST | `/api/v1/ops/ai/analyze` | AI 全面运营分析 |
| POST | `/api/v1/ops/ai/generate-content` | AI 生成/改写内容 |
| POST | `/api/v1/ops/websites` | 创建网站/网店 |
| GET | `/api/v1/ops/websites` | 网站列表 |
| GET | `/api/v1/ops/websites/{website_id}` | 网站详情 |
| PUT | `/api/v1/ops/websites/{website_id}` | 更新网站/网店 |
| DELETE | `/api/v1/ops/websites/{website_id}` | 删除网站/网店 |
| POST | `/api/v1/ops/websites/{website_id}/ai-config` | 创建/更新 AI 配置 |
| GET | `/api/v1/ops/websites/{website_id}/ai-config` | AI 配置列表 |
| POST | `/api/v1/ops/websites/{website_id}/crawl` | 站内预览与可控抓取 |
| POST | `/api/v1/ops/websites/{website_id}/geo` | 执行 GEO 任务 |
| GET | `/api/v1/ops/websites/{website_id}/geo` | GEO 任务列表 |
| POST | `/api/v1/ops/websites/{website_id}/media` | 上传媒体 |
| GET | `/api/v1/ops/websites/{website_id}/media` | 媒体列表 |
| GET | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 媒体详情 |
| PUT | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 更新媒体 |
| DELETE | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 删除媒体 |
| POST | `/api/v1/ops/websites/{website_id}/pages` | 创建页面/文章 |
| GET | `/api/v1/ops/websites/{website_id}/pages` | 页面列表 |
| GET | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 页面详情 |
| PUT | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 更新页面/文章 |
| DELETE | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 删除页面/文章 |
| POST | `/api/v1/ops/websites/{website_id}/products` | 创建商品 |
| GET | `/api/v1/ops/websites/{website_id}/products` | 商品列表 |
| PUT | `/api/v1/ops/websites/{website_id}/products/{product_id}` | 更新商品 |
| DELETE | `/api/v1/ops/websites/{website_id}/products/{product_id}` | 删除商品 |
| POST | `/api/v1/ops/websites/{website_id}/seo` | 执行 SEO 任务 |
| GET | `/api/v1/ops/websites/{website_id}/seo` | SEO 任务列表 |
| POST | `/api/v1/ops/websites/{website_id}/social` | 创建自媒体发布 |
| POST | `/api/v1/ops/websites/{website_id}/social/analytics` | AI 分析自媒体数据 |
| POST | `/api/v1/ops/websites/{website_id}/social/optimize` | AI 优化自媒体内容 |
| POST | `/api/v1/ops/websites/{website_id}/social/schedule` | AI 智能安排发布时间 |

### PUT `/api/v1/ops/ai-configs/{config_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `config_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AiConfigCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteAiConfigOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/ai/analyze`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AiAnalysisRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/ai/generate-content`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ContentGenerateRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`WebsiteCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `site_type` | query | 否 | object | 筛选类型 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_WebsiteOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ops/websites/{website_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`WebsiteUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ops/websites/{website_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/ai-config`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AiConfigCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteAiConfigOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/ai-config`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `setting_type` | query | 否 | object | 筛选类型 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_WebsiteAiConfigOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/crawl`

抓取本站同域页面并做 SEO 体检：仅同域、禁内网、限速限量，不跟随跨域重定向。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CrawlRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CrawlResultOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/geo`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`GeoTaskCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_GeoTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/geo`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `status` | query | 否 | object | 筛选状态 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_GeoTaskOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/media`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`MediaCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MediaItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/media`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `media_type` | query | 否 | object | 筛选类型 |
| `folder` | query | 否 | object | 筛选文件夹 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_MediaItemOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/media/{media_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `media_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MediaItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ops/websites/{website_id}/media/{media_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `media_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`MediaCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MediaItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ops/websites/{website_id}/media/{media_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `media_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/pages`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`PageCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsitePageOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/pages`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `publish_status` | query | 否 | object | 筛选状态 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_WebsitePageOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/pages/{page_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `page_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsitePageOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ops/websites/{website_id}/pages/{page_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `page_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`PageUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsitePageOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ops/websites/{website_id}/pages/{page_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `page_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/products`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ProductCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ProductItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/products`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `status` | query | 否 | object | 筛选状态 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_ProductItemOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ops/websites/{website_id}/products/{product_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `product_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ProductUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ProductItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ops/websites/{website_id}/products/{product_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `product_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/seo`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`SeoTaskCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_SeoTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/seo`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `status` | query | 否 | object | 筛选状态 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_SeoTaskOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/social`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`SocialPostCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/social/analytics`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`object`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/social/optimize`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`SocialOptimizeRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/social/schedule`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`object`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## plugins

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/plugins/market` | 插件市场列表 |
| GET | `/api/v1/plugins/market/{plugin_id}` | 插件详情 |
| POST | `/api/v1/plugins/market/{plugin_id}/disable` | 禁用插件 |
| POST | `/api/v1/plugins/market/{plugin_id}/enable` | 启用插件 |
| POST | `/api/v1/plugins/market/{plugin_id}/install` | 安装并启用插件 |
| POST | `/api/v1/plugins/market/{plugin_id}/uninstall` | 卸载插件 |

### GET `/api/v1/plugins/market`

返回市场插件列表：以运行时发现的插件为准，合并数据库登记状态。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `kind` | query | 否 | object | official / community |
| `state` | query | 否 | object | installed / enabled / disabled / uninstalled |
| `keyword` | query | 否 | object | 名称/ID 关键词（模糊） |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_dict__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/plugins/market/{plugin_id}`

插件详情：元信息 + 数据库登记状态 + 签名校验状态。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `plugin_id` | path | 是 | string |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/plugins/market/{plugin_id}/disable`

禁用插件（数据与权限声明保留）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `plugin_id` | path | 是 | string |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/plugins/market/{plugin_id}/enable`

启用已安装插件（数据保留）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `plugin_id` | path | 是 | string |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/plugins/market/{plugin_id}/install`

安装插件：注册 → 监督建表 → 加载 backend → 启用（激活）。

社区插件安全策略：默认需要人工启用；本接口即“安装并启用”显式动作，
管理员点击安装即视为授权启用。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `plugin_id` | path | 是 | string |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/plugins/market/{plugin_id}/uninstall`

卸载插件（回收上下文与权限声明；数据保留，由后续清理策略决定）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `plugin_id` | path | 是 | string |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## rbac

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/rbac/permissions` | 权限点列表 |
| GET | `/api/v1/rbac/roles` | 角色列表 |
| POST | `/api/v1/rbac/roles` | 新建角色 |
| PATCH | `/api/v1/rbac/roles/{role_id}` | 更新角色 |
| DELETE | `/api/v1/rbac/roles/{role_id}` | 删除角色 |
| GET | `/api/v1/rbac/users` | 用户列表 |
| POST | `/api/v1/rbac/users` | 新建用户 |
| GET | `/api/v1/rbac/users/{user_id}` | 用户详情 |
| PATCH | `/api/v1/rbac/users/{user_id}` | 更新用户 |
| DELETE | `/api/v1/rbac/users/{user_id}` | 删除用户 |
| POST | `/api/v1/rbac/users/{user_id}/reset-password` | 重置用户密码 |

### GET `/api/v1/rbac/permissions`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `module` | query | 否 | object | 按模块筛选 |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_PermissionOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/rbac/roles`

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_RoleOut__` |

### POST `/api/v1/rbac/roles`

**请求参数**

无

**请求体**

`RoleCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_RoleOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PATCH `/api/v1/rbac/roles/{role_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `role_id` | path | 是 | integer |  |

**请求体**

`RoleUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_RoleOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/rbac/roles/{role_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `role_id` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/rbac/users`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `keyword` | query | 否 | object | 用户名/姓名/邮箱模糊匹配 |
| `is_active` | query | 否 | object | 启用状态 |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_UserOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/rbac/users`

**请求参数**

无

**请求体**

`UserCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_UserOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/rbac/users/{user_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `user_id` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_UserOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PATCH `/api/v1/rbac/users/{user_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `user_id` | path | 是 | integer |  |

**请求体**

`UserUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_UserOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/rbac/users/{user_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `user_id` | path | 是 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/rbac/users/{user_id}/reset-password`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `user_id` | path | 是 | integer |  |

**请求体**

`ResetPasswordRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## storage

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/storage/backfill` | 回填存量指标值到时序分区表 |
| POST | `/api/v1/storage/bootstrap` | 幂等初始化存储适配层 |
| GET | `/api/v1/storage/consistency/recent` | 最近对账记录 |
| POST | `/api/v1/storage/consistency/run` | 执行跨存储一致性对账 |
| GET | `/api/v1/storage/overview` | 存储适配层总览 |
| POST | `/api/v1/storage/routing/identify` | 识别数据类型并给出目标存储引擎 |
| GET | `/api/v1/storage/routing/rules` | 路由规则列表 |
| GET | `/api/v1/storage/search` | 全文检索 |
| POST | `/api/v1/storage/search/reindex` | 重建全文检索索引 |

### POST `/api/v1/storage/backfill`

幂等回填：仅补时序表中缺失的指标值，已有记录不覆盖。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `batch_size` | query | 否 | object | 单批行数 |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/storage/bootstrap`

受管目录 + 内置路由规则 + 时序月分区，可在容器内重复执行。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### GET `/api/v1/storage/consistency/recent`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `limit` | query | 否 | integer |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_dict__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/storage/consistency/run`

**请求参数**

无

**请求体**

`ConsistencyIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/storage/overview`

引擎能力矩阵 + 各类型规模统计 + 路由规则 + 样例识别。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### POST `/api/v1/storage/routing/identify`

**请求参数**

无

**请求体**

`IdentifyIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/storage/routing/rules`

内置规则 + 当前租户自定义规则 + 各类型引擎映射。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |

### GET `/api/v1/storage/search`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `q` | query | 是 | string | 检索关键词 |
| `doc_type` | query | 否 | object | 限定文档类型 |
| `limit` | query | 否 | object | 返回条数上限 |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/storage/search/reindex`

**请求参数**

无

**请求体**

`ReindexIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## system

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/system/health` | Health |
| GET | `/api/v1/system/info` | Info |
| GET | `/api/v1/system/security-overview` | 安全配置概览 |
| GET | `/health` | Health |

### GET `/api/v1/system/health`

服务健康检查（开放）。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `object` |

### GET `/api/v1/system/info`

服务基础信息（需登录）。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `object` |

### GET `/api/v1/system/security-overview`

当前安全配置概览：监听地址、CORS 白名单、IP 白名单、认证与审计策略。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_SecurityOverviewOut_` |

### GET `/health`

健康检查（开放）。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `object` |

## tenants

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/tenants` | 租户列表 |
| POST | `/api/v1/tenants` | 新建租户 |

### GET `/api/v1/tenants`

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_TenantOut__` |

### POST `/api/v1/tenants`

**请求参数**

无

**请求体**

`TenantCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_TenantOut_` |
| 422 | Validation Error | `HTTPValidationError` |

## 营销渠道

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/marketing/campaigns` | 创建投放任务 |
| GET | `/api/v1/marketing/campaigns` | 投放任务列表 |
| PUT | `/api/v1/marketing/campaigns/{campaign_id}` | 编辑投放任务 |
| DELETE | `/api/v1/marketing/campaigns/{campaign_id}` | 删除投放任务 |
| POST | `/api/v1/marketing/campaigns/{campaign_id}/execute` | 执行投放任务（本地演练） |
| GET | `/api/v1/marketing/channel-types` | 渠道类型目录 |
| POST | `/api/v1/marketing/channels` | 新增渠道账号 |
| GET | `/api/v1/marketing/channels` | 渠道列表 |
| PUT | `/api/v1/marketing/channels/{channel_id}` | 编辑渠道账号 |
| DELETE | `/api/v1/marketing/channels/{channel_id}` | 删除渠道账号 |
| POST | `/api/v1/marketing/channels/{channel_id}/authorize` | 写入凭据并授权 |
| POST | `/api/v1/marketing/channels/{channel_id}/revoke` | 撤销授权 |
| POST | `/api/v1/marketing/channels/{channel_id}/sync` | 触发渠道数据同步 |
| GET | `/api/v1/marketing/events` | 渠道事件日志 |
| GET | `/api/v1/marketing/overview` | 渠道接入概览 |

### POST `/api/v1/marketing/campaigns`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CampaignCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ChannelCampaignOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/campaigns`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | query | 否 | object | 按渠道筛选 |
| `status` | query | 否 | object | 按状态筛选 |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_ChannelCampaignOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/marketing/campaigns/{campaign_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `campaign_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CampaignUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ChannelCampaignOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/marketing/campaigns/{campaign_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `campaign_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/campaigns/{campaign_id}/execute`

执行投放编排。

当前版本为接入骨架：仅校验渠道授权状态并记录演练结果（simulated=true），
未调用任何平台真实 API，因此不写入曝光/点击/转化等平台回传指标。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `campaign_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ChannelCampaignOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/channel-types`

返回可接入的平台类型、授权方式与能力，并统计本租户已接入/已授权数量。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_ChannelTypeOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/channels`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ChannelCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/channels`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_type` | query | 否 | object | 按平台类型筛选 |
| `status` | query | 否 | object | 按授权状态筛选 |
| `keyword` | query | 否 | object | 名称/账号模糊匹配 |
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_MarketingChannelOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/marketing/channels/{channel_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ChannelUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/marketing/channels/{channel_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/channels/{channel_id}/authorize`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AuthorizePayload`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/channels/{channel_id}/revoke`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/marketing/channels/{channel_id}/sync`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingChannelOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/events`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `channel_id` | query | 否 | object | 按渠道筛选 |
| `limit` | query | 否 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_ChannelEventOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/marketing/overview`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MarketingOverviewOut_` |
| 422 | Validation Error | `HTTPValidationError` |

## 运营参谋

| 方法 | 路径 | 说明 |
|---|---|---|
| PUT | `/api/v1/ops/ai-configs/{config_id}` | 更新 AI 配置 |
| POST | `/api/v1/ops/ai/analyze` | AI 全面运营分析 |
| POST | `/api/v1/ops/ai/generate-content` | AI 生成/改写内容 |
| POST | `/api/v1/ops/websites` | 创建网站/网店 |
| GET | `/api/v1/ops/websites` | 网站列表 |
| GET | `/api/v1/ops/websites/{website_id}` | 网站详情 |
| PUT | `/api/v1/ops/websites/{website_id}` | 更新网站/网店 |
| DELETE | `/api/v1/ops/websites/{website_id}` | 删除网站/网店 |
| POST | `/api/v1/ops/websites/{website_id}/ai-config` | 创建/更新 AI 配置 |
| GET | `/api/v1/ops/websites/{website_id}/ai-config` | AI 配置列表 |
| POST | `/api/v1/ops/websites/{website_id}/crawl` | 站内预览与可控抓取 |
| POST | `/api/v1/ops/websites/{website_id}/geo` | 执行 GEO 任务 |
| GET | `/api/v1/ops/websites/{website_id}/geo` | GEO 任务列表 |
| POST | `/api/v1/ops/websites/{website_id}/media` | 上传媒体 |
| GET | `/api/v1/ops/websites/{website_id}/media` | 媒体列表 |
| GET | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 媒体详情 |
| PUT | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 更新媒体 |
| DELETE | `/api/v1/ops/websites/{website_id}/media/{media_id}` | 删除媒体 |
| POST | `/api/v1/ops/websites/{website_id}/pages` | 创建页面/文章 |
| GET | `/api/v1/ops/websites/{website_id}/pages` | 页面列表 |
| GET | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 页面详情 |
| PUT | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 更新页面/文章 |
| DELETE | `/api/v1/ops/websites/{website_id}/pages/{page_id}` | 删除页面/文章 |
| POST | `/api/v1/ops/websites/{website_id}/products` | 创建商品 |
| GET | `/api/v1/ops/websites/{website_id}/products` | 商品列表 |
| PUT | `/api/v1/ops/websites/{website_id}/products/{product_id}` | 更新商品 |
| DELETE | `/api/v1/ops/websites/{website_id}/products/{product_id}` | 删除商品 |
| POST | `/api/v1/ops/websites/{website_id}/seo` | 执行 SEO 任务 |
| GET | `/api/v1/ops/websites/{website_id}/seo` | SEO 任务列表 |
| POST | `/api/v1/ops/websites/{website_id}/social` | 创建自媒体发布 |
| POST | `/api/v1/ops/websites/{website_id}/social/analytics` | AI 分析自媒体数据 |
| POST | `/api/v1/ops/websites/{website_id}/social/optimize` | AI 优化自媒体内容 |
| POST | `/api/v1/ops/websites/{website_id}/social/schedule` | AI 智能安排发布时间 |

### PUT `/api/v1/ops/ai-configs/{config_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `config_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AiConfigCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteAiConfigOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/ai/analyze`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AiAnalysisRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/ai/generate-content`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ContentGenerateRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`WebsiteCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `site_type` | query | 否 | object | 筛选类型 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_WebsiteOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ops/websites/{website_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`WebsiteUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ops/websites/{website_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/ai-config`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`AiConfigCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsiteAiConfigOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/ai-config`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `setting_type` | query | 否 | object | 筛选类型 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_WebsiteAiConfigOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/crawl`

抓取本站同域页面并做 SEO 体检：仅同域、禁内网、限速限量，不跟随跨域重定向。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CrawlRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CrawlResultOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/geo`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`GeoTaskCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_GeoTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/geo`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `status` | query | 否 | object | 筛选状态 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_GeoTaskOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/media`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`MediaCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MediaItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/media`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `media_type` | query | 否 | object | 筛选类型 |
| `folder` | query | 否 | object | 筛选文件夹 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_MediaItemOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/media/{media_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `media_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MediaItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ops/websites/{website_id}/media/{media_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `media_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`MediaCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_MediaItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ops/websites/{website_id}/media/{media_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `media_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/pages`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`PageCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsitePageOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/pages`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `publish_status` | query | 否 | object | 筛选状态 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_WebsitePageOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/pages/{page_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `page_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsitePageOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ops/websites/{website_id}/pages/{page_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `page_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`PageUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_WebsitePageOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ops/websites/{website_id}/pages/{page_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `page_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/products`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ProductCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ProductItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/products`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `status` | query | 否 | object | 筛选状态 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_ProductItemOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/ops/websites/{website_id}/products/{product_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `product_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`ProductUpdate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_ProductItemOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/ops/websites/{website_id}/products/{product_id}`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `product_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/seo`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`SeoTaskCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_SeoTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/ops/websites/{website_id}/seo`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `status` | query | 否 | object | 筛选状态 |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_SeoTaskOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/social`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`SocialPostCreate`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/social/analytics`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`object`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/social/optimize`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`SocialOptimizeRequest`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/ops/websites/{website_id}/social/schedule`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `website_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`object`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

## 采集调度

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/collect/modes` | List Modes |
| GET | `/api/v1/collect/overview` | Overview |
| GET | `/api/v1/collect/runs` | List Runs |
| POST | `/api/v1/collect/scheduler/scan` | Scan Due |
| GET | `/api/v1/collect/sources` | List Sources |
| GET | `/api/v1/collect/tasks` | List Tasks |
| POST | `/api/v1/collect/tasks` | Create Task |
| GET | `/api/v1/collect/tasks/{task_id}` | Get Task |
| PUT | `/api/v1/collect/tasks/{task_id}` | Update Task |
| DELETE | `/api/v1/collect/tasks/{task_id}` | Delete Task |
| POST | `/api/v1/collect/tasks/{task_id}/run` | Run Task |
| POST | `/api/v1/collect/tasks/{task_id}/toggle` | Toggle Task |

### GET `/api/v1/collect/modes`

采集方式目录：三种方式的能力与目标格式说明。

**请求参数**

无

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_CollectModeOut__` |

### GET `/api/v1/collect/overview`

采集调度总览：任务态势、近 24 小时运行质量、执行趋势与最近记录。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectOverviewOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/collect/runs`

运行记录（可按任务、状态筛选）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `task_id` | query | 否 | object |  |
| `status` | query | 否 | object |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_CollectRunOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/collect/scheduler/scan`

立即扫描并执行到期任务（手动兜底调度，便于无后台线程环境使用）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/collect/sources`

可绑定的数据源下拉项。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_list_CollectSourceOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/collect/tasks`

采集任务列表（支持状态 / 方式 / 关键词筛选）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `page` | query | 否 | integer |  |
| `page_size` | query | 否 | integer |  |
| `status` | query | 否 | object | enabled/paused |
| `collect_mode` | query | 否 | object | csv/api/sql |
| `keyword` | query | 否 | object |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_PageResult_CollectTaskOut__` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/collect/tasks`

新建采集任务（interval 模式自动排期下次执行时间）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CollectTaskIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### GET `/api/v1/collect/tasks/{task_id}`

采集任务详情。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### PUT `/api/v1/collect/tasks/{task_id}`

编辑采集任务（编码不可改；改动调度策略会重排下次执行时间）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

`CollectTaskUpdateIn`（JSON 对象）

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### DELETE `/api/v1/collect/tasks/{task_id}`

删除采集任务（运行记录随任务级联清理）。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_dict_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/collect/tasks/{task_id}/run`

手动执行一次采集，返回本次运行记录。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectRunOut_` |
| 422 | Validation Error | `HTTPValidationError` |

### POST `/api/v1/collect/tasks/{task_id}/toggle`

启用 / 暂停任务；启用时重排下次执行时间。

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 说明 |
|---|---|---|---|---|
| `task_id` | path | 是 | integer |  |
| `X-Tenant-Id` | header | 否 | object |  |

**请求体**

无

**响应**

| 状态码 | 说明 | 响应体 |
|---|---|---|
| 200 | Successful Response | `ApiResponse_CollectTaskOut_` |
| 422 | Validation Error | `HTTPValidationError` |
*（内容由AI生成，仅供参考）*
