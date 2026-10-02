# 运营智脑 OpsCompass · 本地软件安装指南

> 从 TCR 拉取镜像，生成本地可安装软件包（Windows 环境）
> 版本：v0.10.1 | 生成时间：2026-10-01

## 一、准备工作

### 1. 环境要求

| 项目 | 最低要求 | 推荐配置 |
|---|---|---|
| 操作系统 | Windows 10 20H2+ / Windows Server 2019+ | Windows 11 |
| Docker Desktop | 4.20+ | Docker Desktop 27.3+ |
| 内存 | 8 GB | 16 GB |
| 磁盘空间 | 15 GB 可用（系统盘） | 25 GB 可用 |
| 网络 | 拉取镜像时需要有外网访问 | 可访问 ccr.ccs.tencentyun.com |

### 2. 下载 Docker Desktop

- 地址：https://www.docker.com/products/docker-desktop/
- 安装后确认 Docker Desktop 正常运行：`docker info`

## 二、获取镜像

### 方式一：从 TCR 拉取（推荐）

```powershell
# 登录 TCR（按提示交互输入密码，切勿将真实密码写入脚本或文档）
docker login ccr.ccs.tencentyun.com -u <YOUR_TCR_UIN>

# 拉取镜像
docker pull ccr.ccs.tencentyun.com/laomeng-ops/opscompass-backend:0.10.1
docker pull ccr.ccs.tencentyun.com/laomeng-ops/opscompass-frontend:0.10.1

# 验证
docker images --filter reference='*opscompass*'
```

### 方式二：离线安装

如果服务器无法访问外网，可先在本机导出镜像：

```powershell
# 导出镜像（需先拉取）
docker save -o opscompass-backend.tar ccr.ccs.tencentyun.com/laomeng-ops/opscompass-backend:0.10.1
docker save -o opscompass-frontend.tar ccr.ccs.tencentyun.com/laomeng-ops/opscompass-frontend:0.10.1

# 在目标机器上导入
docker load -i opscompass-backend.tar
docker load -i opscompass-frontend.tar
```

## 三、部署 OpsCompass

### 1. 获取部署文件

从 GitHub Releases 下载或从源码获取：

```powershell
# 从 Releases 下载
Invoke-WebRequest -Uri "https://github.com/mxh678988/opscompass/releases/download/v0.10.1/deploy.zip" -OutFile "deploy.zip"
Expand-Archive -Path "deploy.zip" -DestinationPath "C:\OpsCompass"

# 或从本地源码复制
Copy-Item -Path "D:\OpsCompass\deploy\*" -Destination "C:\OpsCompass\deploy" -Recurse
```

### 2. 配置环境

```powershell
# 复制环境变量模板
Copy-Item "C:\OpsCompass\.env.example" "C:\OpsCompass\.env"

# 编辑 .env 文件，配置数据库密码等参数
# 关键配置项：
#   POSTGRES_PASSWORD: 数据库密码（必须修改默认值）
#   FRONTEND_PORT: 前端端口（默认 80）
#   TIMEZONE: 时区（默认 Asia/Shanghai）
```

### 3. 启动服务

```powershell
# 进入项目目录
Set-Location C:\OpsCompass

# 启动所有服务
docker compose -f docker-compose.prod.yml up -d

# 查看状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f backend
```

### 4. 验证部署

```powershell
# 检查后端 API
Invoke-WebRequest -Uri "http://localhost:8000/docs" | Select-Object StatusCode

# 检查前端页面
Start-Process "http://localhost"

# 检查数据库
docker exec opscompass-postgres pg_isready -U opscompass -d opscompass
```

## 四、创建桌面快捷方式

### 方式一：使用 PowerShell 脚本

创建 `C:\OpsCompass\create-shortcuts.ps1`：

```powershell
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\运营智脑.lnk")
$Shortcut.TargetPath = "http://localhost"
$Shortcut.WorkingDirectory = "C:\OpsCompass"
$Shortcut.Save()
```

运行：

```powershell
powershell -ExecutionPolicy Bypass -File "C:\OpsCompass\create-shortcuts.ps1"
```

### 方式二：手动创建

1. 桌面右键 → 新建 → 快捷方式
2. 输入网址：`http://localhost`
3. 完成创建后，右键快捷方式 → 更改图标，选择你喜欢的图标

## 五、注册为 Windows 服务

### 1. 使用 NSSM（非侵入式 Windows 服务管理器）

```powershell
# 下载 NSSM
Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "nssm.zip"
Expand-Archive -Path "nssm.zip" -DestinationPath "C:\nssm"

# 注册 Docker Compose 为服务
$NssmPath = "C:\nssm\win64\nssm.exe"
& $NssmPath install "OpsCompass" "docker-compose.exe" "-f C:\OpsCompass\docker-compose.prod.yml", "up", "-d"
& $NssmPath start "OpsCompass"
```

### 2. 使用 Windows Service 命令

```powershell
# 配置 Docker Compose 自动启动
Set-Service -Name "docker" -StartupType Automatic
Start-Service -Name "docker"
```

## 六、管理脚本

### 1. 启动/停止/重启

```powershell
# 启动
docker compose -f C:\OpsCompass\docker-compose.prod.yml up -d

# 停止
docker compose -f C:\OpsCompass\docker-compose.prod.yml down

# 重启
docker compose -f C:\OpsCompass\docker-compose.prod.yml restart

# 更新镜像后重启
docker compose -f C:\OpsCompass\docker-compose.prod.yml pull
docker compose -f C:\OpsCompass\docker-compose.prod.yml up -d
```

### 2. 监控脚本

创建 `C:\OpsCompass\monitor.ps1`：

```powershell
$LogPath = "C:\OpsCompass\logs\monitor.log"

while ($true) {
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Status = docker compose -f C:\OpsCompass\docker-compose.prod.yml ps --format table
    Add-Content -Path $LogPath -Value "[$Timestamp] $Status"
    Start-Sleep -Seconds 300
}
```

## 七、HTTPS 配置（可选）

### 1. 获取 SSL 证书

```powershell
# 方法一：使用 Let's Encrypt
Install-Module -Name Posh-ACME -Scope CurrentUser
Import-Module Posh-ACME

# 方法二：使用自签名证书（仅测试环境）
$Cert = New-SelfSignedCertificate -DnsName "localhost" -CertStoreLocation "cert:\LocalMachine\My"
$Cert | Export-Certificate -FilePath "C:\OpsCompass\certs\server.crt" -Force
$Cert.PrivateKey | Export-PfxCertificate -FilePath "C:\OpsCompass\certs\server.pfx" -Password (ConvertTo-SecureString -String "YourPassword" -AsPlainText -Force) -Force
```

### 2. 配置 Nginx HTTPS

编辑 `C:\OpsCompass\deploy\nginx\nginx.conf`：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate C:/OpsCompass/certs/server.crt;
    ssl_certificate_key C:/OpsCompass/certs/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 启动 HTTPS

```powershell
docker compose -f C:\OpsCompass\docker-compose.prod.yml -f C:\OpsCompass\deploy\docker\docker-compose.prod.https.yml up -d
```

## 八、故障排查

### 1. 常见问题

| 问题 | 解决方案 |
|---|---|
| 端口冲突 | 修改 .env 中的 FRONTEND_PORT |
| 数据库连接失败 | 检查 .env 中 POSTGRES_PASSWORD 是否设置 |
| 镜像拉取失败 | 检查网络连接，或改用离线 tar 包 |
| 容器启动失败 | 查看日志：`docker compose -f docker-compose.prod.yml logs` |

### 2. 日志查看

```powershell
# 查看后端日志
docker logs opscompass-backend -f

# 查看前端日志
docker logs opscompass-frontend -f

# 查看数据库日志
docker logs opscompass-postgres -f
```

## 九、备份与恢复

### 1. 数据备份

```powershell
# 备份数据库
docker exec opscompass-postgres pg_dump -U opscompass -d opscompass -F c -f /backup/opscompass_backup_$(Get-Date -Format "yyyy-MM-dd").dump

# 备份 Redis
docker exec opscompass-redis redis-cli BGSAVE

# 备份 Docker 镜像
docker save -o /backup/opscompass_images.tar opscompass-backend:0.10.1 opscompass-frontend:0.10.1
```

### 2. 数据恢复

```powershell
# 恢复数据库
docker exec -i opscompass-postgres pg_restore -U opscompass -d opscompass /backup/opscompass_backup_*.dump

# 恢复 Redis
docker exec -i opscompass-redis redis-cli RESTORE 0 0 < /backup/redis_backup.rdb

# 恢复镜像
docker load -i /backup/opscompass_images.tar
```

## 十、安全建议

1. 修改默认数据库密码，使用强密码
2. 配置防火墙规则，仅开放必要端口
3. 定期更新 Docker 镜像和系统
4. 使用 HTTPS 保护数据传输
5. 配置日志轮转，避免磁盘占满
6. 定期备份重要数据

## 附录：文件结构

```
C:\OpsCompass\
├── docker-compose.prod.yml    # 生产环境编排
├── .env                        # 环境变量配置
├── .env.example               # 环境变量模板
├── deploy/
│   ├── nginx/                 # Nginx 配置
│   ├── docker/                # HTTPS 覆盖编排
│   └── scripts/               # 辅助脚本
├── docs/                      # 文档
│   └── deploy/                # 部署文档
└── data/                      # 数据持久化
    ├── postgres/              # PostgreSQL 数据
    └── redis/                 # Redis 数据
```
