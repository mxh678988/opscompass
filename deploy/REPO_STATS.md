# OpsCompass 镜像仓库统计

> 统计时间：2026-10-01 | 应用版本：v0.10.1

## 一、核心镜像对比

| 指标 | opscompass-backend | opscompass-frontend |
|------|-------------------|---------------------|
| **版本** | 0.10.1 | 0.10.1 |
| **架构** | linux/amd64 | linux/amd64 |
| **操作系统** | Linux | Linux |
| **基础镜像** | Python 3.11.16 (Alpine) | Nginx 1.27.5 (Alpine) |
| **构建工具** | Docker BuildKit | Docker BuildKit |
| **暴露端口** | 8000 | 80 |
| **健康检查** | curl /health | wget / |
| **构建时间** | 2026-09-29 23:54:42 UTC | 2026-09-22 06:20:15 UTC |
| **镜像层数** | 9 层 | 10 层 |

## 二、仓库地址对比

| 镜像 | 腾讯云 TCR（主） | GitHub Container Registry（备用） |
|------|------------------|----------------------------------|
| opscompass-backend | `ccr.ccs.tencentyun.com/laomeng-ops/opscompass-backend:0.10.1` | `ghcr.io/mxh678988/opscompass-backend:0.10.1` |
| opscompass-frontend | `ccr.ccs.tencentyun.com/laomeng-ops/opscompass-frontend:0.10.1` | `ghcr.io/mxh678988/opscompass-frontend:0.10.1` |

## 三、Digest 一致性校验

两个仓库的同一版本镜像 **Digest 完全一致**，说明 TCR 与 GHCR 上的是同一份内容，仅仓库地址不同。

| 镜像 | TCR Digest | GHCR Digest | 一致 |
|------|-----------|------------|------|
| opscompass-backend | `sha256:f008dde52341983885a336208f1b736b4fdafd4eaa3170453247a5031080145c` | `sha256:f008dde52341983885a336208f1b736b4fdafd4eaa3170453247a5031080145c` | ✅ |
| opscompass-frontend | `sha256:133ca9a8bd05d58b52cc5b1498cfb6c04497bf5be7545e5c9e86c836785ba622` | `sha256:133ca9a8bd05d58b52cc5b1498cfb6c04497bf5be7545e5c9e86c836785ba622` | ✅ |

## 四、镜像大小

| 镜像 | 磁盘占用 | 内容大小 | 说明 |
|------|---------|---------|------|
| opscompass-backend:0.10.1 | 787 MB | 174 MB | 后端 API 服务，含 Python 运行时 |
| opscompass-frontend:0.10.1 | 73.9 MB | 21.1 MB | 前端静态资源 + Nginx |
| **合计** | **860.9 MB** | **195.1 MB** | 仅核心服务 |

> 内容大小 = 去重后实际存储的层内容量，磁盘占用含所有层头信息。

## 五、本地镜像池概况

| 镜像 | 磁盘占用 | 内容大小 | 状态 |
|------|---------|---------|------|
| opscompass-backend:0.10.1 | 787 MB | 174 MB | 核心 |
| opscompass-frontend:0.10.1 | 73.9 MB | 21.1 MB | 核心 |
| postgres:16-alpine | 420 MB | 117 MB | 依赖 |
| redis:7-alpine | 57.8 MB | 16.7 MB | 依赖 |
| clickhouse/clickhouse-server:24.8 | 807 MB | 179 MB | 备用 |
| mariadb:11.4 | 455 MB | 108 MB | 备用 |
| **本地合计** | **2.42 GB** | — | 含开发依赖 |

## 六、离线镜像包

| 文件 | 路径 | 大小 | SHA256 |
|------|------|------|--------|
| 镜像导出包 | `deploy/dist/opscompass-0.10.1-images.tar` | 313.7 MB | `39ad9dac99a244c7315f5e8c9103d8d2846980c2270f924c638d54848e9b7540` |
| 校验文件 | `deploy/dist/opscompass-0.10.1-images.tar.sha256` | 112 B | — |

离线包包含：opscompass-backend、opscompass-frontend、postgres:16-alpine、redis:7-alpine 四个镜像。

## 七、部署环境配置

- **TCR 仓库名**：`laomeng-ops`
- **TCR 命名空间**：`ccr.ccs.tencentyun.com`
- **GHCR 仓库名**：`mxh678988`
- **GHCR 镜像名**：`opscompass-backend` / `opscompass-frontend`
- **环境变量**：`OPS_VERSION` 控制镜像版本，默认 `0.10.1`
