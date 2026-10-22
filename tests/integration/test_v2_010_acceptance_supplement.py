"""V2-010 Acceptance Test Supplements for AT-V2-010-03, 04, 05.

Supplementary tests to complete V2-010 acceptance coverage per test-catalog.yaml.

These tests verify:
- AT-V2-010-03: Long-term commit evidence retrieval (not just hash)
- AT-V2-010-04: In-place replacement rejection and historical preservation
- AT-V2-010-05: Response loss retry deduplication

All tests use real PostgreSQL 17.11 (no mocks).
"""

import hashlib
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from test_postgres_environment import postgres

from anovel.canon.commit_service import (
    CanonCommitService,
    CommitRequest,
    ExecutionPermit,
)
from anovel.canon.repository import (
    CanonRepository,
    IdempotencyConflictError,
)
from anovel.domain.delta import (
    DeltaId,
    EvidenceRef,
    ExpectAbsent,
    ExpectValue,
    NarrativeDelta,
    SetFactOperation,
    get_fact_path,
)
from anovel.domain.identity import EntityId, ProjectId

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


class TestPermitVerifier:
    """Test implementation of PermitVerifier for integration testing."""

    def __init__(self):
        self.allowed_permits: dict[str, dict[str, any]] = {}

    def add_permit(
        self, permit_id: str, project_id: str, branch_name: str, execution_version: int
    ):
        """Add valid permit to allowed list."""
        self.allowed_permits[permit_id] = {
            "project_id": project_id,
            "branch_name": branch_name,
            "execution_version": execution_version,
        }

    def verify_permit(
        self, permit_id: str, project_id: str, branch_name: str, execution_version: int
    ) -> bool:
        """Verify permit is valid for given scope."""
        from anovel.canon.commit_service import NoPermitError

        if permit_id not in self.allowed_permits:
            raise NoPermitError(f"Permit {permit_id} not found in allowed list")

        permit_data = self.allowed_permits[permit_id]
        if permit_data["project_id"] != project_id:
            raise NoPermitError("Permit project mismatch")
        if permit_data["branch_name"] != branch_name:
            raise NoPermitError("Permit branch mismatch")
        if permit_data["execution_version"] != execution_version:
            raise NoPermitError("Permit execution version mismatch")

        return True


def create_evidence(text: str) -> EvidenceRef:
    """Create EvidenceRef with proper SHA-256 hash."""
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return EvidenceRef(
        source_type="TEXT",
        source_ref=f"test:evidence:{uuid.uuid4().hex[:8]}",
        content_hash=content_hash,
    )


def create_set_fact(
    entity_id: str, project_id: str, fact_path: str, value: any, precondition=None
) -> SetFactOperation:
    """Helper to create SetFactOperation with proper domain types."""
    if precondition is None:
        precondition = ExpectAbsent()

    return SetFactOperation(
        subject=EntityId(entity_id),
        scope=ProjectId(project_id),
        path=get_fact_path(fact_path),
        value=value,
        precondition=precondition,
        evidence=create_evidence(f"{entity_id}:{fact_path}:{value}"),
    )


def create_narrative_delta(project_id: str, operations: list) -> NarrativeDelta:
    """Helper to create NarrativeDelta with proper structure."""
    return NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId(project_id),
        operations=tuple(operations),
        source_chapter=None,
        created_at=datetime.now(),
        authority="test:authority",
        provenance=(("test", "integration"),),
    )


def test_at_v2_010_03_long_term_commit_evidence_retrieval():
    """AT-V2-010-03: Long-term commit evidence retrieval with full changeset.

    Verifies:
    - Multiple chapter commits with Chinese content
    - Service restart
    - Full changeset retrieval (not just hash)
    - NarrativeDelta structure preserved
    - Chinese characters preserved
    - All operations, evidence, preconditions accessible
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        # First session: commit multiple chapters
        repo1 = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier1 = TestPermitVerifier()
        service1 = CanonCommitService(repo1, verifier1)

        commit_ids = []

        try:
            with repo1.transaction() as session:
                repo1.create_project(session, "novel-project")
                repo1.init_execution_control(session, "novel-project", "main")
                repo1.create_root_commit(
                    session,
                    "novel-project",
                    "main",
                    "commit-root",
                    "idem-root",
                    "hash-root",
                    {"type": "root"},
                )
                repo1.update_branch_head_cas(
                    session, "novel-project", "main", "commit-root", None
                )

            verifier1.add_permit("permit-chapters", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-chapters",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # Chapter 1: 主角林舟初入江湖
            delta1 = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 18),
                    create_set_fact("char-linzhou", "novel-project", "description", "炼气初期修士"),
                    create_set_fact("location-qingfeng", "novel-project", "name", "青枫镇"),
                ],
            )

            request1 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="test-key-alpha",
                narrative_delta=delta1,
                permit=permit,
            )

            receipt1 = service1.commit_narrative_delta(request1)
            commit_ids.append(("chapter-001", receipt1.commit_id, "test-key-alpha"))

            # Chapter 2: 林舟突破境界
            delta2 = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact(
                        "char-linzhou",
                        "novel-project",
                        "description",
                        "炼气后期修士",
                        precondition=ExpectValue("炼气初期修士"),
                    ),
                    create_set_fact("char-linzhou", "novel-project", "age", 19, ExpectValue(18)),
                ],
            )

            request2 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id=receipt1.commit_id,
                idempotency_key="test-key-beta",
                narrative_delta=delta2,
                permit=permit,
            )

            receipt2 = service1.commit_narrative_delta(request2)
            commit_ids.append(("chapter-002", receipt2.commit_id, "test-key-beta"))

        finally:
            repo1.close()

        # Simulated restart: new repository instance
        repo2 = CanonRepository(env["ANOVELOS_TEST_DSN"])

        try:
            with repo2.transaction() as session:
                # Retrieve chapter 1 commit
                commit1 = repo2.get_commit(session, "novel-project", "main", commit_ids[0][1])
                assert commit1 is not None, "Chapter 1 commit not found"

                # Verify full changeset structure (not just hash)
                import json

                changeset1 = commit1["changeset"]
                if isinstance(changeset1, str):
                    changeset1 = json.loads(changeset1)

                # Verify NarrativeDelta structure preserved
                assert "project_id" in changeset1
                assert changeset1["project_id"] == "novel-project"
                assert "operations" in changeset1
                assert len(changeset1["operations"]) == 4

                # Verify Chinese characters preserved in all operations
                name_op = next(
                    op for op in changeset1["operations"] if op["path"]["path"] == "name" and op["subject"] == "char-linzhou"
                )
                assert name_op["value"] == "林舟", "Chinese character name not preserved"

                description_op = next(
                    op for op in changeset1["operations"] if op["path"]["path"] == "description" and op["subject"] == "char-linzhou"
                )
                assert description_op["value"] == "炼气初期修士", "Chinese description not preserved"

                location_op = next(
                    op for op in changeset1["operations"] if op["subject"] == "location-qingfeng"
                )
                assert location_op["value"] == "青枫镇", "Chinese location name not preserved"

                # Verify evidence preserved
                assert "evidence" in name_op
                assert name_op["evidence"]["source_type"] == "TEXT"
                assert len(name_op["evidence"]["content_hash"]) == 64  # SHA-256

                # Verify precondition structure
                assert name_op["precondition"]["type"] == "ExpectAbsent"

                # Retrieve chapter 2 commit
                commit2 = repo2.get_commit(session, "novel-project", "main", commit_ids[1][1])
                assert commit2 is not None, "Chapter 2 commit not found"

                changeset2 = commit2["changeset"]
                if isinstance(changeset2, str):
                    changeset2 = json.loads(changeset2)

                # Verify state change preconditions preserved
                description_update = next(
                    op for op in changeset2["operations"] if op["path"]["path"] == "description"
                )
                assert description_update["value"] == "炼气后期修士"
                assert description_update["precondition"]["type"] == "ExpectValue"
                assert description_update["precondition"]["expected_value"] == "炼气初期修士"

                # Verify parent chain
                assert commit2["parent_commit_id"] == commit_ids[0][1]

        finally:
            repo2.close()


def test_at_v2_010_04_in_place_replacement_rejection():
    """AT-V2-010-04: In-place replacement of accepted content is rejected.

    Verifies:
    - Accepted commit with idempotency key
    - Attempt to modify with same key but different payload
    - IdempotencyConflictError raised
    - Original commit unchanged
    - Historical changeset preserved
    - No corruption of accepted narrative
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

            verifier.add_permit("permit-test", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-test",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # Original accepted chapter: 林舟年龄 25
            delta_original = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 25),
                    create_set_fact("char-linzhou", "novel-project", "is_alive", True),
                ],
            )

            request_original = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-chapter-final",
                narrative_delta=delta_original,
                permit=permit,
            )

            receipt_original = service.commit_narrative_delta(request_original)
            original_commit_id = receipt_original.commit_id

            # Store original changeset for later verification
            with repo.transaction() as session:
                original_commit = repo.get_commit(
                    session, "novel-project", "main", original_commit_id
                )
                import json

                original_changeset = original_commit["changeset"]
                if isinstance(original_changeset, str):
                    original_changeset = json.loads(original_changeset)

            # Attempt in-place replacement with SAME key but DIFFERENT content
            delta_modified = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 30),  # Changed!
                    create_set_fact("char-linzhou", "novel-project", "is_alive", False),  # Changed!
                ],
            )

            request_modified = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-chapter-final",  # SAME KEY!
                narrative_delta=delta_modified,
                permit=permit,
            )

            # Should raise IdempotencyConflictError
            with pytest.raises(IdempotencyConflictError) as exc_info:
                service.commit_narrative_delta(request_modified)

            assert "different payload" in str(exc_info.value)
            assert "idem-chapter-final" in str(exc_info.value)

            # Verify original commit UNCHANGED
            with repo.transaction() as session:
                current_commit = repo.get_commit(
                    session, "novel-project", "main", original_commit_id
                )
                current_changeset = current_commit["changeset"]
                if isinstance(current_changeset, str):
                    current_changeset = json.loads(current_changeset)

                # Verify age still 25 (not 30)
                age_op = next(
                    op for op in current_changeset["operations"] if op["path"]["path"] == "age"
                )
                assert age_op["value"] == 25, "Original age was modified!"

                # Verify is_alive still True (not False)
                is_alive_op = next(
                    op for op in current_changeset["operations"] if op["path"]["path"] == "is_alive"
                )
                assert is_alive_op["value"] is True, "Original is_alive was modified!"

                # Verify no new commit created with modified content
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
                        "key": "idem-chapter-final",
                    },
                )
                assert result.scalar() == 1, "Multiple commits with same idempotency key!"

        finally:
            repo.close()


def test_at_v2_010_05_response_loss_retry_no_duplicate():
    """AT-V2-010-05: Response loss retry does not create duplicate commits.

    Verifies:
    - Commit succeeds, receipt obtained
    - Simulate response loss (caller doesn't save receipt)
    - Retry with same key+payload
    - Returns original receipt (recovered=True)
    - No duplicate commit created
    - Cancel-after-commit: old receipt still recoverable
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

            verifier.add_permit("permit-retry", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-retry",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # Chapter commit
            delta = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 20),
                ],
            )

            request = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-chapter-retry-test",
                narrative_delta=delta,
                permit=permit,
            )

            # First attempt: succeeds, but caller loses response
            receipt1 = service.commit_narrative_delta(request)
            original_commit_id = receipt1.commit_id
            original_timestamp = receipt1.committed_at
            assert receipt1.recovered is False

            # Simulate response loss: caller doesn't know commit succeeded
            # Retry with identical request
            receipt2 = service.commit_narrative_delta(request)

            # Verify idempotent recovery
            assert receipt2.commit_id == original_commit_id, "Different commit ID returned!"
            assert receipt2.idempotency_key == "idem-chapter-retry-test"
            assert receipt2.committed_at == original_timestamp, "Timestamp changed!"
            assert receipt2.recovered is True, "recovered flag not set!"

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
                        "key": "idem-chapter-retry-test",
                    },
                )
                assert result.scalar() == 1, "Duplicate commit created!"

                # Verify only one event
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_event
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                    """),
                    {"project_id": "novel-project", "branch_name": "main"},
                )
                assert result.scalar() == 1, "Duplicate event created!"

            # Cancel execution (simulate workflow cancellation)
            with repo.transaction() as session:
                new_version = repo.cancel_execution(session, "novel-project", "main")
                assert new_version == 2

            # After cancel: old receipt STILL recoverable
            verifier.add_permit("permit-retry-2", "novel-project", "main", 2)
            permit2 = ExecutionPermit(
                permit_id="permit-retry-2",
                project_id="novel-project",
                branch_name="main",
                execution_version=2,
                issued_at=datetime.now(),
            )

            request_after_cancel = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-chapter-retry-test",  # Same key
                narrative_delta=delta,  # Same payload
                permit=permit2,
            )

            receipt3 = service.commit_narrative_delta(request_after_cancel)
            assert receipt3.commit_id == original_commit_id, "Cancel corrupted receipt recovery!"
            assert receipt3.recovered is True
            assert receipt3.committed_at == original_timestamp

        finally:
            repo.close()
