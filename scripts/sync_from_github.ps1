# Pulls the latest data collected by the GitHub Actions "Collect Real
# Airfare Data" workflow into the local checkout, so the local dashboard/API
# (which reads the local airfare_observatory.db file) reflects what GitHub
# collected. GitHub is the source of truth for data now -- local collection
# (the "APIx Collection Cycle" scheduled task) has been disabled to avoid
# the two ever diverging or conflicting over the same tracked DB file.
#
# Safety:
# - If the local working tree has uncommitted changes (e.g. someone is
#   mid-edit on code), skip entirely rather than risk conflicting with or
#   overwriting that work.
# - A `git pull` that touches airfare_observatory.db fails on Windows if the
#   API server has the file open (confirmed: "unable to unlink old
#   'airfare_observatory.db': Invalid argument"). Only stop/restart the
#   server when a fetch shows there's actually a new commit to bring in, so
#   this doesn't cause an API blip on every sync tick -- only on the ones
#   that matter.

$repoDir = "C:\Users\cecilia\Downloads\APIx-main\APIx-main"
Set-Location $repoDir

$dirty = git status --porcelain
if ($dirty) {
    Write-Output "$(Get-Date -Format o) - Skipped: working tree has uncommitted changes."
    exit 0
}

git fetch origin main 2>&1 | Out-Null
$local = git rev-parse HEAD
$remote = git rev-parse origin/main

if ($local -eq $remote) {
    Write-Output "$(Get-Date -Format o) - No new commits."
    exit 0
}

# New data is waiting -- stop the API server so it releases its handle on
# airfare_observatory.db, pull, then bring it back up.
$apiProc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*uvicorn*apps.api.main*' }
if ($apiProc) {
    Stop-Process -Id $apiProc.ProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

git pull origin main --ff-only 2>&1 | Out-String | Write-Output
$after = git rev-parse HEAD
Write-Output "$(Get-Date -Format o) - Synced: $local -> $after"

if ($apiProc) {
    Start-Process -FilePath "python" `
        -ArgumentList "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory $repoDir -WindowStyle Hidden
    Write-Output "$(Get-Date -Format o) - API server restarted."
}
