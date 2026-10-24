"""Canon projection service for snapshot and history reconstruction.

Provides non-authoritative projection capabilities:
- Rebuild CanonState from commit history to any point
- Create snapshots of projected state
- Restore from snapshots with version validation
- Compute state digests for consistency verification

Projections are derived views, not Canon authority. Projection failures
do not invalidate committed Canon history.

Public API:
    CanonProjectionService: Main projection service
    SnapshotData: Snapshot metadata and payload
    ProjectionError: Base projection error
    SnapshotCorruptedError: Snapshot integrity failure
    VersionIncompatibleError: Version compatibility failure
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..domain.delta import CanonState, CommitId
from ..domain.identity import ProjectId
from .repository import CanonRepository
from .version import (
    REDUCER_VERSION,
    SCHEMA_VERSION,
    VersionCompatibilityError,
    validate_versions,
)


class ProjectionError(Exception):
    """Base exception for projection errors."""

    pass


class SnapshotCorruptedError(ProjectionError):
    """Raised when snapshot data is corrupted or invalid."""

    pass


class VersionIncompatibleError(ProjectionError):
    """Raised when snapshot version is incompatible with current runtime."""

    pass


@dataclass(frozen=True)
class SnapshotData:
    """Snapshot metadata and payload.

    Attributes:
        snapshot_id: Unique snapshot identifier
        project_id: Project scope
        branch_name: Branch name
        commit_id: Source commit for this snapshot
        reducer_version: Reducer version used to create snapshot
        schema_version: Schema version used to create snapshot
        state_digest: SHA-256 digest of canonical state representation
        canon_state: Reconstructed CanonState
        created_at: Snapshot creation timestamp
    """

    snapshot_id: str
    project_id: str
    branch_name: str
    commit_id: str
    reducer_version: str
    schema_version: str
    state_digest: str
    canon_state: CanonState
    created_at: datetime


class CanonProjectionService:
    """Service for Canon history projection and snapshot management.

    Responsibilities:
    - Reconstruct CanonState from commit history (any commit, not just HEAD)
    - Create snapshots with version metadata and integrity digests
    - Restore from snapshots with version validation
    - Verify snapshot integrity and consistency

    This service DOES NOT modify Canon authority. Projections are read-only
    derived views. Projection failures are isolated from Canon commits.
    """

    def __init__(self, repository: CanonRepository):
        """Initialize projection service.

        Args:
            repository: CanonRepository for database access
        """
        self.repository = repository

    def reconstruct_state_at_commit(
        self,
        session: Session,
        project_id: str,
        branch_name: str,
        target_commit_id: str | None = None,
    ) -> CanonState:
        """Reconstruct CanonState from commit history up to target commit.

        Optimization: Uses compatible snapshots when available, falling back
        to full history replay if no snapshot found or snapshot corrupted.

        Args:
            session: Active database session
            project_id: Project ID
            branch_name: Branch name
            target_commit_id: Target commit (None = current HEAD)

        Returns:
            CanonState reconstructed up to target commit

        Raises:
            ProjectionError: If reconstruction fails
            CanonRepositoryError: If commit chain invalid
        """
        from sqlalchemy import text

        # If no target specified, use HEAD
        if target_commit_id is None:
            target_commit_id = self.repository.get_branch_head(
                session, project_id, branch_name
            )

        # Initialize empty state
        canon_state = CanonState(
            project_id=ProjectId(project_id),
            facts=(),
            tombstones=frozenset(),
            commit_history=(),
            commit_changes=(),
        )

        # If no target commit (empty branch), return empty state
        if target_commit_id is None:
            return canon_state

        # Build commit chain from target to root
        commit_chain: list[str] = []
        current_commit_id = target_commit_id
        seen_commits: set[str] = set()

        while current_commit_id is not None:
            if current_commit_id in seen_commits:
                raise ProjectionError(f"Commit cycle detected at {current_commit_id}")
            seen_commits.add(current_commit_id)
            commit_chain.append(current_commit_id)

            if len(commit_chain) > 10000:
                raise ProjectionError("Commit chain exceeds maximum length of 10000")

            commit = self.repository.get_commit(
                session, project_id, branch_name, current_commit_id
            )
            if commit is None:
                raise ProjectionError(f"Commit not found: {current_commit_id}")
            current_commit_id = commit["parent_commit_id"]

        # Reverse to get root-to-target order
        commit_chain.reverse()

        # Try to find a compatible snapshot in the commit chain
        snapshot_commit_id = None
        snapshot_state = None

        for commit_id in reversed(commit_chain):
            result = session.execute(
                text("""
                    SELECT snapshot_id, reducer_version, schema_version, state_digest, snapshot_data
                    FROM canon_snapshot
                    WHERE project_id = :project_id
                      AND branch_name = :branch_name
                      AND commit_id = :commit_id
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {
                    "project_id": project_id,
                    "branch_name": branch_name,
                    "commit_id": commit_id,
                },
            ).fetchone()

            if result:
                (
                    snapshot_id,
                    reducer_version,
                    schema_version,
                    state_digest,
                    snapshot_data,
                ) = result
                try:
                    validate_versions(reducer_version, schema_version)
                    snapshot_data_dict = json.loads(snapshot_data)
                    restored_state = self._deserialize_canon_state(snapshot_data_dict)
                    computed_digest = self.compute_state_digest(restored_state)
                    if computed_digest == state_digest:
                        snapshot_commit_id = commit_id
                        snapshot_state = restored_state
                        break
                except (VersionCompatibilityError, SnapshotCorruptedError, Exception):
                    continue

        # Determine replay range
        if snapshot_state is not None:
            canon_state = snapshot_state
            replay_from_index = commit_chain.index(snapshot_commit_id) + 1
        else:
            replay_from_index = 0

        # Apply commits from replay point
        for commit_id in commit_chain[replay_from_index:]:
            commit = self.repository.get_commit(
                session, project_id, branch_name, commit_id
            )
            if commit is None:
                raise ProjectionError(f"Commit disappeared: {commit_id}")

            changeset = commit["changeset"]
            if isinstance(changeset, str):
                changeset = json.loads(changeset)

            # Skip root commits
            if changeset.get("type") == "root":
                canon_state = CanonState(
                    project_id=canon_state.project_id,
                    facts=canon_state.facts,
                    tombstones=canon_state.tombstones,
                    commit_history=canon_state.commit_history + (CommitId(commit_id),),
                    commit_changes=canon_state.commit_changes,
                )
                continue

            # Reconstruct and apply delta
            delta = self._deserialize_delta(changeset)

            # Add commit to history
            canon_state = CanonState(
                project_id=canon_state.project_id,
                facts=canon_state.facts,
                tombstones=canon_state.tombstones,
                commit_history=canon_state.commit_history + (CommitId(commit_id),),
                commit_changes=canon_state.commit_changes,
            )

            # Apply operations
            canon_state = self._apply_operations_to_state(
                canon_state, delta, CommitId(commit_id)
            )

        return canon_state

    def compute_state_digest(self, canon_state: CanonState) -> str:
        """Compute deterministic digest of CanonState.

        Includes commit_changes to ensure UNDO_FACT restoration integrity.

        Args:
            canon_state: CanonState to digest

        Returns:
            Hex-encoded SHA-256 digest
        """
        # Serialize state to canonical JSON representation
        state_dict = {
            "project_id": str(canon_state.project_id),
            "facts": sorted(
                [
                    {
                        "subject": str(subject),
                        "path": path,
                        "value": self._serialize_value(value),
                    }
                    for (subject, path), value in canon_state.facts
                ],
                key=lambda x: (x["subject"], x["path"]),
            ),
            "tombstones": list(
                sorted(
                    [
                        {"subject": str(subject), "path": path}
                        for subject, path in canon_state.tombstones
                    ],
                    key=lambda x: (x["subject"], x["path"]),
                )
            ),
            "commit_history": [str(cid) for cid in canon_state.commit_history],
            "commit_changes": list(
                sorted(
                    [
                        {
                            "commit_id": str(change.commit_id),
                            "project_id": str(change.project_id),
                            "subject": str(change.subject),
                            "path": change.path,
                            "value_before": self._serialize_value(change.value_before),
                            "existed_before": change.existed_before,
                            "value_after": self._serialize_value(change.value_after),
                            "existed_after": change.existed_after,
                        }
                        for change in canon_state.commit_changes
                    ],
                    key=lambda x: (x["commit_id"], x["subject"], x["path"]),
                )
            ),
        }

        # Compute hash of canonical JSON
        canonical_json = json.dumps(state_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def create_snapshot(
        self,
        session: Session,
        project_id: str,
        branch_name: str,
        commit_id: str,
        canon_state: CanonState,
    ) -> SnapshotData:
        """Create snapshot of CanonState with version metadata.

        Args:
            session: Active database session
            project_id: Project ID
            branch_name: Branch name
            commit_id: Source commit ID
            canon_state: CanonState to snapshot

        Returns:
            SnapshotData with metadata

        Raises:
            ProjectionError: If snapshot creation fails
        """
        snapshot_id = f"snapshot-{uuid.uuid4().hex[:12]}"
        state_digest = self.compute_state_digest(canon_state)

        # Serialize state
        snapshot_data_json = self._serialize_canon_state(canon_state)

        # Insert snapshot record
        from sqlalchemy import text

        try:
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
                    "snapshot_id": snapshot_id,
                    "commit_id": commit_id,
                    "reducer_version": REDUCER_VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "state_digest": state_digest,
                    "snapshot_data": json.dumps(snapshot_data_json),
                },
            )
        except Exception as e:
            raise ProjectionError(f"Failed to create snapshot: {e}") from e

        # Get created_at timestamp
        created_at_result = session.execute(
            text("""
                SELECT created_at FROM canon_snapshot
                WHERE project_id = :project_id
                  AND branch_name = :branch_name
                  AND snapshot_id = :snapshot_id
            """),
            {
                "project_id": project_id,
                "branch_name": branch_name,
                "snapshot_id": snapshot_id,
            },
        ).scalar()

        return SnapshotData(
            snapshot_id=snapshot_id,
            project_id=project_id,
            branch_name=branch_name,
            commit_id=commit_id,
            reducer_version=REDUCER_VERSION,
            schema_version=SCHEMA_VERSION,
            state_digest=state_digest,
            canon_state=canon_state,
            created_at=created_at_result or datetime.now(),
        )

    def restore_from_snapshot(
        self,
        session: Session,
        project_id: str,
        branch_name: str,
        snapshot_id: str,
    ) -> SnapshotData:
        """Restore CanonState from snapshot with validation.

        Validates:
        - Version compatibility (reducer and schema)
        - Snapshot integrity (state digest)

        Args:
            session: Active database session
            project_id: Project ID
            branch_name: Branch name
            snapshot_id: Snapshot ID to restore

        Returns:
            SnapshotData with restored state

        Raises:
            SnapshotCorruptedError: If snapshot invalid or corrupted
            VersionIncompatibleError: If version incompatible
            ProjectionError: If restore fails
        """
        from sqlalchemy import text

        # Fetch snapshot record
        result = session.execute(
            text("""
                SELECT snapshot_id, commit_id, reducer_version, schema_version,
                       state_digest, snapshot_data, created_at
                FROM canon_snapshot
                WHERE project_id = :project_id
                  AND branch_name = :branch_name
                  AND snapshot_id = :snapshot_id
            """),
            {
                "project_id": project_id,
                "branch_name": branch_name,
                "snapshot_id": snapshot_id,
            },
        ).fetchone()

        if result is None:
            raise ProjectionError(
                f"Snapshot not found: {project_id}/{branch_name}/{snapshot_id}"
            )

        (
            stored_snapshot_id,
            commit_id,
            reducer_version,
            schema_version,
            stored_digest,
            snapshot_data_json,
            created_at,
        ) = result

        # Validate versions
        try:
            validate_versions(reducer_version, schema_version)
        except VersionCompatibilityError as e:
            raise VersionIncompatibleError(str(e)) from e

        # Deserialize state
        try:
            if isinstance(snapshot_data_json, str):
                snapshot_data_dict = json.loads(snapshot_data_json)
            else:
                snapshot_data_dict = snapshot_data_json

            canon_state = self._deserialize_canon_state(snapshot_data_dict)
        except Exception as e:
            raise SnapshotCorruptedError(
                f"Failed to deserialize snapshot data: {e}"
            ) from e

        # Verify digest
        computed_digest = self.compute_state_digest(canon_state)
        if computed_digest != stored_digest:
            raise SnapshotCorruptedError(
                f"Snapshot digest mismatch: stored={stored_digest}, "
                f"computed={computed_digest}"
            )

        return SnapshotData(
            snapshot_id=stored_snapshot_id,
            project_id=project_id,
            branch_name=branch_name,
            commit_id=commit_id,
            reducer_version=reducer_version,
            schema_version=schema_version,
            state_digest=stored_digest,
            canon_state=canon_state,
            created_at=created_at,
        )

    def verify_snapshot_consistency(
        self,
        session: Session,
        project_id: str,
        branch_name: str,
        snapshot_id: str,
    ) -> bool:
        """Verify snapshot consistency by comparing with full rebuild.

        Args:
            session: Active database session
            project_id: Project ID
            branch_name: Branch name
            snapshot_id: Snapshot ID to verify

        Returns:
            True if snapshot digest matches full rebuild digest

        Raises:
            ProjectionError: If verification fails
        """
        # Restore from snapshot
        snapshot = self.restore_from_snapshot(
            session, project_id, branch_name, snapshot_id
        )

        # Rebuild from history
        rebuilt_state = self.reconstruct_state_at_commit(
            session, project_id, branch_name, snapshot.commit_id
        )

        # Compare digests
        rebuilt_digest = self.compute_state_digest(rebuilt_state)
        return rebuilt_digest == snapshot.state_digest

    # --- Internal helpers ---

    def _deserialize_delta(self, changeset: dict[str, Any]) -> Any:
        """Deserialize NarrativeDelta from changeset (reuse from commit_service)."""
        # Import here to avoid circular dependency
        from .commit_service import CanonCommitService

        # Create a temporary service instance just for deserialization
        # We don't need the permit verifier for reconstruction
        class DummyPermitVerifier:
            def verify_permit(self, *args, **kwargs):
                return True

        temp_service = CanonCommitService(self.repository, DummyPermitVerifier())
        return temp_service._deserialize_delta(changeset)

    def _apply_operations_to_state(
        self, canon_state: CanonState, delta: Any, commit_id: CommitId
    ) -> CanonState:
        """Apply delta operations to CanonState (historical replay logic)."""
        from ..domain.delta import (
            EndFactOperation,
            SetFactOperation,
            UndoFactOperation,
        )

        for op in delta.operations:
            if isinstance(op, SetFactOperation):
                if canon_state.is_ended(op.subject, op.path):
                    raise ProjectionError(
                        f"Cannot SET_FACT on ended fact {op.path.path}"
                    )
                canon_state = canon_state.set_value(
                    op.subject, op.path, op.value, commit_id
                )

            elif isinstance(op, EndFactOperation):
                current_value, path_exists = canon_state.get_value(op.subject, op.path)
                if not path_exists:
                    raise ProjectionError(
                        f"Cannot END_FACT on non-existent fact {op.path.path}"
                    )
                if canon_state.is_ended(op.subject, op.path):
                    raise ProjectionError(f"Fact already ended {op.path.path}")
                canon_state = canon_state.end_fact(op.subject, op.path, commit_id)

            elif isinstance(op, UndoFactOperation):
                if not canon_state.commit_exists(op.original_commit_ref):
                    raise ProjectionError(
                        f"Original commit not found {op.original_commit_ref}"
                    )

                change = canon_state.get_commit_change(
                    op.original_commit_ref, op.subject, op.path.path
                )
                if change is None:
                    raise ProjectionError(
                        f"No CommitChange for UNDO_FACT "
                        f"{op.original_commit_ref}:{op.subject}:{op.path.path}"
                    )

                if change.project_id != canon_state.project_id:
                    raise ProjectionError("Cannot undo commit from different project")

                if canon_state.has_subsequent_modifications(
                    op.original_commit_ref, op.subject, op.path.path
                ):
                    raise ProjectionError(
                        f"Cannot undo {op.original_commit_ref}, "
                        f"fact has been modified by subsequent commits"
                    )

                # Restore to value_before
                key = (op.subject, op.path.path)
                if change.existed_before:
                    new_facts = tuple(
                        (k, v) for (k, v) in canon_state.facts if k != key
                    ) + ((key, change.value_before),)
                else:
                    new_facts = tuple(
                        (k, v) for (k, v) in canon_state.facts if k != key
                    )
                canon_state = CanonState(
                    project_id=canon_state.project_id,
                    facts=new_facts,
                    tombstones=canon_state.tombstones,
                    commit_history=canon_state.commit_history,
                    commit_changes=canon_state.commit_changes,
                )

        return canon_state

    def _serialize_canon_state(self, canon_state: CanonState) -> dict[str, Any]:
        """Serialize CanonState to JSON-compatible dict."""
        return {
            "project_id": str(canon_state.project_id),
            "facts": [
                {
                    "subject": str(subject),
                    "path": path,
                    "value": self._serialize_value(value),
                }
                for (subject, path), value in canon_state.facts
            ],
            "tombstones": [
                {"subject": str(subject), "path": path}
                for subject, path in canon_state.tombstones
            ],
            "commit_history": [str(cid) for cid in canon_state.commit_history],
            "commit_changes": [
                {
                    "commit_id": str(change.commit_id),
                    "project_id": str(change.project_id),
                    "subject": str(change.subject),
                    "path": change.path,
                    "value_before": self._serialize_value(change.value_before),
                    "existed_before": change.existed_before,
                    "value_after": self._serialize_value(change.value_after),
                    "existed_after": change.existed_after,
                }
                for change in canon_state.commit_changes
            ],
        }

    def _deserialize_canon_state(self, state_dict: dict[str, Any]) -> CanonState:
        """Deserialize CanonState from JSON dict."""
        from ..domain.delta import CommitChange
        from ..domain.identity import EntityId

        # Deserialize facts
        facts = tuple(
            (
                (EntityId(fact["subject"]), fact["path"]),
                self._deserialize_value(fact["value"]),
            )
            for fact in state_dict["facts"]
        )

        # Deserialize tombstones
        tombstones = frozenset(
            (EntityId(tomb["subject"]), tomb["path"])
            for tomb in state_dict["tombstones"]
        )

        # Deserialize commit history
        commit_history = tuple(CommitId(cid) for cid in state_dict["commit_history"])

        # Deserialize commit changes
        commit_changes = tuple(
            CommitChange(
                commit_id=CommitId(change["commit_id"]),
                project_id=ProjectId(change["project_id"]),
                subject=EntityId(change["subject"]),
                path=change["path"],
                value_before=self._deserialize_value(change["value_before"]),
                existed_before=change["existed_before"],
                value_after=self._deserialize_value(change["value_after"]),
                existed_after=change["existed_after"],
            )
            for change in state_dict.get("commit_changes", [])
        )

        return CanonState(
            project_id=ProjectId(state_dict["project_id"]),
            facts=facts,
            tombstones=tombstones,
            commit_history=commit_history,
            commit_changes=commit_changes,
        )

    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for JSON storage."""
        from ..domain.delta import FactValue

        if value is None:
            return None
        if isinstance(value, FactValue):
            return value.value
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        return value

    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize value from JSON storage."""
        from ..domain.delta import FactValue

        if value == "UNKNOWN":
            return FactValue.UNKNOWN
        return value
