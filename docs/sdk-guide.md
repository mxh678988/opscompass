# SDK 使用手册（D1）

> 适用产品：运营智脑（让数据自动做出最优决策）
> SDK 版本：`1.0.0` ｜ 对应内核：v0.12.0+（min_kernel_version 见插件清单）

插件作者**只依赖本 SDK 包**，通过 `PluginContext` 使用内核能力；SDK 不 import 任何内核内部模块（依赖倒置，M2 设计约束），内核可自由重构而不破坏插件。

- 源码：`backend/app/sdk/__init__.py`（门面导出）、`backend/app/sdk/context.py`（实现）
- 异常：`SdkError` / `NamespaceViolation` / `NotAvailableError` / `ManifestError`（`backend/app/sdk/exceptions.py`）

## 1. 入口：register(runtime)

内核按清单 `entry`（如 `backend.src.main:register`）加载插件，把内核实例传给 `register()`；插件在此把业务引擎注入内核，或读取 `ctx` 完成初始化。

```python
from __future__ import annotations
from typing import Any


def register(runtime: Any) -> None:
    """插件注册入口：把业务引擎注入内核 runtime。"""
    runtime.inject_sentiment_engine(create_for_plugin)
```

## 2. 门面总览

| 分类 | 门面 | 常用接口 | 落地 |
|---|---|---|---|
| 数据 | `ctx.db` | `session()` / `assert_table()` | M2 |
| 事件 | `ctx.bus` | `publish()` / `subscribe()` | M1/M2 |
| 权限 | `ctx.auth` | `require()` / `check()` | M3 |
| 配置 | `ctx.config` | `get()` / `set()` / `all()` | M2 |
| 模型 | `ctx.model` | `run()` / `declare()` / `stats()` / `is_degraded()` | M6 |
| 日志 | `ctx.log` | `info/warn/error/debug` / `bind(trace_id)` | M2 |
| 定时 | `ctx.job` | `register(job_id, cron, handler)` | M4 |
| 存储 | `ctx.storage` | `save()` / `read()` / `delete()` / `list()` | M5 |
| 待办 | `ctx.task` | `create(title, sla)` | M4 |
| 工作流 | `ctx.workflow` | `create_instance/run/pause/resume/cancel` | M7 |
| 签名 | `ctx.signing` | `verify_self()` / `key_fingerprint()` | M7 |
| 前端 | `ctx.ui` | `register_menu()` / `register_route()` | M2（登记） |
| 业务 | `ctx.sentiment` | 舆情监控业务门面（试点插件专属） | M8 |

## 3. 数据门面 `ctx.db`

只能访问**自身命名空间表**（`namespace.tables` 前缀，如 `os_sentiment_`）；越界表名抛 `NamespaceViolation`。

```python
with ctx.db.session() as db:
    rows = db.execute(text("SELECT * FROM os_sentiment_topic WHERE tenant_id=:t"), {"t": tid}).all()
```

- `session()`：打开会话（由内核注入的会话工厂创建）
- `assert_table(name)`：校验表名落在插件命名空间内

## 4. 事件门面 `ctx.bus`

强制约束：只能发布 `自身事件前缀*` 的事件；只能订阅 `自身前缀*` 或 `core.*`。

```python
# 发布（返回 event_id）
event_id = ctx.bus.publish("sentiment.alert.created", {"topic_id": "t1"})

# 订阅
ctx.bus.subscribe("core.metric.written", on_metric, subscriber="sentiment")
```

支持 `**kwargs` 透传内核发布参数：`delay_seconds`（延迟秒数）、`max_attempts`、`priority`（越小越先派发，S7）、`trace_id`。

## 5. 权限门面 `ctx.auth`

统一鉴权，插件不得自行实现；权限点必须落在自身 `namespace.permissions` 前缀内。

```python
ctx.auth.require("sentiment:alert:view", user=current_user)
if ctx.auth.check(user, "sentiment:task:create"):
    ...
```

未装配时 `require` / `check` 抛 `NotAvailableError`，防止插件误以为已受控。

## 6. 配置门面 `ctx.config`

独立配置分区（内核 `ConfigStore` 实现），按插件隔离。

```python
batch = ctx.config.get("sentiment.collection_batch_size", default=5000)
ctx.config.set("sentiment.alert_cooldown_seconds", 300)
all_cfg = ctx.config.all()  # {"sentiment": {...}, "storage": {...}}
```

## 7. 模型门面 `ctx.model`

统一模型路由（M6），本地不可用时自动降级规则兜底。

```python
result = ctx.model.run("classify", {"text": "..."})
ctx.model.declare("classify", provider="rule")
stats = ctx.model.stats()
if ctx.model.is_degraded():
    ...
ctx.model.set_global_degrade(True)  # 全局降级开关
```

## 8. 日志门面 `ctx.log`

自动携带 `plugin_id`，可选 `trace_id` 串联请求全链路。

```python
ctx.log.info("主题创建成功 topic_id=%s", topic_id)
ctx.log.warn("采集超时 source_id=%s", sid)
ctx.log.error("分析失败: %s", exc)
with_trace = ctx.log.bind(trace_id="req-123")
```

## 9. 定时门面 `ctx.job`

注册 Cron 定时任务（内核调度）。

```python
ctx.job.register("sentiment-daily-report", "0 6 * * *", run_daily_report)
```

## 10. 存储门面 `ctx.storage`

插件私有文件空间：`plugins_dir/<plugin_id>/storage`；路径经 `_resolve` 校验，拒绝绝对路径 / `..` 穿越，必须落在插件根内。

```python
ctx.storage.save("exports/report.csv", csv_bytes)   # 自动建父目录
data = ctx.storage.read("exports/report.csv")
ctx.storage.delete("exports/report.csv")
files = ctx.storage.list("exports/")                # 前缀过滤
```

## 11. 待办门面 `ctx.task`

```python
ctx.task.create("舆情预警待复核", sla={"deadline_hours": 24})
```

## 12. 工作流门面 `ctx.workflow`（M7）

```python
inst = ctx.workflow.create_instance("risk_response", input={"event_id": "e1"})
ctx.workflow.run(inst["instance_id"])
ctx.workflow.confirm_wait_step(inst_id, seq=2)
ctx.workflow.pause(inst_id, reason="等待人工")
ctx.workflow.resume(inst_id)
```

## 13. 签名门面 `ctx.signing`（M7）

```python
info = ctx.signing.verify_self()          # 校验自身签名
fp = ctx.signing.key_fingerprint()        # 公钥指纹
```

## 14. 前端门面 `ctx.ui`

菜单 / 路由声明，由内核动态注入前端装配表。

```python
ctx.ui.register_menu("/sentiment", "舆情监控", icon="dashboard")
ctx.ui.register_route("/sentiment/detail", "SentimentDetail.vue")
```

## 15. 接口稳定性承诺

SDK 主版本内向后兼容；弃用项提前一个次版本标注，下个大版本移除。插件清单 `sdk.min_version` 与内核版本独立。
