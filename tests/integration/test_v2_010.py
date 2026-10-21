"""V2-010 CanonCommitService integration tests.

Tests the unified business service for Canon narrative commits with real PostgreSQL.

Test coverage:
- AT-V2-010-01: No permit rejection
- AT-V2-010-02: Valid narrative delta commits successfully
- AT-V2-010-03: Commit + Event + HEAD atomic consistency
- AT-V2-010-04: CAS conflict triggers full rollback
- AT-V2-010-05: Idempotent receipt recovery after success
- AT-V2-010-06: Same key different payload rejection
- AT-V2-010-07: Character creation persists and rebuilds

All tests use real PostgreSQL 17.11 (no mocks).
"""

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
    CommitReceipt,
    CommitRequest,
    ExecutionPermit,
    InvalidDeltaError,
    NoPermitError,
)
from anovel.canon.repository import (
    CanonRepository,
    CanonRepositoryError,
    IdempotencyConflictError,
)
from anovel.domain.character import Character, CharacterLifecycle
from anovel.domain.delta import (
    NarrativeDelta,
    SetFactOperation,
    OperationType,
    ExpectAbsent,
    FactPath,
    EvidenceRef,
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


def create_simple_set_fact(
    entity_id: str, project_id: str, path_str: str, value: Any
) -> SetFactOperation:
    """Helper to create SetFactOperation for testing.

    Args:
        entity_id: Entity ID
        project_id: Project ID
        path_str: Fact path string
        value: Fact value

    Returns:
        SetFactOperation instance
    """
    from anovel.domain.delta import get_fact_path

    return SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId(entity_id),
        scope=ProjectId(project_id),
        path=get_fact_path(path_str),
        value=value,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="test:evidence",
            content_hash="test-hash-" + uuid.uuid4().hex[:8],
        ),
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
        service = CanonCommitService(repo)

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

            # Create invalid permit
            invalid_permit = ExecutionPermit(
                permit_id="permit-invalid",
                project_id="test-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.utcnow(),
                valid=False,  # Invalid!
            )

            # Create simple delta
            delta = NarrativeDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:12]}",
                project_id=ProjectId("test-project"),
                created_at=datetime.utcnow(),
                description="Test character creation",
                operations=[
                    create_simple_set_fact("char-1", "test-project", "name", "Alice")
                ],
            )

            request = CommitRequest(
                project_id="test-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-test-1",
                narrative_delta=delta,
                permit=invalid_permit,
            )

            # Attempt commit with invalid permit
            with pytest.raises(NoPermitError, match="not valid"):
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

                # Verify no event created
                result = session.execute(
                    text("SELECT COUNT(*) FROM canon_event WHERE project_id = 'test-project'")
                )
                assert result.scalar() == 0

                # Verify HEAD unchanged
                head = repo.get_branch_head(session, "test-project", "main")
                assert head == "commit-root"

        finally:
            repo.close()


def test_at_v2_010_02_valid_delta_commits_successfully():
    """AT-V2-010-02: Valid narrative delta commits successfully.

    Verifies:
    - Valid permit allows commit
    - Commit created with correct data
    - Receipt returned with commit_id
    - Execution version validated
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        service = CanonCommitService(repo)

        try:
            # Setup
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

            # Valid permit
            permit = ExecutionPermit(
                permit_id="permit-valid",
                project_id="test-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.utcnow(),
                valid=True,
            )

            # Create delta
            delta = NarrativeDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:12]}",
                project_id=ProjectId("test-project"),
                created_at=datetime.utcnow(),
                description="Create character Alice",
                operations=[
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["characters", "char-alice", "name"],
                        target_value="Alice",
                        precondition=Precondition(expect="ABSENT"),
                    )
                ],
            )

            request = CommitRequest(
                project_id="test-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-test-2",
                narrative_delta=delta,
                permit=permit,
            )

            # Commit should succeed
            receipt = service.commit_narrative_delta(request)

            assert isinstance(receipt, CommitReceipt)
            assert receipt.project_id == "test-project"
            assert receipt.branch_name == "main"
            assert receipt.idempotency_key == "idem-test-2"
            assert receipt.recovered is False
            assert receipt.commit_id is not None
            assert receipt.committed_at is not None

            # Verify commit exists
            with repo.transaction() as session:
                commit = repo.get_commit(session, "test-project", "main", receipt.commit_id)
                assert commit is not None
                assert commit["idempotency_key"] == "idem-test-2"
                assert commit["permit_ref"] == "permit-valid"

        finally:
            repo.close()


def test_at_v2_010_03_commit_event_head_atomic():
    """AT-V2-010-03: Commit + Event + HEAD update atomic consistency.

    Verifies:
    - Commit, Event, and HEAD update in single transaction
    - All three succeed or all fail together
    - Event references correct commit_id
    - HEAD points to new commit
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        service = CanonCommitService(repo)

        try:
            # Setup
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

            permit = ExecutionPermit(
                permit_id="permit-atomic",
                project_id="test-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.utcnow(),
                valid=True,
            )

            delta = NarrativeDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:12]}",
                project_id=ProjectId("test-project"),
                created_at=datetime.utcnow(),
                description="Atomic test",
                operations=[
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["test", "atomic"],
                        target_value=True,
                        precondition=Precondition(expect="ABSENT"),
                    )
                ],
            )

            request = CommitRequest(
                project_id="test-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-atomic",
                narrative_delta=delta,
                permit=permit,
            )

            receipt = service.commit_narrative_delta(request)

            # Verify atomic consistency
            with repo.transaction() as session:
                # 1. Commit exists
                commit = repo.get_commit(session, "test-project", "main", receipt.commit_id)
                assert commit is not None

                # 2. Event exists and references commit
                event_result = session.execute(
                    text("""
                        SELECT event_id, commit_id, event_type
                        FROM canon_event
                        WHERE project_id = 'test-project'
                          AND branch_name = 'main'
                          AND commit_id = :commit_id
                    """),
                    {"commit_id": receipt.commit_id},
                )
                event = event_result.fetchone()
                assert event is not None
                assert event[1] == receipt.commit_id  # commit_id
                assert event[2] == "NARRATIVE_COMMIT"  # event_type

                # 3. HEAD points to new commit
                head = repo.get_branch_head(session, "test-project", "main")
                assert head == receipt.commit_id

        finally:
            repo.close()


def test_at_v2_010_04_cas_conflict_full_rollback():
    """AT-V2-010-04: CAS conflict triggers complete transaction rollback.

    Verifies:
    - Concurrent HEAD change detected
    - Transaction rolls back completely
    - No partial commit left
    - No event created
    - HEAD remains at concurrent value
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        service = CanonCommitService(repo)

        try:
            # Setup
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

                # Create concurrent commit (simulate race)
                repo.create_commit(
                    session,
                    "test-project",
                    "main",
                    "commit-concurrent",
                    "commit-root",
                    "idem-concurrent",
                    "hash-concurrent",
                    {"type": "concurrent"},
                )
                repo.update_branch_head_cas(
                    session, "test-project", "main", "commit-concurrent", "commit-root"
                )

            permit = ExecutionPermit(
                permit_id="permit-cas",
                project_id="test-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.utcnow(),
                valid=True,
            )

            delta = NarrativeDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:12]}",
                project_id=ProjectId("test-project"),
                created_at=datetime.utcnow(),
                description="CAS conflict test",
                operations=[
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["test", "cas"],
                        target_value=True,
                        precondition=Precondition(expect="ABSENT"),
                    )
                ],
            )

            # Attempt commit with stale parent (expect CAS failure)
            request = CommitRequest(
                project_id="test-project",
                branch_name="main",
                parent_commit_id="commit-root",  # Stale! HEAD is now commit-concurrent
                idempotency_key="idem-cas-fail",
                narrative_delta=delta,
                permit=permit,
            )

            with pytest.raises(CanonRepositoryError, match="HEAD CAS failed"):
                service.commit_narrative_delta(request)

            # Verify complete rollback
            with repo.transaction() as session:
                # No commit with this idempotency key
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE idempotency_key = 'idem-cas-fail'
                    """)
                )
                assert result.scalar() == 0

                # No event for failed commit
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_event
                        WHERE event_type = 'NARRATIVE_COMMIT'
                          AND project_id = 'test-project'
                    """)
                )
                assert result.scalar() == 0

                # HEAD still at concurrent commit
                head = repo.get_branch_head(session, "test-project", "main")
                assert head == "commit-concurrent"

        finally:
            repo.close()


def test_at_v2_010_05_idempotent_receipt_recovery():
    """AT-V2-010-05: Idempotent retry returns original receipt.

    Verifies:
    - Same key + same payload returns original receipt
    - recovered=True in returned receipt
    - No duplicate commit created
    - Original commit_id returned
    - Original timestamp preserved
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        service = CanonCommitService(repo)

        try:
            # Setup
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

            permit = ExecutionPermit(
                permit_id="permit-idempotent",
                project_id="test-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.utcnow(),
                valid=True,
            )

            delta = NarrativeDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:12]}",
                project_id=ProjectId("test-project"),
                created_at=datetime.utcnow(),
                description="Idempotent test",
                operations=[
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["test", "idempotent"],
                        target_value="original",
                        precondition=Precondition(expect="ABSENT"),
                    )
                ],
            )

            request = CommitRequest(
                project_id="test-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-retry",
                narrative_delta=delta,
                permit=permit,
            )

            # First commit
            receipt1 = service.commit_narrative_delta(request)
            assert receipt1.recovered is False

            # Retry with same key and same payload
            receipt2 = service.commit_narrative_delta(request)
            assert receipt2.recovered is True
            assert receipt2.commit_id == receipt1.commit_id
            assert receipt2.committed_at == receipt1.committed_at
            assert receipt2.idempotency_key == receipt1.idempotency_key

            # Verify only one commit exists
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE idempotency_key = 'idem-retry'
                    """)
                )
                assert result.scalar() == 1

        finally:
            repo.close()


def test_at_v2_010_06_same_key_different_payload_rejected():
    """AT-V2-010-06: Same idempotency key with different payload rejected.

    Verifies:
    - Same key + different payload raises IdempotencyConflictError
    - No second commit created
    - Original commit unchanged
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        service = CanonCommitService(repo)

        try:
            # Setup
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

            permit = ExecutionPermit(
                permit_id="permit-conflict",
                project_id="test-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.utcnow(),
                valid=True,
            )

            # First delta
            delta1 = NarrativeDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:12]}",
                project_id=ProjectId("test-project"),
                created_at=datetime.utcnow(),
                description="Original delta",
                operations=[
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["test", "value"],
                        target_value="original",
                        precondition=Precondition(expect="ABSENT"),
                    )
                ],
            )

            request1 = CommitRequest(
                project_id="test-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-conflict",
                narrative_delta=delta1,
                permit=permit,
            )

            # First commit succeeds
            receipt1 = service.commit_narrative_delta(request1)

            # Second delta (different payload, same key)
            delta2 = NarrativeDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:12]}",
                project_id=ProjectId("test-project"),
                created_at=datetime.utcnow(),
                description="Different delta",
                operations=[
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["test", "value"],
                        target_value="different",  # Different value!
                        precondition=Precondition(expect="ABSENT"),
                    )
                ],
            )

            request2 = CommitRequest(
                project_id="test-project",
                branch_name="main",
                parent_commit_id=receipt1.commit_id,
                idempotency_key="idem-conflict",  # Same key!
                narrative_delta=delta2,
                permit=permit,
            )

            # Second commit should fail with conflict
            with pytest.raises(IdempotencyConflictError, match="already used with different payload"):
                service.commit_narrative_delta(request2)

            # Verify only original commit exists
            with repo.transaction() as session:
                result = session.execute(
                    text("""
                        SELECT COUNT(*) FROM canon_commit
                        WHERE idempotency_key = 'idem-conflict'
                    """)
                )
                assert result.scalar() == 1

        finally:
            repo.close()


def test_at_v2_010_07_character_creation_persists_and_rebuilds():
    """AT-V2-010-07: Character creation commits and data can be rebuilt.

    Verifies:
    - Character creation delta commits successfully
    - Commit contains character data
    - Data can be read back from commit
    - Changeset structure preserved
    - Novel facts persist and rebuild
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        service = CanonCommitService(repo)

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

            permit = ExecutionPermit(
                permit_id="permit-character",
                project_id="novel-project",
                branch_name="main",
                execution_version=1,
                issued_at=datetime.utcnow(),
                valid=True,
            )

            # Create character delta
            delta = NarrativeDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:12]}",
                project_id=ProjectId("novel-project"),
                created_at=datetime.utcnow(),
                description="Create character Bob with age 25",
                operations=[
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["characters", "char-bob", "name"],
                        target_value="Bob",
                        precondition=Precondition(expect="ABSENT"),
                    ),
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["characters", "char-bob", "age"],
                        target_value=25,
                        precondition=Precondition(expect="ABSENT"),
                    ),
                    Operation(
                        operation_type=OperationType.SET_FACT,
                        target_path=["characters", "char-bob", "lifecycle"],
                        target_value="ACTIVE",
                        precondition=Precondition(expect="ABSENT"),
                    ),
                ],
            )

            request = CommitRequest(
                project_id="novel-project",
                branch_name="main",
                parent_commit_id="commit-root",
                idempotency_key="idem-create-bob",
                narrative_delta=delta,
                permit=permit,
            )

            # Commit character creation
            receipt = service.commit_narrative_delta(request)
            assert receipt.recovered is False

            # Rebuild: Read commit and verify character data
            with repo.transaction() as session:
                commit = repo.get_commit(session, "novel-project", "main", receipt.commit_id)
                assert commit is not None

                # Verify changeset contains character operations
                import json
                changeset = json.loads(commit["changeset"])
                assert changeset["description"] == "Create character Bob with age 25"
                assert len(changeset["operations"]) == 3

                # Verify character name operation
                name_op = next(
                    op for op in changeset["operations"]
                    if op["target_path"] == ["characters", "char-bob", "name"]
                )
                assert name_op["target_value"] == "Bob"

                # Verify character age operation
                age_op = next(
                    op for op in changeset["operations"]
                    if op["target_path"] == ["characters", "char-bob", "age"]
                )
                assert age_op["target_value"] == 25

                # Verify lifecycle operation
                lifecycle_op = next(
                    op for op in changeset["operations"]
                    if op["target_path"] == ["characters", "char-bob", "lifecycle"]
                )
                assert lifecycle_op["target_value"] == "ACTIVE"

            # Verify service can recover if restarted (simulated by new request)
            receipt2 = service.commit_narrative_delta(request)
            assert receipt2.recovered is True
            assert receipt2.commit_id == receipt.commit_id

        finally:
            repo.close()
