# 运营智脑 本地开发启动脚本（后端 + 前端）
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Write-Host "[运营智脑] 项目根目录: $Root"

# 1. 检查 .env
if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "[运营智脑] 已从 .env.example 生成 .env，请按需修改后重新运行" -ForegroundColor Yellow
}

# 2. 启动后端
Write-Host "[运营智脑] 启动后端 (http://localhost:8000) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Root\backend'; if (-not (Test-Path '.venv')) { python -m venv .venv }; " +
    ".venv\Scripts\Activate.ps1; pip install -r requirements.txt; " +
    "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
)

# 3. 启动前端
Write-Host "[运营智脑] 启动前端 (http://localhost:5173) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Root\frontend'; if (-not (Test-Path 'node_modules')) { npm install }; npm run dev"
)

Write-Host "[运营智脑] 两个开发服务已在新窗口启动" -ForegroundColor Green
