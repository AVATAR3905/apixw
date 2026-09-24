# Restarting APIx After a Reboot

A system restart kills the API server and the dashboard. Nothing is lost —
the database (`airfare_observatory.db`) and all code are on disk — you just
need to relaunch the two processes. Run everything below from the project
root: `C:\Users\cecilia\Downloads\APIx-main\APIx-main`.

## Where data collection actually happens now

**Real-data collection runs on GitHub Actions, not this machine.**
`.github/workflows/collect.yml` runs the same 4x-daily cycle
(06:00/12:00/18:00/23:00 IST) on GitHub's own infrastructure and commits the
updated `airfare_observatory.db` back to `main` — it's completely
independent of whether this machine, or the local API server, is even on.
Check its history any time:

```bash
gh run list --repo AVATAR3905/apixw --workflow="Collect Real Airfare Data"
```

(Why: the local machine turned out to be unreliable for this — sleep/wake
cycles, process crashes, and an in-process APScheduler that silently missed
scheduled runs with no error. See `TASKS.md` v2.7/v2.8 changelog entries for
the full history. Known tradeoff: GitHub's runner IPs are datacenter
ranges, which has already fully blocked Akasa Air's carrier-direct feed
there (robots.txt won't even serve to that IP range) — SpiceJet and the
Google Flights RPC feed still work fine from GitHub; Ixigo/EaseMyTrip are
inconsistent. Local collection generally gets better source coverage when
it does work, which is the tradeoff being made here.)

**This machine just displays GitHub's data — it doesn't collect
independently anymore.** The local "APIx Collection Cycle" scheduled task is
**disabled** (not deleted, so it can be re-enabled if you ever want to go
back to local collection). In its place, a new task, **"APIx GitHub Sync"**,
runs every 30 minutes: it checks for new commits on GitHub and, only when
there actually are some, stops the local API server (which holds the DB file
open), pulls, and restarts it. If nothing's new, it's a no-op and doesn't
touch the running server. Check its log:

```powershell
Get-Content "C:\Users\cecilia\Downloads\APIx-main\APIx-main\logs\sync_from_github.log" -Tail 20
```

or run it manually any time you want the latest data immediately, without
waiting for the next 30-minute tick:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\cecilia\Downloads\APIx-main\APIx-main\scripts\sync_from_github.ps1"
```

**Both of these Task Scheduler entries survive a reboot automatically** —
nothing to redo after restarting Windows.

## 1. Check what's already running

```bash
netstat -ano | grep -E ":8000|:3000" | grep LISTENING
```

If both lines show up, you're already good — skip to step 4 (health check).

## 2. Start the API server (port 8000)

Standalone launch — recommended (avoids the `run_observatory.py` cascade-kill
issue noted below). This process still starts an in-process scheduler too,
but that one is no longer what runs the real data collection — see the note
above about Task Scheduler.

```bash
nohup python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
```

Wait for it to bind before moving on:

```bash
until netstat -ano | grep ":8000" | grep -q LISTENING; do sleep 2; done; echo "API is up"
```

## 3. Start the dashboard (port 3000)

```bash
cd apps/dashboard
nohup npm run dev > /tmp/dashboard.log 2>&1 &
cd ../..
```

Wait for it to bind:

```bash
until netstat -ano | grep ":3000" | grep -q LISTENING; do sleep 2; done; echo "Dashboard is up"
```

## 4. Health check

```bash
curl -s "http://localhost:8000/api/v1/index?series=BASE_FARE&horizon=t15"
```

Should return JSON with a real `index_value`. Then open whichever frontend
you're using:

- Dashboard (Next.js): http://localhost:3000
- Lightweight viewer (the one actually in use): http://localhost:8000/ui

## Notes

- **Don't use `scripts/run_observatory.py` to start these** unless you want
  both processes tied together — its watchdog loop kills *both* the moment
  *either one* exits, which has caused accidental full outages before. The
  standalone commands above are more resilient if you ever need to restart
  just one side.
- To stop a server: find its PID with the `netstat` command in step 1, then
  `taskkill //PID <pid> //F` (Bash) or `Stop-Process -Id <pid> -Force`
  (PowerShell). The sync task (above) will restart the API server on its own
  the next time it finds new data, so don't worry about it staying down —
  just don't be surprised if it comes back up without you doing anything.
- If you ever want local collection back instead of GitHub Actions:
  `Enable-ScheduledTask -TaskName "APIx Collection Cycle"` (and consider
  disabling "APIx GitHub Sync" first, so the two don't fight over the same
  tracked `airfare_observatory.db`).
