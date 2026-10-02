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

# 网络：若本机走代理（Clash Verge 默认 127.0.0.1:7897），执行前需设置
#   $env:HTTPS_PROXY = 'http://127.0.0.1:7897'
# 否则 wrangler 可能出现 fetch failed。
#
# 凭据路线（二选一）：
#   ① 环境变量注入 API Token —— 必须同时提供 CLOUDFLARE_ACCOUNT_ID，且 Token 的
#      Account Resources 需 Include 目标账号，权限含 Account → Cloudflare Pages → Edit；
#   ② 复用本机 wrangler 登录态（npx wrangler login 浏览器授权）—— 无需任何环境变量。
if ($env:CLOUDFLARE_API_TOKEN) {
  if (-not $env:CLOUDFLARE_ACCOUNT_ID) {
    throw '已设置 CLOUDFLARE_API_TOKEN 但缺少 CLOUDFLARE_ACCOUNT_ID（Token 路线必须同时提供）'
  }
} else {
  Write-Host '[凭据] 未检测到 CLOUDFLARE_API_TOKEN，复用本机 wrangler 登录态' -ForegroundColor Yellow
  Write-Host '[凭据] 前置校验：npx wrangler whoami ...' -ForegroundColor Cyan
  $prevWho = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $whoLog = (npx --yes wrangler whoami 2>&1 | Out-String)
  $whoExit = $LASTEXITCODE
  $ErrorActionPreference = $prevWho
  $whoLog | Out-Host
  if ($whoExit -ne 0 -or $whoLog -match 'not authenticated|not logged in') {
    throw '本机 wrangler 未登录或登录态失效。请在本机终端执行 npx wrangler login 完成浏览器授权后重试；或改用 CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID。'
  }
  Write-Host '[凭据] 校验通过：wrangler 登录态有效' -ForegroundColor Green
}

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
$createLog = (npx --yes wrangler pages project create $ProjectName --production-branch main 2>&1 | Out-String)
$createExit = $LASTEXITCODE
$createLog | Out-Host
if ($createExit -ne 0) {
  if ($createLog -match 'already exists') {
    Write-Host '[2/3] 项目已存在，跳过创建' -ForegroundColor Yellow
  } else {
    throw "创建 Pages 项目失败：wrangler 退出码 $createExit（认证/权限问题，勿仅凭输出判定成功）"
  }
}
$ErrorActionPreference = $prev

Write-Host '[3/3] 上传构建产物 ...' -ForegroundColor Cyan
npx --yes wrangler pages deploy $DistDir --project-name $ProjectName --branch $Branch --commit-dirty=true
if ($LASTEXITCODE -ne 0) {
  throw "上传失败：wrangler 退出码 $LASTEXITCODE（认证/权限问题，勿仅凭输出判定成功）"
}

Write-Host ''
Write-Host '完成（已校验 wrangler 退出码）。发布后请独立复核部署记录：' -ForegroundColor Green
Write-Host "  npx wrangler pages deployment list --project-name $ProjectName" -ForegroundColor Green
Write-Host "生产地址：https://$ProjectName.pages.dev/" -ForegroundColor Green
Write-Host "隐私政策 URL：https://$ProjectName.pages.dev/privacy （Pages 对 /privacy.html 返回 308 跳转，商店栏位请填 canonical）" -ForegroundColor Green