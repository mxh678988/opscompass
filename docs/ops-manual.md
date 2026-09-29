---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_52ecf8d6b9a111f1b172525400248c00
    ReservedCode1: SJ+bCBIIx+Fs/ClHCdr0BnLN8jUECosgVSRZ41P5d60iW1CcZUIJ1MEBAn4QKH0jO6WJivB9vmmdZ2adxZeO91ReQqmqtpcsJYiLaXmbGbbd8GetqbCDWm2qEora1j9gFWD3kgx25d9aT+87ecoQyCh1Lku5TGDYe6s490yPr6VNvUpxBwfffLTBySg=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_52ecf8d6b9a111f1b172525400248c00
    ReservedCode2: SJ+bCBIIx+Fs/ClHCdr0BnLN8jUECosgVSRZ41P5d60iW1CcZUIJ1MEBAn4QKH0jO6WJivB9vmmdZ2adxZeO91ReQqmqtpcsJYiLaXmbGbbd8GetqbCDWm2qEora1j9gFWD3kgx25d9aT+87ecoQyCh1Lku5TGDYe6s490yPr6VNvUpxBwfffLTBySg=
---

# 运营智脑 OpsCompass 运维手册

> 适用版本：v0.10.0　适用对象：运维 / 技术支持人员

## 1. 服务拓扑与依赖

```
浏览器 ──> frontend(Nginx:80) ──静态产物──> frontend/dist
                    │
                    └──> backend(FastAPI:8000) ──> postgres:5432
                                              └──> redis:6379
```

四个容器：`opscompass-postgres`、`opscompass-redis`、`opscompass-backend`、`opscompass-frontend`，同属 `opscompass-net` 网络。

启动顺序依赖：postgres / redis healthy → backend → frontend。

## 2. 日常巡检

| 项 | 命令 | 正常判据 |
|---|---|---|
| 容器状态 | `docker compose ps` | 4 容器 running，postgres/redis healthy |
| 后端健康 | `curl http://localhost:8000/api/v1/health` | HTTP 200 |
| 前端可用 | 浏览器访问 http://localhost | 登录页正常渲染 |
| 后端日志 | `docker compose logs --tail=200 backend` | 无 ERROR 堆栈 |
| 安全日志 | 查看 `logs/security.log` | 无未处置 CRITICAL |
| 磁盘 | 检查 `data/`、`logs/` 增长 | 剩余空间充足 |

## 3. 启停与重启

| 目的 | 命令 |
|---|---|
| 启动全部 | `docker compose up -d` |
| 停止（保留数据） | `docker compose down` |
| 重启后端（改路由/环境变量后） | `docker compose restart backend` |
| 重启单个数据库 | `docker compose restart postgres` |
| 重建镜像 | `docker compose build` |
| 查看实时日志 | `docker compose logs -f --tail=100 backend` |

> 注意：修改 `.env` 后必须重启 backend 才生效；修改前端源码后必须 `npm run build`，因为 Nginx 托管的是构建产物。

## 4. 备份与恢复

**备份**

```powershell
powershell -File scripts/backup.ps1     # 导出数据库到备份目录
```

**恢复**

1. 记录当前版本与时间点。
2. `docker compose stop backend`（停写入）。
3. 还原数据库备份至 `opscompass` 库。
4. `docker compose start backend`，执行 `python scripts/init_db.py`（幂等校验表结构）。
5. 校验：登录、指标列表、最近业务数据条数。

**校验项**：备份文件非空可解压；恢复后行数与备份前一致；关键表（`oc_metric*`、`oc_ops*`、`oc_dh_*`）数据完整。

## 5. 日志管理

| 日志 | 路径 | 说明 |
|---|---|---|
| 应用日志 | `logs/app.log` | 运行与异常信息 |
| 安全日志 | `logs/security.log` | 按级别过滤，大小 5MB 轮转，保留 5 份 |
| 容器日志 | `docker compose logs <service>` | 标准输出通道 |

排查建议：先看 `docker compose logs backend` 的 ERROR 行，再核对 `logs/security.log` 是否有鉴权/锁定记录。

## 6. 常见故障处理

| 现象 | 排查步骤 | 处理 |
|---|---|---|
| 接口全部 502 / 无响应 | `docker compose ps` 看 backend 是否 running | 查看日志；常见为数据库未 healthy，等待或重启 postgres |
| 新加接口 404 | 确认代码已在容器内（`./backend` 已挂载） | `docker compose restart backend` |
| 前端页面改动不生效 | 确认是否重新构建 | `cd frontend; npm run build`，清理浏览器缓存 |
| 登录提示账号锁定 | 查看 `SECURITY_LOGIN_LOCK_MINUTES` | 等待锁定期结束，或由管理员在用户管理中处理 |
| 数据库连接失败 | 容器内主机名应为 `postgres`，宿主机调试才用 `localhost` | 修正 `.env` 后重启 backend |
| 磁盘增长过快 | 检查 `data/postgres`、`logs/` | 归档旧日志、清理导出文件，必要时扩容 |
| 端口冲突 | `netstat -ano | findstr :80` | 改 `.env` 端口或释放占用进程 |
| Redis 连接异常 | `docker compose exec redis redis-cli ping` | 返回 PONG 正常，否则重启 redis |
| 无外网无法构建 | 使用离线产物 | 直接挂载 `frontend/dist`，镜像走离线包导入 |

## 7. 性能与容量

| 维度 | 观察点 | 建议 |
|---|---|---|
| CPU / 内存 | `docker stats` | 后端持续高占用时排查慢查询与长任务 |
| 数据库 | 连接数、慢查询 | 为高频指标查询建立索引；定期 VACUUM |
| Redis | 内存占用、命中率 | 关注大 key，必要时调整淘汰策略 |
| 磁盘 | 数据卷与日志增长 | 按月归档，保留合规所需期限 |
| 前端 | 首屏加载 | 产物已压缩，必要时开启代理缓存 |

## 8. 升级与版本节奏

- 版本发布节奏：按季度（约 3 个月）一个稳定小版本。
- 进化原则：无故障且无人操作连续达标即冻结；正常不回退，仅故障触发回退。
- 升级流程：备份 → 构建 → 启动 → 迁移 → 验证 → 观察 24 小时。
- 回滚准备：保留上一版本镜像与发布包，确保可 10 分钟内回退。

## 9. 变更与应急联系

| 场景 | 动作 |
|---|---|
| 常规变更 | 记录变更项、时间、执行人，变更后验证 |
| 紧急变更 | 先止损（重启/回滚/收紧权限），事后补记录 |
| 安全事件 | 按《安全白皮书》第 9 章流程处置 |
| 数据丢失 | 立即停止写入，从最近备份恢复，评估影响范围 |
*（内容由AI生成，仅供参考）*
