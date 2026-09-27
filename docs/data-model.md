---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_ef874132b61311f188f9525400248c00
    ReservedCode1: gwOlNeUkrnRgtoCtxnu45Vrq5BwqFV8/9cVMCGGSkP9V/RT4kqdyllW2eDwT2HFhKeCYFqYr8TmMW0LuXDa4geQ/L6kn8QxWtdlY98jrlB5LtKmkS9ocmZ6Orofs6PzZbyoX3imYPVnkkHfXEUHB/qGO6hitFqvML+wpnrSef3YtVsWipnHQK3qHy40=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_ef874132b61311f188f9525400248c00
    ReservedCode2: gwOlNeUkrnRgtoCtxnu45Vrq5BwqFV8/9cVMCGGSkP9V/RT4kqdyllW2eDwT2HFhKeCYFqYr8TmMW0LuXDa4geQ/L6kn8QxWtdlY98jrlB5LtKmkS9ocmZ6Orofs6PzZbyoX3imYPVnkkHfXEUHB/qGO6hitFqvML+wpnrSef3YtVsWipnHQK3qHy40=
---



# 数据模型设计

> 适用范围：运营智脑 Phase 1 数据模型（多租户 + 数据源 + 指标中心）。
> 实现位置：`backend/app/models/`，统一前缀 `oc_`（沿用技术前缀 OpsCompass）。

## 1. 设计原则

1. **多租户隔离**：除租户外，所有业务表均携带 `tenant_id`，唯一约束一律按 `(tenant_id, code)` 组合，避免跨租户编码冲突。
2. **元数据与数据分离**：指标口径（`oc_metric`）与指标值（`oc_metric_value`）分表，口径变更不影响历史数据。
3. **可扩展维度**：维度以独立表 + 多对多关联实现，指标值侧用 `dims` JSON + `dims_hash` 承载维度组合。
4. **敏感字段密文**：数据源密码以 Fernet 密文存入 `password_enc`，接口一律不回显。
5. **时间统一**：所有时间字段使用 `DateTime(timezone=True)`，默认 `now()`。

## 2. 实体关系

```
Tenant (oc_tenant)
  │
  ├── DataSource (oc_data_source)         数据供给端
  │
  ├── MetricCategory (oc_metric_category) 指标分类（自关联树）
  │        │
  ├── MetricDimension (oc_metric_dimension) 维度定义
  │        │  ↕ oc_metric_dimension_rel（多对多）
  └── Metric (oc_metric) ────────────────▶ 指标定义
           │
           └── MetricValue (oc_metric_value) 指标值
```

## 3. 表结构

### 3.1 oc_tenant 租户

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | 自增主键 |
| code | varchar(64) UK | 租户编码 |
| name | varchar(128) | 租户名称 |
| status | varchar(16) | active / disabled |
| remark | varchar(255) | 备注 |
| created_at / updated_at | timestamptz | 创建 / 更新时间 |

### 3.2 oc_data_source 数据源

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | 自增主键 |
| tenant_id | int IDX | 租户 ID |
| code / name | varchar | 数据源编码 / 名称 |
| ds_type | varchar(32) | mysql / postgresql / clickhouse / hive / api / csv |
| host / port / db_name / username | - | 连接信息 |
| password_enc | varchar(512) | 加密后的密码（Fernet） |
| extra_config | json | 扩展配置（API 地址、字符集等） |
| status | varchar(16) | enabled / disabled |
| last_sync_at | timestamptz | 最近同步时间 |

唯一约束：`(tenant_id, code)`。

### 3.3 oc_metric_category 指标分类

`id` / `tenant_id` / `code` / `name` / `parent_id`（自关联，支持多级树） / `sort_order` / `created_at`。
唯一约束：`(tenant_id, code)`。

### 3.4 oc_metric_dimension 维度

| 字段 | 类型 | 说明 |
|---|---|---|
| code / name | varchar | 维度编码 / 名称 |
| dim_type | varchar(16) | enum 枚举 / datetime 时间 / number 数值 |
| source_field | varchar(128) | 来源字段 |
| value_scope | json | 可选值范围 |

唯一约束：`(tenant_id, code)`；与指标通过 `oc_metric_dimension_rel(metric_id, dimension_id)` 多对多关联。

### 3.5 oc_metric 指标定义（核心）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | 自增主键 |
| tenant_id | int IDX | 租户 ID |
| category_id | int FK→category | 分类，删除时 SET NULL |
| source_id | int FK→data_source | 来源数据源，删除时 SET NULL |
| code / name | varchar | 指标编码（如 gmv） / 名称 |
| description | text | 口径说明 |
| metric_type | varchar(16) | atomic 原子 / derived 派生 |
| agg_func | varchar(24) | sum / avg / count / count_distinct / max / min / ratio |
| formula | text | 派生指标表达式（如 `orders / users * 100`） |
| unit | varchar(16) | 元 / 单 / 人 / % |
| precision | int | 小数位，默认 2 |
| granularity | varchar(16) | 默认粒度 hour / day / week / month |
| owner / tags | varchar / json | 负责人 / 标签 |
| status | varchar(16) | draft 草稿 / online 上线 / offline 下线 |
| created_at / updated_at | timestamptz | 时间戳（更新自动刷新） |

约束与索引：唯一 `(tenant_id, code)`；联合索引 `(tenant_id, status)`。
枚举取值集中定义在 `app/models/metric.py`：`METRIC_TYPES` / `AGG_FUNCS` / `GRANULARITIES`。

### 3.6 oc_metric_value 指标值

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | 自增主键 |
| tenant_id | int IDX | 租户 ID |
| metric_id | int FK→metric IDX | 指标 ID，删除时 CASCADE |
| stat_time | timestamptz | 统计时间点 |
| granularity | varchar(16) | 统计粒度 |
| dims | json | 维度组合，如 `{"channel": "app"}` |
| dims_hash | varchar(64) | 维度组合哈希，参与唯一约束 |
| value | numeric(20,6) | 指标值 |
| created_at | timestamptz | 写入时间 |

唯一约束：`(metric_id, stat_time, granularity, dims_hash)` —— **同一「指标 + 时间 + 粒度 + 维度」重复写入即覆盖**（upsert 语义）。
查询索引：`(metric_id, stat_time)`。

## 4. 关键约定

- **命名**：表名 `oc_` 前缀 + 下划线；指标编码使用业务语义小写下划线（`gmv`、`conversion_rate`）。
- **精度**：指标值统一 `numeric(20,6)` 存储，展示精度由 `oc_metric.precision` 控制。
- **软约束**：`status` 字段同时承载「生命周期」语义，指标下线不删除历史值。
- **初始化**：`python -m app.init_db` 建表，`python -m app.seed_demo` 写入演示数据（默认租户 + 演示数据源 + 4 个核心指标 + 近 31 天指标值）。
- **迁移**：开发阶段用 `create_all`，进入 Phase 2 前引入 Alembic 管理增量迁移。

## 5. 表清单速查（v0.10.0，共 64 张）

> 全量字段级定义见 `docs/data-dictionary.md`；表数量以 `python -m app.init_db` 输出为准。

### 5.1 核心与业务表

| 表名 | 字段数 | 当前行数 |
|---|---|---|
| alembic_version | 1 | 1 |
| oc_ai_action_item | 20 | 9 |
| oc_ai_action_policy | 17 | 13 |
| oc_ai_analysis | 21 | 2 |
| oc_ai_audit_log | 11 | 15 |
| oc_ai_data_level_record | 14 | 9 |
| oc_ai_data_level_rule | 15 | 7 |
| oc_ai_insight | 16 | 9 |
| oc_ai_model_endpoint | 20 | 0 |
| oc_audit_log | 14 | 229 |
| oc_channel_campaign | 20 | 1 |
| oc_channel_event | 9 | 7 |
| oc_collect_run | 16 | 1 |
| oc_collect_task | 22 | 1 |
| oc_com_license | 19 | 8 |
| oc_com_license_event | 8 | 29 |
| oc_com_order | 17 | 4 |
| oc_com_plan | 20 | 7 |
| oc_com_usage | 11 | 2 |
| oc_data_source | 15 | 2 |
| oc_dh_avatar | 13 | 2 |
| oc_dh_project | 26 | 1 |
| oc_dh_task | 17 | 4 |
| oc_dh_voice | 13 | 2 |
| oc_dh_workflow | 10 | 1 |
| oc_doc_index | 11 | 9 |
| oc_geo_task | 11 | 10 |
| oc_import_task | 22 | 5 |
| oc_learn_case | 19 | 1 |
| oc_learn_experiment | 22 | 1 |
| oc_learn_feedback | 17 | 1 |
| oc_learn_policy_weight | 16 | 1 |
| oc_marketing_channel | 17 | 3 |
| oc_media_item | 18 | 2 |
| oc_metric | 18 | 5 |
| oc_metric_category | 7 | 3 |
| oc_metric_dimension | 8 | 0 |
| oc_metric_dimension_rel | 2 | 0 |
| oc_metric_value | 9 | 222 |
| oc_page_media_ref | 6 | 0 |
| oc_page_seo_task | 9 | 0 |
| oc_permission | 6 | 52 |
| oc_product_item | 16 | 2 |
| oc_role | 6 | 4 |
| oc_role_permission | 2 | 141 |
| oc_seo_task | 12 | 7 |
| oc_storage_consistency_check | 15 | 66 |
| oc_storage_route_rule | 12 | 28 |
| oc_tenant | 7 | 1 |
| oc_ts_metric_point | 11 | 222 |
| oc_ts_metric_point_p202607 | 11 | 1 |
| oc_ts_metric_point_p202608 | 11 | 63 |
| oc_ts_metric_point_p202609 | 11 | 156 |
| oc_ts_metric_point_p202610 | 11 | 1 |
| oc_ts_metric_point_p202611 | 11 | 0 |
| oc_ts_metric_point_p202612 | 11 | 1 |
| oc_ts_metric_point_p202701 | 11 | 0 |
| oc_ts_metric_point_p202702 | 11 | 0 |
| oc_ts_metric_point_p202703 | 11 | 0 |
| oc_user | 13 | 1 |
| oc_user_role | 2 | 1 |
| oc_website | 16 | 1 |
| oc_website_ai_config | 9 | 1 |
| oc_website_page | 17 | 2 |

### 5.2 数字人模块五表（P6，0.9.0）

| 表名 | 用途 |
|---|---|
| oc_dh_avatar | 数字人形象库（名称、预览图、风格标签、状态） |
| oc_dh_voice | 音色库（名称、语言、性别、引擎参数） |
| oc_dh_workflow | 工作流模板（步骤序列、是否默认） |
| oc_dh_project | 生成项目（口播稿、绑定形象/音色/工作流） |
| oc_dh_task | 生成任务与四阶段状态（script→voice→avatar→compose） |

> 数字人四阶段编排在引擎不可用时自动降级为演练模式（任务留痕，不产出真实媒体文件）。

### 5.3 商业化模块五表（P10，0.10.0）

| 表名 | 用途 |
|---|---|
| oc_com_plan | 套餐定义（编码、名称、授权形态 local / saas / market、计费周期、价格、功能权益 JSON、配额 JSON、状态） |
| oc_com_license | 授权实例（授权码、绑定套餐、主体信息、机器指纹、生效 / 到期时间、签发状态、HMAC-SHA256 签名、离线可复核） |
| oc_com_order | 订单（订单号、套餐、金额、支付渠道、支付状态、下单 / 支付时间、外部交易号） |
| oc_com_usage | 用量计量（授权 × 计量项 × 统计周期的累计用量与配额，用于超限判断） |
| oc_com_license_event | 授权事件流（签发 / 激活 / 校验 / 续期 / 吊销 / 过期等动作留痕，含结果与备注） |

> 授权校验走 `POST /commercial/license/verify`，本地私有化场景可用内置公钥 / 密钥离线复核签名，不依赖联网回源。
*（内容由AI生成，仅供参考）*
