"""Database engine and session management with PostgreSQL primary and SQLite fallback."""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from packages.schemas.models import Base
from packages.shared.config import settings

logger = logging.getLogger(__name__)

# Determine active database URL
db_url = settings.DATABASE_URL

# Connect to database with resilient fallback
try:
    engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600, echo=False)
    # Test connection
    with engine.connect() as conn:
        logger.info("Successfully connected to primary PostgreSQL database.")
except Exception as e:
    logger.warning(
        f"Could not connect to PostgreSQL at {db_url} ({e}). Falling back to local SQLite engine for development."
    )
    fallback_url = "sqlite:///./airfare_observatory.db"
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False}, echo=False)
    logger.info(f"Initialized fallback SQLite engine at {fallback_url}.")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _existing_columns(connection, table: str) -> set:
    """Return the set of column names that already exist on a table."""
    dialect = connection.dialect.name
    if dialect == "postgresql":
        rows = connection.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :tbl"),
            {"tbl": table},
        )
    else:
        rows = connection.execute(text(f"PRAGMA table_info({table})"))
        return {str(r[1]) for r in rows}
    return {str(r[0]) for r in rows}


# Additive-only schema migrations (no destructive operations).
# Keeps existing databases compatible when new columns are introduced.
SCHEMA_ADDITIONS = {
    "sources": {
        "access_mode": "ALTER TABLE sources ADD COLUMN access_mode VARCHAR(20) DEFAULT 'PUBLIC'"
    },
    "fare_observations": {
        "extraction_method": (
            "ALTER TABLE fare_observations ADD COLUMN extraction_method VARCHAR(40) "
            "DEFAULT 'NETWORK'"
        )
    },
    "index_values": {
        "standard_error": "ALTER TABLE index_values ADD COLUMN standard_error FLOAT",
        "index_ci_lower": "ALTER TABLE index_values ADD COLUMN index_ci_lower FLOAT",
        "index_ci_upper": "ALTER TABLE index_values ADD COLUMN index_ci_upper FLOAT",
        "bootstrap_replications": (
            "ALTER TABLE index_values ADD COLUMN bootstrap_replications INTEGER"
        ),
        "variance_method": (
            "ALTER TABLE index_values ADD COLUMN variance_method VARCHAR(40)"
        ),
    },
}


def ensure_schema():
    """Add missing columns to already-created tables (lightweight migration)."""
    with engine.connect() as conn:
        for table, columns in SCHEMA_ADDITIONS.items():
            existing = _existing_columns(conn, table)
            for col_name, ddl in columns.items():
                if col_name in existing:
                    continue
                try:
                    conn.execute(text(ddl))
                    conn.commit()
                    logger.info("Added missing column %s.%s via ensure_schema.", table, col_name)
                except Exception as e:  # pragma: no cover - defensive
                    conn.rollback()
                    logger.warning("Could not add column %s.%s (%s).", table, col_name, e)


def init_db():
    """Create all database tables from SQLAlchemy declarative metadata."""
    Base.metadata.create_all(bind=engine)
    ensure_schema()


def get_db():
    """FastAPI Dependency providing a transactional database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
