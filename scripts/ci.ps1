<#
.SYNOPSIS
    OpsCompass 本地 CI：升版 / 提交前的一键校验。

.DESCRIPTION
    校验项：
      1 版本一致性   config.APP_VERSION / frontend package.json / docs/openapi.json / docs/changelog.md
                     / docker-compose.prod.yml（OPS_VERSION 默认镜像版本）
      2 后端编译     docker exec ... python -m compileall -q /app/app
      3 后端单测     docker exec ... python -m pytest -q tests
      4 接口契约     运行实例 /openapi.json 与 docs/openapi.json 路径集合逐条比对
      5 容器健康     opscompass-* 容器状态
      6 运行版本     运行实例版本与配置源一致（防止改版未重启）
      7 前端构建     vue-tsc 类型检查 + vite 生产构建
      8 前端 lint    eslint（未安装则跳过）
      9 依赖可复现   backend/requirements.txt 各 pin 是否真实存在于 PyPI（防止构建不可复现）

    退出码：0 全部通过；1 存在失败项。日志输出到 temp/ci-logs/<时间戳>/。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/ci.ps1
    powershell -ExecutionPolicy Bypass -File scripts/ci.ps1 -SkipFrontend
    powershell -ExecutionPolicy Bypass -File scripts/ci.ps1 -SkipBackend -SkipRuntime
#>
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$SkipRuntime,
    [string]$BaseUrl = 'http://localhost:8000'
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $root "temp\ci-logs\$stamp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$results = New-Object System.Collections.ArrayList

function Add-Result {
    param([string]$Name, [string]$Status, [string]$Detail)
    [void]$results.Add([pscustomobject]@{ Check = $Name; Status = $Status; Detail = $Detail })
    $color = switch ($Status) { 'PASS' { 'Green' } 'SKIP' { 'DarkGray' } default { 'Red' } }
    Write-Host ("  [{0}] {1} - {2}" -f $Status, $Name, $Detail) -ForegroundColor $color
}

function Invoke-Step {
    param([string]$Name, [scriptblock]$Body)
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    try {
        $detail = & $Body
        Add-Result -Name $Name -Status 'PASS' -Detail ([string]$detail)
    } catch {
        Add-Result -Name $Name -Status 'FAIL' -Detail $_.Exception.Message
    }
}

function Get-ConfigVersion {
    $raw = Get-Content 'backend\app\core\config.py' -Raw
    $m = [regex]::Match($raw, 'APP_VERSION:\s*str\s*=\s*"([^"]+)"')
    if (-not $m.Success) { throw 'config.py 未找到 APP_VERSION 定义' }
    return $m.Groups[1].Value
}

Write-Host ""
Write-Host "OpsCompass CI  @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
Write-Host "仓库根目录：$root"
Write-Host "日志目录：  $logDir"

# ---------------------------------------------------------------- 1 版本一致性
Invoke-Step '版本一致性' {
    $cfgVer = Get-ConfigVersion
    $pkgVer = (Get-Content 'frontend\package.json' -Raw | ConvertFrom-Json).version
    $oaVer  = (Get-Content 'docs\openapi.json' -Raw | ConvertFrom-Json).info.version
    $clRaw  = Get-Content 'docs\changelog.md' -Raw
    $clMatch = [regex]::Match($clRaw, '##\s*\[(\d+\.\d+\.\d+)\]')
    $clVer = if ($clMatch.Success) { $clMatch.Groups[1].Value } else { 'n/a' }

    # 生产编排中的镜像版本默认值（OPS_VERSION）须与配置源同源
    $prodVer = 'n/a'
    if (Test-Path 'docker-compose.prod.yml') {
        $prodRaw = Get-Content 'docker-compose.prod.yml' -Raw
        $prodHits = @([regex]::Matches($prodRaw, 'OPS_VERSION:-([0-9]+\.[0-9]+\.[0-9]+)') |
                      ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
        if ($prodHits.Count -eq 0) { throw 'docker-compose.prod.yml 未找到 OPS_VERSION 默认版本号' }
        if ($prodHits.Count -gt 1) { throw "docker-compose.prod.yml 存在多个 OPS_VERSION 默认值：$($prodHits -join ', ')" }
        $prodVer = $prodHits[0]
    }

    $uniq = @($cfgVer, $pkgVer, $oaVer, $clVer, $prodVer) | Sort-Object -Unique
    if ($uniq.Count -ne 1) {
        throw "版本不一致 -> config=$cfgVer / package=$pkgVer / openapi=$oaVer / changelog=$clVer / prod-compose=$prodVer"
    }
    "五源一致：$cfgVer（config / package / openapi / changelog / prod-compose）"
}

# ---------------------------------------------------------------- 9 依赖可复现性
Invoke-Step '依赖清单可复现性' {
    $log = Join-Path $logDir 'requirements-check.log'
    python scripts\verify_requirements.py *> $log
    $code = $LASTEXITCODE
    $summary = (Get-Content $log -ErrorAction SilentlyContinue |
                Select-String -Pattern '有效 \d+' |
                Select-Object -Last 1).Line
    if ($code -eq 2) { throw "清单文件缺失（日志：$log）" }
    if ($code -ne 0) {
        $bad = @(Get-Content $log -ErrorAction SilentlyContinue |
                 Select-String -Pattern '\[无效\]' |
                 Select-Object -Last 10)
        throw "存在无效 pin：$($bad -join '; ')（日志：$log）"
    }
    if (-not $summary) { $summary = '依赖清单全部有效' }
    $summary.Trim()
}

# ---------------------------------------------------------------- 2/3 后端
if (-not $SkipBackend) {
    Invoke-Step '后端语法编译' {
        $out = docker exec opscompass-backend python -m compileall -q /app/app 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "compileall 失败：$((@($out) | Select-Object -Last 3) -join ' ')"
        }
        'compileall 通过（/app/app）'
    }

    Invoke-Step '后端单元测试' {
        $log = Join-Path $logDir 'pytest.log'
        docker exec -w /app opscompass-backend python -m pytest -q tests --no-header *> $log
        $code = $LASTEXITCODE
        $summary = (Get-Content $log -ErrorAction SilentlyContinue |
                    Select-String -Pattern '\d+ (passed|failed|error)' |
                    Select-Object -Last 1).Line
        if ($code -ne 0) { throw "pytest 退出码 $code；$summary（日志：$log）" }
        if (-not $summary) { $summary = 'pytest 通过' }
        $summary.Trim()
    }
} else {
    Add-Result -Name '后端校验' -Status 'SKIP' -Detail '已指定 -SkipBackend'
}

# ---------------------------------------------------------------- 4 接口契约
Invoke-Step '接口契约基线' {
    $live = Invoke-RestMethod "$BaseUrl/openapi.json" -TimeoutSec 15
    $snap = Get-Content 'docs\openapi.json' -Raw | ConvertFrom-Json
    $livePaths = @($live.paths.PSObject.Properties.Name)
    $snapPaths = @($snap.paths.PSObject.Properties.Name)
    $added   = @($livePaths | Where-Object { $snapPaths -notcontains $_ })
    $removed = @($snapPaths | Where-Object { $livePaths -notcontains $_ })

    if ($added.Count -or $removed.Count) {
        $diff = @()
        if ($added.Count)   { $diff += ('实例新增: ' + ($added -join ', ')) }
        if ($removed.Count) { $diff += ('快照多余: ' + ($removed -join ', ')) }
        $diff | Out-File (Join-Path $logDir 'openapi-diff.txt') -Encoding UTF8
        throw "快照与实例不一致（新增 $($added.Count) / 缺失 $($removed.Count) 条），详见 openapi-diff.txt"
    }
    if ($live.info.version -ne $snap.info.version) {
        throw "版本不一致：实例 $($live.info.version) / 快照 $($snap.info.version)"
    }
    "路径 $($livePaths.Count) 条与 docs/openapi.json 完全一致（v$($live.info.version)）"
}

# ---------------------------------------------------------------- 5/6 运行态
if (-not $SkipRuntime) {
    Invoke-Step '容器健康' {
        $rows = @(docker ps --filter 'name=opscompass' --format '{{.Names}}|{{.Status}}')
        if ($rows.Count -eq 0) { throw '未发现 opscompass-* 运行容器，请先执行 docker compose up -d' }
        $bad = @($rows | Where-Object { $_ -notmatch '\(healthy\)' })
        if ($bad.Count) { throw "非健康容器：$($bad -join '; ')" }
        "$($rows.Count) 个容器全部 healthy"
    }

    Invoke-Step '运行版本生效' {
        $live = Invoke-RestMethod "$BaseUrl/openapi.json" -TimeoutSec 15
        $cfgVer = Get-ConfigVersion
        if ($live.info.version -ne $cfgVer) {
            throw "运行实例 $($live.info.version) 与配置源 $cfgVer 不一致（是否未重启生效？）"
        }
        "运行实例 v$($live.info.version) 与配置源一致"
    }
} else {
    Add-Result -Name '运行态校验' -Status 'SKIP' -Detail '已指定 -SkipRuntime'
}

# ---------------------------------------------------------------- 7/8 前端
if (-not $SkipFrontend) {
    Invoke-Step '前端类型检查与构建' {
        if (-not (Test-Path 'frontend\node_modules')) { throw 'frontend\node_modules 不存在，请先在 frontend 目录执行 npm install' }
        $log = Join-Path $logDir 'frontend-build.log'
        Push-Location frontend
        try {
            npm run build *> $log
            $code = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($code -ne 0) { throw "npm run build 退出码 $code（日志：$log）" }
        $tail = (Get-Content $log -ErrorAction SilentlyContinue | Select-String 'built in' | Select-Object -Last 1).Line
        if (-not $tail) { $tail = 'vue-tsc + vite build 通过' }
        $tail.Trim()
    }

    Write-Host ""
    Write-Host "==> 前端 lint" -ForegroundColor Cyan
    if (Test-Path 'frontend\node_modules\.bin\eslint.cmd') {
        Invoke-Step '前端 lint' {
            $log = Join-Path $logDir 'frontend-lint.log'
            Push-Location frontend
            try {
                npm run lint *> $log
                $code = $LASTEXITCODE
            } finally {
                Pop-Location
            }
            if ($code -ne 0) { throw "npm run lint 退出码 $code（日志：$log）" }
            'eslint 通过'
        }
    } else {
        Add-Result -Name '前端 lint' -Status 'SKIP' -Detail '未安装 eslint（devDependencies 未含），未纳入基线'
    }
} else {
    Add-Result -Name '前端校验' -Status 'SKIP' -Detail '已指定 -SkipFrontend'
}

# ---------------------------------------------------------------- 汇总
$pass = @($results | Where-Object { $_.Status -eq 'PASS' }).Count
$fail = @($results | Where-Object { $_.Status -eq 'FAIL' }).Count
$skip = @($results | Where-Object { $_.Status -eq 'SKIP' }).Count

Write-Host ""
Write-Host "================== OpsCompass CI 汇总 ==================" -ForegroundColor White
$results | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
Write-Host ("通过 {0} / 失败 {1} / 跳过 {2}    日志：{3}" -f $pass, $fail, $skip, $logDir)
$results | ConvertTo-Json -Depth 3 | Out-File (Join-Path $logDir 'summary.json') -Encoding UTF8

if ($fail -gt 0) {
    Write-Host "CI 结果：失败" -ForegroundColor Red
    exit 1
}
Write-Host "CI 结果：通过" -ForegroundColor Green
exit 0
