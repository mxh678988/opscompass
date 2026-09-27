---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_4fc9f56cb9a111f1b172525400248c00
    ReservedCode1: Z+xgrA440BSDI5ta63r2F+kzkgkqOywYxxkpfqfrEUnxGKzet9/djr0TADh61DyfuLGIz0HQVRJGs9tJpPIDwGkBOyJqRxr3ZJLjfmB8/35dIZ8bt3FJWuHJWpxmsVPzUKv4AC2kOR6w8+YdfRbWh1nu13SGB/A0Uz/yxoinOLCSFbrzr/uiQIdMmj8=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_4fc9f56cb9a111f1b172525400248c00
    ReservedCode2: Z+xgrA440BSDI5ta63r2F+kzkgkqOywYxxkpfqfrEUnxGKzet9/djr0TADh61DyfuLGIz0HQVRJGs9tJpPIDwGkBOyJqRxr3ZJLjfmB8/35dIZ8bt3FJWuHJWpxmsVPzUKv4AC2kOR6w8+YdfRbWh1nu13SGB/A0Uz/yxoinOLCSFbrzr/uiQIdMmj8=
---

# 运营智脑 OpsCompass 管理员手册

> 适用版本：v0.9.0　适用对象：系统管理员（具备全部权限点）

## 1. 管理员职责

| 职责 | 涉及页面 |
|---|---|
| 账号与角色维护 | 用户管理、角色权限 |
| 安全基线维护 | 安全日志、系统配置（`.env`） |
| 数据接入与口径治理 | 数据源、指标中心 |
| 审计与合规 | 审计日志、安全日志导出 |
| 备份与恢复 | 运维脚本（见运维手册） |

登录：系统无公开注册入口，管理员账号在初始化时创建，用户名/密码取自 `.env` 的 `SECURITY_ADMIN_USERNAME` / `SECURITY_ADMIN_PASSWORD`。

## 2. 用户与角色管理

1. **新建用户**：填写用户名、初始密码（长度须满足 `SECURITY_PASSWORD_MIN_LENGTH`）、所属角色。
2. **岗位变更**：优先调整角色，而非逐条加权限。
3. **离职/停用**：立即禁用账号，保留历史操作审计记录。
4. **密码重置**：使用「重置密码」权限点操作，重置后通知本人首次登录修改。

## 3. 权限点清单（共 50 个）

权限模型为 RBAC：权限点 → 角色 → 用户。角色权限应遵循**最小必要**原则。

| 模块 | 权限点 | 说明 |
|---|---|---|
| 系统 | `system:view` | 查看系统概览与状态 |
| 租户 | `tenant:view` / `tenant:create` / `tenant:update` / `tenant:delete` | 租户全生命周期管理 |
| 数据源 | `datasource:view` / `datasource:create` / `datasource:update` / `datasource:delete` / `datasource:sync` | 新增数据源、执行同步 |
| 指标 | `metric:view` / `metric:create` / `metric:update` / `metric:delete` | 指标口径与目标维护 |
| 数据导入 | `ingest:view` / `ingest:run` | 查看与执行导入任务 |
| AI 能力 | `ai:view` / `ai:analyze` / `ai:config` | 触发分析属敏感操作，配置仅管理员 |
| 运营决策 | `ops:view` / `ops:create` / `ops:update` / `ops:delete` | 决策建议与行动项 |
| 用户 | `user:view` / `user:create` / `user:update` / `user:delete` / `user:reset_password` | 账号管理 |
| 角色 | `role:view` / `role:create` / `role:update` / `role:delete` | 角色与授权 |
| 营销渠道 | `marketing:view` / `marketing:create` / `marketing:update` / `marketing:authorize` / `marketing:delete` | 授权属高敏操作 |
| 采集调度 | `collect:view` / `collect:create` / `collect:update` / `collect:run` / `collect:delete` | 采集任务编排与运行 |
| 审计 | `audit:view` / `audit:export` | 导出会留痕，建议限管理员 |
| 模型中心 | `model:view` / `model:config` | 模型接入配置 |
| 学习进化 | `learning:view` / `learning:manage` | 策略权重与经验案例管理 |
| 数字人 | `digital_human:view` / `digital_human:manage` | 形象、音色、工作流与任务 |

**建议角色模板**

| 角色 | 权限点建议 |
|---|---|
| 超级管理员 | 全部 50 个 |
| 运营负责人 | `system:view`、`metric:*`、`ops:*`、`marketing:*`、`learning:*`、`digital_human:*`、`ai:view`、`ai:analyze` |
| 数据分析员 | `datasource:view`、`datasource:sync`、`metric:view`、`ingest:*`、`collect:view`、`ai:view`、`ai:analyze` |
| 内容运营 | `digital_human:*`、`marketing:view`、`learning:view` |
| 只读观察者 | 各模块 `*:view` |

## 4. 安全配置（`.env` 关键项）

| 变量 | 建议值 | 作用 |
|---|---|---|
| `SECRET_KEY` | 32 字节随机串 | JWT 签名，泄露需立即更换并使 Token 失效 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 生产建议 120 以内 | 会话有效期 |
| `SECURITY_LOGIN_MAX_FAILURES` | 5 | 连续失败锁定阈值 |
| `SECURITY_LOGIN_LOCK_MINUTES` | 15 | 锁定时长 |
| `SECURITY_PASSWORD_MIN_LENGTH` | 10 | 口令强度下限 |
| `SECURITY_IP_ALLOWLIST_ENABLED` + `SECURITY_IP_ALLOWLIST` | 生产建议开启 | 管理入口来源限制 |
| `SECURITY_TRUST_FORWARDED_HEADERS` | 反向代理后为 true | 取真实客户端 IP |
| `SECURITY_AUDIT_ENABLED` / `SECURITY_AUDIT_WRITE_OPERATIONS` / `SECURITY_AUDIT_RETENTION_DAYS` | true / true / 180 | 写操作留痕与保留期 |
| `SECURITY_LOG_MIN_LEVEL` / `SECURITY_LOG_ALERT_LEVEL` | INFO / CRITICAL | 过滤与告警镜像 |

修改 `.env` 后执行 `docker compose restart backend` 生效。

## 5. 审计与安全日志

| 类型 | 位置 | 内容 |
|---|---|---|
| 审计日志 | 「安全日志」页 / 库表 | 登录、写操作、权限变更，可按人/时间/动作检索 |
| 安全日志文件 | `logs/security.log` | 独立文件通道，达 `SECURITY_LOG_ALERT_LEVEL` 镜像到主日志供外部告警 |
| 主日志 | `logs/app.log` | 应用运行日志 |

日常动作：每周查看一次 CRITICAL/WARNING 事件；每月导出一次审计记录归档（导出操作本身会留痕）。

## 6. 系统配置与 AI 接入

- **AI 双通道**：`AI_MODE` 选择云端（`AI_API_BASE_URL`/`AI_API_KEY`/`AI_API_MODEL`）或本地（`AI_LOCAL_BASE_URL`/`AI_LOCAL_MODEL`）。
- **模型中心**：硬件探测 → 分档推荐 → 接入验证。
- **密钥保管**：`AI_API_KEY` 仅存于服务端 `.env`，页面不回显明文。

## 7. 数据维护

| 场景 | 操作 |
|---|---|
| 例行备份 | `powershell -File scripts/backup.ps1` |
| 恢复 | 停止 backend → 还原数据库 → 启动并校验数据 |
| 导出数据 | 结果落在 `.env` 的 `EXPORT_DIR`（默认 `./data/exports`） |
| 初始化/迁移 | `python scripts/init_db.py`（幂等，建表 59 张） |

## 8. 管理员日常检查表

| 周期 | 检查项 |
|---|---|
| 每日 | 容器状态、健康检查、CRITICAL 安全事件 |
| 每周 | 账号异动、登录失败趋势、磁盘占用 |
| 每月 | 备份可恢复性验证、权限复核、审计导出归档 |
| 每季度 | 口令轮换、版本升级评估（按季度稳定版本节奏） |
*（内容由AI生成，仅供参考）*
