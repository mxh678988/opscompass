---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_4d0185a8b9a111f1b172525400248c00
    ReservedCode1: YJWRRRLMjtvCsry0OLaYqHxhOsarh77yDecOgHAVQxLiktjB8rC1l6ZhG6tQLQ9TY8Bl4SWeizyBD+l9/gGd8pfLuFeRZnxA50qy8X6/6GV8p5dwQHVLwbqYcY9Eyl4yIdrgYoTWE7oCgNtRqiZJ6gDz0XYrinjqJWStCL/lGrwrnAl2g0bbzr8KE7M=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_4d0185a8b9a111f1b172525400248c00
    ReservedCode2: YJWRRRLMjtvCsry0OLaYqHxhOsarh77yDecOgHAVQxLiktjB8rC1l6ZhG6tQLQ9TY8Bl4SWeizyBD+l9/gGd8pfLuFeRZnxA50qy8X6/6GV8p5dwQHVLwbqYcY9Eyl4yIdrgYoTWE7oCgNtRqiZJ6gDz0XYrinjqJWStCL/lGrwrnAl2g0bbzr8KE7M=
---

# 运营智脑 OpsCompass 部署手册

> 适用版本：v0.10.1　覆盖本地私有化 / 云端 SaaS / 应用市场离线三种形态

## 1. 部署形态总览

| 形态 | 适用对象 | 关键差异 |
|---|---|---|
| A 本地私有化 | 单商家、数据不出内网 | 默认端口直连，可加自签 HTTPS |
| B 云端 SaaS | 多商家订阅制 | 域名 + 正式证书、多租户、安全组收敛、异地备份 |
| C 生产镜像直用 | 正式生产 / 交付客户 | 免构建（只用已发布版本镜像）、内部端口不外露、离线镜像包 + SHA256 校验 |
| D 应用市场离线 | 渠道分发 / 无外网 | 离线镜像或安装包、签名校验、授权码绑定机器指纹 |

形态 A 使用开发编排 `docker-compose.yml`（源码 bind mount + 现场构建）；形态 B/C 均基于生产编排 `docker-compose.prod.yml`（镜像直用、免构建），仅环境变量、域名证书与分发方式不同。两套编排并列存在、互不叠加，同一台机器同一时刻只运行其中一套。

## 2. 组件与端口

| 容器 | 镜像 | 端口（默认） | 数据卷 |
|---|---|---|---|
| opscompass-postgres | postgres:16-alpine | 5432 | `./data/postgres` |
| opscompass-redis | redis:7-alpine（AOF 持久化） | 6379 | `./data/redis` |
| opscompass-backend | 本地构建 `deploy/docker/Dockerfile.backend` / 生产用 `opscompass-backend:<版本>` | 8000 | `./backend`、`./data`、`./logs` |
| opscompass-frontend | 本地构建 `deploy/docker/Dockerfile.frontend`（Nginx）/ 生产用 `opscompass-frontend:<版本>` | 80 | `./frontend/dist`（只读挂载，仅开发编排） |

网络：桥接网络 `opscompass-net`；容器间以服务名互访（backend 连 `postgres:5432`、`redis:6379`）。

| 编排文件 | 场景 | 端口暴露 | 源码挂载 |
|---|---|---|---|
| `docker-compose.yml` | 开发 / 本地私有化（形态 A） | 80 / 443 / 8000 / 5432 / 6379 | 挂载 `./backend`、`./frontend/dist` |
| `docker-compose.prod.yml` | 生产 / 交付（形态 B、C） | 仅 80（HTTPS 叠加后 80 + 443） | 不挂载源码，镜像自包含 |

## 3. 形态 A：本地私有化部署

```powershell
cd D:\OpsCompass
Copy-Item .env.example .env          # 首次
# 编辑 .env：修改 SECRET_KEY、POSTGRES_PASSWORD、SECURITY_ADMIN_PASSWORD
docker compose up -d --build
docker compose ps                     # 4 容器 healthy
# 前端如需改动：
cd frontend; npm run build
```

验收：`http://localhost` 可登录，`http://localhost:8000/api/v1/health` 返回正常。

**HTTPS（可选）**：使用 `deploy/nginx` 下的配置模板，替换证书路径为自签证书，nginx 侧 443 监听并 301 跳转 80。

## 4. 形态 B：云端 SaaS 部署

| 项 | 建议 |
|---|---|
| 服务器 | 4 核 8GB 起（含容器与数据库），磁盘 100GB SSD |
| 安全组 | 仅放行 443（对外）；8000 / 5432 / 6379 **不得**对公网开放 |
| 域名与证书 | 正式证书（Let's Encrypt 或商业证书），Nginx 终结 TLS |
| 多租户 | 开启租户隔离能力，按租户分配独立数据空间与账号 |
| CORS | `BACKEND_CORS_ORIGINS` 改为正式域名，禁用 `*` |
| 密钥 | 更换 `SECRET_KEY`（32 字节随机串）、数据库强口令、Redis 设密码 |
| 备份 | 定时 `pg_dump` + 异地留存，保留周期按合规要求设定 |

上线前务必执行：① 关闭 `DEBUG`；② 管理员默认口令替换；③ 开启 IP 白名单（`SECURITY_IP_ALLOWLIST_ENABLED=true`）；④ 反向代理下开启 `SECURITY_TRUST_FORWARDED_HEADERS=true` 以取真实客户端 IP。

## 5. 形态 C：生产环境 · 镜像直用部署（推荐）

生产环境**不在服务器上构建**，只运行已发布的版本化镜像（`opscompass-backend:<版本>` / `opscompass-frontend:<版本>`）。编排文件为根目录 `docker-compose.prod.yml`，与开发编排并列且互不叠加。

**与开发编排的关键差异**

| 维度 | docker-compose.yml（开发） | docker-compose.prod.yml（生产） |
|---|---|---|
| 镜像来源 | `build:` 现场构建 | `image:` 拉取 / 载入版本镜像 |
| 源码挂载 | 挂载 `./backend`、`./frontend/dist` | 不挂载（镜像自包含） |
| 端口暴露 | 80 / 443 / 8000 / 5432 / 6379 | 仅 80（后端与数据层仅容器网内可达） |
| 重启策略 | 无 | `restart: always` |
| 日志 | 默认 | json-file 轮转（10~20MB × 5） |
| 版本标识 | — | `OPS_VERSION` 变量，默认 0.10.1 |

**部署步骤（联网服务器）**

```bash
cd /opt/opscompass
cp .env.example .env            # 编辑 SECRET_KEY / POSTGRES_PASSWORD / SECURITY_ADMIN_PASSWORD
                                # 并将 DEBUG=false、ENV=production
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
curl http://127.0.0.1/health
```

**部署步骤（无外网服务器：离线镜像包）**

```powershell
# ① 构建机：导出镜像 + 生成 SHA256（默认输出 deploy/dist/，已 gitignore）
powershell -File deploy/scripts/pack-images.ps1
#   → deploy/dist/opscompass-0.10.1-images.tar
#   → deploy/dist/opscompass-0.10.1-images.tar.sha256
```

```bash
# ② 服务器：校验并载入（校验失败即中止，退出码 3）
bash deploy/scripts/load-images.sh deploy/dist/opscompass-0.10.1-images.tar

# ③ 校验并启动
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

**启用 HTTPS（可选）**

```bash
# 证书放入 deploy/nginx/certs/server.crt|server.key
docker compose -f docker-compose.prod.yml \
               -f deploy/docker/docker-compose.prod.https.yml up -d
```

叠加后 80 端口 301 跳转 443，`/api/` 反向代理至 `backend:8000`。

**验收**：`http://<域名或IP>/` 可访问登录页，`/health` 返回 `ok`；`docker compose -f docker-compose.prod.yml ps` 中 4 容器 running，postgres/redis healthy。

## 6. 形态 D：应用市场 / 离线交付

1. **构建产物**：构建机执行 `pack-images.ps1` 导出离线镜像包（含 SHA256）；前端产物同时可从 `frontend/dist` 取用。
2. **免构建启动**：基于形态 C 的 `docker-compose.prod.yml`，镜像内已含前端构建产物与 Nginx 站点配置，无外网环境无需拉取基础镜像即可运行。
3. **完整性校验**：发布包附数字签名，安装前校验签名，避免被篡改。
4. **授权绑定**：授权码与机器指纹绑定，防止跨机复制运行。
5. **安装包**：`deploy` 目录已含安装脚本与说明，按渠道要求打包上架。

## 7. 环境变量分类

| 分类 | 关键变量 | 说明 |
|---|---|---|
| 项目 | `PROJECT_NAME`、`PROJECT_SLOGAN`、`ENV`、`DEBUG`、`TIMEZONE` | `ENV=development`、`DEBUG=true` 仅用于开发 |
| 后端 | `BACKEND_HOST`、`BACKEND_PORT`、`BACKEND_CORS_ORIGINS`、`SECRET_KEY`、`ACCESS_TOKEN_EXPIRE_MINUTES`、`LOG_LEVEL` | Token 默认 1440 分钟 |
| 数据库 | `POSTGRES_HOST/PORT/USER/PASSWORD/DB`、`DATABASE_URL` | 容器内主机名为 `postgres` |
| Redis | `REDIS_HOST/PORT/DB/PASSWORD` | 生产必须设密码 |
| 前端 | `FRONTEND_PORT`、`VITE_APP_TITLE`、`VITE_API_BASE_URL` | 改动后需重新 build |
| AI | `AI_ENABLED`、`AI_MODE`、`AI_API_BASE_URL`、`AI_API_KEY`、`AI_API_MODEL`、`AI_LOCAL_BASE_URL`、`AI_LOCAL_MODEL`、`AI_PROXY`、`AI_TIMEOUT`、`AI_MAX_TOKENS`、`AI_TEMPERATURE` | 支持云端 OpenAI 兼容接口与本地 Ollama 双通道 |
| 安全 | `SECURITY_IP_ALLOWLIST_ENABLED`、`SECURITY_IP_ALLOWLIST`、`SECURITY_TRUST_FORWARDED_HEADERS`、`SECURITY_AUDIT_ENABLED`、`SECURITY_AUDIT_WRITE_OPERATIONS`、`SECURITY_AUDIT_RETENTION_DAYS`、`SECURITY_LOGIN_MAX_FAILURES`、`SECURITY_LOGIN_LOCK_MINUTES`、`SECURITY_PASSWORD_MIN_LENGTH`、`SECURITY_ADMIN_USERNAME`、`SECURITY_ADMIN_PASSWORD` | 详见安全白皮书 |
| 安全日志 | `SECURITY_LOG_ENABLED`、`SECURITY_LOG_MIN_LEVEL`、`SECURITY_LOG_FILE`、`SECURITY_LOG_MAX_BYTES`、`SECURITY_LOG_BACKUP_COUNT`、`SECURITY_LOG_ALERT_LEVEL`、`SECURITY_LOG_MIRROR_TO_MAIN` | 独立文件通道 + 高危镜像告警 |
| 目录 | `DATA_DIR`、`EXPORT_DIR`、`LOG_DIR` | 默认 `./data`、`./data/exports`、`./logs` |

## 8. 升级与回滚

**升级（开发 / 形态 A）**

```powershell
powershell -File scripts/backup.ps1        # 1 备份数据库
docker compose build                        # 2 构建新镜像
docker compose up -d                        # 3 滚动替换
python scripts/init_db.py                   # 4 执行建表/迁移（幂等）
docker compose ps && curl http://localhost:8000/api/v1/health
```

**升级（生产 / 形态 C：镜像直用，免构建）**

```powershell
# 构建机
docker build -f deploy/docker/Dockerfile.backend  -t opscompass-backend:0.10.2  .
docker build -f deploy/docker/Dockerfile.frontend -t opscompass-frontend:0.10.2 .
powershell -File deploy/scripts/pack-images.ps1 -Version 0.10.2   # 导出 tar + SHA256

# 服务器
bash deploy/scripts/load-images.sh deploy/dist/opscompass-0.10.2-images.tar
# 将 .env 与编排中的 OPS_VERSION 改为 0.10.2
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
curl http://127.0.0.1/health
```

**回滚**：保留上一版本镜像与发布包，`docker compose down` 后用旧镜像启动（生产环境把 `OPS_VERSION` 改回旧版本即可，无需重新构建），并按备份恢复数据库；版本原则为「正常不回退，仅故障触发回退」。

## 9. 部署检查清单

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 容器状态 | 4 容器 running，postgres/redis healthy |
| 2 | 健康检查 | `/api/v1/health` 正常返回 |
| 3 | 登录 | 管理员可登录，默认口令已更换 |
| 4 | 密钥 | `SECRET_KEY` 为随机强串，非模板默认值 |
| 5 | 网络暴露 | 8000/5432/6379 未对公网开放 |
| 6 | CORS | 仅允许正式域名 |
| 7 | 日志 | `logs/security.log`、`logs/app.log` 正常写入 |
| 8 | 备份 | 已执行一次备份并验证可恢复 |
| 9 | 数据持久化 | 重启容器后数据不丢失 |
| 10 | 权限 | 各角色权限点最小化，无越权 |
*（内容由AI生成，仅供参考）*
