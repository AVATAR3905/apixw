# Contributing

This project follows a **statistics-first, incremental** development process (PRD §4, §56, §71). The scraper is replaceable; the measurement methodology is the product. Keep that priority order in mind for every change.

## Setup

```bash
git clone <repo>
cd APIx-main
pip install -r requirements.txt
cp .env.example .env          # fill in real values locally; .env is gitignored, never commit it
alembic upgrade head          # apply database migrations
python -m database.seeds.seed_all   # optional: seed reference data (routes, airlines, sources)
```

Bring up the stack with the `Makefile` targets:

```bash
make api          # FastAPI on :8000, --reload
make dashboard    # Next.js on :3000
make full         # full pipeline: seed + live collection + API + dashboard (scripts/run_observatory.py)
```

## Before opening a PR

```bash
make lint     # ruff check + ruff format --check
make test     # pytest tests/ -v
```

Both must pass. CI (`.github/workflows/ci.yml`) re-runs the same checks on every push.

## Where things live

```
apps/api/            FastAPI app and routers (apps/api/routers/api_v1.py is the main surface)
apps/dashboard/       Next.js dashboard
services/collectors/  Per-source scrapers/connectors (carrier-direct, OTA, RPC, GDS)
services/scheduler/   CollectionScheduler — the resume-safe 10-route x 5-horizon job loop
packages/statistics/  Index engine, quality engine, weights, forecasting, anomaly detection
packages/schemas/     SQLAlchemy models
database/migrations/  Alembic migrations
tests/unit/           Fast, isolated tests (mocked I/O)
tests/integration/    Multi-component tests (real DB, no network)
tests/statistical/    Deterministic fixtures for index/weight math (PRD §61)
tests/chaos/          Resilience tests (crash recovery, resume logic, malformed responses)
```

## Rules that matter more here than in a typical repo

These come directly from the PRD (§4, §56, §71) and from real incidents hit during development — they are not stylistic preferences.

1. **Never silently substitute a fabricated value for missing data.** A sold-out flight is `SOLD_OUT`, not `₹0`. A failed source is `SOURCE_ERROR`, not a quietly-dropped observation. A crashed connector must never produce data that looks like a clean success (see `QualityEngine` and `SourceRegistryService.can_collect`).
2. **Statistical formulas need deterministic tests, not just integration coverage.** If you touch `packages/statistics/index_engine.py` or anything computing weights/relatives/index values, add a fixture with a hand-computed expected output (see `tests/statistical/` for the pattern: known route prices + known weights → known expected index).
3. **A methodology change is a new version, not a silent edit.** Changing the base period, price estimator, missing-data treatment, outlier method, or weight formula requires a new `methodology_version` row, not an in-place change to existing logic (PRD §41, §6.4).
4. **Test cleanup must never touch production data by a broad filter.** A prior bug here cleaned up test rows via `source_id.in_([...])`, which matched and deleted real collected fare data on every test run. Always scope test fixtures/cleanup to data you created yourself (a dedicated test route/id), never to a shared `source_id` or other value real data also uses.
5. **A collector crash must be resumable, not a restart-from-scratch.** `CollectionScheduler.trigger_collection_cycle` is resume-safe by design (it skips already-`COMPLETED` route/horizon pairs for the same date). If you add a new collection entry point, preserve this property — don't reintroduce a full-basket restart on every retry.
6. **Don't build anti-detection/evasion tooling.** IP rotation, TLS/fingerprint spoofing, and CAPTCHA-solving are explicitly out of scope (PRD §6). If a source blocks the scraper, that's a `PERMISSION_DENIED`/`SOURCE_UNAVAILABLE` state to surface, not a problem to engineer around.
7. **Raw payloads are immutable.** Never overwrite a `raw_payload` row — the pipeline's auditability (`raw_payload -> observation -> quality_decision -> index_value`) depends on every stage being traceable back to what was actually fetched.

## Commit messages

Reference the module for statistical/methodology changes, e.g.:

```
feat(index): introduce APIX-1.1 trimmed mean estimator
fix(scraper): stop OCR fallback capping carrier-direct results at one flight
```

## Adding a new data source

For an OTA/metasearch-style source, the collection engine is pluggable: write
a `BaseOTAScraper` subclass (`services/collectors/ota/`) implementing
`_execute_scrape` and `_generate_calibrated_quotes`, decorate it with
`@register_ota_scraper("<exact sources.name value>")`, and add/approve its row
in the `sources` table. `CollectionScheduler` and `MultiSourceFlightOrchestrator`
both discover scrapers through this registry (`services/collectors/ota/registry.py`)
rather than a hard-coded list, so nothing else needs to change (PRD US-014).
The registry only *instantiates* a scraper whose DB row currently passes
`SourceRegistryService.can_collect` — writing the class doesn't turn on live
collection against that site; approving the source does.

A collector is only "done" when (PRD §87):

- it's registered in the `sources` table with a documented `permission_status`
- input parameters are validated
- responses are logged and raw payloads stored
- normalized observations pass through the quality engine (sold-out handling included)
- parser errors surface as a classified error code, not a silent empty result
- retries are bounded (no infinite retry loops)
- health metrics are emitted (`source-health` reflects it)
- it has integration test coverage
