"""V2-009 Canon Persistence Integration Tests.

AT-V2-009-01: Empty database migration and scope FK validation
AT-V2-009-02: Cross-project relationship rejection
AT-V2-009-03: Concurrent root commit uniqueness
AT-V2-009-04: Atomic cancel/commit ordering, permit fencing, recovery boundaries
"""

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

# Import postgres fixture from same directory
from test_postgres_environment import postgres

from anovel.canon.hash import canonical_hash, raw_text_hash
from anovel.canon.repository import (
    CanonRepository,
    ExecutionVersionMismatchError,
    IdempotencyConflictError,
    ProjectScopeViolationError,
    RootCommitExistsError,
)

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
                result = session.execute(
                    text("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                )
                tables = [row[0] for row in result.fetchall()]
                assert tables == [
                    "alembic_version",
                    "artifact_content",
                    "branch_head",
                    "canon_commit",
                    "canon_event",
                    "execution_control",
                    "project",
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
                    changeset={"type": "root", "data": {}},
                )

                # Verify foreign key constraint enforces project scope
                with pytest.raises(IntegrityError):
                    session.execute(
                        text("""
                        INSERT INTO canon_commit
                        (project_id, branch_name, commit_id, parent_commit_id,
                         idempotency_key, payload_hash, changeset)
                        VALUES ('nonexistent-project', 'main', 'commit-1', NULL,
                                'idem-1', 'hash-1', '{}')
                    """)
                    )
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
                    session,
                    "project-a",
                    "main",
                    "commit-a-root",
                    "idem-a-root",
                    "hash-a",
                    {"type": "root"},
                )
                repo.create_root_commit(
                    session,
                    "project-b",
                    "main",
                    "commit-b-root",
                    "idem-b-root",
                    "hash-b",
                    {"type": "root"},
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
                        changeset={"type": "update"},
                    )

            # Attempt cross-branch parent reference within same project (should fail)
            with repo.transaction() as session:
                repo.create_root_commit(
                    session,
                    "project-a",
                    "dev",
                    "commit-a-dev-root",
                    "idem-a-dev-root",
                    "hash-a-dev",
                    {"type": "root"},
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
                        changeset={"type": "update"},
                    )
        finally:
            repo.close()


def test_at_v2_009_03_concurrent_root_commit_uniqueness():
    """AT-V2-009-03: Concurrent root commit uniqueness.

    Verifies:
    - Partial UNIQUE index prevents duplicate root commits per project/branch
    - True concurrent transactions compete for root
    - Database ensures exactly one root succeeds
    - Failed transaction leaves no residual data
    """
    import threading
    import time

    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        try:
            with repo.transaction() as session:
                repo.create_project(session, "test-project")

            # Concurrent root commit attempt
            results = {"success": [], "failed": []}
            lock = threading.Lock()

            def attempt_root(commit_num: int):
                try:
                    repo_thread = CanonRepository(env["ANOVELOS_TEST_DSN"])
                    with repo_thread.transaction() as session:
                        # Small delay to increase concurrency likelihood
                        time.sleep(0.01)
                        repo_thread.create_root_commit(
                            session,
                            "test-project",
                            "main",
                            f"commit-root-{commit_num}",
                            f"idem-root-{commit_num}",
                            f"hash-{commit_num}",
                            {"type": "root", "num": commit_num},
                        )
                    with lock:
                        results["success"].append(commit_num)
                except (RootCommitExistsError, IntegrityError):
                    with lock:
                        results["failed"].append(commit_num)
                finally:
                    repo_thread.close()

            # Launch 5 concurrent threads trying to create root
            threads = [threading.Thread(target=attempt_root, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Exactly one should succeed
            assert len(results["success"]) == 1, f"Expected 1 success, got {len(results['success'])}: {results}"
            assert len(results["failed"]) == 4, f"Expected 4 failures, got {len(results['failed'])}: {results}"

            # Verify only one root exists in database
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE project_id = 'test-project'
                          AND branch_name = 'main'
                          AND parent_commit_id IS NULL
                    """)
                )
                assert result.scalar() == 1

            # But root on different branch should succeed
            with repo.transaction() as session:
                repo.create_root_commit(
                    session,
                    "test-project",
                    "dev",
                    "commit-dev-root",
                    "idem-dev-root",
                    "hash-dev",
                    {"type": "root"},
                )

            # Non-root commits should succeed
            with repo.transaction() as session:
                winner_id = f"commit-root-{results['success'][0]}"
                repo.create_commit(
                    session,
                    "test-project",
                    "main",
                    "commit-2",
                    winner_id,
                    "idem-2",
                    "hash-2",
                    {"type": "update"},
                )

            # Idempotency key conflict should fail
            with pytest.raises(IdempotencyConflictError):
                with repo.transaction() as session:
                    repo.create_commit(
                        session,
                        "test-project",
                        "main",
                        "commit-3",
                        "commit-2",
                        "idem-2",  # Duplicate key!
                        "hash-3",
                        {"type": "update"},
                    )
        finally:
            repo.close()


def test_at_v2_009_04_atomic_cancel_commit_ordering():
    """AT-V2-009-04: Atomic cancel/commit ordering, permit fencing, recovery.

    Verifies:
    - Transaction rollback on error (atomicity)
    - CAS semantics for branch HEAD updates
    - Execution version fencing prevents stale commits
    - Cancel increments version, blocking old commits
    - Idempotent retry after rollback
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        try:
            # Test transaction rollback
            with pytest.raises(RuntimeError, match="Simulated failure"):
                with repo.transaction() as session:
                    repo.create_project(session, "test-project")
                    repo.create_root_commit(
                        session,
                        "test-project",
                        "main",
                        "commit-root",
                        "idem-root",
                        "hash-root",
                        {"type": "root"},
                    )
                    raise RuntimeError("Simulated failure")

            # Verify rollback - project should not exist
            with repo.transaction() as session:
                result = session.execute(
                    text(
                        "SELECT COUNT(*) FROM project WHERE project_id = 'test-project'"
                    )
                )
                assert result.scalar() == 0

            # Now commit successfully with execution control
            with repo.transaction() as session:
                repo.create_project(session, "test-project")
                repo.init_execution_control(session, "test-project", "main")
                repo.create_root_commit(
                    session,
                    "test-project",
                    "main",
                    "commit-root",
                    "idem-root",
                    "hash-root",
                    {"type": "root"},
                )

                # Initialize branch HEAD
                success = repo.update_branch_head_cas(
                    session,
                    "test-project",
                    "main",
                    "commit-root",
                    expected_head_commit_id=None,
                )
                assert success

            # Verify HEAD was set
            with repo.transaction() as session:
                head = repo.get_branch_head(session, "test-project", "main")
                assert head == "commit-root"
                version = repo.get_execution_version(session, "test-project", "main")
                assert version == 1

            # Test execution fencing: cancel increments version
            with repo.transaction() as session:
                new_version = repo.cancel_execution(session, "test-project", "main")
                assert new_version == 2

            # Attempt commit with old version should fail
            with pytest.raises(ExecutionVersionMismatchError, match="expected 1, found 2"):
                with repo.transaction() as session:
                    repo.create_commit_with_fencing(
                        session,
                        "test-project",
                        "main",
                        "commit-2",
                        "commit-root",
                        expected_execution_version=1,  # Stale!
                        idempotency_key="idem-2",
                        payload_hash="hash-2",
                        changeset={"type": "update"},
                    )

            # Commit with correct version should succeed
            with repo.transaction() as session:
                receipt = repo.create_commit_with_fencing(
                    session,
                    "test-project",
                    "main",
                    "commit-2",
                    "commit-root",
                    expected_execution_version=2,  # Current version
                    idempotency_key="idem-2",
                    payload_hash="hash-2",
                    changeset={"type": "update"},
                )
                assert receipt["commit_id"] == "commit-2"
                assert receipt["idempotency_key"] == "idem-2"
                assert receipt["recovered"] is False
                original_timestamp = receipt["committed_at"]

            # Test idempotent receipt recovery: same key + same payload
            with repo.transaction() as session:
                receipt2 = repo.create_commit_with_fencing(
                    session,
                    "test-project",
                    "main",
                    "commit-2-retry",  # Different commit_id attempt
                    "commit-root",
                    expected_execution_version=2,
                    idempotency_key="idem-2",  # Same key
                    payload_hash="hash-2",  # Same payload
                    changeset={"type": "update"},
                )
                assert receipt2["commit_id"] == "commit-2"  # Original commit_id returned
                assert receipt2["idempotency_key"] == "idem-2"
                assert receipt2["recovered"] is True
                assert receipt2["committed_at"] == original_timestamp

            # Test idempotent conflict: same key + different payload
            with pytest.raises(
                IdempotencyConflictError,
                match="already used with different payload.*hash-2.*hash-2-different",
            ):
                with repo.transaction() as session:
                    repo.create_commit_with_fencing(
                        session,
                        "test-project",
                        "main",
                        "commit-2-conflict",
                        "commit-root",
                        expected_execution_version=2,
                        idempotency_key="idem-2",  # Same key
                        payload_hash="hash-2-different",  # Different payload!
                        changeset={"type": "different"},
                    )

            # Verify recovery works even after cancel (commit already succeeded)
            with repo.transaction() as session:
                repo.cancel_execution(session, "test-project", "main")

            # Recovery should still work for already-committed transaction
            with repo.transaction() as session:
                receipt3 = repo.create_commit_with_fencing(
                    session,
                    "test-project",
                    "main",
                    "commit-2-after-cancel",
                    "commit-root",
                    expected_execution_version=3,  # New version after cancel
                    idempotency_key="idem-2",  # Same key as original
                    payload_hash="hash-2",  # Same payload
                    changeset={"type": "update"},
                )
                assert receipt3["recovered"] is True
                assert receipt3["commit_id"] == "commit-2"

            # CAS update with correct expected HEAD should succeed
            with repo.transaction() as session:
                success = repo.update_branch_head_cas(
                    session,
                    "test-project",
                    "main",
                    "commit-2",
                    expected_head_commit_id="commit-root",
                )
                assert success

            # CAS update with wrong expected HEAD should fail
            with repo.transaction() as session:
                success = repo.update_branch_head_cas(
                    session,
                    "test-project",
                    "main",
                    "commit-3",
                    expected_head_commit_id="commit-root",  # Outdated!
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
                        session,
                        "test-project",
                        "main",
                        "commit-3",
                        "commit-2",
                        "idem-3",
                        "hash-3",
                        {"type": "update"},
                    )
                    raise RuntimeError("Simulated failure")
            except RuntimeError:
                pass

            # Retry with same idempotency key should succeed
            with repo.transaction() as session:
                repo.create_commit(
                    session,
                    "test-project",
                    "main",
                    "commit-3",
                    "commit-2",
                    "idem-3",
                    "hash-3",
                    {"type": "update"},
                )

            # Verify commit exists
            with repo.transaction() as session:
                commit = repo.get_commit(session, "test-project", "main", "commit-3")
                assert commit is not None
                assert commit["parent_commit_id"] == "commit-2"
                assert commit["idempotency_key"] == "idem-3"
        finally:
            repo.close()


def test_at_v2_009_05_concurrent_cancel_commit_race():
    """AT-V2-009-05: True concurrent cancel/commit atomic race.

    Verifies:
    - Cancel and commit compete with real concurrent transactions
    - Winner depends on database lock acquisition order
    - Cancel-first: commit blocked by version mismatch
    - Commit-first: cancel cannot undo successful commit
    - No partial state from concurrent operations
    """
    import threading
    import time

    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        try:
            # Setup project with execution control
            with repo.transaction() as session:
                repo.create_project(session, "race-project")
                repo.init_execution_control(session, "race-project", "main")
                repo.create_root_commit(
                    session,
                    "race-project",
                    "main",
                    "commit-root",
                    "idem-root",
                    "hash-root",
                    {"type": "root"},
                )
                repo.update_branch_head_cas(
                    session, "race-project", "main", "commit-root", None
                )

            # Test 1: Cancel wins (acquires lock first)
            cancel_result = {"version": None, "error": None}
            commit_result = {"receipt": None, "error": None}
            barrier = threading.Barrier(2)

            def cancel_execution():
                try:
                    repo_thread = CanonRepository(env["ANOVELOS_TEST_DSN"])
                    with repo_thread.transaction() as session:
                        barrier.wait()  # Synchronize start
                        time.sleep(0.001)  # Tiny delay for cancel to win
                        version = repo_thread.cancel_execution(
                            session, "race-project", "main"
                        )
                        cancel_result["version"] = version
                except Exception as e:
                    cancel_result["error"] = e
                finally:
                    repo_thread.close()

            def commit_with_old_version():
                try:
                    repo_thread = CanonRepository(env["ANOVELOS_TEST_DSN"])
                    with repo_thread.transaction() as session:
                        barrier.wait()  # Synchronize start
                        receipt = repo_thread.create_commit_with_fencing(
                            session,
                            "race-project",
                            "main",
                            "commit-2",
                            "commit-root",
                            expected_execution_version=1,  # Will be stale if cancel wins
                            idempotency_key="idem-cancel-race",
                            payload_hash="hash-cancel-race",
                            changeset={"type": "race-test"},
                        )
                        commit_result["receipt"] = receipt
                except Exception as e:
                    commit_result["error"] = e
                finally:
                    repo_thread.close()

            t1 = threading.Thread(target=cancel_execution)
            t2 = threading.Thread(target=commit_with_old_version)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # If cancel won, version should be 2 and commit should have failed
            if cancel_result["version"] == 2:
                assert isinstance(
                    commit_result["error"], ExecutionVersionMismatchError
                )
                # Verify no commit was created
                with repo.transaction() as session:
                    result = session.execute(
                        text("""
                            SELECT COUNT(*) FROM canon_commit
                            WHERE project_id = 'race-project'
                              AND branch_name = 'main'
                              AND idempotency_key = 'idem-cancel-race'
                        """)
                    )
                    assert result.scalar() == 0

            # Test 2: Commit wins (different idempotency key for clean slate)
            with repo.transaction() as session:
                # Reset version to known state
                current_version = repo.get_execution_version(
                    session, "race-project", "main"
                )

            commit_first_result = {"receipt": None, "error": None}
            cancel_after_result = {"version": None, "error": None}
            barrier2 = threading.Barrier(2)

            def commit_first():
                try:
                    repo_thread = CanonRepository(env["ANOVELOS_TEST_DSN"])
                    with repo_thread.transaction() as session:
                        barrier2.wait()
                        # No sleep - let commit win
                        receipt = repo_thread.create_commit_with_fencing(
                            session,
                            "race-project",
                            "main",
                            "commit-3",
                            "commit-root",
                            expected_execution_version=current_version,
                            idempotency_key="idem-commit-wins",
                            payload_hash="hash-commit-wins",
                            changeset={"type": "commit-first"},
                        )
                        commit_first_result["receipt"] = receipt
                except Exception as e:
                    commit_first_result["error"] = e
                finally:
                    repo_thread.close()

            def cancel_after():
                try:
                    repo_thread = CanonRepository(env["ANOVELOS_TEST_DSN"])
                    with repo_thread.transaction() as session:
                        barrier2.wait()
                        time.sleep(0.01)  # Let commit win
                        version = repo_thread.cancel_execution(
                            session, "race-project", "main"
                        )
                        cancel_after_result["version"] = version
                except Exception as e:
                    cancel_after_result["error"] = e
                finally:
                    repo_thread.close()

            t3 = threading.Thread(target=commit_first)
            t4 = threading.Thread(target=cancel_after)
            t3.start()
            t4.start()
            t3.join()
            t4.join()

            # If commit won, it should have succeeded
            if commit_first_result["receipt"] is not None:
                assert commit_first_result["receipt"]["commit_id"] == "commit-3"
                # Cancel should have incremented version after commit
                assert cancel_after_result["version"] == current_version + 1
                # Commit should still exist (cancel doesn't undo successful commits)
                with repo.transaction() as session:
                    commit = repo.get_commit(
                        session, "race-project", "main", "commit-3"
                    )
                    assert commit is not None
                    assert commit["idempotency_key"] == "idem-commit-wins"

        finally:
            repo.close()


def test_adr_005_hash_functions():
    """Verify ADR-005 hash implementation.

    Tests raw_text_hash and canonical_hash against known test vectors.
    """
    # Test raw_text_hash
    assert (
        raw_text_hash("hello")
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
    assert (
        raw_text_hash("")
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )

    # Test canonical_hash with simple values
    assert canonical_hash("hello") == raw_text_hash('"hello"')
    assert canonical_hash(42) == raw_text_hash("42")
    assert canonical_hash(True) == raw_text_hash("true")
    assert canonical_hash(None) == raw_text_hash("null")

    # Test canonical_hash with dict (sorted keys)
    obj = {"b": 2, "a": 1}
    expected_json = '{"a":1,"b":2}'
    assert canonical_hash(obj) == raw_text_hash(expected_json)

    # Test canonical_hash with nested structure
    nested = {"outer": {"b": 2, "a": 1}, "list": [3, 2, 1]}
    expected_nested = '{"list":[3,2,1],"outer":{"a":1,"b":2}}'
    assert canonical_hash(nested) == raw_text_hash(expected_nested)

    # Test NFC normalization - equivalent strings produce same hash
    # "café" with precomposed é (U+00E9)
    cafe_precomposed = {"key": "café"}
    # "café" with combining accent (e + U+0301)
    cafe_combining = {"key": "café"}
    # After NFC normalization, both should produce the same hash
    assert canonical_hash(cafe_precomposed) == canonical_hash(cafe_combining)

    # Test NaN rejection
    with pytest.raises(ValueError, match="NaN or Infinity"):
        canonical_hash(float("nan"))

    # Test Infinity rejection
    with pytest.raises(ValueError, match="NaN or Infinity"):
        canonical_hash(float("inf"))

    # Test negative Infinity rejection
    with pytest.raises(ValueError, match="NaN or Infinity"):
        canonical_hash(float("-inf"))

    # Test duplicate key detection after NFC normalization
    # Create two different strings that normalize to the same NFC form
    # Using é (U+00E9) vs e+combining (U+0065 U+0301)
    with pytest.raises(ValueError, match="Duplicate key after NFC normalization"):
        # Manually construct dict to bypass Python's literal deduplication
        d = {}
        d["café"] = 1  # precomposed
        d["café"] = 2  # combining - will collide after NFC
        canonical_hash(d)

    # Test nested duplicate key detection
    with pytest.raises(ValueError, match="Duplicate key after NFC normalization"):
        d = {}
        d["outer"] = {}
        d["outer"]["keyé"] = 1  # precomposed
        d["outer"]["keyé"] = 2  # combining - will collide
        canonical_hash(d)

    # Test non-string key rejection
    with pytest.raises(TypeError, match="JSON object keys must be strings"):
        canonical_hash({1: "value"})

    # Test non-JSON-serializable type
    with pytest.raises(TypeError, match="not JSON-serializable"):
        canonical_hash({"key": set([1, 2, 3])})
