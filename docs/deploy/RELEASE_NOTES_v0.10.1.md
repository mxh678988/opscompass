# 运营智脑 OpsCompass v0.10.1 发布说明

> 发布日期：2026-10-02 | 版本：v0.10.1 | 类型：生产部署能力版本

## 一、版本概述

v0.10.1 聚焦**交付能力**：新增镜像直用型生产编排（免构建）、离线镜像打包/载入链路、本地 CI 五源版本一致性校验，并修复 Hive 方言与依赖清单可复现性问题。配套产出 Windows / macOS / Linux 三平台安装包与离线镜像包。

## 二、新增能力

### 2.1 生产部署编排（形态 C）

根目录新增 `docker-compose.prod.yml`——镜像直用型免构建编排，服务器不再需要 Node / 构建工具链。

| 差异点 | 说明 |
|---|---|
| 镜像直用 | 仅引用已发布镜像 `opscompass-backend/frontend:${OPS_VERSION:-0.10.1}`，不挂载宿主源码目录，避免生产被本地目录覆盖 |
| 端口收敛 | 仅前端 80 端口对外，`postgres` / `redis` / `backend` 仅在容器网络内可达 |
| 长期运行 | `restart: always` + 容器日志轮转（10~20MB × 5） |

配套新增 HTTPS 叠加文件 `deploy/docker/docker-compose.prod.https.yml`（80 → 443 跳转 + `/api/` 反代 `backend:8000`）。

### 2.2 离线镜像打包 / 载入链路（形态 D）

- `deploy/scripts/pack-images.ps1`：构建机执行，自动读取 `config.py` 的 `APP_VERSION` 或 `-Version` 指定版本，校验镜像就绪后 `docker save` 导出，可选一并打包 postgres / redis 基础镜像，并生成 `.sha256` 校验文件。
- `deploy/scripts/load-images.sh`：服务器执行，载入前校验 SHA256，校验失败以退出码 3 中止；支持 `SKIP_CHECK=1` 显式跳过。

服务于无外网交付场景。

### 2.3 本地 CI 版本校验扩为五源

`scripts/ci.ps1` 第 1 项新增 `docker-compose.prod.yml` 中 `OPS_VERSION` 默认版本号校验（该值出现多次且不一致时报错），确保发布新版本时生产编排不会漏改。

## 三、修复

| 问题 | 根因 | 处置 |
|---|---|---|
| Hive 连接串畸形 | 方言名误写为 `hive://`，而 `_build_sql_url` 已统一补 `://`，实际拼出 `hive://://user@host:10000/db`，SQLAlchemy 解析为主机为空 | 修正为 `hive`（与 PostgreSQL / MySQL / ClickHouse 对齐），新增 `backend/tests/test_collect_sql.py` 50 条纯函数用例，容器内测试由 2 passed 升至 **52 passed** |
| 依赖清单不可复现 | `requirements.txt` 中 `pymysql==2.2.8` 在 PyPI 不存在（最新 1.2.3），干净环境镜像构建必然失败 | 改为 `pymysql==1.2.3`，新增 `scripts/verify_requirements.py` 静态校验每个 pin 的 PyPI 存在性，接入 `ci.ps1` 第 9 项 |
| 版本号硬编码 | `/api/v1/system/info` 返回硬编码 `0.1.0` | 统一读取 `settings.APP_VERSION`，升版只需改一处 |

## 四、发布物清单

镜像地址：`ccr.ccs.tencentyun.com/laomeng-ops/{backend,frontend}:0.10.1`（GHCR 备用）

| 文件 | 大小 | SHA256 |
|---|---|---|
| `opscompass-0.10.1-windows-setup.exe` | 188.0 KB | `29e5ffa111e22409da5c00a2d8ebaea271e096e137794f0bce5e89fcc6b34cd8` |
| `opscompass-0.10.1-macos.tar.gz` | 6,976 B | `82e33b06b08e56b38cdc934a0a584f33d65350b986979fb60d923735f8ea5db2` |
| `opscompass-0.10.1-linux.tar.gz` | 6,176 B | `f77332a7f98601aabf2548bf225047c83645037b1e287c10194272a5247a3424` |
| `opscompass-0.10.1-images.tar` | 313.7 MB | `39ad9dac3fc660021e230f9ed540049308a8c592ad47feb64c6c52d30c25544a` |

统一校验清单见同目录 `SHA256SUMS.txt`。校验方式：

```bash
# Linux / macOS
sha256sum -c SHA256SUMS.txt

# Windows PowerShell
Get-FileHash .\opscompass-0.10.1-windows-setup.exe -Algorithm SHA256
```

## 五、安装方式

### Windows

```powershell
# 双击 opscompass-0.10.1-windows-setup.exe；默认装到 %LOCALAPPDATA%\OpsCompass
# 离线环境先执行：
docker load -i opscompass-0.10.1-images.tar
```

### macOS

```bash
tar -xzf opscompass-0.10.1-macos.tar.gz && cd opscompass-0.10.1-macos
./install.sh          # 默认 ~/Applications/OpsCompass，无需 sudo
./start.sh            # 需 Docker Desktop 已运行
```

### Linux

```bash
tar -xzf opscompass-0.10.1-linux.tar.gz && cd opscompass-0.10.1-linux
./install.sh          # 默认 ~/OpsCompass
./start.sh
# 可选：./register-service.sh 注册 systemd 服务
```

访问入口：前端 http://localhost ｜ API http://localhost:8000 ｜ 文档 http://localhost:8000/docs

## 六、系统要求

| 平台 | 要求 |
|---|---|
| Windows | Windows 10/11（64 位）、Docker Desktop 4.0+、PowerShell 5.1+ |
| macOS | macOS 11+、Docker Desktop for Mac（x86_64 / Apple Silicon） |
| Linux | Linux x86_64、Docker Engine 20.10+、systemd 或 Upstart |
| 通用 | 磁盘空间 ≥ 5 GB（含 Docker 镜像） |

## 七、已知限制

- Hive 数据源因本机无 HiveServer2 实例，仅验证驱动可用性与失败降级，真实源端到端落库待具备实例后补验。
- 阿里云 ACR 推送受账号风控阻塞，当前镜像分发以腾讯云 TCR 为主、GHCR 备用。
- macOS 包未做 bash 语法自检（本机 WSL 不可用）。
- macOS 安装包为 tar.gz 分发件，`.dmg` 需在 macOS 上由 `make-dmg.sh` 就地生成。

## 八、升级说明

从 v0.10.0 升级：

```bash
# 生产环境（形态 C）
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

数据存储于 `data/` 目录，升级前建议备份。生产环境请修改 `.env` 中的数据库密码与 `SECRET_KEY`。
