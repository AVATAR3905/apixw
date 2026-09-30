"""One-time migration of the local SQLite dev DB into a hosted Postgres instance.

Run once, after provisioning the target Postgres (e.g. Neon/Supabase free tier)
and before pointing GitHub Actions / the deployed API at it via DATABASE_URL.

Usage:
    DATABASE_URL=postgresql://user:pass@host/dbname python scripts/migrate_sqlite_to_postgres.py
"""

import os
import sys

from sqlalchemy import create_engine, select

from packages.schemas.models import Base

SQLITE_PATH = "airfare_observatory.db"


def main() -> None:
    pg_url = os.environ.get("DATABASE_URL")
    if not pg_url or not pg_url.startswith("postgres"):
        print("Set DATABASE_URL to the target Postgres connection string (postgres:// or postgresql://).")
        sys.exit(1)

    if not os.path.exists(SQLITE_PATH):
        print(f"Local SQLite DB not found at ./{SQLITE_PATH}")
        sys.exit(1)

    sqlite_engine = create_engine(f"sqlite:///./{SQLITE_PATH}")
    pg_engine = create_engine(pg_url)

    print(f"Creating schema on target Postgres ({pg_engine.url.host})...")
    Base.metadata.create_all(bind=pg_engine)

    with sqlite_engine.connect() as src, pg_engine.begin() as dst:
        for table in Base.metadata.sorted_tables:
            rows = [dict(r._mapping) for r in src.execute(select(table))]
            if not rows:
                print(f"  {table.name}: 0 rows, skipping")
                continue
            dst.execute(table.delete())
            dst.execute(table.insert(), rows)
            print(f"  {table.name}: migrated {len(rows)} rows")

            if "id" in table.c:
                dst.exec_driver_sql(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 1))"
                )

    print("Migration complete.")


if __name__ == "__main__":
    main()
