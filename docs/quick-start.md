---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_49d19a78b9a111f1b172525400248c00
    ReservedCode1: YHO1zUW/xw4mPbk57/jWadcindRSKxDpFDYfNnR/G+ls3wsOuE7Gwk1w72Vl4MyRSI68NhvlpkbTiZzIdyTikLmN18ZaaszfxjKOby2OapluIolL6BKTwmGGRUF6hw7RZDjCqf3EtQanlIJSqTGQrRqpNNTHQPcjFlrsBogPjwoyo91L8GrC/LLtHfU=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_49d19a78b9a111f1b172525400248c00
    ReservedCode2: YHO1zUW/xw4mPbk57/jWadcindRSKxDpFDYfNnR/G+ls3wsOuE7Gwk1w72Vl4MyRSI68NhvlpkbTiZzIdyTikLmN18ZaaszfxjKOby2OapluIolL6BKTwmGGRUF6hw7RZDjCqf3EtQanlIJSqTGQrRqpNNTHQPcjFlrsBogPjwoyo91L8GrC/LLtHfU=
---

# 运营智脑 OpsCompass 快速上手

> 适用版本：v0.10.1　目标：15 分钟内跑通「接入 → 度量 → 决策」最小闭环

## 1. 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 11（本项目主用环境）/ Linux |
| 容器运行时 | Docker Desktop（WSL2 后端）或 Docker Engine + Compose v2 |
| 前端开发（可选） | Node.js 20+、npm |
| 端口 | 80（前端）、8000（后端）、5432（PostgreSQL）、6379（Redis）需空闲 |
| 资源建议 | 4 核 CPU / 8GB 内存 / 30GB 磁盘起 |

## 2. 三步启动

```powershell
# 1) 首次：生成环境变量文件
Copy-Item .env.example .env

# 2) 构建并启动四个容器（postgres / redis / backend / frontend）
docker compose up -d --build

# 3) 查看状态，等待 4 个容器均为 healthy / running
docker compose ps
```

| 入口 | 地址 |
|---|---|
| 前端界面 | http://localhost |
| 后端接口文档（Swagger） | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/api/v1/health |

## 3. 登录

- 管理员账号在初始化时由脚本创建，**系统不提供公开注册入口**。
- 用户名取自 `.env` 的 `SECURITY_ADMIN_USERNAME`，密码取自 `.env` 的 `SECURITY_ADMIN_PASSWORD`。
- 连续登录失败达到 `SECURITY_LOGIN_MAX_FAILURES` 次后，账号将锁定 `SECURITY_LOGIN_LOCK_MINUTES` 分钟。
- 首次登录后请立即在「用户管理」中修改密码，并把 `.env` 中的默认口令替换为强口令。

## 4. 五步走通业务闭环

| 步骤 | 页面 | 做什么 |
|---|---|---|
| 1 | 数据源 | 新建数据源（库表/接口/文件），执行连通性测试 |
| 2 | 数据导入 | 上传文件或选择数据源，完成字段映射与校验入库 |
| 3 | 指标中心 | 定义指标口径与目标值，确认指标可回溯 |
| 4 | 运营总览 / 全景罗盘 | 查看关键指标、趋势、链路健康与瓶颈 |
| 5 | 运营参谋 | 触发 AI 分析，查看决策建议与行动项；执行后到「学习进化」回收反馈 |

## 5. 可选能力

**接入本地/云端大模型**

1. 进入「模型中心」，点击硬件探测（自动读取 CPU / 内存 / 显卡）。
2. 按分档建议选择模型（本地 Ollama 或云端 OpenAI 兼容接口）。
3. 在 `.env` 中配置 `AI_ENABLED`、`AI_MODE`、`AI_API_BASE_URL`、`AI_API_KEY`、`AI_API_MODEL` 后重启 backend 容器。

**数字人一键生成**

1. 「数字人」页面依次维护形象库、音色库。
2. 选用或新建工作流模板（`script → voice → avatar → compose` 四阶段）。
3. 提交任务，跟踪四阶段进度与结果。

## 6. 常用命令

| 目的 | 命令 |
|---|---|
| 启动全部服务 | `docker compose up -d` |
| 停止（保留数据） | `docker compose down` |
| 查看日志 | `docker compose logs -f backend` |
| 重启后端（加载新路由后必做） | `docker compose restart backend` |
| 前端重新构建 | `cd frontend; npm run build` |
| 数据库备份 | `powershell -File scripts/backup.ps1` |
| 初始化数据库/建表 | `python scripts/init_db.py` |

## 7. 常见问题

| 现象 | 原因与处理 |
|---|---|
| 接口返回 401 / 403 | Token 过期或权限点不足；重新登录，或由管理员在 RBAC 中为角色补权限 |
| 新接口 404 | 后端容器未加载新路由，执行 `docker compose restart backend` |
| 前端改动不生效 | 前端由 Nginx 托管**构建产物**，改动后必须 `npm run build`，刷新浏览器缓存 |
| 页面白屏 / 接口跨域 | 检查 `.env` 的 `BACKEND_CORS_ORIGINS` 是否包含当前访问地址 |
| 端口被占用 | 修改 `.env` 的 `FRONTEND_PORT` / `BACKEND_PORT` / `POSTGRES_PORT` / `REDIS_PORT` 后重启 |
| 无外网环境构建失败 | 使用宿主机离线构建的 `frontend/dist` 直接挂载（compose 已配置该挂载点） |
| 数据库连不上 | 确认 postgres 容器 healthy，`DATABASE_URL` 主机名在容器内应为 `postgres` |

## 8. 下一步

- 生产部署与安全加固：见 `docs/deployment-manual.md`、`docs/security-whitepaper.md`
- 角色与权限配置：见 `docs/admin-manual.md`
- 备份、故障处理与升级：见 `docs/ops-manual.md`
*（内容由AI生成，仅供参考）*
