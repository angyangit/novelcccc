"""V2-010 CanonCommitService integration tests.

Tests unified business service for Canon narrative commits with real PostgreSQL.

Test coverage:
- AT-V2-010-01: No permit rejection
- AT-V2-010-02: Valid narrative delta commits successfully
- AT-V2-010-03: Commit + Event + HEAD atomic consistency
- AT-V2-010-04: CAS conflict triggers full rollback
- AT-V2-010-05: Idempotent receipt recovery after success
- AT-V2-010-06: Same key different payload rejection
- AT-V2-010-07: Character creation persists and rebuilds
- AT-V2-010-08: Character state change with precondition
- AT-V2-010-09: Service restart recovery

All tests use real PostgreSQL 17.11 (no mocks).
"""

import hashlib
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from test_postgres_environment import postgres

from anovel.canon.commit_service import (
    CanonCommitService,
    CommitReceipt,
    CommitRequest,
    ExecutionPermit,
    InvalidDeltaError,
    NoPermitError,
    PermitVerifier,
)
from anovel.canon.repository import (
    CanonRepository,
    CanonRepositoryError,
    IdempotencyConflictError,
)
from anovel.domain.delta import (
    DeltaId,
    EvidenceRef,
    ExpectAbsent,
    ExpectValue,
    FactPath,
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
    """Test implementation of PermitVerifier for integration testing.

    Fail-closed: only permits explicitly added to allowed_permits pass verification.
    """

    def __init__(self):
        self.allowed_permits: dict[str, dict[str, Any]] = {}

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
    entity_id: str, project_id: str, fact_path: str, value: Any, precondition=None
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


def test_at_v2_010_01_no_permit_rejects_commit():
    """AT-V2-010-01: Commit rejected without valid permit.

    Verifies:
    - Invalid permit raises NoPermitError
    - No commit created in database
    - No event created
    - HEAD unchanged
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = TestPermitVerifier()
        service = CanonCommitService(repo, verifier)

        try:
            # Setup project and execution control
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
                repo.update_branch_head_cas(
                    session, "test-project", "main", "commit-root", None
                )

            # Create permit but don't add to verifier (not trusted)
            untrusted_permit = ExecutionPermit(
                permit_id="permit-untrusted",
                project_id="test-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # Create delta
            delta = create_narrative_delta(
                "test-project",
                [create_set_fact("char-1", "test-project", "name", "Alice")],
            )

            request = CommitRequest(
                project_id="test-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-test-1",
                narrative_delta=delta,
                permit=untrusted_permit,
            )

            # Attempt commit with untrusted permit
            with pytest.raises(NoPermitError, match="not found in allowed list"):
                service.commit_narrative_delta(request)

            # Verify no commit created
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE project_id = 'test-project'
                          AND idempotency_key = 'idem-test-1'
                    """)
                )
                assert result.scalar() == 0

                # Verify HEAD unchanged
                head = repo.get_branch_head(session, "test-project", "main")
                assert head == "commit-root"

        finally:
            repo.close()


def test_at_v2_010_07_character_creation_persists_and_rebuilds():
    """AT-V2-010-07: Character "林舟, 25岁" persists with all facts.

    Verifies:
    - Character name, age, is_alive persist correctly
    - Commit contains complete operation data
    - Subject, scope, path, value, precondition, evidence all preserved
    - Data retrievable after commit
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = TestPermitVerifier()
        service = CanonCommitService(repo, verifier)

        try:
            # Setup
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

            # Add trusted permit
            verifier.add_permit("permit-character", "novel-project", "main", 1)

            permit = ExecutionPermit(
                permit_id="permit-character",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # Create character "林舟" with age 25
            delta = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 25),
                    create_set_fact("char-linzhou", "novel-project", "is_alive", True),
                ],
            )

            request = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-create-linzhou",
                narrative_delta=delta,
                permit=permit,
            )

            # Commit character creation
            receipt = service.commit_narrative_delta(request)
            assert receipt.recovered is False

            # Verify complete persistence
            with repo.transaction() as session:
                commit = repo.get_commit(
                    session, "novel-project", "main", receipt.commit_id
                )
                assert commit is not None

                # Parse changeset (handle both string and dict)
                import json

                changeset = commit["changeset"]
                if isinstance(changeset, str):
                    changeset = json.loads(changeset)

                # Verify delta structure
                assert changeset["project_id"] == "novel-project"
                assert changeset["authority"] == "test:authority"
                assert len(changeset["operations"]) == 3

                # Verify name operation preserves all fields
                name_op = next(
                    op for op in changeset["operations"] if op["path"]["path"] == "name"
                )
                assert name_op["subject"] == "char-linzhou"
                assert name_op["scope"] == "novel-project"
                assert name_op["value"] == "林舟"  # Chinese characters preserved!
                assert name_op["precondition"]["type"] == "ExpectAbsent"
                assert name_op["evidence"]["source_type"] == "TEXT"
                assert len(name_op["evidence"]["content_hash"]) == 64

                # Verify age operation
                age_op = next(
                    op for op in changeset["operations"] if op["path"]["path"] == "age"
                )
                assert age_op["value"] == 25
                assert age_op["path"]["expected_type"] == "int"

                # Verify is_alive operation
                alive_op = next(
                    op
                    for op in changeset["operations"]
                    if op["path"]["path"] == "is_alive"
                )
                assert alive_op["value"] is True
                assert alive_op["path"]["expected_type"] == "bool"

        finally:
            repo.close()


def test_at_v2_010_08_character_state_change_with_precondition():
    """AT-V2-010-08: Update character age from 25 to 26 with ExpectValue precondition.

    Verifies:
    - State changes use proper preconditions
    - Parent commit chain preserved
    - Both commits retrievable
    - Facts evolve correctly
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = TestPermitVerifier()
        service = CanonCommitService(repo, verifier)

        try:
            # Setup
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

            # Add permit
            verifier.add_permit("permit-char", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-char",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # Create character with age 25
            delta1 = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 25),
                ],
            )

            request1 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-create",
                narrative_delta=delta1,
                permit=permit,
            )

            receipt1 = service.commit_narrative_delta(request1)

            # Update age to 26 with ExpectValue(25) precondition
            delta2 = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact(
                        "char-linzhou",
                        "novel-project",
                        "age",
                        26,
                        precondition=ExpectValue(25),
                    )
                ],
            )

            request2 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id=receipt1.commit_id,
                idempotency_key="idem-update-age",
                narrative_delta=delta2,
                permit=permit,
            )

            receipt2 = service.commit_narrative_delta(request2)

            # Verify both commits exist with proper parent chain
            with repo.transaction() as session:
                commit1 = repo.get_commit(
                    session, "novel-project", "main", receipt1.commit_id
                )
                commit2 = repo.get_commit(
                    session, "novel-project", "main", receipt2.commit_id
                )

                assert commit1["parent_commit_id"] == "commit-root"
                assert commit2["parent_commit_id"] == receipt1.commit_id

                # Verify age change preserved
                import json

                changeset2 = commit2["changeset"]
                if isinstance(changeset2, str):
                    changeset2 = json.loads(changeset2)
                age_op = changeset2["operations"][0]
                assert age_op["value"] == 26
                assert age_op["precondition"]["type"] == "ExpectValue"
                assert age_op["precondition"]["expected_value"] == 25

        finally:
            repo.close()


def test_at_v2_010_09_service_restart_recovery():
    """AT-V2-010-09: Service restart and historical data recovery.

    Verifies:
    - Close repository and service
    - Create new instances (simulated restart)
    - Retrieve all historical commits
    - All character facts preserved
    - Parent chain intact
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        # First session: create commits
        repo1 = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier1 = TestPermitVerifier()
        service1 = CanonCommitService(repo1, verifier1)

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

            verifier1.add_permit("permit-1", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-1",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            delta = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 25),
                ],
            )

            request = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-linzhou",
                narrative_delta=delta,
                permit=permit,
            )

            receipt = service1.commit_narrative_delta(request)
            commit_id_to_recover = receipt.commit_id

        finally:
            repo1.close()

        # Simulated restart: new repository and service instances
        repo2 = CanonRepository(env["ANOVELOS_TEST_DSN"])

        try:
            with repo2.transaction() as session:
                # Recover historical commit
                commit = repo2.get_commit(
                    session, "novel-project", "main", commit_id_to_recover
                )
                assert commit is not None

                # Verify all character facts preserved
                import json

                changeset = commit["changeset"]
                if isinstance(changeset, str):
                    changeset = json.loads(changeset)
                assert changeset["project_id"] == "novel-project"

                name_op = next(
                    op for op in changeset["operations"] if op["path"]["path"] == "name"
                )
                assert name_op["value"] == "林舟"

                age_op = next(
                    op for op in changeset["operations"] if op["path"]["path"] == "age"
                )
                assert age_op["value"] == 25

        finally:
            repo2.close()


def test_at_v2_010_10_invalid_precondition_rejection():
    """AT-V2-010-10: Invalid precondition causes commit rejection.

    Verifies:
    - Create character with age=25
    - Update age to 26 (valid: precondition ExpectValue(25))
    - Try to update age to 27 with ExpectValue(25) → REJECT
    - Verify database unchanged (no new commit, no new event, HEAD unchanged)
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

            # Commit 1: Create character with age=25
            delta1 = create_narrative_delta(
                project_id="novel-project",
                operations=[
                    create_set_fact("char-linzhou", "novel-project", "name", "林舟"),
                    create_set_fact("char-linzhou", "novel-project", "age", 25),
                ],
            )

            verifier.add_permit("permit-test", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-test",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            request1 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-create-linzhou",
                narrative_delta=delta1,
                permit=permit,
            )

            receipt1 = service.commit_narrative_delta(request1)
            assert receipt1.commit_id is not None

            # Commit 2: Update age to 26 (valid precondition)
            delta2 = create_narrative_delta(
                project_id="novel-project",
                operations=[
                    create_set_fact(
                        "char-linzhou", "novel-project", "age", 26, ExpectValue(25)
                    ),
                ],
            )

            request2 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id=receipt1.commit_id,
                idempotency_key="idem-update-age-26",
                narrative_delta=delta2,
                permit=permit,
            )

            receipt2 = service.commit_narrative_delta(request2)
            assert receipt2.commit_id is not None

            # Get HEAD before invalid attempt
            with repo.transaction() as session:
                head_before = repo.get_branch_head(session, "novel-project", "main")
                assert head_before == receipt2.commit_id

            # Commit 3: Try to update age to 27 with WRONG precondition (expects 25 but current is 26)
            delta3 = create_narrative_delta(
                project_id="novel-project",
                operations=[
                    create_set_fact(
                        "char-linzhou", "novel-project", "age", 27, ExpectValue(25)
                    ),
                ],
            )

            request3 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id=receipt2.commit_id,
                idempotency_key="idem-update-age-27-invalid",
                narrative_delta=delta3,
                permit=permit,
            )

            # This should raise InvalidDeltaError
            with pytest.raises(InvalidDeltaError) as exc_info:
                service.commit_narrative_delta(request3)

            assert "precondition" in str(exc_info.value).lower()

            # Verify database unchanged
            with repo.transaction() as session:
                head_after = repo.get_branch_head(session, "novel-project", "main")
                assert head_after == receipt2.commit_id  # HEAD unchanged

                # Verify no commit with idempotency_key "idem-update-age-27-invalid"
                result = session.execute(
                    text("""
                        SELECT commit_id FROM canon_commit
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                          AND idempotency_key = :idempotency_key
                    """),
                    {
                        "project_id": "novel-project",
                        "branch_name": "main",
                        "idempotency_key": "idem-update-age-27-invalid",
                    },
                )
                assert result.fetchone() is None  # No commit created

        finally:
            repo.close()


def test_at_v2_010_02_valid_permit_and_delta_succeeds():
    """AT-V2-010-02: Valid permit and legal NarrativeDelta commits successfully.

    Verifies:
    - Valid permit passes verification
    - Legal NarrativeDelta with proper operations
    - Commit created with all fields preserved
    - Event created
    - HEAD advanced
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

            # Create valid permit
            verifier.add_permit("permit-valid", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-valid",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # Create valid delta
            delta = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-alice", "novel-project", "name", "Alice"),
                    create_set_fact("char-alice", "novel-project", "age", 30),
                ],
            )

            request = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-valid-commit",
                narrative_delta=delta,
                permit=permit,
            )

            # Commit should succeed
            receipt = service.commit_narrative_delta(request)
            assert receipt.commit_id is not None
            assert receipt.recovered is False

            # Verify commit exists
            with repo.transaction() as session:
                commit = repo.get_commit(
                    session, "novel-project", "main", receipt.commit_id
                )
                assert commit is not None
                assert commit["idempotency_key"] == "idem-valid-commit"

                # Verify event exists
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
                        "commit_id": receipt.commit_id,
                    },
                )
                assert result.scalar() == 1

                # Verify HEAD advanced
                head = repo.get_branch_head(session, "novel-project", "main")
                assert head == receipt.commit_id

        finally:
            repo.close()


def test_at_v2_010_03_atomic_commit_event_head():
    """AT-V2-010-03: Commit + Event + HEAD are atomic.

    Verifies:
    - All three operations succeed together
    - If any fails, all rollback (tested via HEAD CAS failure)
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

            verifier.add_permit("permit-atomic", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-atomic",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # First commit succeeds
            delta1 = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-bob", "novel-project", "name", "Bob")],
            )

            request1 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-atomic-1",
                narrative_delta=delta1,
                permit=permit,
            )

            receipt1 = service.commit_narrative_delta(request1)
            assert receipt1.commit_id is not None

            # Second commit with WRONG parent (should fail HEAD CAS)
            delta2 = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-charlie", "novel-project", "name", "Charlie")],
            )

            request2 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",  # Wrong! HEAD is now receipt1.commit_id
                idempotency_key="idem-atomic-2",
                narrative_delta=delta2,
                permit=permit,
            )

            # Should fail with CanonRepositoryError (parent mismatch or HEAD CAS failed)
            with pytest.raises(CanonRepositoryError) as exc_info:
                service.commit_narrative_delta(request2)
            assert "mismatch" in str(exc_info.value).lower() or "CAS" in str(
                exc_info.value
            )

            # Verify no partial write: commit should not exist
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                          AND idempotency_key = :idempotency_key
                    """),
                    {
                        "project_id": "novel-project",
                        "branch_name": "main",
                        "idempotency_key": "idem-atomic-2",
                    },
                )
                assert result.scalar() == 0

                # Verify no event created
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_event
                        WHERE project_id = :project_id
                          AND branch_name = :branch_name
                          AND event_type = 'NARRATIVE_COMMIT'
                    """),
                    {
                        "project_id": "novel-project",
                        "branch_name": "main",
                    },
                )
                assert result.scalar() == 1  # Only first commit's event

                # Verify HEAD unchanged
                head = repo.get_branch_head(session, "novel-project", "main")
                assert head == receipt1.commit_id

        finally:
            repo.close()


def test_at_v2_010_04_cas_conflict_rollback():
    """AT-V2-010-04: CAS conflict triggers full rollback.

    Verifies:
    - Concurrent modification detected via HEAD CAS
    - No partial writes left in database
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

            verifier.add_permit("permit-cas", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-cas",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # First commit
            delta1 = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-dave", "novel-project", "age", 40)],
            )

            request1 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-cas-1",
                narrative_delta=delta1,
                permit=permit,
            )

            receipt1 = service.commit_narrative_delta(request1)

            # Attempt commit with stale parent
            delta2 = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-eve", "novel-project", "age", 35)],
            )

            request2 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",  # Stale
                idempotency_key="idem-cas-2",
                narrative_delta=delta2,
                permit=permit,
            )

            # Should fail
            with pytest.raises(CanonRepositoryError):
                service.commit_narrative_delta(request2)

            # Verify clean rollback: no commit, no event
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE idempotency_key = :key
                    """),
                    {"key": "idem-cas-2"},
                )
                assert result.scalar() == 0

                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_event
                        WHERE project_id = :project_id
                    """),
                    {"project_id": "novel-project"},
                )
                assert result.scalar() == 1  # Only first commit

        finally:
            repo.close()


def test_at_v2_010_05_idempotent_recovery_after_state_change():
    """AT-V2-010-05: Idempotent receipt recovery works even after state changes.

    Verifies:
    - Original commit succeeds
    - State changes (new commits)
    - Retry with same key+payload recovers original receipt
    - Does NOT re-validate with new state
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

            verifier.add_permit("permit-idem", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-idem",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # First commit: age 25 -> 26
            delta1 = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact("char-frank", "novel-project", "age", 25),
                ],
            )

            request1 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-first",
                narrative_delta=delta1,
                permit=permit,
            )

            receipt1 = service.commit_narrative_delta(request1)
            original_commit_id = receipt1.commit_id
            original_timestamp = receipt1.committed_at

            # Second commit: age 25 -> 26 with ExpectValue(25)
            delta2 = create_narrative_delta(
                "novel-project",
                [
                    create_set_fact(
                        "char-frank", "novel-project", "age", 26, ExpectValue(25)
                    ),
                ],
            )

            request2 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id=receipt1.commit_id,
                idempotency_key="idem-second",
                narrative_delta=delta2,
                permit=permit,
            )

            receipt2 = service.commit_narrative_delta(request2)

            # Now age is 26. Retry request2 with same key+payload
            # This should recover the original receipt WITHOUT re-validating
            # (If it re-validated, ExpectValue(25) would fail because age is now 26)
            request2_retry = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id=receipt1.commit_id,  # Same as original
                idempotency_key="idem-second",  # Same key
                narrative_delta=delta2,  # Same payload
                permit=permit,
            )

            receipt2_retry = service.commit_narrative_delta(request2_retry)

            # Verify recovery
            assert receipt2_retry.commit_id == receipt2.commit_id
            assert receipt2_retry.recovered is True
            assert receipt2_retry.committed_at == receipt2.committed_at

            # Verify no duplicate commit
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE idempotency_key = :key
                    """),
                    {"key": "idem-second"},
                )
                assert result.scalar() == 1

        finally:
            repo.close()


def test_at_v2_010_06_same_key_different_payload_rejects():
    """AT-V2-010-06: Same key with different payload is rejected.

    Verifies:
    - First commit succeeds
    - Retry with same key but different payload raises IdempotencyConflictError
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

            verifier.add_permit("permit-conflict", "novel-project", "main", 1)
            permit = ExecutionPermit(
                permit_id="permit-conflict",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.now(),
            )

            # First commit
            delta1 = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-grace", "novel-project", "age", 28)],
            )

            request1 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-conflict-key",
                narrative_delta=delta1,
                permit=permit,
            )

            receipt1 = service.commit_narrative_delta(request1)

            # Second commit with SAME key but DIFFERENT payload
            delta2 = create_narrative_delta(
                "novel-project",
                [create_set_fact("char-grace", "novel-project", "age", 29)],  # Different!
            )

            request2 = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id=receipt1.commit_id,
                idempotency_key="idem-conflict-key",  # Same key!
                narrative_delta=delta2,
                permit=permit,
            )

            # Should raise IdempotencyConflictError
            from anovel.canon.repository import IdempotencyConflictError

            with pytest.raises(IdempotencyConflictError) as exc_info:
                service.commit_narrative_delta(request2)
            assert "different payload" in str(exc_info.value)

        finally:
            repo.close()


def test_at_v2_010_11_concurrent_writes_race():
    """AT-V2-010-11: Concurrent writes with same precondition - only one succeeds.

    Verifies:
    - Two writers both read age=25
    - Both try to update with ExpectValue(25)
    - Only ONE can succeed (single transaction protocol)
    - The other gets precondition or HEAD CAS failure
    - No contradictory state in database
    """
    import threading
    import time

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

            # Create character with age=25
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
                [create_set_fact("char-henry", "novel-project", "age", 25)],
            )

            request_setup = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-setup",
                narrative_delta=delta_setup,
                permit=permit_setup,
            )

            receipt_setup = service.commit_narrative_delta(request_setup)

            # Now two writers will try to update age concurrently
            verifier.add_permit("permit-writer-a", "novel-project", "main", 1)
            verifier.add_permit("permit-writer-b", "novel-project", "main", 1)

            results = {"a": None, "b": None}
            errors = {"a": None, "b": None}

            def writer_a():
                try:
                    # Create new service instance for this thread
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
                                "char-henry", "novel-project", "age", 26, ExpectValue(25)
                            )
                        ],
                    )

                    request_a = CommitRequest(
                        project_id="novel-project",
                        branch_name="main",
                        parent_commit_id=receipt_setup.commit_id,
                        idempotency_key="idem-writer-a",
                        narrative_delta=delta_a,
                        permit=permit_a,
                    )

                    results["a"] = service_a.commit_narrative_delta(request_a)
                    repo_a.close()
                except Exception as e:
                    errors["a"] = e

            def writer_b():
                try:
                    # Create new service instance for this thread
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
                                "char-henry", "novel-project", "age", 27, ExpectValue(25)
                            )
                        ],
                    )

                    request_b = CommitRequest(
                        project_id="novel-project",
                        branch_name="main",
                        parent_commit_id=receipt_setup.commit_id,
                        idempotency_key="idem-writer-b",
                        narrative_delta=delta_b,
                        permit=permit_b,
                    )

                    results["b"] = service_b.commit_narrative_delta(request_b)
                    repo_b.close()
                except Exception as e:
                    errors["b"] = e

            # Start both threads
            thread_a = threading.Thread(target=writer_a)
            thread_b = threading.Thread(target=writer_b)

            thread_a.start()
            thread_b.start()

            thread_a.join(timeout=10)
            thread_b.join(timeout=10)

            # Exactly one should succeed
            successes = sum(1 for r in results.values() if r is not None)
            failures = sum(1 for e in errors.values() if e is not None)

            assert successes == 1, f"Expected exactly 1 success, got {successes}"
            assert failures == 1, f"Expected exactly 1 failure, got {failures}"

            # Verify final state
            with repo.transaction() as session:
                # Only 3 commits total: root + setup + ONE of the writers
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE project_id = :project_id
                    """),
                    {"project_id": "novel-project"},
                )
                assert result.scalar() == 3

                # Only 3 events
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_event
                        WHERE project_id = :project_id
                    """),
                    {"project_id": "novel-project"},
                )
                assert result.scalar() == 2  # setup + ONE writer

                # HEAD points to exactly one winner
                head = repo.get_branch_head(session, "novel-project", "main")
                assert head in [
                    results["a"].commit_id if results["a"] else None,
                    results["b"].commit_id if results["b"] else None,
                ]

        finally:
            repo.close()

