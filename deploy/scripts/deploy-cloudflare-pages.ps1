<#
.SYNOPSIS
  将运营智脑（OpsCompass）前端构建产物发布到 Cloudflare Pages。
.DESCRIPTION
  依赖全局 wrangler：npm i -g wrangler
  凭据通过环境变量读取，禁止写入命令行或脚本：
    $env:CLOUDFLARE_API_TOKEN  = "<Pages:Edit 权限的 API Token>"
    $env:CLOUDFLARE_ACCOUNT_ID = "<Cloudflare Account ID>"
.EXAMPLE
  cd D:\OpsCompass\deploy\scripts
  .\deploy-cloudflare-pages.ps1
.EXAMPLE
  .\deploy-cloudflare-pages.ps1 -SkipBuild -Branch preview
#>
[CmdletBinding()]
param(
  [string]$ProjectName = 'opscompass',
  [string]$Branch = 'main',
  [string]$DistDir = '',
  [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $DistDir) { $DistDir = Join-Path $repoRoot 'frontend\dist' }

if (-not $env:CLOUDFLARE_API_TOKEN) { throw '缺少环境变量 CLOUDFLARE_API_TOKEN（需 Pages:Edit 权限）' }
if (-not $env:CLOUDFLARE_ACCOUNT_ID) { throw '缺少环境变量 CLOUDFLARE_ACCOUNT_ID' }

if (-not $SkipBuild) {
  Write-Host '[1/3] 构建前端 ...' -ForegroundColor Cyan
  Push-Location (Join-Path $repoRoot 'frontend')
  npm run build
  Pop-Location
}

$manifest = Join-Path $DistDir 'manifest.webmanifest'
if (-not (Test-Path $manifest)) { throw "构建产物缺少 PWA 资源：$manifest" }

Write-Host '[2/3] 确保 Cloudflare Pages 项目存在 ...' -ForegroundColor Cyan
$prev = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
npx --yes wrangler pages project create $ProjectName --production-branch main 2>&1 | Out-Host
$ErrorActionPreference = $prev

Write-Host '[3/3] 上传构建产物 ...' -ForegroundColor Cyan
npx --yes wrangler pages deploy $DistDir --project-name $ProjectName --branch $Branch --commit-dirty=true

Write-Host ''
Write-Host "完成。生产地址：https://$ProjectName.pages.dev/" -ForegroundColor Green
Write-Host "隐私政策 URL：https://$ProjectName.pages.dev/privacy.html" -ForegroundColor Green