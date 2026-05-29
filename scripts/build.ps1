# AutoRegister 打包脚本 (PyInstaller)
# Usage: .\scripts\build.ps1
# 在项目根目录执行: .\scripts\build.ps1

$ErrorActionPreference = "Stop"

# 获取项目根目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

function Write-Step { param($Msg) Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Err  { param($Msg) Write-Host "ERROR: $Msg" -ForegroundColor Red }
function Write-Ok   { param($Msg) Write-Host "OK: $Msg" -ForegroundColor Green }

# ========== 1. 环境检查 ==========
Write-Step "Check Python..."

$pythonCmd = $null
try {
    $pythonCmd = Get-Command python -ErrorAction Stop | Select-Object -ExpandProperty Source
} catch {
    try { $pythonCmd = Get-Command python3 -ErrorAction Stop | Select-Object -ExpandProperty Source } catch {}
}
if (-not $pythonCmd) {
    Write-Err "Python not found, need 3.10+"
    exit 1
}

$getVerScript = Join-Path $ScriptDir "get_python_version.py"
$pyVersion = & $pythonCmd $getVerScript 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Cannot get Python version"
    exit 1
}
$major = [int]($pyVersion.Split('.')[0])
$minor = [int]($pyVersion.Split('.')[1])
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Write-Err "Need Python 3.10+, got $pyVersion"
    exit 1
}
Write-Ok "Python $pyVersion"

# ========== 2. 安装依赖 ==========
Write-Step "Install deps..."

Push-Location $ProjectRoot
try {
    & $pythonCmd -m pip install --quiet --upgrade pip 2>$null | Out-Null
    & $pythonCmd -m pip install --quiet -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    & $pythonCmd -m pip install --quiet pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "pyinstaller install failed" }
    Write-Ok "Deps ready"
} catch {
    Write-Err $_
    Pop-Location
    exit 1
}
Pop-Location

# ========== 3. Patchright Chromium ==========
Write-Step "Patchright Chromium..."

$env:PLAYWRIGHT_BROWSERS_PATH = "0"
$chromiumInstalled = $false
try {
    $checkScript = Join-Path $ScriptDir "check_patchright.py"
$checkResult = & $pythonCmd $checkScript 2>&1
    if ($LASTEXITCODE -eq 0 -and $checkResult) {
        $chromiumInstalled = $true
        Write-Ok "Chromium installed"
    }
} catch { $null }

if (-not $chromiumInstalled) {
    Write-Host "Installing Chromium..."
    & $pythonCmd -m patchright install chromium
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Chromium install failed"
        Write-Host "Press Enter to continue, or Ctrl+C to exit" -ForegroundColor Yellow
        Read-Host
    } else {
        Write-Ok "Chromium installed"
    }
}

# ========== 4. 收集打包数据 ==========
Write-Step "Collect resources..."

$addDataArgs = @()
$getCtkScript = Join-Path $ScriptDir "get_ctk_path.py"
$ctkPath = & $pythonCmd $getCtkScript 2>$null

# CustomTkinter 资源（必须为完整包目录）
if (Test-Path $ctkPath) {
    $addDataArgs += "--add-data"
    $addDataArgs += "`"$ctkPath;customtkinter`""
}

# 项目 src 作为模块路径
$srcPath = Join-Path $ProjectRoot "src"
if (-not (Test-Path $srcPath)) {
    Write-Err "src dir not found"
    exit 1
}

# ========== 5. PyInstaller 打包 ==========
Write-Step "PyInstaller build..."

$iconPath = Join-Path $ProjectRoot "assets\app_icon.ico"

$pyinstallerArgs = @(
    "--noconfirm",
    "--windowed",
    "--onefile",
    "--name", "auto_register",
    "--icon", $iconPath,
    "--paths", $srcPath,
    "--hidden-import", "auto_register",
    "--hidden-import", "auto_register.gui.app",
    "--hidden-import", "auto_register.gui.log_panel",
    "--hidden-import", "auto_register.integrations.qwen_portal",
    "--hidden-import", "auto_register.integrations.qwen_oauth_client",
    "--hidden-import", "auto_register.providers.one_sec_mail_provider",
    "--hidden-import", "auto_register.providers.username_provider",
    "--hidden-import", "auto_register.writer.auth_profiles_writer",
    "--hidden-import", "auto_register.utils.token_utils",
    "--hidden-import", "auto_register.utils.gateway",
    "--hidden-import", "customtkinter",
    "--hidden-import", "patchright",
    "--hidden-import", "httpx"
) + $addDataArgs + @(
    ("$ProjectRoot\src\launch_gui.py")
)

Push-Location $ProjectRoot
try {
    & $pythonCmd -m PyInstaller @pyinstallerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed"
    }
} catch {
    Write-Err $_
    Pop-Location
    exit 1
}
Pop-Location

# ========== 6. 验证输出 ==========
$exePath = Join-Path $ProjectRoot "dist\auto_register.exe"
if (-not (Test-Path $exePath)) {
    Write-Err "Output not found: $exePath"
    exit 1
}
$exeSize = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
Write-Host ""
Write-Ok "Build done!"
Write-Host ('  Output: ' + $exePath) -ForegroundColor White
Write-Host ('  Size: ' + $exeSize + ' MB') -ForegroundColor Gray
Write-Host ""
Write-Host 'Notes:' -ForegroundColor Yellow
Write-Host '  - First run may be slow'
Write-Host '  - If Chromium missing run patchright install chromium'
Write-Host '  - exe file size is large'
Write-Host ""
