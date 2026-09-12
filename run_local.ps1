#requires -Version 5.1
<#
.SYNOPSIS
  Boots the full India Airfare Price Observatory stack (APIX-2.0): optional dep
  install, optional DB re-seed, FastAPI backend on :8000, Next.js dashboard on :3000.

.DESCRIPTION
  Default (no switches): verifies DB exists (seeds if missing), starts API + dashboard
  and waits for health with hard timeouts. Never loops indefinitely.

.EXAMPLE
  .\run_local.ps1                          # start everything from default python (seeds only if DB missing)
  .\run_local.ps1 -PyEnv apix              # deploy from a dedicated conda env / python.exe path
  .\run_local.ps1 -Seed                    # reset DB and re-seed fresh synthetic data first
  .\run_local.ps1 -SkipInstall             # skip pip / npm install checks
  .\run_local.ps1 -Status                  # just report what is up
  .\run_local.ps1 -Stop                    # stop API + dashboard
#>
param(
  [string]$PyEnv = "",
  [switch]$Seed,
  [switch]$SkipInstall,
  [switch]$Status,
  [switch]$Stop
)

function Resolve-PythonPath([string]$PyEnv) {
  if (-not $PyEnv) { return (Get-Command python -ErrorAction SilentlyContinue).Source }
  # direct path to python.exe
  if (Test-Path $PyEnv) {
    if ((Split-Path -Leaf $PyEnv) -ieq "python.exe") { return $PyEnv }
    $cand = Join-Path $PyEnv "python.exe"
    if (Test-Path $cand) { return $cand }
  }
  # conda env name -> <base>/envs/<name>/python.exe
  try {
    $condaBase = (& conda info --base 2>$null).Trim()
    if ($condaBase) {
      $cand = Join-Path $condaBase ("envs\$PyEnv\python.exe")
      if (Test-Path $cand) { return $cand }
    }
  } catch {}
  throw "Python environment '$PyEnv' not found (checked path and conda envs)."
}

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$API_PORT = 8000
$DASH_PORT = 3000
$API_URL = "http://127.0.0.1:$API_PORT"
$DASH_URL = "http://localhost:$DASH_PORT"
$DB_FILE = Join-Path $ROOT "airfare_observatory.db"
$LOG_DIR = Join-Path $env:TEMP "opencode"
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null
$API_OUT = Join-Path $LOG_DIR "run_local_api_out.log"
$API_ERR = Join-Path $LOG_DIR "run_local_api_err.log"
$DASH_OUT = Join-Path $LOG_DIR "run_local_dash_out.log"
$DASH_ERR = Join-Path $LOG_DIR "run_local_dash_err.log"

function Say($msg) { Write-Host $msg }

function Wait-Port([int]$Port, [int]$TimeoutSec) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { return $true }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Get-ListenerPids([int]$Port) {
  Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
}

function Get-ServicePid([int]$Port, [string]$ProcName) {
  $ids = Get-ListenerPids $Port
  foreach ($procId in $ids) {
    try { if ((Get-Process -Id $procId -ErrorAction Stop).ProcessName -like "*$ProcName*") { return $procId } } catch {}
  }
  return $null
}

function Stop-Service([int]$Port, [string]$Label) {
  $ids = Get-ListenerPids $Port
  if (-not $ids) { Say "$Label already stopped."; return }
  foreach ($procId in $ids) {
    Say "Stopping $Label (pid $procId)..."
    & taskkill /T /F /PID $procId 2>&1 | Out-Null
  }
  Start-Sleep -Seconds 2
  if (Get-ListenerPids $Port) { Say "WARN: $Label still listening on $Port - stop it manually." }
}

function Invoke-Get([string]$Url, [int]$TimeoutSec) {
  try {
    $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
    return $r.StatusCode -eq 200
  } catch { return $false }
}

# ---------------------------------------------------------------- status / stop
if ($Status) {
  $apiPid = Get-ServicePid $API_PORT "python"
  $dashPid = Get-ServicePid $DASH_PORT "node"
  $api = if ($apiPid) { (Invoke-Get "$API_URL/health" 5) } else { $false }
  $dash = if ($dashPid) { (Invoke-Get $DASH_URL 5) } else { $false }
  Say "API       : $(if($api){"UP (pid $apiPid)"}else{"DOWN"})  -> $API_URL/health"
  Say "Dashboard : $(if($dash){"UP (pid $dashPid)"}else{"DOWN"})  -> $DASH_URL"
  Say "DB        : $(if(Test-Path $DB_FILE){"present"}else{"MISSING (will seed on start)"})"
  exit 0
}

if ($Stop) {
  Stop-Service $API_PORT "API"
  Stop-Service $DASH_PORT "Dashboard"
  Say "Done."
  exit 0
}

# ---------------------------------------------------------------- checks
try {
  $py = Resolve-PythonPath $PyEnv
} catch {
  Say "ERROR: $($_.Exception.Message)"; exit 1
}
$node = (Get-Command node -ErrorAction SilentlyContinue).Source
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $py) { Say "ERROR: python not found on PATH (or -PyEnv)."; exit 1 }
if (-not $npm) { Say "ERROR: npm not found on PATH."; exit 1 }
Say "[env] Using Python: $py"

# ---------------------------------------------------------------- installs
if (-not $SkipInstall) {
  Say "[deps] Installing Python requirements..."
  & $py -m pip install -q -r (Join-Path $ROOT "requirements.txt")
  if ($LASTEXITCODE -ne 0) { Say "ERROR: pip install failed."; exit 1 }

  $dashDir = Join-Path $ROOT "apps\dashboard"
  if (-not (Test-Path (Join-Path $dashDir "node_modules"))) {
    Say "[deps] Installing dashboard npm packages (first run)..."
    Push-Location $dashDir
    & npm.cmd install --no-fund --no-audit
    $npmCode = $LASTEXITCODE
    Pop-Location
    if ($npmCode -ne 0) { Say "ERROR: npm install failed. Re-run with -SkipInstall to bypass."; exit 1 }
  } else {
    Say "[deps] Dashboard node_modules found; skipping npm install (use -SkipInstall to force-skip checks)."
  }
}

# ---------------------------------------------------------------- seed
if ($Seed -and (Test-Path $DB_FILE)) {
  $bak = "$DB_FILE.bak-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
  Say "[seed] Resetting DB -> $bak"
  Move-Item -Force $DB_FILE $bak
}

if ($Seed -or -not (Test-Path $DB_FILE)) {
  Say "[seed] Running unified seed pipeline (python -m database.seeds.seed_all)..."
  Push-Location $ROOT
  & $py -m database.seeds.seed_all
  $seedCode = $LASTEXITCODE
  Pop-Location
  if ($seedCode -ne 0) { Say "ERROR: seed pipeline failed with exit $seedCode"; exit 1 }
  Say "[seed] Done."
} else {
  Say "[seed] DB present; skipping seed (use -Seed to rebuild)."
}

# ---------------------------------------------------------------- dashboard build (if needed)
$dashDir = Join-Path $ROOT "apps\dashboard"
if (-not (Test-Path (Join-Path $dashDir ".next"))) {
  Say "[dash] .next build missing - building (may take a couple minutes)..."
  Push-Location $dashDir
  & npm.cmd run build
  $buildCode = $LASTEXITCODE
  Pop-Location
  if ($buildCode -ne 0) { Say "ERROR: dashboard build failed."; exit 1 }
}

# ---------------------------------------------------------------- start API
if (Get-ListenerPids $API_PORT) {
  Say "[api] Already listening on :$API_PORT; skipping start."
} else {
  Say "[api] Starting FastAPI on :$API_PORT ..."
  $apiArgs = @("-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "$API_PORT")
  $env:PYTHONFAULTHANDLER = "1"
  $api = Start-Process -FilePath $py -ArgumentList $apiArgs -WorkingDirectory $ROOT -RedirectStandardOutput $API_OUT -RedirectStandardError $API_ERR -PassThru
  Say "[api] Waiting for /health (timeout 60s)..."
  $ok = $false
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while ($sw.Elapsed.TotalSeconds -lt 60) {
    if (Invoke-Get "$API_URL/health" 3) { $ok = $true; break }
    if ($api.HasExited) { break }
    Start-Sleep -Seconds 2
  }
  if (-not $ok) {
    Say "ERROR: API did not become healthy in 60s."
    Say "--- recent API stderr ---"
    Get-Content $API_ERR -ErrorAction SilentlyContinue | Select-Object -Last 15
    exit 1
  }
  Say "[api] Healthy at $API_URL (docs at $API_URL/docs)."
}

# ---------------------------------------------------------------- start dashboard
if (Get-ListenerPids $DASH_PORT) {
  Say "[dash] Already listening on :$DASH_PORT; skipping start."
} else {
  Say "[dash] Starting Next.js dashboard on :$DASH_PORT ..."
  $dashArgs = @("run", "start")
  $dash = Start-Process -FilePath $npm -ArgumentList $dashArgs -WorkingDirectory $dashDir -RedirectStandardOutput $DASH_OUT -RedirectStandardError $DASH_ERR -PassThru
  Say "[dash] Waiting for HTTP 200 (timeout 120s)..."
  $ok = $false
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while ($sw.Elapsed.TotalSeconds -lt 120) {
    if (Invoke-Get $DASH_URL 5) { $ok = $true; break }
    if ($dash.HasExited) { break }
    Start-Sleep -Seconds 3
  }
  if (-not $ok) {
    Say "ERROR: dashboard did not respond in 120s."
    Say "--- recent dashboard stderr ---"
    Get-Content $DASH_ERR -ErrorAction SilentlyContinue | Select-Object -Last 15
    exit 1
  }
  Say "[dash] Serving at $DASH_URL."
}

Say ""
Say "========= STACK UP ========="
Say "  API       : http://localhost:$API_PORT  (OpenAPI docs at /docs)"
Say "  Dashboard : http://localhost:$DASH_PORT"
Say "  Stop with : .\run_local.ps1 -Stop   |   Status: .\run_local.ps1 -Status"
Say "============================="