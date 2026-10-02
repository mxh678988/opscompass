# 运营智脑 OpsCompass · 发布清单（v0.10.1）

> 生成时间：2026-10-01 | 版本：v0.10.1 | 最后更新：2026-10-02

## 一、发布平台概览

| 平台 | 安装包格式 | 状态 | 文件大小 | 签名要求 | 审核要求 |
|---|---|---|---|---|---|
| **Windows** | .exe（IExpress 自解压） | 已产出 | 188.0 KB | 可选（EV 证书） | 无 |
| **macOS** | .tar.gz（内含 .dmg 生成脚本） | 已产出 | 6,976 B | 需 Apple ID 签名 | 可选（App Store） |
| **Linux** | .tar.gz（内含 systemd 安装脚本） | 已产出 | 6,176 B | 需 GPG 签名 | 无 |
| **GitHub Releases** | 三平台安装包 + 离线镜像包 + 校验清单 | 已发布（私有仓库） | 5 项资产（最大 313.7 MB） | 无 | 无 |
| **iOS App Store**（iPhone 手机版） | .ipa | 规划中 | — | 需 Apple 签名 | Apple 审核 |
| **华为应用市场**（鸿蒙手机版） | .hap | 规划中 | — | 需华为签名 | 华为审核 |
| **应用宝 / 安卓各市场**（安卓手机版） | .apk / .aab | 规划中 | — | 需自有签名 | 各市场审核 |
| **Microsoft Store** | .msixbundle（PWA 打包） | 规划中（免注册费） | — | 微软托管签名 | Microsoft 审核 |

> **手机版三端**（iPhone / 鸿蒙 / 安卓）已纳入规划，技术选型、排期与预算详见 `docs/MOBILE_PLAN.md`；
> 启动条件：各市场 / 应用商店发布成功 → Mac 系统应用开发完成。
> **Microsoft Store** 上架方案（免费政策、PWA→MSIX 路线、操作步骤与风险）详见 `docs/deploy/MSSTORE_GUIDE.md`。

## 二、Windows 安装包

### 2.1 生成状态：已产出

| 项目 | 详情 |
|---|---|
| **安装包文件** | `opscompass-0.10.1-windows-setup.exe`（Windows 自带 IExpress 构建的自解压安装程序，PE 头校验通过） |
| **文件大小** | 188.0 KB（轻量分发件，镜像按需从 TCR 拉取或离线 tar 载入） |
| **SHA256** | `29e5ffa111e22409da5c00a2d8ebaea271e096e137794f0bce5e89fcc6b34cd8` |
| **生成时间** | 2026-10-01 |
| **输出位置** | `D:\OpsCompass\deploy\dist\`（校验文件同名 `.sha256`） |
| **默认安装目录** | `%LOCALAPPDATA%\OpsCompass`（可传入首个参数自定义） |
| **安装行为** | 双击后自动解压并执行安装向导；不覆盖用户已有的 `.env` |

### 2.2 安装包组成（exe 内 5 个源文件，已静默解压实测一致）

| 组件 | 说明 | 状态 |
|---|---|---|
| `setup.cmd` | 安装入口（解压后自动执行） | ✅ |
| `docker-compose.prod.yml` | 生产环境编排文件（直接使用 TCR 已发布镜像） | ✅ |
| `.env` / `.env.example` | 环境变量模板（含数据库、Redis、AI、前端配置） | ✅ |
| `opscompass-0.10.1-windows-installer.ps1` | 安装主脚本 | ✅ |
| `README.txt` | 安装说明 | ✅ |
| 安装后目录 | `docker-compose.prod.yml`、`.env`、`.env.example`、安装脚本、`start.cmd`、`stop.cmd`、`README.txt`、`data\`、`logs\` | ✅ |

### 2.3 系统要求

- Windows 10/11（64位）
- Docker Desktop（4.0+）
- PowerShell 5.1+
- 磁盘空间：≥ 5 GB（含 Docker 镜像）

### 2.4 安装流程

1. 取得 `opscompass-0.10.1-windows-setup.exe` 与校验文件 `.sha256`，可选校验：`Get-FileHash .\opscompass-0.10.1-windows-setup.exe -Algorithm SHA256`
2. **双击 exe**，自动解压并执行安装向导（默认装到 `%LOCALAPPDATA%\OpsCompass`）
3. 离线环境：先 `docker load -i opscompass-0.10.1-images.tar` 载入镜像
4. 运行 `start.cmd` 启动服务（需 Docker Desktop 已运行）
5. 访问 http://localhost 与 http://localhost:8000/docs

### 2.5 离线部署

镜像离线包 `opscompass-0.10.1-images.tar`（313.7 MB）位于 `D:\OpsCompass\deploy\dist\`，
SHA256：`39ad9dac3fc660021e230f9ed540049308a8c592ad47feb64c6c52d30c25544a`。
内网/无外网环境按第 3 步先载入镜像即可，无需访问 TCR。

### 2.6 访问地址

- 前端：http://localhost
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 三、macOS 安装包

### 3.1 生成状态：已产出

| 项目 | 详情 |
|---|---|
| **安装包文件** | `opscompass-0.10.1-macos.tar.gz`（顶层目录 `opscompass-0.10.1-macos/`，脚本全部 LF 换行、`.sh` 权限 755） |
| **文件大小** | 6,976 B（轻量分发件；`.dmg` 可在 macOS 上由 `make-dmg.sh` 就地生成） |
| **SHA256** | `82e33b06b08e56b38cdc934a0a584f33d65350b986979fb60d923735f8ea5db2` |
| **生成时间** | 2026-10-02 |
| **输出位置** | `D:\OpsCompass\deploy\dist\`（校验文件同名 `.sha256`） |

### 3.2 安装包组成（tar.gz 内 9 项，已逐项校验）

| 组件 | 说明 | 状态 |
|---|---|---|
| `install.sh` | 安装入口（`--prefix` / `--no-service`，默认装到 `~/Applications/OpsCompass`） | ✅ |
| `start.sh` / `stop.sh` | Bash 启动/停止脚本（docker compose） | ✅ |
| `register-service.sh` | launchd 用户级服务注册脚本（开机自启） | ✅ |
| `create-shortcut.sh` | 桌面快捷方式脚本（OpsCompass.command） | ✅ |
| `make-dmg.sh` | 在 macOS 上生成 `.dmg` 的脚本 | ✅ |
| `docker-compose.prod.yml` | 生产环境编排文件（直接使用 TCR 已发布镜像） | ✅ |
| `.env.example` | 环境变量模板（安装时复制为 `.env`） | ✅ |
| `README.txt` | 安装说明（含 FAQ 与卸载） | ✅ |
| 镜像获取 | 在线从 TCR 拉取，或离线 `docker load -i opscompass-0.10.1-images.tar` | ✅ |

### 3.3 系统要求

- macOS 11 (Big Sur) 或更高版本
- Docker Desktop for Mac
- x86_64 或 Apple Silicon (M1/M2/M3/M4)
- 磁盘空间：≥ 5 GB（含 Docker 镜像）

### 3.4 安装流程

```bash
# 1) 解压
tar -xzf opscompass-0.10.1-macos.tar.gz && cd opscompass-0.10.1-macos

# 2)（可选）载入离线镜像
docker load -i opscompass-0.10.1-images.tar

# 3) 安装（默认 ~/Applications/OpsCompass，无需 sudo）
./install.sh

# 4) 启动（先确保 Docker Desktop 已运行）
cd ~/Applications/OpsCompass && ./start.sh
```

可选：`./register-service.sh` 注册 launchd 开机自启；`./create-shortcut.sh` 创建桌面快捷方式；`./make-dmg.sh` 生成 `.dmg`。

### 3.5 访问地址

- 前端：http://localhost
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 四、Linux 安装包

### 4.1 生成状态：已产出

| 项目 | 详情 |
|---|---|
| **安装包文件** | `opscompass-0.10.1-linux.tar.gz`（顶层目录 `opscompass-0.10.1-linux/`，脚本 LF 换行） |
| **文件大小** | 6,176 B（轻量分发件，镜像按需拉取或离线载入） |
| **SHA256** | `f77332a7f98601aabf2548bf225047c83645037b1e287c10194272a5247a3424` |
| **生成时间** | 2026-10-01 |
| **输出位置** | `D:\OpsCompass\deploy\dist\`（校验文件同名 `.sha256`） |

### 4.2 安装包组成

| 组件 | 说明 | 状态 |
|---|---|---|
| `install.sh` | 安装入口（支持 `--prefix`，默认装到 `~/OpsCompass`） | ✅ |
| `start.sh` / `stop.sh` | Bash 启动/停止脚本 | ✅ |
| `register-service.sh` | systemd 服务注册脚本 | ✅ |
| `create-shortcut.sh` | 桌面快捷方式脚本 | ✅ |
| `docker-compose.prod.yml` | 生产环境编排文件 | ✅ |
| `.env.example` | 环境变量模板 | ✅ |
| `README.txt` | 安装说明 | ✅ |

### 4.3 系统要求

- Linux x86_64
- Docker Engine（20.10+）
- systemd 或 Upstart
- 磁盘空间：≥ 5 GB（含 Docker 镜像）

### 4.4 安装流程

```bash
tar -xzf opscompass-0.10.1-linux.tar.gz && cd opscompass-0.10.1-linux
docker load -i opscompass-0.10.1-images.tar     # 可选：离线镜像
./install.sh                                     # 默认 ~/OpsCompass
cd ~/OpsCompass && ./start.sh
# 可选：./register-service.sh 注册 systemd 服务
```

### 4.5 访问地址

- 前端：http://localhost
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 五、各平台审核要求

### 5.1 Microsoft Store（Windows）

| 项目 | 要求 |
|---|---|
| **签名证书** | 无需自备，代码签名与二进制托管由微软承担 |
| **隐私政策** | 必须在应用商店页面展示可公网访问的隐私政策 URL |
| **内容审核** | 需要符合 Microsoft Store 内容标准 |
| **开发者账号** | Microsoft Partner Center 账号（个人微软账户即可注册） |
| **开发成本** | **免费**（个人开发者；2025-09-11 起取消原 $19 注册费；企业账号 $99） |
| **审核周期** | 1-5 个工作日 |
| **上架路线** | PWA → MSIX（推荐，与三端移动端前端同源）/ Win32 → MSIX，详见 `docs/deploy/MSSTORE_GUIDE.md` |

### 5.2 应用宝（HarmonyOS / Android）

| 项目 | 要求 |
|---|---|
| **签名证书** | 腾讯应用宝签名证书 |
| **隐私政策** | 需要展示隐私政策，说明数据收集和使用 |
| **内容审核** | 需要符合应用宝内容标准 |
| **开发者账号** | 腾讯开放平台账号 |
| **开发成本** | 注册免费 |
| **审核周期** | 1-3 个工作日 |

### 5.3 华为应用市场（HarmonyOS）

| 项目 | 要求 |
|---|---|
| **签名证书** | 华为应用签名证书 |
| **隐私政策** | 需要展示隐私政策，说明数据收集和使用 |
| **内容审核** | 需要符合华为应用市场内容标准 |
| **开发者账号** | 华为开发者联盟账号 |
| **开发成本** | 注册免费 |
| **审核周期** | 1-5 个工作日 |

### 5.4 自发布（GitHub Releases）

| 项目 | 要求 |
|---|---|
| **签名证书** | 可选（EV 证书） |
| **隐私政策** | 需要在 README 中展示 |
| **内容审核** | 无（开源仓库） |
| **开发者账号** | GitHub 账号 |
| **开发成本** | 免费 |
| **审核周期** | 无（直接发布） |

**发布实况（2026-10-02 已完成）**

| 项目 | 详情 |
|---|---|
| 仓库 | https://github.com/mxh678988/opscompass（**私有**，默认分支 main） |
| Release | https://github.com/mxh678988/opscompass/releases/tag/v0.10.1 |
| Tag | v0.10.1 |
| 资产（5 项） | `opscompass-0.10.1-windows-setup.exe`、`opscompass-0.10.1-macos.tar.gz`、`opscompass-0.10.1-linux.tar.gz`、`opscompass-0.10.1-images.tar`（313.7 MB）、`SHA256SUMS.txt` |
| 访问说明 | 私有仓库，下载与克隆需仓库协作者凭据；转公开前需确认凭据清理与开源时机 |
| 发布前处置 | 已移除 `LOCAL_INSTALLER_GUIDE.md` 中的明文仓库凭据并以 `--amend` 重写未推送提交，确保历史无凭据残留 |

## 六、发布检查清单

### 6.1 发布前检查

| 项目 | 状态 | 备注 |
|---|---|---|
| 版本检查 | ✅ | v0.10.1 |
| 镜像检查 | ✅ | backend:0.10.1, frontend:0.10.1 |
| Windows 安装包 | ✅ | `opscompass-0.10.1-windows-setup.exe`（188.0 KB，已校验） |
| macOS 安装包 | ✅ | `opscompass-0.10.1-macos.tar.gz`（6,976 B，已校验） |
| Linux 安装包 | ✅ | `opscompass-0.10.1-linux.tar.gz`（6,176 B，已校验） |
| 离线镜像包 | ✅ | `opscompass-0.10.1-images.tar`（313.7 MB，已校验） |
| SHA256 校验文件 | ✅ | 四组 `.sha256` 全部比对一致 |
| PWA 能力 | ✅ | manifest + Service Worker + 全套图标 + 离线页（见 `docs/deploy/PWA_GUIDE.md`） |
| 隐私政策页 | ✅ | `frontend/public/privacy.html` 已就绪（联系邮箱 mxh6789@live.cn），待公网托管 |
| 文档更新 | ✅ | PUBLISH_CHECKLIST.md / RELEASE_NOTES_v0.10.1.md |
| 发布说明 | ✅ | docs/deploy/RELEASE_NOTES_v0.10.1.md |
| GitHub Release | ✅ | v0.10.1 已发布（私有仓库，5 项资产全部 uploaded） |
| 签名证书 | ✅ | 可选 |
| 隐私政策 | ✅ | 需要 |
| 开发者账号 | ✅ | GitHub 账号已具备（微软/华为/腾讯开放平台账号待开通） |
| 审核材料 | ⬜ | 需要 |

### 6.2 发布后检查

| 项目 | 状态 |
|---|---|
| 下载链接有效 | ✅ 已发布（私有仓库，需协作者凭据访问） |
| 安装包可安装 | 待验证 |
| 应用可运行 | 待验证 |
| API 可访问 | 待验证 |
| 数据持久化正常 | 待验证 |

## 七、版本发布历史

| 版本 | 发布日期 | 主要更新 |
|---|---|---|
| v0.10.1 | 2026-10-02 | **移动端三端纳入规划**（iPhone / 鸿蒙 / 安卓），技术选型、排期与预算见 `docs/MOBILE_PLAN.md` |
| v0.10.1 | 2026-10-02 | **GitHub Release 已发布**（私有仓库 mxh678988/opscompass，tag `v0.10.1`，5 项资产：三平台安装包 + 离线镜像包 + SHA256SUMS） |
| v0.10.1 | 2026-10-02 | 三平台安装包 + 离线镜像包全部产出并附 SHA256（Windows exe / Linux tar.gz / macOS tar.gz） |
| v0.10.1 | 2026-10-01 | Windows、Linux 安装包生成；后端/前端镜像推送 TCR 与 GHCR |

## 八、注意事项

1. **Docker 镜像**：所有安装包均基于 TCR 镜像，需要稳定的网络连接拉取镜像
2. **磁盘空间**：建议预留至少 5 GB 空间（含 Docker 镜像）
3. **系统兼容**：Windows 10/11、macOS 11+、Linux x86_64
4. **网络要求**：首次启动需要拉取 Docker 镜像（约 860 MB）
5. **数据持久化**：数据存储在 `data/` 目录，建议定期备份
6. **安全配置**：生产环境请修改 `.env` 中的敏感配置（数据库密码、SECRET_KEY 等）
