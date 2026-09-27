# 运营智脑 数据备份脚本（技术产物名 opscompass-*.zip 保持不变）
# 备份内容：data 目录 + .env + docker-compose.yml，输出到 backups 目录
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $Root "backups\$Stamp"

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Write-Host "[backup] 备份数据目录 ..." -ForegroundColor Cyan
if (Test-Path (Join-Path $Root "data")) {
    Copy-Item (Join-Path $Root "data") $BackupDir -Recurse -Force
}

Write-Host "[backup] 备份环境配置 ..." -ForegroundColor Cyan
foreach ($f in @(".env", "docker-compose.yml")) {
    $p = Join-Path $Root $f
    if (Test-Path $p) { Copy-Item $p $BackupDir -Force }
}

$Zip = Join-Path $Root "backups\opscompass-$Stamp.zip"
Compress-Archive -Path (Join-Path $BackupDir "*") -DestinationPath $Zip -Force
Remove-Item $BackupDir -Recurse -Force

Write-Host "[backup] 完成: $Zip" -ForegroundColor Green
