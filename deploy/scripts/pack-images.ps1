# ==============================================================
# 运营智脑 OpsCompass · 离线镜像打包脚本（构建机执行）
# 版权：BY LAOMENG 网络工作室
# --------------------------------------------------------------
# 作用：把已发布的版本化镜像导出为单个 tar，并生成 SHA256 校验文件，
#       供内网 / 无外网服务器通过 load-images.sh 校验载入。
# 前置：镜像已构建并打好版本 tag（如 opscompass-backend:0.10.1）。
# 用法：
#   powershell -ExecutionPolicy Bypass -File deploy/scripts/pack-images.ps1
#   powershell -ExecutionPolicy Bypass -File deploy/scripts/pack-images.ps1 -Version 0.10.1
#   powershell -ExecutionPolicy Bypass -File deploy/scripts/pack-images.ps1 -Version 0.10.1 -OutputDir D:\release
# 产物：<OutputDir>\opscompass-<Version>-images.tar
#       <OutputDir>\opscompass-<Version>-images.tar.sha256
# ==============================================================
[CmdletBinding()]
param(
    # 镜像版本，默认读取根目录 config.py 中的 APP_VERSION
    [string]$Version = "",
    # 导出目录，默认 deploy\dist
    [string]$OutputDir = "",
    # 额外镜像（默认含 postgres / redis，服务器无外网时一并离线携带）
    [string[]]$ExtraImages = @("postgres:16-alpine", "redis:7-alpine"),
    # 是否跳过 postgres / redis 打包
    [switch]$SkipBaseImages
)

$ErrorActionPreference = "Stop"

# 定位项目根目录（本脚本位于 <root>\deploy\scripts\）
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root      = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
Set-Location $Root

# ---------- 1. 解析版本号 ----------
if ([string]::IsNullOrWhiteSpace($Version)) {
    $configPath = Join-Path $Root "backend\app\core\config.py"
    if (-not (Test-Path $configPath)) {
        $configPath = Join-Path $Root "config.py"
    }
    if (Test-Path $configPath) {
        $m = Select-String -Path $configPath -Pattern 'APP_VERSION\s*[:=].*?["'']([0-9]+\.[0-9]+\.[0-9]+)["'']' |
             Select-Object -First 1
        if ($m) { $Version = $m.Matches[0].Groups[1].Value }
    }
    if ([string]::IsNullOrWhiteSpace($Version)) {
        throw "无法自动解析版本号，请显式传入 -Version（例：-Version 0.10.1）"
    }
}
Write-Host "[pack] 版本号: $Version" -ForegroundColor Cyan

# ---------- 2. 准备输出目录 ----------
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $Root "deploy\dist"
}
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}
$TarName = "opscompass-$Version-images.tar"
$TarPath = Join-Path $OutputDir $TarName
$ShaPath = "$TarPath.sha256"

# ---------- 3. 校验镜像存在 ----------
$Images = @("opscompass-backend:$Version", "opscompass-frontend:$Version")
if (-not $SkipBaseImages) {
    $Images += $ExtraImages
}

Write-Host "[pack] 待导出镜像：" -ForegroundColor Cyan
$Missing = @()
foreach ($img in $Images) {
    $found = docker image inspect $img 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($found)) {
        $Missing += $img
        Write-Host "  [缺失] $img" -ForegroundColor Red
    } else {
        Write-Host "  [就绪] $img" -ForegroundColor Green
    }
}
if ($Missing.Count -gt 0) {
    throw "以下镜像不存在，请先构建：$($Missing -join ', ')"
}

# ---------- 4. 导出镜像 ----------
if (Test-Path $TarPath) { Remove-Item $TarPath -Force }

Write-Host "[pack] 正在导出镜像（体积较大，请耐心等待）..." -ForegroundColor Cyan
& docker save -o $TarPath @Images
if ($LASTEXITCODE -ne 0) { throw "docker save 失败（退出码 $LASTEXITCODE）" }

$sizeMB = [math]::Round((Get-Item $TarPath).Length / 1MB, 1)
Write-Host "[pack] 导出完成：$TarPath（${sizeMB} MB）" -ForegroundColor Green

# ---------- 5. 生成 SHA256 校验文件 ----------
$hash = (Get-FileHash -Path $TarPath -Algorithm SHA256).Hash.ToLower()
"$hash  $TarName" | Out-File -FilePath $ShaPath -Encoding ASCII -NoNewline
Write-Host "[pack] SHA256: $hash" -ForegroundColor Yellow
Write-Host "[pack] 校验文件: $ShaPath" -ForegroundColor Yellow

# ---------- 6. 分发提示 ----------
Write-Host ""
Write-Host "下一步（服务器执行）：" -ForegroundColor Cyan
Write-Host "  bash deploy/scripts/load-images.sh $TarName"
Write-Host "  docker compose -f docker-compose.prod.yml up -d"
