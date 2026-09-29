---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_56c0550bb9a111f189c8525400393706
    ReservedCode1: QtCNvKHC+LzYBVICpmjjBOL1ef7DOG9ETWV7CwZoQrmTc7hL29lPuSfP/gyFk3TpQQ+nbT/0GrS4mct290syyUpxUdOrMfcMZ1UPXSvaTJMFgogY3BlkNu2VNm7FdRRjl31X+01/6u4UpNN9rbxOfff58hrNS8TV5IFawq2emQwC2HKDIlVIdFSs4jk=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_56c0550bb9a111f189c8525400393706
    ReservedCode2: QtCNvKHC+LzYBVICpmjjBOL1ef7DOG9ETWV7CwZoQrmTc7hL29lPuSfP/gyFk3TpQQ+nbT/0GrS4mct290syyUpxUdOrMfcMZ1UPXSvaTJMFgogY3BlkNu2VNm7FdRRjl31X+01/6u4UpNN9rbxOfff58hrNS8TV5IFawq2emQwC2HKDIlVIdFSs4jk=
---

# 运营智脑 OpsCompass 安全白皮书

> 适用版本：v0.10.0　编制：BY LAOMENG 网络工作室　日期：2026-09-26

## 1. 安全目标与设计原则

| 目标 | 落地手段 |
|---|---|
| 身份可信 | JWT 令牌认证 + 登录失败锁定 |
| 权限最小 | RBAC 权限点（50 个）+ 接口级权限依赖注入 |
| 行为可溯 | 审计日志 + 分级安全日志 |
| 传输可控 | 反向代理 TLS、CORS 白名单、来源 IP 白名单 |
| 数据可守 | 容器隔离、持久化卷、备份与恢复流程 |

设计原则：默认拒绝（未显式授权即不可访问）、最小暴露（端口与接口收敛）、可审计（关键操作留痕）、可回滚（备份优先）。

## 2. 身份认证

- **令牌机制**：登录成功后签发 JWT，默认有效期 `ACCESS_TOKEN_EXPIRE_MINUTES`（模板 1440 分钟，生产建议 ≤120 分钟）。
- **签名密钥**：`SECRET_KEY` 用于令牌签名；泄露或轮换时须同步使在途令牌失效。
- **口令策略**：口令长度下限由 `SECURITY_PASSWORD_MIN_LENGTH` 控制；口令不以明文存储、不在页面回显。
- **防暴力破解**：连续失败达 `SECURITY_LOGIN_MAX_FAILURES` 次锁定账号 `SECURITY_LOGIN_LOCK_MINUTES` 分钟，并写入安全日志。
- **无公开注册**：系统不提供开放注册接口，账号仅由管理员创建，从源头消除匿名入口。

## 3. 访问控制

- **模型**：RBAC（角色—权限点—用户），权限点共 **50 个**，按 15 个模块划分（system、tenant、datasource、metric、ingest、ai、ops、user、role、marketing、collect、audit、model、learning、digital_human）。
- **校验位置**：路由层以依赖注入方式声明所需权限点，未授权请求返回 403；未认证返回 401。
- **高危操作**：`ai:config`、`model:config`、`marketing:authorize`、`user:reset_password`、`audit:export`、`tenant:delete` 建议仅授予管理员。
- **租户隔离**：多租户场景下按租户维度隔离数据访问范围。

## 4. 传输与网络

| 项 | 措施 |
|---|---|
| 加密传输 | 由 Nginx / 反向代理终结 TLS（证书由部署环境提供），公网仅暴露 443 |
| CORS | `BACKEND_CORS_ORIGINS` 显式白名单，生产禁止 `*` |
| 安全响应头 | 后端中间件链统一注入安全响应头 |
| 来源限制 | `SECURITY_IP_ALLOWLIST_ENABLED` + `SECURITY_IP_ALLOWLIST` 限制管理入口来源 |
| 真实 IP | 反向代理后置 `SECURITY_TRUST_FORWARDED_HEADERS=true`，审计记录真实客户端 IP |
| 端口收敛 | 8000 / 5432 / 6379 不对公网开放 |

## 5. 审计与安全日志

| 通道 | 配置 | 用途 |
|---|---|---|
| 审计日志 | `SECURITY_AUDIT_ENABLED=true`、`SECURITY_AUDIT_WRITE_OPERATIONS=true`、`SECURITY_AUDIT_RETENTION_DAYS=180` | 记录登录与写操作，支撑追责与合规 |
| 安全日志文件 | `SECURITY_LOG_FILE=security.log`，`SECURITY_LOG_MAX_BYTES=5242880`，`SECURITY_LOG_BACKUP_COUNT=5` | 独立文件通道，按级别过滤，自动轮转 |
| 高危告警镜像 | `SECURITY_LOG_ALERT_LEVEL=CRITICAL`、`SECURITY_LOG_MIRROR_TO_MAIN=true` | 高危事件镜像至主日志，供外部告警系统抓取 |

级别定义：INFO（常规安全事件）、WARNING（可疑行为，如多次失败登录）、CRITICAL（高危，如权限变更、敏感配置修改）。

## 6. 凭据与敏感数据保护

- 敏感配置（数据库口令、`SECRET_KEY`、`AI_API_KEY`）仅存于服务端 `.env`，`.env` 不得提交版本库。
- 前端不存储密钥，接口密钥仅在服务端参与调用。
- 部署交付时随包附数字签名，校验通过后方可安装，防止被篡改。
- 授权码与机器指纹绑定，防止跨机复制运行。

## 7. 容器与运行环境

| 措施 | 说明 |
|---|---|
| 网络隔离 | 四容器置于独立桥接网络 `opscompass-net`，仅必要端口映射到宿主机 |
| 依赖收敛 | 数据库/缓存仅在编排网络内可达，不对外暴露 |
| 数据持久化 | 数据卷 `./data/postgres`、`./data/redis` 独立于容器生命周期 |
| 最小权限运行 | 生产环境关闭 `DEBUG`，降低错误细节外泄风险 |
| 健康检查 | postgres / redis 内置健康检查，后端启动依赖其 healthy 状态 |

## 8. 安全运维要求

| 周期 | 要求 |
|---|---|
| 上线前 | 更换 `SECRET_KEY` 与管理员默认口令；关闭 `DEBUG`；开启 IP 白名单；收敛 CORS |
| 每日 | 关注 CRITICAL 安全事件 |
| 每周 | 检查登录失败趋势与账号异动 |
| 每月 | 备份可恢复性验证、权限最小化复核 |
| 每季度 | 口令与密钥轮换、依赖版本安全评估、版本升级（季度稳定版本） |

## 9. 事件响应流程

1. **发现**：安全日志 CRITICAL 告警或人工上报。
2. **止损**：禁用涉事账号、轮换 `SECRET_KEY`（使令牌失效）、必要时收紧 IP 白名单或下线接口。
3. **取证**：导出审计日志与安全日志，锁定时间线与影响范围。
4. **修复**：修补缺陷、更新配置、升级版本。
5. **复盘**：输出改进项，必要时沉淀为策略规则与检测项。

## 10. 已知边界与责任划分

- TLS 证书、主机加固、云安全组、宿主机账号安全由**部署方**负责。
- 本产品负责应用层认证、授权、审计、日志与配置安全。
- 本白皮书描述的能力以 v0.10.0 实际实现为准，实现细节可参见 `backend/app/services/auth_service.py`、`backend/app/api/deps.py`、`backend/app/core` 相关模块。
*（内容由AI生成，仅供参考）*
