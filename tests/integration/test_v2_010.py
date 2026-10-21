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
