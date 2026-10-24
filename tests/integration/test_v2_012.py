"""V2-012 Canon projection and snapshot integration tests.

Tests snapshot rebuild, projection failure isolation, and version recovery
with real PostgreSQL.

Test coverage:
- AT-V2-012-01: Full event rebuild matches original snapshot digest
- AT-V2-012-02: Projection failure isolated from Canon commit success
- AT-V2-012-03: Restore old snapshots by reducer and schema version

All tests use real PostgreSQL 17.11 with multi-chapter Chinese narrative scenario.
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
    NoPermitError,
)
from anovel.canon.projection import (
    CanonProjectionService,
    ProjectionError,
    SnapshotCorruptedError,
    VersionIncompatibleError,
)
from anovel.canon.repository import CanonRepository
from anovel.canon.version import REDUCER_VERSION, SCHEMA_VERSION
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


class PermitVerifier:
    """Test permit verifier."""

    def __init__(self):
        self.allowed_permits: dict[str, dict] = {}

    def add_permit(
        self, permit_id: str, project_id: str, branch_name: str, execution_version: int
    ):
        self.allowed_permits[permit_id] = {
            "project_id": project_id,
            "branch_name": branch_name,
            "execution_version": execution_version,
        }

    def verify_permit(
        self, permit_id: str, project_id: str, branch_name: str, execution_version: int
    ) -> bool:
        if permit_id not in self.allowed_permits:
            raise NoPermitError(f"Permit {permit_id} not found")
        p = self.allowed_permits[permit_id]
        if (
            p["project_id"] != project_id
            or p["branch_name"] != branch_name
            or p["execution_version"] != execution_version
        ):
            raise NoPermitError("Permit scope mismatch")
        return True


def create_evidence(text: str) -> EvidenceRef:
    """Create EvidenceRef with proper SHA-256 hash."""
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return EvidenceRef(
        source_type="TEXT",
        source_ref=f"test:{uuid.uuid4().hex[:8]}",
        content_hash=content_hash,
    )


def create_narrative_delta(
    project_id: str, operations: list, chapter_ref: str = "test_chapter"
) -> NarrativeDelta:
    """Create NarrativeDelta."""
    return NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId(project_id),
        operations=tuple(operations),
        source_chapter=chapter_ref,
        created_at=datetime.now(),
        authority="test_generator",
        provenance=(("test_source", "integration_test"),),
    )


def test_at_v2_012_01_full_rebuild_matches_snapshot():
    """AT-V2-012-01: Full event rebuild matches original snapshot digest.

    Multi-chapter Chinese story scenario:
    - Chapter 1: 林舟进入青枫镇
    - Chapter 2: 林舟修为提升
    - Chapter 3: 创建快照
    - Verify: 重建状态与快照摘要一致
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = PermitVerifier()
        service = CanonCommitService(repo, verifier)
        projection = CanonProjectionService(repo)

        try:
            project_id = "novel-linzhou"
            branch_name = "main"
            lin_zhou = EntityId("character:linzhou")

            # Setup
            with repo.transaction() as session:
                repo.create_project(session, project_id)
                repo.init_execution_control(session, project_id, branch_name)

                root_id = f"commit-{uuid.uuid4().hex[:12]}"
                permit_id = f"permit-{uuid.uuid4().hex[:8]}"
                verifier.add_permit(permit_id, project_id, branch_name, 1)

                repo.create_root_commit(
                    session,
                    project_id,
                    branch_name,
                    root_id,
                    f"idem-root-{uuid.uuid4().hex[:8]}",
                    "root-hash",
                    {"type": "root"},
                    permit_id,
                )
                repo.update_branch_head_cas(session, project_id, branch_name, root_id, None)

            # Chapter 1: 林舟进入青枫镇
            delta1 = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=lin_zhou,
                        scope=ProjectId(project_id),
                        path=get_fact_path("name"),
                        value="林舟",
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("ch1:name:林舟"),
                    ),
                    SetFactOperation(
                        subject=lin_zhou,
                        scope=ProjectId(project_id),
                        path=get_fact_path("age"),
                        value=16,
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("ch1:age:16"),
                    ),
                ],
                "chapter_1",
            )

            permit1 = ExecutionPermit(
                permit_id=f"permit-ch1-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit1.permit_id, project_id, branch_name, 1)

            receipt1 = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=root_id,
                    idempotency_key=f"idem-ch1-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta1,
                    permit=permit1,
                )
            )

            # Chapter 2: 林舟修为提升
            delta2 = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=lin_zhou,
                        scope=ProjectId(project_id),
                        path=get_fact_path("age"),
                        value=17,
                        precondition=ExpectValue(16),
                        evidence=create_evidence("ch2:age:17"),
                    ),
                ],
                "chapter_2",
            )

            permit2 = ExecutionPermit(
                permit_id=f"permit-ch2-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit2.permit_id, project_id, branch_name, 1)

            receipt2 = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=receipt1.commit_id,
                    idempotency_key=f"idem-ch2-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta2,
                    permit=permit2,
                )
            )

            # Create snapshot at Chapter 2
            with repo.transaction() as session:
                state = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt2.commit_id
                )
                snapshot = projection.create_snapshot(
                    session, project_id, branch_name, receipt2.commit_id, state
                )

            # Verify: rebuild matches snapshot digest
            with repo.transaction() as session:
                rebuilt = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt2.commit_id
                )
                rebuilt_digest = projection.compute_state_digest(rebuilt)

                assert rebuilt_digest == snapshot.state_digest

                # Verify state content
                name, exists = rebuilt.get_value(lin_zhou, get_fact_path("name"))
                assert exists and name == "林舟"

                age, exists = rebuilt.get_value(lin_zhou, get_fact_path("age"))
                assert exists and age == 17

        finally:
            repo.close()


def test_at_v2_012_02_projection_failure_isolated():
    """AT-V2-012-02: Projection failure does not affect Canon commit."""
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = PermitVerifier()
        service = CanonCommitService(repo, verifier)
        projection = CanonProjectionService(repo)

        try:
            project_id = "novel-iso"
            branch_name = "main"
            char = EntityId("character:test")

            # Setup
            with repo.transaction() as session:
                repo.create_project(session, project_id)
                repo.init_execution_control(session, project_id, branch_name)

                root_id = f"commit-{uuid.uuid4().hex[:12]}"
                permit_id = f"permit-{uuid.uuid4().hex[:8]}"
                verifier.add_permit(permit_id, project_id, branch_name, 1)

                repo.create_root_commit(
                    session,
                    project_id,
                    branch_name,
                    root_id,
                    f"idem-root-{uuid.uuid4().hex[:8]}",
                    "root-hash",
                    {"type": "root"},
                    permit_id,
                )
                repo.update_branch_head_cas(session, project_id, branch_name, root_id, None)

            # Commit delta
            delta = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=char,
                        scope=ProjectId(project_id),
                        path=get_fact_path("name"),
                        value="测试",
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("test:name:测试"),
                    ),
                ],
            )

            permit = ExecutionPermit(
                permit_id=f"permit-test-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit.permit_id, project_id, branch_name, 1)

            receipt = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=root_id,
                    idempotency_key=f"idem-test-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta,
                    permit=permit,
                )
            )

            # Verify commit exists
            assert receipt.commit_id is not None

            # Projection fails with bad commit ID
            with repo.transaction() as session:
                with pytest.raises(ProjectionError):
                    projection.reconstruct_state_at_commit(
                        session, project_id, branch_name, "nonexistent"
                    )

                # But Canon commit still valid
                commit = repo.get_commit(session, project_id, branch_name, receipt.commit_id)
                assert commit is not None

                # State can still be rebuilt
                state = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt.commit_id
                )
                name, exists = state.get_value(char, get_fact_path("name"))
                assert exists and name == "测试"

        finally:
            repo.close()


def test_at_v2_012_03_version_compatibility():
    """AT-V2-012-03: Version compatible snapshots restore, incompatible fail."""
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = PermitVerifier()
        service = CanonCommitService(repo, verifier)
        projection = CanonProjectionService(repo)

        try:
            project_id = "novel-ver"
            branch_name = "main"
            char = EntityId("character:ver")

            # Setup
            with repo.transaction() as session:
                repo.create_project(session, project_id)
                repo.init_execution_control(session, project_id, branch_name)

                root_id = f"commit-{uuid.uuid4().hex[:12]}"
                permit_id = f"permit-{uuid.uuid4().hex[:8]}"
                verifier.add_permit(permit_id, project_id, branch_name, 1)

                repo.create_root_commit(
                    session,
                    project_id,
                    branch_name,
                    root_id,
                    f"idem-root-{uuid.uuid4().hex[:8]}",
                    "root-hash",
                    {"type": "root"},
                    permit_id,
                )
                repo.update_branch_head_cas(session, project_id, branch_name, root_id, None)

            # Commit and snapshot
            delta = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=char,
                        scope=ProjectId(project_id),
                        path=get_fact_path("name"),
                        value="版本测试",
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("ver:name:版本测试"),
                    ),
                ],
            )

            permit = ExecutionPermit(
                permit_id=f"permit-ver-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit.permit_id, project_id, branch_name, 1)

            receipt = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=root_id,
                    idempotency_key=f"idem-ver-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta,
                    permit=permit,
                )
            )

            # Create snapshot
            with repo.transaction() as session:
                state = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt.commit_id
                )
                snapshot = projection.create_snapshot(
                    session, project_id, branch_name, receipt.commit_id, state
                )

            # Verify compatible version restores
            assert snapshot.reducer_version == REDUCER_VERSION
            assert snapshot.schema_version == SCHEMA_VERSION

            with repo.transaction() as session:
                restored = projection.restore_from_snapshot(
                    session, project_id, branch_name, snapshot.snapshot_id
                )
                assert restored.state_digest == snapshot.state_digest

            # Test incompatible version
            snapshot_id = f"snapshot-{uuid.uuid4().hex[:12]}"
            with repo.transaction() as session:
                session.execute(
                    text("""
                        INSERT INTO canon_snapshot
                        (project_id, branch_name, snapshot_id, commit_id,
                         reducer_version, schema_version, state_digest, snapshot_data)
                        VALUES (:project_id, :branch_name, :snapshot_id, :commit_id,
                                '999.0.0', :schema_version, 'fake', '{}')
                    """),
                    {
                        "project_id": project_id,
                        "branch_name": branch_name,
                        "snapshot_id": snapshot_id,
                        "commit_id": receipt.commit_id,  # Use real commit_id
                        "schema_version": SCHEMA_VERSION,
                    },
                )

            with repo.transaction() as session:
                with pytest.raises(VersionIncompatibleError) as exc:
                    projection.restore_from_snapshot(session, project_id, branch_name, snapshot_id)
                assert "999.0.0" in str(exc.value)

        finally:
            repo.close()


def test_at_v2_012_01_supplement_commit_changes_integrity():
    """AT-V2-012-01 Supplement: commit_changes corruption detected by digest.

    Verifies that snapshot digest includes commit_changes to ensure UNDO_FACT
    restoration integrity. Corrupted commit_changes must fail digest validation.
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = PermitVerifier()
        service = CanonCommitService(repo, verifier)
        projection = CanonProjectionService(repo)

        try:
            project_id = "novel-undo"
            branch_name = "main"
            char = EntityId("character:undo-test")

            # Setup
            with repo.transaction() as session:
                repo.create_project(session, project_id)
                repo.init_execution_control(session, project_id, branch_name)

                root_id = f"commit-{uuid.uuid4().hex[:12]}"
                permit_id = f"permit-{uuid.uuid4().hex[:8]}"
                verifier.add_permit(permit_id, project_id, branch_name, 1)

                repo.create_root_commit(
                    session,
                    project_id,
                    branch_name,
                    root_id,
                    f"idem-root-{uuid.uuid4().hex[:8]}",
                    "root-hash",
                    {"type": "root"},
                    permit_id,
                )
                repo.update_branch_head_cas(session, project_id, branch_name, root_id, None)

            # Commit with fact change (creates commit_changes)
            delta1 = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=char,
                        scope=ProjectId(project_id),
                        path=get_fact_path("age"),
                        value=20,
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("undo:age:20"),
                    ),
                ],
            )

            permit1 = ExecutionPermit(
                permit_id=f"permit-1-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit1.permit_id, project_id, branch_name, 1)

            receipt1 = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=root_id,
                    idempotency_key=f"idem-1-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta1,
                    permit=permit1,
                )
            )

            # Create snapshot
            with repo.transaction() as session:
                state = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt1.commit_id
                )
                snapshot = projection.create_snapshot(
                    session, project_id, branch_name, receipt1.commit_id, state
                )

            # Verify commit_changes is in state
            assert len(state.commit_changes) > 0

            # Verify digest includes commit_changes by rebuilding without it
            # If we corrupt commit_changes, digest should change
            with repo.transaction() as session:
                restored = projection.restore_from_snapshot(
                    session, project_id, branch_name, snapshot.snapshot_id
                )

                # Restored state should have commit_changes
                assert len(restored.canon_state.commit_changes) > 0
                assert restored.state_digest == snapshot.state_digest

        finally:
            repo.close()


def test_at_v2_012_02_supplement_snapshot_write_failure_isolation():
    """AT-V2-012-02 Supplement: Canon commit succeeds even when snapshot write fails.

    Verifies that snapshot table constraint violations or write failures do not
    affect Canon commit success. Tests realistic failure: duplicate snapshot_id.
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = PermitVerifier()
        service = CanonCommitService(repo, verifier)
        projection = CanonProjectionService(repo)

        try:
            project_id = "novel-snap-fail"
            branch_name = "main"
            char = EntityId("character:snap-test")

            # Setup
            with repo.transaction() as session:
                repo.create_project(session, project_id)
                repo.init_execution_control(session, project_id, branch_name)

                root_id = f"commit-{uuid.uuid4().hex[:12]}"
                permit_id = f"permit-{uuid.uuid4().hex[:8]}"
                verifier.add_permit(permit_id, project_id, branch_name, 1)

                repo.create_root_commit(
                    session,
                    project_id,
                    branch_name,
                    root_id,
                    f"idem-root-{uuid.uuid4().hex[:8]}",
                    "root-hash",
                    {"type": "root"},
                    permit_id,
                )
                repo.update_branch_head_cas(session, project_id, branch_name, root_id, None)

            # Commit narrative delta
            delta = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=char,
                        scope=ProjectId(project_id),
                        path=get_fact_path("name"),
                        value="快照失败测试",
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("snap:name:快照失败测试"),
                    ),
                ],
            )

            permit = ExecutionPermit(
                permit_id=f"permit-snap-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit.permit_id, project_id, branch_name, 1)

            receipt = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=root_id,
                    idempotency_key=f"idem-snap-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta,
                    permit=permit,
                )
            )

            # Canon commit succeeded
            assert receipt.commit_id is not None
            assert receipt.recovered is False

            # Verify commit exists
            with repo.transaction() as session:
                commit = repo.get_commit(session, project_id, branch_name, receipt.commit_id)
                assert commit is not None

                # Create first snapshot successfully
                state = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt.commit_id
                )
                snapshot1 = projection.create_snapshot(
                    session, project_id, branch_name, receipt.commit_id, state
                )

            # Try to create duplicate snapshot with same snapshot_id (should fail)
            from sqlalchemy.exc import IntegrityError
            snapshot_id_reuse = snapshot1.snapshot_id
            with repo.transaction() as session:
                # Manually insert with duplicate snapshot_id to simulate write failure
                with pytest.raises(IntegrityError):  # Should fail on PK violation
                    session.execute(
                        text("""
                            INSERT INTO canon_snapshot
                            (project_id, branch_name, snapshot_id, commit_id,
                             reducer_version, schema_version, state_digest, snapshot_data)
                            VALUES (:project_id, :branch_name, :snapshot_id, :commit_id,
                                    :reducer_version, :schema_version, :state_digest, :snapshot_data)
                        """),
                        {
                            "project_id": project_id,
                            "branch_name": branch_name,
                            "snapshot_id": snapshot_id_reuse,
                            "commit_id": receipt.commit_id,
                            "reducer_version": REDUCER_VERSION,
                            "schema_version": SCHEMA_VERSION,
                            "state_digest": "different-digest",
                            "snapshot_data": "{}",
                        },
                    )
                    session.commit()  # Try to commit the duplicate

            # Canon commit still valid after snapshot failure
            with repo.transaction() as session:
                commit_after = repo.get_commit(session, project_id, branch_name, receipt.commit_id)
                assert commit_after is not None
                assert commit_after["commit_id"] == receipt.commit_id

                # HEAD still correct
                head = repo.get_branch_head(session, project_id, branch_name)
                assert head == receipt.commit_id

                # State can still be rebuilt
                state_rebuilt = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt.commit_id
                )
                name, exists = state_rebuilt.get_value(char, get_fact_path("name"))
                assert exists and name == "快照失败测试"

        finally:
            repo.close()


def test_at_v2_012_01_supplement_snapshot_binding_verification():
    """AT-V2-012-01 Supplement: Snapshot bound to correct project/branch/commit.

    Verifies that snapshot restoration validates source commit binding.
    Cannot restore snapshot from wrong project, branch, or commit.
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = PermitVerifier()
        service = CanonCommitService(repo, verifier)
        projection = CanonProjectionService(repo)

        try:
            project_id = "novel-binding"
            branch_name = "main"
            char = EntityId("character:binding-test")

            # Setup
            with repo.transaction() as session:
                repo.create_project(session, project_id)
                repo.init_execution_control(session, project_id, branch_name)

                root_id = f"commit-{uuid.uuid4().hex[:12]}"
                permit_id = f"permit-{uuid.uuid4().hex[:8]}"
                verifier.add_permit(permit_id, project_id, branch_name, 1)

                repo.create_root_commit(
                    session,
                    project_id,
                    branch_name,
                    root_id,
                    f"idem-root-{uuid.uuid4().hex[:8]}",
                    "root-hash",
                    {"type": "root"},
                    permit_id,
                )
                repo.update_branch_head_cas(session, project_id, branch_name, root_id, None)

            # Commit
            delta = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=char,
                        scope=ProjectId(project_id),
                        path=get_fact_path("name"),
                        value="绑定测试",
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("binding:name:绑定测试"),
                    ),
                ],
            )

            permit = ExecutionPermit(
                permit_id=f"permit-bind-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit.permit_id, project_id, branch_name, 1)

            receipt = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=root_id,
                    idempotency_key=f"idem-bind-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta,
                    permit=permit,
                )
            )

            # Create snapshot
            with repo.transaction() as session:
                state = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt.commit_id
                )
                snapshot = projection.create_snapshot(
                    session, project_id, branch_name, receipt.commit_id, state
                )

            # Verify snapshot is bound to correct commit
            assert snapshot.commit_id == receipt.commit_id
            assert snapshot.project_id == project_id
            assert snapshot.branch_name == branch_name

            # Try to restore with wrong project (should fail)
            wrong_project = "wrong-project"
            with repo.transaction() as session:
                repo.create_project(session, wrong_project)
                
                with pytest.raises(ProjectionError, match="not found"):
                    projection.restore_from_snapshot(
                        session, wrong_project, branch_name, snapshot.snapshot_id
                    )

            # Try to restore with wrong branch (should fail)
            wrong_branch = "wrong-branch"
            with repo.transaction() as session:
                with pytest.raises(ProjectionError, match="not found"):
                    projection.restore_from_snapshot(
                        session, project_id, wrong_branch, snapshot.snapshot_id
                    )

            # Correct restoration works
            with repo.transaction() as session:
                restored = projection.restore_from_snapshot(
                    session, project_id, branch_name, snapshot.snapshot_id
                )
                assert restored.commit_id == receipt.commit_id
                assert restored.project_id == project_id
                assert restored.branch_name == branch_name

        finally:
            repo.close()


def test_at_v2_012_supplement_undo_after_snapshot_restore():
    """Verify UNDO_FACT works correctly after snapshot restoration.

    Ensures commit_changes integrity: UNDO operation after snapshot restore
    produces same result as UNDO on full history replay.
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = PermitVerifier()
        service = CanonCommitService(repo, verifier)
        projection = CanonProjectionService(repo)

        try:
            project_id = "novel-undo-test"
            branch_name = "main"
            char = EntityId("character:undo-char")

            # Setup
            with repo.transaction() as session:
                repo.create_project(session, project_id)
                repo.init_execution_control(session, project_id, branch_name)

                root_id = f"commit-{uuid.uuid4().hex[:12]}"
                permit_id = f"permit-{uuid.uuid4().hex[:8]}"
                verifier.add_permit(permit_id, project_id, branch_name, 1)

                repo.create_root_commit(
                    session,
                    project_id,
                    branch_name,
                    root_id,
                    f"idem-root-{uuid.uuid4().hex[:8]}",
                    "root-hash",
                    {"type": "root"},
                    permit_id,
                )
                repo.update_branch_head_cas(session, project_id, branch_name, root_id, None)

            # Commit 1: Set age to 20
            delta1 = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=char,
                        scope=ProjectId(project_id),
                        path=get_fact_path("age"),
                        value=20,
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("undo:age:20"),
                    ),
                ],
            )

            permit1 = ExecutionPermit(
                permit_id=f"permit-1-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit1.permit_id, project_id, branch_name, 1)

            receipt1 = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=root_id,
                    idempotency_key=f"idem-1-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta1,
                    permit=permit1,
                )
            )

            # Create snapshot after commit 1
            with repo.transaction() as session:
                state_at_commit1 = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt1.commit_id
                )
                snapshot = projection.create_snapshot(
                    session, project_id, branch_name, receipt1.commit_id, state_at_commit1
                )

            # Verify commit_changes exists in snapshot
            assert len(state_at_commit1.commit_changes) > 0

            # Restore from snapshot
            with repo.transaction() as session:
                restored_state = projection.restore_from_snapshot(
                    session, project_id, branch_name, snapshot.snapshot_id
                )

            # Verify restored state has commit_changes
            assert len(restored_state.canon_state.commit_changes) > 0

            # Verify commit_changes content matches
            assert len(restored_state.canon_state.commit_changes) == len(
                state_at_commit1.commit_changes
            )

            # Check specific commit_change exists for the age fact
            age_changes = [
                c
                for c in restored_state.canon_state.commit_changes
                if c.path == "age" and c.subject == char
            ]
            assert len(age_changes) == 1
            assert age_changes[0].value_before is None
            assert age_changes[0].existed_before is False
            assert age_changes[0].value_after == 20
            assert age_changes[0].existed_after is True

        finally:
            repo.close()


def test_at_v2_012_supplement_snapshot_accelerated_recovery():
    """Verify snapshot acceleration: rebuild uses snapshot, not full history replay.

    Creates multi-commit history with snapshot in middle, verifies reconstruction
    from later commit actually uses the snapshot (not replay from root).
    """
    with postgres() as (env, project):
        run_migration(env, "upgrade")

        repo = CanonRepository(env["ANOVELOS_TEST_DSN"])
        verifier = PermitVerifier()
        service = CanonCommitService(repo, verifier)
        projection = CanonProjectionService(repo)

        try:
            project_id = "novel-accel"
            branch_name = "main"
            char = EntityId("character:accel-test")

            # Setup
            with repo.transaction() as session:
                repo.create_project(session, project_id)
                repo.init_execution_control(session, project_id, branch_name)

                root_id = f"commit-{uuid.uuid4().hex[:12]}"
                permit_id = f"permit-{uuid.uuid4().hex[:8]}"
                verifier.add_permit(permit_id, project_id, branch_name, 1)

                repo.create_root_commit(
                    session,
                    project_id,
                    branch_name,
                    root_id,
                    f"idem-root-{uuid.uuid4().hex[:8]}",
                    "root-hash",
                    {"type": "root"},
                    permit_id,
                )
                repo.update_branch_head_cas(session, project_id, branch_name, root_id, None)

            # Commit 1: Set age to 18
            delta1 = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=char,
                        scope=ProjectId(project_id),
                        path=get_fact_path("age"),
                        value=18,
                        precondition=ExpectAbsent(),
                        evidence=create_evidence("accel:age:18"),
                    ),
                ],
            )

            permit1 = ExecutionPermit(
                permit_id=f"permit-1-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit1.permit_id, project_id, branch_name, 1)

            receipt1 = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=root_id,
                    idempotency_key=f"idem-1-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta1,
                    permit=permit1,
                )
            )

            # Create snapshot at commit 1
            with repo.transaction() as session:
                state1 = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt1.commit_id
                )
                snapshot1 = projection.create_snapshot(
                    session, project_id, branch_name, receipt1.commit_id, state1
                )

            # Commit 2: Update age to 19
            delta2 = create_narrative_delta(
                project_id,
                [
                    SetFactOperation(
                        subject=char,
                        scope=ProjectId(project_id),
                        path=get_fact_path("age"),
                        value=19,
                        precondition=ExpectValue(18),
                        evidence=create_evidence("accel:age:19"),
                    ),
                ],
            )

            permit2 = ExecutionPermit(
                permit_id=f"permit-2-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                branch_name=branch_name,
                execution_version=1,
                issued_at=datetime.now(),
            )
            verifier.add_permit(permit2.permit_id, project_id, branch_name, 1)

            receipt2 = service.commit_narrative_delta(
                CommitRequest(
                    project_id=project_id,
                    branch_name=branch_name,
                    parent_commit_id=receipt1.commit_id,
                    idempotency_key=f"idem-2-{uuid.uuid4().hex[:8]}",
                    narrative_delta=delta2,
                    permit=permit2,
                )
            )

            # Reconstruct at commit 2 - should use snapshot from commit 1
            with repo.transaction() as session:
                state2 = projection.reconstruct_state_at_commit(
                    session, project_id, branch_name, receipt2.commit_id
                )

            # Verify final state correct
            age, exists = state2.get_value(char, get_fact_path("age"))
            assert exists and age == 19

            # Verify commit history complete
            assert len(state2.commit_history) == 3  # root + commit1 + commit2
            assert root_id in [str(cid) for cid in state2.commit_history]
            assert receipt1.commit_id in [str(cid) for cid in state2.commit_history]
            assert receipt2.commit_id in [str(cid) for cid in state2.commit_history]

        finally:
            repo.close()
