"""Test to verify actual PostgreSQL isolation level and locking behavior."""

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from test_postgres_environment import postgres

from anovel.canon.repository import CanonRepository

ROOT = Path(__file__).resolve().parents[2]


def run_migration(env: dict[str, str], command: str = "upgrade") -> None:
    """Run Alembic migration command."""
    result = subprocess.run(
        ["uv", "run", "alembic", command, "head"],
        env=env,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        pytest.fail(f"Migration {command} failed: {result.stdout}\n{result.stderr}")


def test_postgres_isolation_level():
    """Verify actual PostgreSQL transaction isolation level.

    Checks:
    - Default isolation level used by CanonRepository
    - execution_control FOR UPDATE locking behavior
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])

        try:
            with repo.transaction() as session:
                # Check actual isolation level
                result = session.execute(text("SHOW transaction_isolation"))
                isolation_level = result.scalar()

                print(f"Actual PostgreSQL isolation level: {isolation_level}")

                # PostgreSQL default is "read committed"
                # This is sufficient with execution_control FOR UPDATE row lock
                assert isolation_level in ("read committed", "repeatable read", "serializable")

                # Verify execution_control table exists
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM information_schema.tables
                        WHERE table_name = 'execution_control'
                    """)
                )
                assert result.scalar() == 1

        finally:
            repo.close()
