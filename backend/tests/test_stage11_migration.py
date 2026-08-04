"""Structural smoke test for the Alembic migration.

This does not replace running `alembic upgrade head` against a real
Postgres instance (`docker compose up -d postgres`) at least once — it
just proves the migration you generated applies and rolls back cleanly.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {"users", "refresh_tokens", "projects", "api_keys"}


def _has_migrations() -> bool:
    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    if not versions_dir.exists():
        return False
    return any(p.suffix == ".py" and p.name != "__init__.py" for p in versions_dir.iterdir())


@pytest.mark.skipif(
    not _has_migrations(),
    reason="No Alembic migration yet — run `alembic revision --autogenerate` first (see stage 11).",
)
def test_migration_upgrades_and_downgrades_cleanly(tmp_path) -> None:
    db_path = tmp_path / "stage11.db"
    database_url = f"sqlite:///{db_path}"
    env = {**os.environ, "DATABASE_URL": database_url}

    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables
    engine.dispose()

    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert downgrade.returncode == 0, downgrade.stdout + downgrade.stderr

    engine = create_engine(database_url)
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES.isdisjoint(tables_after_downgrade)
    engine.dispose()
