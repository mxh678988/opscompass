---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_5a86212fb9a111f1b172525400248c00
    ReservedCode1: 3SCEhHSlp3zSed62EEpdsmGyv3hdcUySVQCIFLT51ggVUWmhJH8fvhp+x/xko0xXGy1NXWxzcJa3pGw7kCrqV48N4LpgX2n6XJliQOveA/WDbWXOB3Vdza7qjg7wNanFF5RnPccbx0UgyrvqbbTNIIpVJXXmuHHXPGhAXl/yonWTbEEflZz674rTPec=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_5a86212fb9a111f1b172525400248c00
    ReservedCode2: 3SCEhHSlp3zSed62EEpdsmGyv3hdcUySVQCIFLT51ggVUWmhJH8fvhp+x/xko0xXGy1NXWxzcJa3pGw7kCrqV48N4LpgX2n6XJliQOveA/WDbWXOB3Vdza7qjg7wNanFF5RnPccbx0UgyrvqbbTNIIpVJXXmuHHXPGhAXl/yonWTbEEflZz674rTPec=
---

# 运营智脑（OpsCompass）数据字典

> 自动生成于 2026-09-26，数据来源：PostgreSQL 实例 `opscompass-postgres` 的 `information_schema`（实时核对）。

## 概览

| 项 | 值 |
|---|---|
| 数据库 | PostgreSQL 16（postgres:16-alpine） |
| 业务表总数 | 54 |
| 字段总数 | 686 |
|  Alembic 版本表 | alembic_version |
| 表命名规范 | `oc_` 前缀 + 业务域 + 实体名 |

## 表分组

| 业务域 | 表数 | 表名 |
|---|---|---|
| AI 能力与模型中心 | 8 | `oc_ai_action_item`, `oc_ai_action_policy`, `oc_ai_analysis`, `oc_ai_audit_log`, `oc_ai_data_level_record`, `oc_ai_data_level_rule`, `oc_ai_insight`, `oc_ai_model_endpoint` |
| 其他 | 23 | `oc_data_source`, `oc_doc_index`, `oc_geo_task`, `oc_import_task`, `oc_marketing_channel`, `oc_media_item`, `oc_page_media_ref`, `oc_page_seo_task`, `oc_product_item`, `oc_seo_task`, `oc_ts_metric_point`, `oc_ts_metric_point_p202607`, `oc_ts_metric_point_p202608`, `oc_ts_metric_point_p202609`, `oc_ts_metric_point_p202610`, `oc_ts_metric_point_p202611`, `oc_ts_metric_point_p202612`, `oc_ts_metric_point_p202701`, `oc_ts_metric_point_p202702`, `oc_ts_metric_point_p202703`, `oc_website`, `oc_website_ai_config`, `oc_website_page` |
| 基础 | 1 | `alembic_version` |
| 多租户 | 1 | `oc_tenant` |
| 存储适配层 | 2 | `oc_storage_consistency_check`, `oc_storage_route_rule` |
| 学习进化 | 4 | `oc_learn_case`, `oc_learn_experiment`, `oc_learn_feedback`, `oc_learn_policy_weight` |
| 审计与安全 | 1 | `oc_audit_log` |
| 指标 | 5 | `oc_metric`, `oc_metric_category`, `oc_metric_dimension`, `oc_metric_dimension_rel`, `oc_metric_value` |
| 用户与权限 | 5 | `oc_permission`, `oc_role`, `oc_role_permission`, `oc_user`, `oc_user_role` |
| 营销渠道 | 2 | `oc_channel_campaign`, `oc_channel_event` |
| 采集调度 | 2 | `oc_collect_run`, `oc_collect_task` |

## AI 能力与模型中心

### `oc_ai_action_item`

当前行数：**9**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_ai_action_item_id_seq'::regc | PK |
| tenant_id | integer | NO | - | - | - |
| insight_id | integer | YES | - | - | - |
| analysis_id | integer | YES | - | - | - |
| policy_id | integer | YES | - | - | - |
| title | character varying | NO | 200 | - | - |
| action_type | character varying | NO | 16 | 'record'::character varying | - |
| data_level | character varying | NO | 4 | 'L2'::character varying | - |
| severity | character varying | NO | 16 | 'info'::character varying | - |
| handler | character varying | NO | 16 | 'human'::character varying | - |
| status | character varying | NO | 16 | 'pending'::character varying | - |
| review_required | boolean | NO | - | true | - |
| assignee | character varying | YES | 64 | - | - |
| decision_by | character varying | YES | 64 | - | - |
| decision_at | timestamp with time zone | YES | - | - | - |
| decision_note | text | YES | - | - | - |
| execution_result | text | YES | - | - | - |
| executed_at | timestamp with time zone | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

### `oc_ai_action_policy`

当前行数：**13**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_ai_action_policy_id_seq'::re | PK |
| tenant_id | integer | NO | - | - | - |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| data_level | character varying | NO | 4 | - | - |
| actor | character varying | NO | 16 | - | - |
| action_type | character varying | NO | 16 | '*'::character varying | - |
| max_severity | character varying | NO | 16 | 'warning'::character varying | - |
| allow | boolean | NO | - | true | - |
| require_review | boolean | NO | - | false | - |
| require_approval | boolean | NO | - | false | - |
| priority | integer | NO | - | 100 | - |
| enabled | boolean | NO | - | true | - |
| builtin | boolean | NO | - | false | - |
| description | text | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

### `oc_ai_analysis`

当前行数：**2**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_ai_analysis_id_seq'::regclas | PK |
| tenant_id | integer | NO | - | - | - |
| scope | character varying | NO | 32 | 'overview'::character varying | - |
| title | character varying | NO | 200 | ''::character varying | - |
| mode | character varying | NO | 16 | 'local'::character varying | - |
| model | character varying | NO | 128 | ''::character varying | - |
| status | character varying | NO | 16 | 'pending'::character varying | - |
| granularity | character varying | NO | 16 | 'day'::character varying | - |
| dim_key | character varying | YES | 64 | - | - |
| request_params | json | YES | - | - | - |
| input_snapshot | json | YES | - | - | - |
| prompt_digest | text | YES | - | - | - |
| result_summary | text | YES | - | - | - |
| insight_count | integer | NO | - | 0 | - |
| duration_ms | integer | NO | - | 0 | - |
| prompt_tokens | integer | NO | - | 0 | - |
| completion_tokens | integer | NO | - | 0 | - |
| error | text | YES | - | - | - |
| created_by | character varying | NO | 64 | 'system'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| finished_at | timestamp with time zone | YES | - | - | - |

### `oc_ai_audit_log`

当前行数：**15**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_ai_audit_log_id_seq'::regcla | PK |
| tenant_id | integer | NO | - | - | - |
| actor_type | character varying | NO | 16 | 'system'::character varying | - |
| actor | character varying | NO | 64 | 'system'::character varying | - |
| action | character varying | NO | 64 | - | - |
| object_type | character varying | NO | 32 | ''::character varying | - |
| object_id | integer | YES | - | - | - |
| from_state | character varying | YES | 32 | - | - |
| to_state | character varying | YES | 32 | - | - |
| detail | text | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ai_data_level_record`

当前行数：**9**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_ai_data_level_record_id_seq' | PK |
| tenant_id | integer | NO | - | - | - |
| object_type | character varying | NO | 32 | - | - |
| object_id | integer | NO | - | - | - |
| object_code | character varying | NO | 128 | ''::character varying | - |
| level | character varying | NO | 4 | - | - |
| source | character varying | NO | 16 | 'rule'::character varying | - |
| rule_id | integer | YES | - | - | - |
| rule_code | character varying | YES | 64 | - | - |
| confidence | numeric | YES | - | - | - |
| grader | character varying | NO | 64 | 'rule-engine'::character varying | - |
| reason | text | YES | - | - | - |
| graded_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

### `oc_ai_data_level_rule`

当前行数：**7**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_ai_data_level_rule_id_seq':: | PK |
| tenant_id | integer | NO | - | - | - |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| object_type | character varying | NO | 32 | 'metric'::character varying | - |
| field | character varying | NO | 64 | 'code'::character varying | - |
| operator | character varying | NO | 16 | 'in'::character varying | - |
| threshold | json | YES | - | - | - |
| level | character varying | NO | 4 | 'L2'::character varying | - |
| priority | integer | NO | - | 100 | - |
| builtin | boolean | NO | - | false | - |
| enabled | boolean | NO | - | true | - |
| description | text | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

### `oc_ai_insight`

当前行数：**9**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_ai_insight_id_seq'::regclass | PK |
| tenant_id | integer | NO | - | - | - |
| analysis_id | integer | YES | - | - | - |
| seq | integer | NO | - | 1 | - |
| category | character varying | NO | 24 | 'anomaly'::character varying | - |
| severity | character varying | NO | 16 | 'info'::character varying | - |
| title | character varying | NO | 200 | - | - |
| detail | text | YES | - | - | - |
| metric_codes | json | YES | - | - | - |
| evidence | json | YES | - | - | - |
| suggestion | text | YES | - | - | - |
| action_type | character varying | NO | 16 | 'record'::character varying | - |
| data_level | character varying | NO | 4 | 'L2'::character varying | - |
| confidence | numeric | YES | - | - | - |
| status | character varying | NO | 16 | 'new'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ai_model_endpoint`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_ai_model_endpoint_id_seq'::r | PK |
| tenant_id | integer | NO | - | - | - |
| name | character varying | NO | 64 | - | - |
| kind | character varying | NO | 32 | - | - |
| provider | character varying | YES | 32 | - | - |
| base_url | character varying | NO | 255 | - | - |
| model | character varying | NO | 128 | - | - |
| param_scale | character varying | YES | 32 | - | - |
| api_key_enc | text | YES | - | - | - |
| api_key_hint | character varying | YES | 64 | - | - |
| enabled | boolean | NO | - | true | - |
| is_active | boolean | NO | - | false | - |
| source | character varying | YES | 32 | - | - |
| remark | character varying | YES | 255 | - | - |
| last_test_at | timestamp with time zone | YES | - | - | - |
| last_test_ok | boolean | YES | - | - | - |
| last_test_latency_ms | integer | YES | - | - | - |
| last_test_message | character varying | YES | 255 | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

## 其他

### `oc_data_source`

当前行数：**2**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_data_source_id_seq'::regclas | PK |
| tenant_id | integer | NO | - | - | - |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| ds_type | character varying | NO | 32 | - | - |
| host | character varying | YES | 255 | - | - |
| port | integer | YES | - | - | - |
| db_name | character varying | YES | 128 | - | - |
| username | character varying | YES | 128 | - | - |
| password_enc | character varying | YES | 512 | - | - |
| extra_config | json | YES | - | - | - |
| status | character varying | NO | 16 | 'enabled'::character varying | - |
| last_sync_at | timestamp with time zone | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

### `oc_doc_index`

当前行数：**9**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_doc_index_id_seq'::regclass) | PK |
| tenant_id | integer | NO | - | - | - |
| doc_type | character varying | NO | 32 | - | - |
| doc_id | character varying | NO | 64 | - | - |
| title | character varying | NO | 255 | ''::character varying | - |
| content | text | YES | - | - | - |
| keywords | character varying | YES | 512 | - | - |
| url | character varying | YES | 512 | - | - |
| payload | jsonb | YES | - | - | - |
| tsv | tsvector | YES | - | - | - |
| indexed_at | timestamp with time zone | NO | - | now() | - |

### `oc_geo_task`

当前行数：**10**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_geo_task_id_seq'::regclass) | PK |
| tenant_id | integer | NO | - | - | - |
| website_id | integer | NO | - | - | - |
| task_type | character varying | NO | 32 | - | - |
| title | character varying | NO | 128 | ''::character varying | - |
| target_page_ids | text | NO | - | ''::text | - |
| status | character varying | NO | 32 | 'pending'::character varying | - |
| result | text | NO | - | ''::text | - |
| ai_model | character varying | NO | 64 | ''::character varying | - |
| ai_enabled | boolean | NO | - | true | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_import_task`

当前行数：**5**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_import_task_id_seq'::regclas | PK |
| tenant_id | integer | NO | - | - | - |
| source_id | integer | YES | - | - | - |
| file_name | character varying | NO | 255 | - | - |
| file_path | character varying | NO | 512 | - | - |
| file_size | integer | NO | - | 0 | - |
| file_hash | character varying | NO | 64 | ''::character varying | - |
| layout | character varying | NO | 8 | 'wide'::character varying | - |
| granularity | character varying | NO | 16 | 'day'::character varying | - |
| status | character varying | NO | 16 | 'pending'::character varying | - |
| total_rows | integer | NO | - | 0 | - |
| success_rows | integer | NO | - | 0 | - |
| failed_rows | integer | NO | - | 0 | - |
| skipped_rows | integer | NO | - | 0 | - |
| value_count | integer | NO | - | 0 | - |
| metric_codes | json | YES | - | - | - |
| mapping | json | YES | - | - | - |
| error_detail | json | YES | - | - | - |
| error_msg | text | YES | - | - | - |
| elapsed_ms | integer | NO | - | 0 | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| finished_at | timestamp with time zone | YES | - | - | - |

### `oc_marketing_channel`

当前行数：**3**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_marketing_channel_id_seq'::r | PK |
| tenant_id | integer | NO | - | - | - |
| channel_type | character varying | NO | 32 | - | - |
| channel_name | character varying | NO | 128 | - | - |
| account_name | character varying | NO | 128 | - | - |
| auth_type | character varying | NO | 16 | 'apikey'::character varying | - |
| credential_cipher | text | NO | - | ''::text | - |
| credential_masked | character varying | NO | 128 | ''::character varying | - |
| api_base | character varying | NO | 256 | ''::character varying | - |
| scopes | character varying | NO | 256 | ''::character varying | - |
| status | character varying | NO | 32 | 'unauthorized'::character varying | - |
| expires_at | character varying | NO | 64 | ''::character varying | - |
| last_sync_at | character varying | NO | 64 | ''::character varying | - |
| auto_publish | boolean | NO | - | false | - |
| remark | text | NO | - | ''::text | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | YES | - | now() | - |

### `oc_media_item`

当前行数：**2**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_media_item_id_seq'::regclass | PK |
| tenant_id | integer | NO | - | - | - |
| website_id | integer | NO | - | - | - |
| media_type | character varying | NO | 32 | - | - |
| file_url | character varying | NO | 1024 | - | - |
| file_name | character varying | NO | 256 | ''::character varying | - |
| file_size | integer | NO | - | 0 | - |
| mime_type | character varying | NO | 128 | ''::character varying | - |
| width | integer | NO | - | 0 | - |
| height | integer | NO | - | 0 | - |
| tags | text | NO | - | ''::text | - |
| description | text | NO | - | ''::text | - |
| folder | character varying | NO | 128 | ''::character varying | - |
| usage_count | integer | NO | - | 0 | - |
| content_level | character varying | NO | 4 | 'L2'::character varying | - |
| ai_generated | boolean | NO | - | false | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | YES | - | now() | - |

### `oc_page_media_ref`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_page_media_ref_id_seq'::regc | PK |
| tenant_id | integer | NO | - | - | - |
| page_id | integer | NO | - | - | - |
| media_id | integer | NO | - | - | - |
| media_type | character varying | NO | 32 | ''::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_page_seo_task`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_page_seo_task_id_seq'::regcl | PK |
| tenant_id | integer | NO | - | - | - |
| page_id | integer | NO | - | - | - |
| task_type | character varying | NO | 32 | - | - |
| title | character varying | NO | 128 | ''::character varying | - |
| status | character varying | NO | 32 | 'pending'::character varying | - |
| result | text | NO | - | ''::text | - |
| ai_enabled | boolean | NO | - | true | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_product_item`

当前行数：**2**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_product_item_id_seq'::regcla | PK |
| tenant_id | integer | NO | - | - | - |
| website_id | integer | NO | - | - | - |
| name | character varying | NO | 256 | - | - |
| slug | character varying | NO | 256 | ''::character varying | - |
| price | integer | NO | - | 0 | - |
| currency | character varying | NO | 8 | 'CNY'::character varying | - |
| stock | integer | NO | - | 0 | - |
| sku | character varying | NO | 64 | ''::character varying | - |
| description | text | NO | - | ''::text | - |
| status | character varying | NO | 32 | 'draft'::character varying | - |
| seo_title | character varying | NO | 128 | ''::character varying | - |
| seo_desc | character varying | NO | 512 | ''::character varying | - |
| ai_enabled | boolean | NO | - | true | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | YES | - | now() | - |

### `oc_seo_task`

当前行数：**7**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_seo_task_id_seq'::regclass) | PK |
| tenant_id | integer | NO | - | - | - |
| website_id | integer | NO | - | - | - |
| task_type | character varying | NO | 32 | - | - |
| title | character varying | NO | 128 | ''::character varying | - |
| description | text | NO | - | ''::text | - |
| status | character varying | NO | 32 | 'pending'::character varying | - |
| result | text | NO | - | ''::text | - |
| ai_model | character varying | NO | 64 | ''::character varying | - |
| duration_ms | integer | NO | - | 0 | - |
| ai_enabled | boolean | NO | - | true | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point`

当前行数：**222**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202607`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202608`

当前行数：**63**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202609`

当前行数：**156**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202610`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202611`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202612`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202701`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202702`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_ts_metric_point_p202703`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| tenant_id | integer | NO | - | - | PK |
| metric_id | integer | NO | - | - | PK |
| metric_code | character varying | NO | 64 | ''::character varying | - |
| stat_time | timestamp with time zone | NO | - | - | PK |
| granularity | character varying | NO | 16 | 'day'::character varying | PK |
| dims_hash | character varying | NO | 64 | ''::character varying | PK |
| dims | jsonb | YES | - | - | - |
| value | numeric | NO | - | 0 | - |
| source_id | integer | YES | - | - | - |
| origin | character varying | NO | 32 | 'mirror'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_website`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_website_id_seq'::regclass) | PK |
| tenant_id | integer | NO | - | - | - |
| site_name | character varying | NO | 128 | - | - |
| site_url | character varying | NO | 512 | - | - |
| site_type | character varying | NO | 32 | 'cms'::character varying | - |
| theme | character varying | NO | 128 | ''::character varying | - |
| status | character varying | NO | 32 | 'draft'::character varying | - |
| language | character varying | NO | 16 | 'zh-CN'::character varying | - |
| description | text | NO | - | ''::text | - |
| sitemap_generated | boolean | NO | - | false | - |
| seo_score | integer | NO | - | 0 | - |
| geo_score | integer | NO | - | 0 | - |
| ai_enabled | boolean | NO | - | true | - |
| ai_mode | character varying | NO | 16 | 'local'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | YES | - | now() | - |

### `oc_website_ai_config`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_website_ai_config_id_seq'::r | PK |
| tenant_id | integer | NO | - | - | - |
| website_id | integer | NO | - | - | - |
| setting_type | character varying | NO | 32 | - | - |
| config_value | text | NO | - | '{}'::text | - |
| enabled | boolean | NO | - | true | - |
| ai_model | character varying | NO | 64 | ''::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | YES | - | now() | - |

### `oc_website_page`

当前行数：**2**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_website_page_id_seq'::regcla | PK |
| tenant_id | integer | NO | - | - | - |
| website_id | integer | NO | - | - | - |
| title | character varying | NO | 256 | - | - |
| slug | character varying | NO | 256 | ''::character varying | - |
| content | text | NO | - | ''::text | - |
| seo_title | character varying | NO | 128 | ''::character varying | - |
| seo_desc | character varying | NO | 512 | ''::character varying | - |
| seo_keywords | character varying | NO | 256 | ''::character varying | - |
| og_image | character varying | NO | 512 | ''::character varying | - |
| publish_status | character varying | NO | 32 | 'draft'::character varying | - |
| published_at | character varying | NO | 64 | ''::character varying | - |
| ai_enabled | boolean | NO | - | true | - |
| ai_generated | boolean | NO | - | false | - |
| content_level | character varying | NO | 4 | 'L2'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | YES | - | now() | - |

## 基础

### `alembic_version`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| version_num | character varying | NO | 32 | - | PK |

## 多租户

### `oc_tenant`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_tenant_id_seq'::regclass) | PK |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| status | character varying | NO | 16 | 'active'::character varying | - |
| remark | character varying | YES | 255 | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

## 存储适配层

### `oc_storage_consistency_check`

当前行数：**66**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_storage_consistency_check_id | PK |
| tenant_id | integer | NO | - | - | - |
| scope | character varying | NO | 64 | - | - |
| status | character varying | NO | 16 | 'passed'::character varying | - |
| checked | integer | NO | - | 0 | - |
| matched | integer | NO | - | 0 | - |
| missing | integer | NO | - | 0 | - |
| extra | integer | NO | - | 0 | - |
| mismatched | integer | NO | - | 0 | - |
| repaired | integer | NO | - | 0 | - |
| auto_repair | boolean | NO | - | false | - |
| elapsed_ms | integer | NO | - | 0 | - |
| report | jsonb | YES | - | - | - |
| operator | character varying | YES | 64 | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_storage_route_rule`

当前行数：**28**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_storage_route_rule_id_seq':: | PK |
| tenant_id | integer | YES | - | - | - |
| name | character varying | NO | 128 | - | - |
| match_field | character varying | NO | 32 | - | - |
| match_value | character varying | NO | 128 | - | - |
| data_kind | character varying | NO | 32 | - | - |
| engine | character varying | NO | 64 | - | - |
| priority | integer | NO | - | 100 | - |
| enabled | boolean | NO | - | true | - |
| remark | character varying | YES | 255 | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

## 学习进化

### `oc_learn_case`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_learn_case_id_seq'::regclass | PK |
| tenant_id | integer | NO | - | - | - |
| case_no | character varying | NO | 64 | - | - |
| title | character varying | NO | 255 | - | - |
| category | character varying | NO | 64 | - | - |
| tags | json | YES | - | - | - |
| scenario | text | NO | - | - | - |
| action_taken | text | NO | - | - | - |
| outcome | text | NO | - | - | - |
| outcome_score | numeric | YES | - | - | - |
| lesson | text | NO | - | - | - |
| source_insight_id | integer | YES | - | - | - |
| source_feedback_id | integer | YES | - | - | - |
| status | character varying | NO | 16 | - | - |
| hit_count | integer | NO | - | - | - |
| last_hit_at | timestamp without time zone | YES | - | - | - |
| created_by | character varying | NO | 64 | - | - |
| created_at | timestamp without time zone | NO | - | now() | - |
| updated_at | timestamp without time zone | NO | - | now() | - |

### `oc_learn_experiment`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_learn_experiment_id_seq'::re | PK |
| tenant_id | integer | NO | - | - | - |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 255 | - | - |
| hypothesis | text | NO | - | - | - |
| metric_code | character varying | NO | 64 | - | - |
| status | character varying | NO | 16 | - | - |
| variant_a | character varying | NO | 128 | - | - |
| variant_b | character varying | NO | 128 | - | - |
| sample_a | integer | NO | - | - | - |
| sample_b | integer | NO | - | - | - |
| result_a | numeric | NO | - | - | - |
| result_b | numeric | NO | - | - | - |
| lift | numeric | NO | - | - | - |
| confidence | numeric | NO | - | - | - |
| winner | character varying | NO | 8 | - | - |
| conclusion | text | NO | - | - | - |
| started_at | timestamp without time zone | YES | - | - | - |
| finished_at | timestamp without time zone | YES | - | - | - |
| created_by | character varying | NO | 64 | - | - |
| created_at | timestamp without time zone | NO | - | now() | - |
| updated_at | timestamp without time zone | NO | - | now() | - |

### `oc_learn_feedback`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_learn_feedback_id_seq'::regc | PK |
| tenant_id | integer | NO | - | - | - |
| insight_id | integer | YES | - | - | - |
| action_item_id | integer | YES | - | - | - |
| policy_code | character varying | NO | 64 | - | - |
| action_type | character varying | NO | 64 | - | - |
| data_level | character varying | NO | 16 | - | - |
| decision | character varying | NO | 16 | - | - |
| outcome | character varying | NO | 16 | - | - |
| outcome_score | numeric | YES | - | - | - |
| effect_note | text | NO | - | - | - |
| remark | text | NO | - | - | - |
| recorded_by | character varying | NO | 64 | - | - |
| applied | boolean | NO | - | - | - |
| applied_at | timestamp without time zone | YES | - | - | - |
| created_at | timestamp without time zone | NO | - | now() | - |
| updated_at | timestamp without time zone | NO | - | now() | - |

### `oc_learn_policy_weight`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_learn_policy_weight_id_seq': | PK |
| tenant_id | integer | NO | - | - | - |
| policy_code | character varying | NO | 64 | - | - |
| action_type | character varying | NO | 64 | - | - |
| policy_name | character varying | NO | 128 | - | - |
| weight | numeric | NO | - | - | - |
| base_weight | numeric | NO | - | - | - |
| sample_count | integer | NO | - | - | - |
| adopt_count | integer | NO | - | - | - |
| success_count | integer | NO | - | - | - |
| success_rate | numeric | NO | - | - | - |
| avg_score | numeric | NO | - | - | - |
| last_adjusted_at | timestamp without time zone | YES | - | - | - |
| adjust_note | text | NO | - | - | - |
| created_at | timestamp without time zone | NO | - | now() | - |
| updated_at | timestamp without time zone | NO | - | now() | - |

## 审计与安全

### `oc_audit_log`

当前行数：**229**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_audit_log_id_seq'::regclass) | PK |
| tenant_id | integer | YES | - | - | - |
| user_id | integer | YES | - | - | - |
| username | character varying | YES | 64 | - | - |
| event_type | character varying | NO | 32 | - | - |
| action | character varying | YES | 128 | - | - |
| status | character varying | NO | 16 | 'success'::character varying | - |
| status_code | integer | YES | - | - | - |
| method | character varying | YES | 16 | - | - |
| path | character varying | YES | 255 | - | - |
| client_ip | character varying | YES | 64 | - | - |
| user_agent | character varying | YES | 255 | - | - |
| detail | text | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |

## 指标

### `oc_metric`

当前行数：**5**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_metric_id_seq'::regclass) | PK |
| tenant_id | integer | NO | - | - | - |
| category_id | integer | YES | - | - | - |
| source_id | integer | YES | - | - | - |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| description | text | YES | - | - | - |
| metric_type | character varying | NO | 16 | 'atomic'::character varying | - |
| agg_func | character varying | NO | 24 | 'sum'::character varying | - |
| formula | text | YES | - | - | - |
| unit | character varying | NO | 16 | ''::character varying | - |
| precision | integer | NO | - | 2 | - |
| granularity | character varying | NO | 16 | 'day'::character varying | - |
| owner | character varying | YES | 64 | - | - |
| tags | json | YES | - | - | - |
| status | character varying | NO | 16 | 'draft'::character varying | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

### `oc_metric_category`

当前行数：**3**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_metric_category_id_seq'::reg | PK |
| tenant_id | integer | NO | - | - | - |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| parent_id | integer | YES | - | - | - |
| sort_order | integer | NO | - | 0 | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_metric_dimension`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_metric_dimension_id_seq'::re | PK |
| tenant_id | integer | NO | - | - | - |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| dim_type | character varying | NO | 16 | 'enum'::character varying | - |
| source_field | character varying | YES | 128 | - | - |
| value_scope | json | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_metric_dimension_rel`

当前行数：**0**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| metric_id | integer | NO | - | - | PK |
| dimension_id | integer | NO | - | - | PK |

### `oc_metric_value`

当前行数：**222**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_metric_value_id_seq'::regcla | PK |
| tenant_id | integer | NO | - | - | - |
| metric_id | integer | NO | - | - | - |
| stat_time | timestamp with time zone | NO | - | - | - |
| granularity | character varying | NO | 16 | 'day'::character varying | - |
| dims | json | YES | - | - | - |
| dims_hash | character varying | NO | 64 | ''::character varying | - |
| value | numeric | NO | - | '0'::numeric | - |
| created_at | timestamp with time zone | NO | - | now() | - |

## 用户与权限

### `oc_permission`

当前行数：**50**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_permission_id_seq'::regclass | PK |
| code | character varying | NO | 128 | - | - |
| name | character varying | NO | 128 | - | - |
| module | character varying | NO | 64 | - | - |
| description | character varying | YES | 255 | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_role`

当前行数：**4**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_role_id_seq'::regclass) | PK |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| description | character varying | YES | 255 | - | - |
| is_builtin | boolean | NO | - | false | - |
| created_at | timestamp with time zone | NO | - | now() | - |

### `oc_role_permission`

当前行数：**141**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| role_id | integer | NO | - | - | PK |
| permission_id | integer | NO | - | - | PK |

### `oc_user`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_user_id_seq'::regclass) | PK |
| tenant_id | integer | YES | - | - | - |
| username | character varying | NO | 64 | - | - |
| full_name | character varying | YES | 128 | - | - |
| email | character varying | YES | 128 | - | - |
| hashed_password | character varying | NO | 255 | - | - |
| is_active | boolean | NO | - | true | - |
| is_superuser | boolean | NO | - | false | - |
| failed_login_count | integer | NO | - | 0 | - |
| locked_until | timestamp with time zone | YES | - | - | - |
| last_login_at | timestamp with time zone | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |

### `oc_user_role`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| user_id | integer | NO | - | - | PK |
| role_id | integer | NO | - | - | PK |

## 营销渠道

### `oc_channel_campaign`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_channel_campaign_id_seq'::re | PK |
| tenant_id | integer | NO | - | - | - |
| channel_id | integer | NO | - | - | - |
| website_id | integer | YES | - | - | - |
| name | character varying | NO | 128 | - | - |
| campaign_type | character varying | NO | 32 | - | - |
| content_title | character varying | NO | 256 | ''::character varying | - |
| content_body | text | NO | - | ''::text | - |
| target_url | character varying | NO | 512 | ''::character varying | - |
| budget_cents | integer | NO | - | 0 | - |
| schedule_at | character varying | NO | 64 | ''::character varying | - |
| dispatch_mode | character varying | NO | 16 | 'manual'::character varying | - |
| status | character varying | NO | 32 | 'draft'::character varying | - |
| result | text | NO | - | ''::text | - |
| error_message | text | NO | - | ''::text | - |
| reach_count | integer | NO | - | 0 | - |
| click_count | integer | NO | - | 0 | - |
| convert_count | integer | NO | - | 0 | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | YES | - | now() | - |

### `oc_channel_event`

当前行数：**7**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_channel_event_id_seq'::regcl | PK |
| tenant_id | integer | NO | - | - | - |
| channel_id | integer | NO | - | - | - |
| campaign_id | integer | YES | - | - | - |
| event_type | character varying | NO | 32 | - | - |
| level | character varying | NO | 16 | 'info'::character varying | - |
| message | character varying | NO | 512 | ''::character varying | - |
| payload | text | NO | - | ''::text | - |
| created_at | timestamp with time zone | NO | - | now() | - |

## 采集调度

### `oc_collect_run`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_collect_run_id_seq'::regclas | PK |
| tenant_id | integer | NO | - | - | - |
| task_id | integer | NO | - | - | - |
| task_code | character varying | NO | 64 | ''::character varying | - |
| collect_mode | character varying | NO | 16 | 'csv'::character varying | - |
| trigger | character varying | NO | 16 | 'manual'::character varying | - |
| status | character varying | NO | 16 | 'running'::character varying | - |
| rows_in | integer | NO | - | 0 | - |
| rows_written | integer | NO | - | 0 | - |
| rows_failed | integer | NO | - | 0 | - |
| duration_ms | integer | NO | - | 0 | - |
| simulated | boolean | NO | - | false | - |
| message | text | YES | - | - | - |
| detail | json | YES | - | - | - |
| started_at | timestamp with time zone | NO | - | now() | - |
| finished_at | timestamp with time zone | YES | - | - | - |

### `oc_collect_task`

当前行数：**1**

| 字段 | 类型 | 可空 | 长度 | 默认值 | 键 |
|---|---|---|---|---|---|
| id | integer | NO | - | nextval('oc_collect_task_id_seq'::regcla | PK |
| tenant_id | integer | NO | - | - | - |
| code | character varying | NO | 64 | - | - |
| name | character varying | NO | 128 | - | - |
| source_id | integer | YES | - | - | - |
| collect_mode | character varying | NO | 16 | 'csv'::character varying | - |
| target | character varying | NO | 512 | - | - |
| mapping | json | YES | - | - | - |
| extra_config | json | YES | - | - | - |
| schedule_type | character varying | NO | 16 | 'manual'::character varying | - |
| interval_minutes | integer | NO | - | 0 | - |
| cron_expr | character varying | YES | 64 | - | - |
| status | character varying | NO | 16 | 'enabled'::character varying | - |
| last_run_at | timestamp with time zone | YES | - | - | - |
| next_run_at | timestamp with time zone | YES | - | - | - |
| run_count | integer | NO | - | 0 | - |
| success_count | integer | NO | - | 0 | - |
| fail_count | integer | NO | - | 0 | - |
| last_status | character varying | YES | 16 | - | - |
| remark | text | YES | - | - | - |
| created_at | timestamp with time zone | NO | - | now() | - |
| updated_at | timestamp with time zone | NO | - | now() | - |
*（内容由AI生成，仅供参考）*
