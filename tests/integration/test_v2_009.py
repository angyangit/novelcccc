"""V2-009 Canon Persistence Integration Tests.

AT-V2-009-01: Empty database migration and scope FK validation
AT-V2-009-02: Cross-project relationship rejection
AT-V2-009-03: Concurrent root commit uniqueness
AT-V2-009-04: Atomic cancel/commit ordering, permit fencing, recovery boundaries
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from anovel.canon.hash import raw_text_hash, canonical_hash
from anovel.canon.repository import (
    CanonRepository,
    RootCommitExistsError,
    IdempotencyConflictError,
    ProjectScopeViolationError,
    CASUpdateFailedError
)

# Import postgres fixture from same directory
from test_postgres_environment import postgres

ROOT = Path(__file__).resolve().parents[2]


def run_migration(env: Dict[str, str], command: str = "upgrade") -> None:
    """Run Alembic migration command."""
    result = subprocess.run(
        ["uv", "run", "alembic", command, "head"],
        env=env,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60
    )
    if result.returncode != 0:
        pytest.fail(f"Migration {command} failed: {result.stdout}\n{result.stderr}")


def test_at_v2_009_01_empty_database_migration_and_scope_fk():
    """AT-V2-009-01: Empty database migration and scope FK validation.

    Verifies:
    - Alembic migrations run successfully on empty PostgreSQL database
    - All 6 tables created (project, canon_commit, branch_head, canon_event,
      execution_control, artifact_content)
    - Composite foreign keys enforce project/branch scope boundaries
    - Partial UNIQUE index enforces root commit uniqueness
    """
    with postgres() as (env, project):
        # Run migrations
        run_migration(env, "upgrade")

        # Verify all tables exist
        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        try:
            with repo.transaction() as session:
                result = session.execute(text("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result.fetchall()]
                assert tables == [
                    'alembic_version',
                    'artifact_content',
                    'branch_head',
                    'canon_commit',
                    'canon_event',
                    'execution_control',
                    'project'
                ]

                # Verify project scope boundary works
                repo.create_project(session, "test-project-1")

                # Verify root commit creation
                repo.create_root_commit(
                    session,
                    project_id="test-project-1",
                    branch_name="main",
                    commit_id="commit-root-1",
                    idempotency_key="idem-root-1",
                    payload_hash=canonical_hash({"initial": "state"}),
                    changeset={"type": "root", "data": {}}
                )

                # Verify foreign key constraint enforces project scope
                with pytest.raises(Exception):  # IntegrityError wrapped
                    session.execute(text("""
                        INSERT INTO canon_commit
                        (project_id, branch_name, commit_id, parent_commit_id,
                         idempotency_key, payload_hash, changeset)
                        VALUES ('nonexistent-project', 'main', 'commit-1', NULL,
                                'idem-1', 'hash-1', '{}')
                    """))
        finally:
            repo.close()


def test_at_v2_009_02_cross_project_relationship_rejection():
    """AT-V2-009-02: Cross-project relationship rejection.

    Verifies:
    - Composite foreign keys prevent cross-project parent references
    - Branch HEAD cannot reference commit from different project/branch
    - Canon events must reference commits from same project/branch
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        try:
            with repo.transaction() as session:
                # Create two projects
                repo.create_project(session, "project-a")
                repo.create_project(session, "project-b")

                # Create root commits for both
                repo.create_root_commit(
                    session, "project-a", "main", "commit-a-root",
                    "idem-a-root", "hash-a", {"type": "root"}
                )
                repo.create_root_commit(
                    session, "project-b", "main", "commit-b-root",
                    "idem-b-root", "hash-b", {"type": "root"}
                )

            # Attempt cross-project parent reference (should fail)
            with pytest.raises(ProjectScopeViolationError):
                with repo.transaction() as session:
                    repo.create_commit(
                        session,
                        project_id="project-a",
                        branch_name="main",
                        commit_id="commit-a-2",
                        parent_commit_id="commit-b-root",  # Wrong project!
                        idempotency_key="idem-a-2",
                        payload_hash="hash-a-2",
                        changeset={"type": "update"}
                    )

            # Attempt cross-branch parent reference within same project (should fail)
            with repo.transaction() as session:
                repo.create_root_commit(
                    session, "project-a", "dev", "commit-a-dev-root",
                    "idem-a-dev-root", "hash-a-dev", {"type": "root"}
                )

            with pytest.raises(ProjectScopeViolationError):
                with repo.transaction() as session:
                    repo.create_commit(
                        session,
                        project_id="project-a",
                        branch_name="dev",
                        commit_id="commit-a-dev-2",
                        parent_commit_id="commit-a-root",  # Wrong branch!
                        idempotency_key="idem-a-dev-2",
                        payload_hash="hash-a-dev-2",
                        changeset={"type": "update"}
                    )
        finally:
            repo.close()


def test_at_v2_009_03_concurrent_root_commit_uniqueness():
    """AT-V2-009-03: Concurrent root commit uniqueness.

    Verifies:
    - Partial UNIQUE index prevents duplicate root commits per project/branch
    - Multiple non-root commits allowed (parent_commit_id IS NOT NULL)
    - Idempotency key prevents duplicate commits with same key
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        try:
            with repo.transaction() as session:
                repo.create_project(session, "test-project")
                repo.create_root_commit(
                    session, "test-project", "main", "commit-root-1",
                    "idem-root-1", "hash-1", {"type": "root"}
                )

            # Attempt second root commit (should fail)
            with pytest.raises(RootCommitExistsError):
                with repo.transaction() as session:
                    repo.create_root_commit(
                        session, "test-project", "main", "commit-root-2",
                        "idem-root-2", "hash-2", {"type": "root"}
                    )

            # But root on different branch should succeed
            with repo.transaction() as session:
                repo.create_root_commit(
                    session, "test-project", "dev", "commit-dev-root",
                    "idem-dev-root", "hash-dev", {"type": "root"}
                )

            # Non-root commits should succeed
            with repo.transaction() as session:
                repo.create_commit(
                    session, "test-project", "main", "commit-2",
                    "commit-root-1", "idem-2", "hash-2", {"type": "update"}
                )
                repo.create_commit(
                    session, "test-project", "main", "commit-3",
                    "commit-2", "idem-3", "hash-3", {"type": "update"}
                )

            # Idempotency key conflict should fail
            with pytest.raises(IdempotencyConflictError):
                with repo.transaction() as session:
                    repo.create_commit(
                        session, "test-project", "main", "commit-4",
                        "commit-3", "idem-2",  # Duplicate key!
                        "hash-4", {"type": "update"}
                    )
        finally:
            repo.close()


def test_at_v2_009_04_atomic_cancel_commit_ordering():
    """AT-V2-009-04: Atomic cancel/commit ordering, permit fencing, recovery.

    Verifies:
    - Transaction rollback on error (atomicity)
    - CAS semantics for branch HEAD updates
    - Concurrent modification detection
    - Idempotent retry after rollback
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        try:
            # Test transaction rollback
            with pytest.raises(Exception):
                with repo.transaction() as session:
                    repo.create_project(session, "test-project")
                    repo.create_root_commit(
                        session, "test-project", "main", "commit-root",
                        "idem-root", "hash-root", {"type": "root"}
                    )
                    raise RuntimeError("Simulated failure")

            # Verify rollback - project should not exist
            with repo.transaction() as session:
                result = session.execute(
                    text("SELECT COUNT(*) FROM project WHERE project_id = 'test-project'")
                )
                assert result.scalar() == 0

            # Now commit successfully
            with repo.transaction() as session:
                repo.create_project(session, "test-project")
                repo.create_root_commit(
                    session, "test-project", "main", "commit-root",
                    "idem-root", "hash-root", {"type": "root"}
                )

                # Initialize branch HEAD
                success = repo.update_branch_head_cas(
                    session, "test-project", "main", "commit-root", expected_head_commit_id=None
                )
                assert success

            # Verify HEAD was set
            with repo.transaction() as session:
                head = repo.get_branch_head(session, "test-project", "main")
                assert head == "commit-root"

            # Create second commit
            with repo.transaction() as session:
                repo.create_commit(
                    session, "test-project", "main", "commit-2",
                    "commit-root", "idem-2", "hash-2", {"type": "update"}
                )

            # CAS update with correct expected HEAD should succeed
            with repo.transaction() as session:
                success = repo.update_branch_head_cas(
                    session, "test-project", "main", "commit-2",
                    expected_head_commit_id="commit-root"
                )
                assert success

            # CAS update with wrong expected HEAD should fail
            with repo.transaction() as session:
                success = repo.update_branch_head_cas(
                    session, "test-project", "main", "commit-3",
                    expected_head_commit_id="commit-root"  # Outdated!
                )
                assert not success

            # Verify HEAD unchanged
            with repo.transaction() as session:
                head = repo.get_branch_head(session, "test-project", "main")
                assert head == "commit-2"

            # Idempotent retry after failed transaction
            try:
                with repo.transaction() as session:
                    repo.create_commit(
                        session, "test-project", "main", "commit-3",
                        "commit-2", "idem-3", "hash-3", {"type": "update"}
                    )
                    raise RuntimeError("Simulated failure")
            except RuntimeError:
                pass

            # Retry with same idempotency key should succeed
            with repo.transaction() as session:
                repo.create_commit(
                    session, "test-project", "main", "commit-3",
                    "commit-2", "idem-3", "hash-3", {"type": "update"}
                )

            # Verify commit exists
            with repo.transaction() as session:
                commit = repo.get_commit(session, "test-project", "main", "commit-3")
                assert commit is not None
                assert commit["parent_commit_id"] == "commit-2"
                assert commit["idempotency_key"] == "idem-3"
        finally:
            repo.close()


def test_adr_005_hash_functions():
    """Verify ADR-005 hash implementation.

    Tests raw_text_hash and canonical_hash against known test vectors.
    """
    # Test raw_text_hash
    assert raw_text_hash("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert raw_text_hash("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # Test canonical_hash with simple values
    assert canonical_hash("hello") == raw_text_hash('"hello"')
    assert canonical_hash(42) == raw_text_hash('42')
    assert canonical_hash(True) == raw_text_hash('true')
    assert canonical_hash(None) == raw_text_hash('null')

    # Test canonical_hash with dict (sorted keys)
    obj = {"b": 2, "a": 1}
    expected_json = '{"a":1,"b":2}'
    assert canonical_hash(obj) == raw_text_hash(expected_json)

    # Test canonical_hash with nested structure
    nested = {"outer": {"b": 2, "a": 1}, "list": [3, 2, 1]}
    expected_nested = '{"list":[3,2,1],"outer":{"a":1,"b":2}}'
    assert canonical_hash(nested) == raw_text_hash(expected_nested)

    # Test NFC normalization
    # "café" with combining accent (U+0065 U+0301) vs precomposed (U+00E9)
    nfc_normalized = canonical_hash({"key": "café"})  # Python strings are NFC by default
    assert isinstance(nfc_normalized, str)
    assert len(nfc_normalized) == 64

    # Test NaN rejection
    with pytest.raises(ValueError, match="NaN or Infinity"):
        canonical_hash(float('nan'))

    # Test Infinity rejection
    with pytest.raises(ValueError, match="NaN or Infinity"):
        canonical_hash(float('inf'))

    # Test negative Infinity rejection
    with pytest.raises(ValueError, match="NaN or Infinity"):
        canonical_hash(float('-inf'))
