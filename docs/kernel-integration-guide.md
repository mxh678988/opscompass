# 内核集成指南（D3）

> 适用产品：运营智脑（让数据自动做出最优决策）
> 面向：内核开发者 / 平台集成方。说明内核模块如何装配、如何与插件 SDK 对接、如何做稳定性与可观测性保障。

## 1. 模块地图

```
backend/app/
├── main.py               # FastAPI 入口，OpenAPI 装配（/api/v1）
├── core/
│   ├── bus/              # 事件总线（M1）：发布/订阅/死信/水位/超时恢复
│   ├── kernel.py         # CoreEvent / CoreEventAudit（审计追溯）
│   ├── plugin/           # 插件运行时（loader/manifest/registry/runtime/signing/storage）
│   ├── workflow/         # 工作流引擎（M7）
│   └── registry/...      # 模型/能力注册与降级
├── sdk/                  # 插件 SDK：仅依赖本包（依赖倒置）
├── models/  schemas/  crud/  services/
└── storage/
```

## 2. 插件装载链路

```
loader 读 plugin.yaml → manifest_validator 校验 → signing 验签（官方强制）
→ registry 登记 → runtime 装载 → register(runtime) 注入业务引擎
→ SDK 门面经内核回调可用
```

- 官方插件 `activate` 强制验签，失败返回 403 语义（S 系列增强）；
- 插件私有存储：`plugins_dir/<plugin_id>/storage`，路径经 `_resolve` 防穿越（M5/S 增强）。

## 3. 事件总线集成（M1/S2/S4/S7）

- 发布：`bus.publish(name, payload, **opts)`，支持 `delay_seconds` / `max_attempts` / `priority`；
- 订阅：`bus.subscribe(name, handler, subscriber=...)`，`core.*` 供插件订阅内核事件；
- 可靠性：死信告警（S2）、积压水位告警（S3）、消费超时恢复（S4）、批量事务（S6）、优先级队列（S7）；
- 审计：`CoreEventAudit` 记录事件全生命周期（S5），凭 `trace_id` 追溯。

## 4. SDK 装配契约

SDK 不 import 内核；内核装载时注入回调（`session_factory` / `authorize_fn` / `storage_fn` / `model_router` / `workflow_engine` 等）。未装配能力调用抛 `NotAvailableError` 并标注计划版本，插件不得误用半成品。

新增门面步骤：
1. 在 `sdk/context.py` 定义 Facade（接口冻结）；
2. 内核在 `create_context` 注入对应回调；
3. 在 `sdk/__init__.py` 导出并升级 `SDK_VERSION`；
4. 补单测：正常路径 + `NotAvailableError` + `NamespaceViolation`。

## 5. 稳定性与可观测性（S 系列）

| 项 | 说明 | 落点 |
|---|---|---|
| S1 幂等去重 | 订阅处理器重复事件去重 | bus |
| S2 健康/死信 | 订阅者健康检查 + 死信告警 | bus / 告警 |
| S3 水位告警 | 积压水位阈值告警 | bus |
| S4 超时恢复 | 消费超时自动恢复 | bus |
| S5 追溯审计 | 事件审计与追溯 | kernel.py |
| S6 批量事务 | 批量消费事务提交 | bus |
| S7 优先级队列 | 延迟/优先级调度 | bus |

## 6. 契约与 CI（A1/A2）

- `docs/openapi.json`：接口契约快照，`scripts/check_openapi.py` 离线比对（路径集合 + 版本），提交前必须一致；
- `docs/api-reference.md`：由 `scripts/gen_api_docs.py` 从快照自动生成，禁止手改；
- `scripts/check_docs.py`：文档链接 / 引用完整性检查；
- `scripts/ci.ps1`：全量检查入口，见 [部署手册](deployment-manual.md)。

## 7. 版本与文档约定（A3）

- 版本策略见 `docs/VERSIONING.md`；多版本共存时按 `docs/` 内约定组织；
- 每个里程碑：`docs/changelog.md` 的 [Unreleased] 补条目 + `docs/os-kernel-design.md` 补能力设计；
- API 文档由脚本生成，`docs/api.md` 为人工维护的接口说明（高层），两者并存不冲突。

## 8. 上线检查清单

- [ ] `python scripts/check_openapi.py` 返回 PASS（快照一致）
- [ ] `python scripts/gen_api_docs.py --check` 返回 PASS（参考文档最新）
- [ ] `python scripts/check_docs.py` 无坏链
- [ ] 全量 `pytest` 无回归
- [ ] `docs/changelog.md` 已补里程碑条目
