# Restarting APIx After a Reboot

A system restart kills the API server and the dashboard. Nothing is lost —
the database (`airfare_observatory.db`) and all code are on disk — you just
need to relaunch the two processes. Run everything below from the project
root: `C:\Users\cecilia\Downloads\APIx-main\APIx-main`.

**The 4x-daily data collection (06:00/12:00/18:00/23:00 IST) no longer
depends on the API server at all.** It's a Windows Task Scheduler entry
("APIx Collection Cycle") that runs independently — it survives the API
server being down, and Windows itself runs it as soon as possible after a
missed slot (e.g. the machine was asleep). You don't need to do anything for
it to keep working after a reboot; it's registered at the OS level. Check its
history any time with:

```powershell
Get-ScheduledTask -TaskName "APIx Collection Cycle" | Get-ScheduledTaskInfo
```

(The in-process APScheduler that used to live inside the API server for this
was found to silently miss runs with no error — see TASKS.md v2.7 changelog
— so this was moved out to Task Scheduler instead.)

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
- If you stop and restart the API server mid-day, it only schedules *future*
  cron slots from that moment — it won't backfill a collection cycle it
  missed while down.
- To stop a server: find its PID with the `netstat` command in step 1, then
  `taskkill //PID <pid> //F` (Bash) or `Stop-Process -Id <pid> -Force`
  (PowerShell).
