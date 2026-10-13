# 插件开发教程（D2）

> 适用产品：运营智脑（让数据自动做出最优决策）
> 以仓库内 `plugins/sentiment`（舆情监控）为完整可运行范例。

本教程带你从零写一个合规插件：清单 → 入口 → SDK 接入 → 本地调试 → 验签发布。全程遵守命名空间与权限约束。

## 1. 插件目录结构

```
plugins/<plugin_id>/
├── plugin.yaml              # 清单：身份/权限/事件/配置声明
└── backend/
    └── src/
        ├── __init__.py
        ├── main.py          # register() 入口（必需）
        ├── core.py          # 业务引擎
        └── database.py      # 表结构/建表
```

`entry` 指向 `backend.src.main:register`，内核按此加载插件。

## 2. 清单 plugin.yaml

```yaml
id: sentiment
name: 舆情监控
version: "0.12.0"
min_kernel_version: "0.11.0"
kind: community
entry: backend.src.main:register
description: 舆情监控与预警，覆盖主题管理、数据采集、情感分析、事件归并、预警分级与报告。
author: 老孟AI智能写作
email: laomeng@example.com
category: risk
license: commercial

namespace:
  tables: os_sentiment_          # 数据表前缀（强制）
  events: "sentiment."           # 事件前缀（强制）
  permissions: "sentiment:"      # 权限前缀（强制）

permissions:
  - code: sentiment:topic:manage
    name: 主题管理
  - code: sentiment:task:create
    name: 创建舆情任务
  - code: sentiment:alert:view
    name: 查看预警

roles:
  - code: sentiment:analyst
    name: 舆情分析师
    permissions:
      - sentiment:topic:manage
      - sentiment:task:create
      - sentiment:alert:view

events:
  publish:
    - sentiment.task.created
    - sentiment.alert.created
  subscribe:
    - core.metric.written

sdk:
  min_version: "0.11.0"
  required_capabilities:
    - event_bus
    - workflow_engine
    - task_sla
    - plugin_signing
    - plugin_storage

config:
  sentiment:
    collection_batch_size: 5000
    alert_cooldown_seconds: 300
  storage:
    root_type: user
    max_file_size_mb: 100
```

要点：
- `namespace` 三段前缀必须与 `ctx` 各门面一致，越界即抛 `NamespaceViolation`；
- 事件只能发布 `publish` 列内的事件（清单即白名单）；
- `required_capabilities` 声明运行期能力依赖，内核装配不足时拒绝加载。

## 3. 入口 main.py

```python
"""插件后端入口。

由内核 PluginRuntime 按清单 entry 加载：内核把自身实例传给 register()，
插件在此把业务引擎注入内核；随后 SDK 的 *.门面即经内核会话工厂调用插件引擎，
插件侧不直连任何内核模块（M2 设计约束）。
"""

from __future__ import annotations
from typing import Any

from .core import create_for_plugin


def register(runtime: Any) -> None:
    """插件注册入口：把业务引擎注入内核 runtime。"""
    runtime.inject_sentiment_engine(create_for_plugin)
```

## 4. 使用 SDK 能力

见 [SDK 使用手册](sdk-guide.md)。典型组合：

```python
from app.sdk import create_context

# 内核侧创建上下文（示例签名，实际由内核注入）
ctx = create_context(plugin_id="sentiment", ...)

# 事件订阅 + 日志 + 存储
ctx.bus.subscribe("core.metric.written", on_metric)
ctx.log.info("插件已启动")
ctx.storage.save("exports/report.csv", data)
```

## 5. 本地调试

```powershell
# 1) 安装依赖
pip install -r backend\requirements.txt

# 2) 运行全量测试（含插件运行时校验）
python -m pytest backend\tests -q

# 3) 启动服务
python scripts\start_dev.ps1
```

插件加载失败时优先检查：清单 `namespace` 前缀、`entry` 路径、`sdk.required_capabilities` 是否超出当前内核装配。

## 6. 验签与发布（M7）

- 社区插件默认以 `community` 发布；官方插件需内核 `activate` 时通过 `signing` 强制验签（S 系列增强）。
- 签名校验失败：插件被拒绝激活（403 语义），详见 [内核集成指南](kernel-integration-guide.md) 与 `security-whitepaper.md`。
- 发布前运行 `python scripts/check_versions.py` 确认清单版本与代码版本一致。

## 7. 验收清单

- [ ] 三个 namespace 前缀与清单一致，且未越界使用
- [ ] register() 入口存在，entry 路径正确
- [ ] 单测覆盖：加载 / 激活 / 业务调用 / 验签拒绝
- [ ] 全量 pytest 无回归
*（内容由AI生成，仅供参考）*
