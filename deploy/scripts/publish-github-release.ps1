<#
.SYNOPSIS
    OpsCompass GitHub Release 一键发布脚本。

.DESCRIPTION
    在 gh CLI 已登录的前提下，完成：远端仓库创建（如不存在）→ 绑定 origin →
    推送 main 与 tag → 创建 GitHub Release 并上传发布物。
    默认 DryRun，仅打印将要执行的命令，不产生任何外部副作用。

.PARAMETER Repo
    目标仓库全名，格式 owner/name。默认 mxh678988/opscompass。

.PARAMETER Tag
    发布 tag，默认读取仓库当前 tag 中最新者。

.PARAMETER Visibility
    若需创建远端仓库，指定 public / private / internal。默认 private（更安全，需显式改）。

.PARAMETER DryRun
    只打印命令，不执行任何写操作。

.EXAMPLE
    # 预演（默认）
    .\publish-github-release.ps1

.EXAMPLE
    # 实际发布（公开仓库）
    .\publish-github-release.ps1 -Visibility public -DryRun:$false
#>
[CmdletBinding()]
param(
    [string]$Repo = 'mxh678988/opscompass',
    [string]$Tag = '',
    [ValidateSet('public', 'private', 'internal')]
    [string]$Visibility = 'private',
    [string]$DistDir = '',
    [switch]$DryRun = $true
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')

function Step($msg)  { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Fail($msg)  { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Run([string[]]$args_) {
    $line = ($args_ | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
    if ($DryRun) { Write-Host "  [dry-run] $line" -ForegroundColor DarkGray; return $null }
    Write-Host "  $ $line" -ForegroundColor DarkGray
    & $args_[0] $args_[1..($args_.Count - 1)]
}

if (-not $DistDir) { $DistDir = Join-Path $root 'deploy\dist' }
if (-not $Tag) {
    $Tag = (git -C $root tag --sort=-creatordate | Select-Object -First 1)
}
if (-not $Tag) { throw '未找到任何 tag，请用 -Tag 显式指定版本' }

Write-Host "OpsCompass GitHub Release 发布" -ForegroundColor White
Write-Host "  仓库: $Repo"
Write-Host "  版本: $Tag"
Write-Host "  可见性: $Visibility"
Write-Host "  产物目录: $DistDir"
Write-Host "  模式: $(if ($DryRun) { 'DryRun（只打印，不执行）' } else { '实际执行' })"

# ---------- 1. 前置检查 ----------
Step '1. 前置检查'

$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) { throw 'gh CLI 未安装，请先安装 GitHub CLI 后重试' }
Ok "gh: $($gh.Source)"

$auth = gh auth status 2>&1 | Out-String
if ($auth -match 'not logged into any') { throw "gh 未登录，请先执行 gh auth login（需浏览器授权）" }
Ok 'gh 已登录'

if (-not (git -C $root tag | Where-Object { $_ -eq $Tag })) { throw "本地不存在 tag $Tag" }
Ok "本地 tag 存在: $Tag"

$assets = @('SHA256SUMS.txt', 'RELEASE_NOTES_v0.10.1.md')
$patterns = @("opscompass-$($Tag.TrimStart('v'))-windows-setup.exe",
              "opscompass-$($Tag.TrimStart('v'))-macos.tar.gz",
              "opscompass-$($Tag.TrimStart('v'))-linux.tar.gz",
              "opscompass-$($Tag.TrimStart('v'))-images.tar")
$missing = @()
foreach ($p in $patterns) { if (-not (Test-Path (Join-Path $DistDir $p))) { $missing += $p } }
if ($missing.Count -gt 0) {
    Warn "以下产物缺失，将跳过上传: $($missing -join ', ')"
} else {
    Ok '四件发布物齐全'
}

$notesFile = Join-Path $root 'docs\deploy\RELEASE_NOTES_v0.10.1.md'
if (Test-Path $notesFile) { Ok '发布说明存在' } else { Warn '发布说明缺失，将使用 changelog 摘要' }

$dirty = git -C $root status --porcelain
if ($dirty) { Warn "工作区有未提交改动，建议先提交后再发布：`n$dirty" } else { Ok '工作区干净' }

# ---------- 2. 远端仓库 ----------
Step '2. 远端仓库'
$repoExists = $false
try {
    gh repo view $Repo --json name 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $repoExists = $true }
} catch { $repoExists = $false }

if ($repoExists) {
    Ok "远端仓库已存在: $Repo"
} else {
    Warn "远端仓库不存在，将创建（$Visibility）"
    Run @('gh', 'repo', 'create', $Repo, "--$Visibility", '--source', $root, '--remote', 'origin', '--disable-wiki')
}

# ---------- 3. 绑定 remote ----------
Step '3. 绑定 origin'
$remotes = git -C $root remote
if ($remotes -contains 'origin') {
    $url = (git -C $root remote get-url origin).Trim()
    $expect = "https://github.com/$Repo.git"
    if ($url -ne $expect) { Run @('git', '-C', $root, 'remote', 'set-url', 'origin', $expect) }
    else { Ok "origin 已指向 $expect" }
} else {
    Run @('git', '-C', $root, 'remote', 'add', 'origin', "https://github.com/$Repo.git")
}

# ---------- 4. 推送 ----------
Step '4. 推送 main 与 tag'
Run @('git', '-C', $root, 'push', '-u', 'origin', 'main')
Run @('git', '-C', $root, 'push', 'origin', $Tag)

# ---------- 5. 创建 Release ----------
Step '5. 创建 Release 并上传产物'
$existing = gh release view $Tag --repo $Repo --json tagName 2>$null
if ($existing) {
    Warn "Release $Tag 已存在，改用 upload 追加产物"
    foreach ($p in $patterns) {
        $full = Join-Path $DistDir $p
        if (Test-Path $full) { Run @('gh', 'release', 'upload', $Tag, $full, '--clobber', '--repo', $Repo) }
    }
} else {
    $cmd = @('gh', 'release', 'create', $Tag, '--repo', $Repo, '--title', "OpsCompass $Tag", '--notes-file', $notesFile)
    foreach ($p in $patterns) {
        $full = Join-Path $DistDir $p
        if (Test-Path $full) { $cmd += $full }
    }
    if (Test-Path (Join-Path $DistDir 'SHA256SUMS.txt')) { $cmd += (Join-Path $DistDir 'SHA256SUMS.txt') }
    Run $cmd
}

Step '完成'
if ($DryRun) {
    Write-Host '  以上为预演结果。确认无误后加 -DryRun:$false 实际发布。' -ForegroundColor Yellow
} else {
    Write-Host "  Release: https://github.com/$Repo/releases/tag/$Tag" -ForegroundColor Green
}
