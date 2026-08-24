"""
Database connection setup.

Defaults to SQLite (zero-config, single file, perfect for a prototype /
science-fair demo). If you later want PostgreSQL, just set the
DATABASE_URL environment variable, e.g.:

    export DATABASE_URL="postgresql://user:password@localhost:5432/aquasentry"

Nothing else in the codebase needs to change.
"""

import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aquasentry.db")

# check_same_thread is only needed for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_sqlite_columns():
    """Add optional columns introduced after the first SQLite schema version."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    required_columns = {
        "battery_pct": "FLOAT",
        "source_label": "VARCHAR(64)",
    }
    existing_columns = {
        column["name"] for column in inspect(engine).get_columns("readings")
    }
    missing_columns = required_columns.keys() - existing_columns
    if not missing_columns:
        return

    with engine.begin() as connection:
        for column_name in missing_columns:
            connection.execute(
                text(f"ALTER TABLE readings ADD COLUMN {column_name} {required_columns[column_name]}")
            )


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
