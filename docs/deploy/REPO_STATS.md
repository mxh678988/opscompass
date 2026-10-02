# 运营智脑 OpsCompass · 各仓库镜像数据统计

> 生成时间：2026-10-01 | 版本：v0.10.1

## 一、镜像总览

| 镜像 | 主仓库 | 备用仓库 | 后端镜像 ID | 前端镜像 ID |
|---|---|---|---|---|
| opscompass-backend | `ccr.ccs.tencentyun.com/laomeng-ops` | `ghcr.io/mxh678988` | `sha256:f008dde52341` | - |
| opscompass-frontend | `ccr.ccs.tencentyun.com/laomeng-ops` | `ghcr.io/mxh678988` | - | `sha256:133ca9a8bd05` |

## 二、各仓库详细信息

### 腾讯云 TCR（主仓库）

| 项目 | opscompass-backend:0.10.1 | opscompass-frontend:0.10.1 |
|---|---|---|
| 仓库地址 | `ccr.ccs.tencentyun.com/laomeng-ops/opscompass-backend:0.10.1` | `ccr.ccs.tencentyun.com/laomeng-ops/opscompass-frontend:0.10.1` |
| 镜像大小 | 787 MB | 73.9 MB |
| 镜像层数 | 12 层 | 12 层 |
| 创建时间 | 2026-09-28 | 2026-09-22 |
| 内容 digest | `sha256:e3e84dfa3e139854a36242a29a7e69bd5fe7982d2a516cb0c4b3f5a3d4d00408` | `sha256:829429b035a2df06b5f7faa960043114ae237cc275cc89d60ad66e209c1b06eb` |
| 推送时间 | 2026-10-01 13:07 | 2026-10-01 13:05 |

### GitHub Container Registry（备用仓库）

| 项目 | opscompass-backend:0.10.1 | opscompass-frontend:0.10.1 |
|---|---|---|
| 仓库地址 | `ghcr.io/mxh678988/opscompass-backend:0.10.1` | `ghcr.io/mxh678988/opscompass-frontend:0.10.1` |
| 镜像大小 | 787 MB | 73.9 MB |
| 镜像层数 | 12 层 | 12 层 |
| 创建时间 | 2026-09-28 | 2026-09-22 |
| 内容 digest | `sha256:e3e84dfa3e139854a36242a29a7e69bd5fe7982d2a516cb0c4b3f5a3d4d00408` | `sha256:829429b035a2df06b5f7faa960043114ae237cc275cc89d60ad66e209c1b06eb` |
| 推送时间 | 2026-10-01 12:57 | 2026-10-01 12:57 |

## 三、对比

| 项目 | 腾讯云 TCR | GitHub GHCR |
|---|---|---|
| 镜像一致性 | ✅ 内容完全一致（digest 相同） | ✅ 内容完全一致（digest 相同） |
| 推送耗时 | ~2 min | ~3 min |
| 推送网络 | 国内直连，稳定 | 经 Clash 代理，稳定 |
| 适用场景 | 国内服务器部署首选 | 海外服务器/备份场景 |

## 四、安装包统计

> 说明：安装包为轻量分发件（KB 级），不含镜像层；离线部署需配合 `opscompass-0.10.1-images.tar`（313.7 MB）使用。
> 输出目录：`D:\OpsCompass\deploy\dist\`；脚本固化目录：`D:\OpsCompass\deploy\installers\`

| 平台 | 安装包文件 | 格式 | 大小 | 生成时间 | 状态 |
|---|---|---|---|---|---|
| **Windows** | `opscompass-0.10.1-windows-setup.exe` | .exe（IExpress 自解压） | 188.0 KB | 2026-10-01 | 已产出并校验 |
| **Linux** | `opscompass-0.10.1-linux.tar.gz` | .tar.gz | 6,176 B | 2026-10-01 | 已产出并校验 |
| **macOS** | `opscompass-0.10.1-macos.tar.gz` | .tar.gz | 6,976 B | 2026-10-02 | 已产出并校验 |
| **离线镜像** | `opscompass-0.10.1-images.tar` | .tar | 313.7 MB | 2026-09-30 | 已产出并校验 |

### 4.1 安装包 SHA256 校验值

| 文件 | SHA256 |
|---|---|
| `opscompass-0.10.1-windows-setup.exe` | `29e5ffa111e22409da5c00a2d8ebaea271e096e137794f0bce5e89fcc6b34cd8` |
| `opscompass-0.10.1-linux.tar.gz` | `f77332a7f98601aabf2548bf225047c83645037b1e287c10194272a5247a3424` |
| `opscompass-0.10.1-macos.tar.gz` | `82e33b06b08e56b38cdc934a0a584f33d65350b986979fb60d923735f8ea5db2` |
| `opscompass-0.10.1-images.tar` | `39ad9dac3fc660021e230f9ed540049308a8c592ad47feb64c6c52d30c25544a` |

### 4.2 生成脚本固化

| 脚本 | 位置 |
|---|---|
| `opscompass-0.10.1-windows-installer.ps1` | `D:\OpsCompass\deploy\installers\` |
| `opscompass-0.10.1-linux-installer.sh` | `D:\OpsCompass\deploy\installers\` |
| `opscompass-0.10.1-macos-installer.sh` | `D:\OpsCompass\deploy\installers\` |

## 五、补充

- 本地构建镜像：`opscompass-backend:0.10.1`（787 MB，ID f008dde52341）
- 基础镜像：`postgres:16-alpine`（420 MB）、`redis:7-alpine`（57.8 MB）
- 生产环境无需构建，直接 pull 已发布版本镜像，详见 `docker-compose.prod.yml`
