"""Migration integration test: alembic must run cleanly against a fresh database."""

import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from app.core.config import get_settings
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine.url import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_DB = "controlflow_migration_test"

# Derived from DATABASE_URL (see tests/conftest.py) so this works both on the
# host and inside the `api` container on the compose network.
_APP_DB_URL = make_url(get_settings().database_url)
MAINTENANCE_DSN = _APP_DB_URL.set(database="postgres", drivername="postgresql").render_as_string(
    hide_password=False
)
MIGRATION_DB_URL = _APP_DB_URL.set(database=MIGRATION_DB).render_as_string(hide_password=False)


@pytest.fixture
def fresh_migration_database():
    conn = psycopg.connect(MAINTENANCE_DSN, autocommit=True)
    try:
        conn.execute(f'DROP DATABASE IF EXISTS "{MIGRATION_DB}"')
        conn.execute(f'CREATE DATABASE "{MIGRATION_DB}"')
    finally:
        conn.close()
    yield MIGRATION_DB_URL
    conn = psycopg.connect(MAINTENANCE_DSN, autocommit=True)
    try:
        conn.execute(f'DROP DATABASE IF EXISTS "{MIGRATION_DB}"')
    finally:
        conn.close()


def test_alembic_upgrade_head_runs_cleanly(fresh_migration_database):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={"DATABASE_URL": fresh_migration_database, "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    engine = create_engine(fresh_migration_database)
    tables = inspect(engine).get_table_names()
    for expected in [
        "users",
        "entities",
        "cases",
        "documents",
        "controls",
        "audit_logs",
        "workflow_events",
    ]:
        assert expected in tables
    engine.dispose()


def test_alembic_downgrade_and_upgrade_roundtrip(fresh_migration_database):
    env = {"DATABASE_URL": fresh_migration_database, "PATH": "/usr/bin:/bin"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert down.returncode == 0, down.stderr

    engine = create_engine(fresh_migration_database)
    tables = inspect(engine).get_table_names()
    assert "users" not in tables
    engine.dispose()

    up_again = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert up_again.returncode == 0, up_again.stderr
