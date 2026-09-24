# Pulls the latest data collected by the GitHub Actions "Collect Real
# Airfare Data" workflow into the local checkout, so the local dashboard/API
# (which reads the local airfare_observatory.db file) reflects what GitHub
# collected. GitHub is the source of truth for data now -- local collection
# (the "APIx Collection Cycle" scheduled task) has been disabled to avoid
# the two ever diverging or conflicting over the same tracked DB file.
#
# Safety: if the local working tree has uncommitted changes (e.g. someone is
# mid-edit on code), a pull could conflict with or silently overwrite that
# work. Skip the pull rather than risk it -- this is meant to be a quiet,
# unattended sync, not something that should ever surprise-clobber local
# changes.

$repoDir = "C:\Users\cecilia\Downloads\APIx-main\APIx-main"
Set-Location $repoDir

$dirty = git status --porcelain
if ($dirty) {
    Write-Output "$(Get-Date -Format o) - Skipped: working tree has uncommitted changes."
    exit 0
}

$before = git rev-parse HEAD
git pull origin main --ff-only 2>&1 | Out-String | Write-Output
$after = git rev-parse HEAD

if ($before -ne $after) {
    Write-Output "$(Get-Date -Format o) - Synced: $before -> $after"
} else {
    Write-Output "$(Get-Date -Format o) - No new commits."
}
