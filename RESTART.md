# Restarting APIx After a Reboot

The production site no longer depends on this machine being on at all — see
"Live deployment" below. This file is about the **local development**
copy: a system restart kills the local API server and local dashboard,
but nothing is lost (the local SQLite fallback DB and all code are on
disk) — you just need to relaunch the two processes. Run everything below
from the project root: `C:\Users\cecilia\Downloads\APIx-main\APIx-main`.

## Live deployment

The real, production-facing stack runs independently of this machine:

- **API**: https://apix-observatory-api.vercel.app (FastAPI, deployed as a
  Vercel Python function; redeploys automatically on every push to `main`)
- **Dashboard** (the one actually in use): https://apix-observatory-api.vercel.app/ui/
  — a static single-file UI served by the same deployed API. (The separate
  Next.js dashboard that used to run on local port 3000 is **not** deployed
  anywhere anymore — local dev only, see below.)
- **Database**: a shared Neon Postgres instance (`DATABASE_URL`, stored as a
  Vercel secret and a GitHub Actions repo secret) — both the deployed API
  and the scheduled collector read/write the same live data.

## Where data collection actually happens now

**Real-data collection runs on GitHub Actions, writing straight into the
shared Postgres above** — not into a file that gets committed back to git.
`.github/workflows/collect.yml` checks in 8x/day on GitHub's own
infrastructure (2 per ~6h target window instead of the original 1 —
GitHub's scheduled-workflow dispatcher is best-effort and silently dropped
one of the old 4 fixed crons on 2026-10-11, causing a real gap; see the
workflow file's own comment for the full story, including a first attempt
at hourly/24x triggers that made things worse by moving into a frequency
GitHub throttles even harder), completely independent of whether this
machine is even on. A ~5.5h freshness window in the scheduler means the
backup check-in in each pair is usually a cheap no-op (primary already
succeeded) — only roughly 4 of the 8 daily triggers actually turn into a
real collection. Check its history any time:

```bash
gh run list --repo AVATAR3905/apixw --workflow="Collect Real Airfare Data"
```

**The local "APIx Collection Cycle" scheduled task is disabled** (not
deleted — re-enable with `Enable-ScheduledTask -TaskName "APIx Collection
Cycle"` if you ever want local collection back). It used to scrape into the
local `airfare_observatory.db` file independently of GitHub Actions, which
made sense back when GitHub Actions committed its results to that same
tracked file and the two needed reconciling — now that GitHub Actions
writes directly to the shared Postgres instead, local collection would just
be scraping into a SQLite file nothing downstream reads, so it's been
turned off. The local SQLite file remains purely a local-dev fallback (see
`database/session.py`): when `DATABASE_URL` isn't set (or the Postgres
connection fails), the app transparently falls back to
`sqlite:///./airfare_observatory.db`, same as always.

The old "APIx GitHub Sync" scheduled task (pulling git commits every 30 min
to pick up a freshly-committed DB file) is likewise obsolete and was already
disabled — git commits no longer carry fresh data at all now, only code
changes, so there's nothing for a sync task like that to do.

## 1. Check what's already running

```bash
netstat -ano | grep -E ":8000|:3000" | grep LISTENING
```

If both lines show up, you're already good — skip to step 4 (health check).

## 2. Start the local API server (port 8000)

```bash
nohup python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
```

Wait for it to bind before moving on:

```bash
until netstat -ano | grep ":8000" | grep -q LISTENING; do sleep 2; done; echo "API is up"
```

By default (no `DATABASE_URL` env var set locally) this talks to the local
SQLite fallback, not the shared production Postgres — set `DATABASE_URL` to
the Neon connection string first if you want this local server to read/write
the same live data the deployed site uses.

## 3. Start the local dashboard (port 3000) — optional, local dev only

Only needed if you're actively working on the Next.js dashboard itself; it
isn't deployed anywhere and isn't what the live site shows.

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
curl -s "http://localhost:8000/health"
curl -s "http://localhost:8000/api/v1/routes"
```

Then open whichever frontend you're using locally:

- Lightweight viewer (the one actually in use, matches the live `/ui`): http://localhost:8000/ui
- Next.js dashboard (local dev only, not deployed): http://localhost:3000

## Notes

- **Don't use `scripts/run_observatory.py` to start these** unless you want
  both processes tied together — its watchdog loop kills *both* the moment
  *either one* exits, which has caused accidental full outages before. The
  standalone commands above are more resilient if you ever need to restart
  just one side.
- To stop a server: find its PID with the `netstat` command in step 1, then
  `taskkill //PID <pid> //F` (Bash) or `Stop-Process -Id <pid> -Force`
  (PowerShell).
- The local uvicorn server holds a persistent connection to
  `airfare_observatory.db` for as long as it runs. If you need git to update
  that file (e.g. `git pull`, `git checkout`), stop the server first — a
  live connection can block the filesystem write on Windows.
