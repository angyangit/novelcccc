"""V2-011 Canon Idempotency and CAS Acceptance Tests.

V2-011 acceptance verification that reuses V2-010 CanonCommitService implementation.
All idempotency and CAS mechanisms already exist in commit_service.py and repository.py.

This test file provides explicit V2-011 acceptance test identifiers (AT-V2-011-01/02/03)
that map to the existing V2-010 test coverage, confirming:

1. Same key + same payload returns original receipt (idempotent retry)
2. Same key + different payload raises conflict; concurrent CAS only one succeeds
3. Commit success + response loss retry doesn't create duplicate commit

Design Decision: V2-011 does NOT create a separate idempotency module. The idempotency
mechanism is integral to CanonCommitService's atomic transaction protocol (commit_service.py
lines 200-242) and cannot be meaningfully separated without creating duplicate code.

Contract: V2-011 per ADR-006 and 03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from test_postgres_environment import postgres
from test_v2_010 import (
    TestPermitVerifier,
    create_narrative_delta,
    create_set_fact,
    run_migration,
)

from anovel.canon.commit_service import (
    CanonCommitService,
    CommitRequest,
    ExecutionPermit,
)
from anovel.canon.repository import CanonRepository, IdempotencyConflictError
from anovel.domain.delta import ExpectValue


def test_at_v2_011_01_same_key_same_payload_returns_original_receipt():
    """AT-V2-011-01: Same key + same payload returns original receipt.

    Verifies idempotent retry behavior:
    - First commit with key K and payload P succeeds
    - Retry with same key K and same payload P
    - Returns original receipt (same commit_id, committed_at)
    - recovered=True flag indicates idempotent recovery
    - No new commit created in database

    Implementation: CanonCommitService lines 204-235 (idempotency check first)
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = TestPermitVerifier()
        service = CanonCommitService(repo, verifier)

        try:
            with repo.transaction() as session:
                repo.create_project(session, "novel-project")
                repo.init_execution_control(session, "novel-project", "main")
                repo.create_root_commit(
                    session,
                    "novel-project",
                    "main",
                    "commit-root",
                    "idem-root",
                    "hash-root",
                    {"type": "root"},
                )
                repo.update_branch_head_cas(
                    session, "novel-project", "main", "commit-root", None
                )

            verifier.add_permit("permit-v2-011-01", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-v2-011-01",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            delta = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 18),
                ],
            )

            request = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-v2-011-01",
                narrative_delta=delta,
                permit=permit,
            )

            # First commit
            receipt1 = service.commit_narrative_delta(request)
            original_commit_id = receipt1.commit_id
            original_timestamp = receipt1.committed_at
            assert receipt1.recovered is False

            # Retry with same key + same payload
            receipt2 = service.commit_narrative_delta(request)

            # Verify idempotent recovery
            assert receipt2.commit_id == original_commit_id, "Different commit_id!"
            assert receipt2.committed_at == original_timestamp, "Timestamp changed!"
            assert receipt2.recovered is True, "recovered flag not set!"
            assert receipt2.idempotency_key == "idem-v2-011-01"

            # Verify no duplicate commit in database
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                          AND idempotency_key = :key
                    """),
                    {
                        "project_id": "novel-project",
                        "branch_name": "main",
                        "key": "idem-v2-011-01",
                    },
                )
                assert result.scalar() == 1, "Duplicate commit created!"

        finally:
            repo.close()


def test_at_v2_011_02_same_key_different_payload_conflict_and_concurrent_cas():
    """AT-V2-011-02: Same key + different payload raises conflict; concurrent CAS one succeeds.

    Part 1: Idempotency Conflict
    - First commit with key K and payload P1 succeeds
    - Second commit with same key K but different payload P2
    - Raises IdempotencyConflictError

    Part 2: Concurrent CAS (tested separately in Part B below)
    - Two concurrent writers with different idempotency keys
    - Both try to update same entity from same HEAD
    - Only one CAS succeeds, the other fails with CAS or precondition error

    Implementation: CanonCommitService lines 237-242 (conflict detection)
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = TestPermitVerifier()
        service = CanonCommitService(repo, verifier)

        try:
            with repo.transaction() as session:
                repo.create_project(session, "novel-project")
                repo.init_execution_control(session, "novel-project", "main")
                repo.create_root_commit(
                    session,
                    "novel-project",
                    "main",
                    "commit-root",
                    "idem-root",
                    "hash-root",
                    {"type": "root"},
                )
                repo.update_branch_head_cas(
                    session, "novel-project", "main", "commit-root", None
                )

            verifier.add_permit("permit-v2-011-02", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-v2-011-02",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # First commit: age 25
            delta1 = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-alex", "novel-project", "age", 25)],
            )

            request1 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-v2-011-02",
                narrative_delta=delta1,
                permit=permit,
            )

            receipt1 = service.commit_narrative_delta(request1)

            # Second commit: SAME key but DIFFERENT payload (age 26)
            delta2 = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-alex", "novel-project", "age", 26)],
            )

            request2 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id=receipt1.commit_id,
                idempotency_key="idem-v2-011-02",  # Same key!
                narrative_delta=delta2,
                permit=permit,
            )

            # Should raise IdempotencyConflictError
            with pytest.raises(IdempotencyConflictError) as exc_info:
                service.commit_narrative_delta(request2)
            assert "different payload" in str(exc_info.value)

        finally:
            repo.close()


def test_at_v2_011_02_part_b_concurrent_cas_only_one_succeeds():
    """AT-V2-011-02 Part B: Concurrent CAS with different keys - only one succeeds.

    Verifies concurrent write safety:
    - Setup: character age = 30
    - Writer A: tries to update age 30 -> 31 with ExpectValue(30)
    - Writer B: tries to update age 30 -> 32 with ExpectValue(30)
    - Both start at same time (threading.Barrier)
    - Only ONE succeeds (CAS winner)
    - The other fails with precondition or HEAD CAS error
    - Final state has exactly one commit, not contradictory state

    Implementation: CanonCommitService lines 329-342 (CAS atomicity)
    """
    import threading

    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = TestPermitVerifier()
        service = CanonCommitService(repo, verifier)

        try:
            with repo.transaction() as session:
                repo.create_project(session, "novel-project")
                repo.init_execution_control(session, "novel-project", "main")
                repo.create_root_commit(
                    session,
                    "novel-project",
                    "main",
                    "commit-root",
                    "idem-root",
                    "hash-root",
                    {"type": "root"},
                )
                repo.update_branch_head_cas(
                    session, "novel-project", "main", "commit-root", None
                )

            # Setup: create character with age=30
            verifier.add_permit("permit-setup", "novel-project", "main", 1)
            permit_setup = ExecutionPermit(
                permit_id="permit-setup",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            delta_setup = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-beth", "novel-project", "age", 30)],
            )

            request_setup = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-setup-v2-011",
                narrative_delta=delta_setup,
                permit=permit_setup,
            )

            receipt_setup = service.commit_narrative_delta(request_setup)

            # Concurrent writers
            verifier.add_permit("permit-writer-a", "novel-project", "main", 1)
            verifier.add_permit("permit-writer-b", "novel-project", "main", 1)

            results = {"a": None, "b": None}
            errors = {"a": None, "b": None}
            barrier = threading.Barrier(2)

            def writer_a():
                try:
                    repo_a = CanonRepository(env["ANOVELOS_TEST_DSN"])
                    service_a = CanonCommitService(repo_a, verifier)

                    permit_a = ExecutionPermit(
                        permit_id="permit-writer-a",
                        project_id="novel-project",
                        branch_name="main",
                        execution_version=1,
                        issued_at=datetime.now(),
                    )

                    delta_a = create_narrative_delta(
                        "novel-project",
                        [
                            create_set_fact(
                                "char-beth", "novel-project", "age", 31, ExpectValue(30)
                            )
                        ],
                    )

                    request_a = CommitRequest(
                        project_id="novel-project",
                        branch_name="main",
                        parent_commit_id=receipt_setup.commit_id,
                        idempotency_key="idem-writer-a-v2-011",
                        narrative_delta=delta_a,
                        permit=permit_a,
                    )

                    barrier.wait(timeout=5)
                    results["a"] = service_a.commit_narrative_delta(request_a)
                    repo_a.close()
                except Exception as e:
                    errors["a"] = e

            def writer_b():
                try:
                    repo_b = CanonRepository(env["ANOVELOS_TEST_DSN"])
                    service_b = CanonCommitService(repo_b, verifier)

                    permit_b = ExecutionPermit(
                        permit_id="permit-writer-b",
                        project_id="novel-project",
                        branch_name="main",
                        execution_version=1,
                        issued_at=datetime.now(),
                    )

                    delta_b = create_narrative_delta(
                        "novel-project",
                        [
                            create_set_fact(
                                "char-beth", "novel-project", "age", 32, ExpectValue(30)
                            )
                        ],
                    )

                    request_b = CommitRequest(
                        project_id="novel-project",
                        branch_name="main",
                        parent_commit_id=receipt_setup.commit_id,
                        idempotency_key="idem-writer-b-v2-011",
                        narrative_delta=delta_b,
                        permit=permit_b,
                    )

                    barrier.wait(timeout=5)
                    results["b"] = service_b.commit_narrative_delta(request_b)
                    repo_b.close()
                except Exception as e:
                    errors["b"] = e

            thread_a = threading.Thread(target=writer_a)
            thread_b = threading.Thread(target=writer_b)

            thread_a.start()
            thread_b.start()

            thread_a.join(timeout=10)
            thread_b.join(timeout=10)

            # Verify: exactly one succeeded, one failed
            success_count = sum(1 for r in results.values() if r is not None)
            error_count = sum(1 for e in errors.values() if e is not None)

            assert success_count == 1, f"Expected 1 success, got {success_count}"
            assert error_count == 1, f"Expected 1 error, got {error_count}"

            # Verify final state: exactly 2 commits (root + setup), no contradictory state
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE project_id = 'novel-project'
                          AND branch_name = 'main'
                    """)
                )
                # root + setup + winner = 3 commits
                assert result.scalar() == 3

        finally:
            repo.close()


def test_at_v2_011_03_commit_success_response_loss_no_duplicate():
    """AT-V2-011-03: Commit succeeds but response lost - retry doesn't create duplicate.

    Simulates network failure after commit success but before client receives receipt:
    - First commit succeeds, receipt returned
    - Caller simulates response loss (doesn't save receipt)
    - Retry with identical request (same key + same payload)
    - Returns original receipt with recovered=True
    - No duplicate commit created
    - No duplicate event created
    - Original commit still accessible

    Implementation: CanonCommitService lines 221-235 (idempotent recovery path)
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = TestPermitVerifier()
        service = CanonCommitService(repo, verifier)

        try:
            with repo.transaction() as session:
                repo.create_project(session, "novel-project")
                repo.init_execution_control(session, "novel-project", "main")
                repo.create_root_commit(
                    session,
                    "novel-project",
                    "main",
                    "commit-root",
                    "idem-root",
                    "hash-root",
                    {"type": "root"},
                )
                repo.update_branch_head_cas(
                    session, "novel-project", "main", "commit-root", None
                )

            verifier.add_permit("permit-v2-011-03", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-v2-011-03",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            delta = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-cindy", "novel-project", "name", "辛迪"),
                    create_set_fact("char-cindy", "novel-project", "age", 22),
                ],
            )

            request = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-v2-011-03",
                narrative_delta=delta,
                permit=permit,
            )

            # First attempt: commit succeeds
            receipt1 = service.commit_narrative_delta(request)
            original_commit_id = receipt1.commit_id
            original_timestamp = receipt1.committed_at
            assert receipt1.recovered is False

            # Simulate response loss: caller doesn't receive/save receipt
            # Network failure after commit, before client processes response

            # Retry with identical request
            receipt2 = service.commit_narrative_delta(request)

            # Verify idempotent recovery
            assert receipt2.commit_id == original_commit_id, "Different commit_id!"
            assert receipt2.committed_at == original_timestamp, "Timestamp changed!"
            assert receipt2.recovered is True, "recovered flag not set!"
            assert receipt2.idempotency_key == "idem-v2-011-03"

            # Verify no duplicate commit
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                          AND idempotency_key = :key
                    """),
                    {
                        "project_id": "novel-project",
                        "branch_name": "main",
                        "key": "idem-v2-011-03",
                    },
                )
                assert result.scalar() == 1, "Duplicate commit created!"

                # Verify no duplicate event
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_event
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                          AND commit_id = :commit_id
                    """),
                    {
                        "project_id": "novel-project",
                        "branch_name": "main",
                        "commit_id": original_commit_id,
                    },
                )
                assert result.scalar() == 1, "Duplicate event created!"

                # Verify original commit still accessible
                result = session.execute(
                    text("""
                        SELECT changeset FROM canon_commit
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                          AND commit_id = :commit_id
                    """),
                    {
                        "project_id": "novel-project",
                        "branch_name": "main",
                        "commit_id": original_commit_id,
                    },
                )
                changeset = result.scalar()
                assert changeset is not None
                assert "辛迪" in str(changeset)

        finally:
            repo.close()
