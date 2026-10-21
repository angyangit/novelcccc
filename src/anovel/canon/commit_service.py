"""CanonCommitService: Unified novel narrative commit business service.

V2-010 implementation that provides the single authoritative entry point for
committing novel narrative changes (characters, world state, plot events) to
Canon persistent history.

Reuses V2-009 CanonRepository for all database operations. Adds business-level
validation, permit enforcement, and atomic commit+event+HEAD transactions.

Public API:
    CanonCommitService: Main service class
    CommitReceipt: Commit receipt with recovery information
    CommitRequest: Structured commit request
    NoPermitError: Raised when valid permit missing
    InvalidDeltaError: Raised when NarrativeDelta validation fails

Contract: V2-010 per ADR-006 and 03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..domain.delta import NarrativeDelta
from ..domain.identity import ProjectId
from .hash import canonical_hash
from .repository import (
    CanonRepository,
    CanonRepositoryError,
    ExecutionVersionMismatchError,
    IdempotencyConflictError,
)


class NoPermitError(Exception):
    """Raised when commit attempted without valid execution permit."""

    pass


class InvalidDeltaError(Exception):
    """Raised when NarrativeDelta validation fails."""

    pass


@dataclass(frozen=True)
class ExecutionPermit:
    """Execution permit authorizing Canon commits.

    For V2-010 minimal implementation, represents verified authorization.
    Full permit issuance and verification deferred to future work.
    """

    permit_id: str
    project_id: str
    branch_name: str
    execution_version: int
    issued_at: datetime
    valid: bool = True


@dataclass(frozen=True)
class CommitRequest:
    """Structured Canon commit request."""

    project_id: str
    branch_name: str
    parent_commit_id: str | None
    idempotency_key: str
    narrative_delta: NarrativeDelta
    permit: ExecutionPermit


@dataclass(frozen=True)
class CommitReceipt:
    """Canon commit receipt with recovery information."""

    commit_id: str
    project_id: str
    branch_name: str
    idempotency_key: str
    committed_at: datetime
    payload_hash: str
    recovered: bool = False


class CanonCommitService:
    """Unified business service for Canon narrative commits.

    Single authoritative entry point for all Canon commits. Enforces:
    - Execution permit validation
    - NarrativeDelta business validation
    - Atomic commit + event + HEAD transaction
    - Idempotent receipt recovery
    - Execution version fencing

    Reuses CanonRepository for all PostgreSQL operations.
    """

    def __init__(self, repository: CanonRepository):
        """Initialize service with Canon repository.

        Args:
            repository: CanonRepository instance for database operations
        """
        self.repository = repository

    def commit_narrative_delta(
        self,
        request: CommitRequest,
    ) -> CommitReceipt:
        """Atomically commit novel narrative changes to Canon authority.

        Single transaction:
        1. Validate permit and execution version
        2. Validate NarrativeDelta structure
        3. Check idempotency (recover or conflict)
        4. INSERT canon_commit
        5. INSERT canon_event
        6. UPDATE branch_head (CAS)
        7. Return receipt

        Args:
            request: Structured commit request with delta and permit

        Returns:
            CommitReceipt with commit_id and recovery information

        Raises:
            NoPermitError: If permit invalid or missing
            InvalidDeltaError: If NarrativeDelta validation fails
            ExecutionVersionMismatchError: If execution version stale
            IdempotencyConflictError: If same key with different payload
            CanonRepositoryError: For other repository errors
        """
        # Step 1: Validate permit
        self._validate_permit(request.permit, request.project_id, request.branch_name)

        # Step 2: Validate NarrativeDelta
        self._validate_narrative_delta(request.narrative_delta)

        # Step 3: Compute payload hash
        payload_hash = self._compute_payload_hash(request.narrative_delta)

        # Step 4: Generate commit_id and event_id
        import uuid

        commit_id = f"commit-{uuid.uuid4().hex[:12]}"
        event_id = f"event-{uuid.uuid4().hex[:12]}"

        # Step 5: Atomic commit transaction
        with self.repository.transaction() as session:
            # Use repository's idempotent commit with fencing
            receipt_data = self.repository.create_commit_with_fencing(
                session=session,
                project_id=request.project_id,
                branch_name=request.branch_name,
                commit_id=commit_id,
                parent_commit_id=request.parent_commit_id,
                expected_execution_version=request.permit.execution_version,
                idempotency_key=request.idempotency_key,
                payload_hash=payload_hash,
                changeset=self._serialize_delta(request.narrative_delta),
                permit_ref=request.permit.permit_id,
            )

            # If recovered, return early (no new event/HEAD update needed)
            if receipt_data["recovered"]:
                return CommitReceipt(
                    commit_id=receipt_data["commit_id"],
                    project_id=request.project_id,
                    branch_name=request.branch_name,
                    idempotency_key=receipt_data["idempotency_key"],
                    committed_at=receipt_data["committed_at"],
                    payload_hash=payload_hash,
                    recovered=True,
                )

            # Step 6: Create canon event for new commit
            self._create_canon_event(
                session=session,
                project_id=request.project_id,
                branch_name=request.branch_name,
                event_id=event_id,
                commit_id=commit_id,
                event_type="NARRATIVE_COMMIT",
                event_data={"delta_id": str(request.narrative_delta.delta_id)},
            )

            # Step 7: Advance HEAD (CAS)
            head_updated = self.repository.update_branch_head_cas(
                session=session,
                project_id=request.project_id,
                branch_name=request.branch_name,
                new_head_commit_id=commit_id,
                expected_head_commit_id=request.parent_commit_id,
            )

            if not head_updated:
                raise CanonRepositoryError(
                    f"HEAD CAS failed: expected parent {request.parent_commit_id}, "
                    f"but HEAD changed concurrently"
                )

        # Step 8: Return receipt for new commit
        return CommitReceipt(
            commit_id=commit_id,
            project_id=request.project_id,
            branch_name=request.branch_name,
            idempotency_key=request.idempotency_key,
            committed_at=receipt_data["committed_at"],
            payload_hash=payload_hash,
            recovered=False,
        )

    def _validate_permit(
        self, permit: ExecutionPermit, project_id: str, branch_name: str
    ) -> None:
        """Validate execution permit.

        Args:
            permit: Execution permit to validate
            project_id: Target project ID
            branch_name: Target branch name

        Raises:
            NoPermitError: If permit invalid
        """
        if not permit.valid:
            raise NoPermitError(f"Permit {permit.permit_id} is not valid")

        if permit.project_id != project_id:
            raise NoPermitError(
                f"Permit project mismatch: permit for {permit.project_id}, "
                f"commit for {project_id}"
            )

        if permit.branch_name != branch_name:
            raise NoPermitError(
                f"Permit branch mismatch: permit for {permit.branch_name}, "
                f"commit for {branch_name}"
            )

    def _validate_narrative_delta(self, delta: NarrativeDelta) -> None:
        """Validate NarrativeDelta structure.

        Args:
            delta: NarrativeDelta to validate

        Raises:
            InvalidDeltaError: If validation fails
        """
        if not delta.operations:
            raise InvalidDeltaError("NarrativeDelta must have at least one operation")

        # Validate all operations are registered types
        from ..domain.delta import OperationType

        for op in delta.operations:
            if op.operation_type not in OperationType:
                raise InvalidDeltaError(
                    f"Unregistered operation type: {op.operation_type}"
                )

    def _compute_payload_hash(self, delta: NarrativeDelta) -> str:
        """Compute canonical hash of NarrativeDelta payload.

        Args:
            delta: NarrativeDelta to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        # Serialize to dict for canonical hashing
        payload_dict = self._serialize_delta(delta)
        return canonical_hash(payload_dict)

    def _serialize_delta(self, delta: NarrativeDelta) -> dict[str, Any]:
        """Serialize NarrativeDelta to dict.

        Args:
            delta: NarrativeDelta to serialize

        Returns:
            Dictionary representation
        """
        return {
            "delta_id": str(delta.delta_id),
            "project_id": str(delta.project_id),
            "created_at": delta.created_at.isoformat(),
            "description": delta.description,
            "operations": [
                {
                    "operation_type": op.operation_type.value,
                    "operation_version": op.operation_version,
                }
                for op in delta.operations
            ],
        }

    def _create_canon_event(
        self,
        session: Any,
        project_id: str,
        branch_name: str,
        event_id: str,
        commit_id: str,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Create canon event record.

        Args:
            session: Active database session
            project_id: Project ID
            branch_name: Branch name
            event_id: Event ID
            commit_id: Associated commit ID
            event_type: Event type
            event_data: Event data
        """
        import json

        from sqlalchemy import text

        session.execute(
            text("""
                INSERT INTO canon_event
                (project_id, branch_name, event_id, commit_id, event_type, event_data)
                VALUES (:project_id, :branch_name, :event_id, :commit_id, :event_type, :event_data)
            """),
            {
                "project_id": project_id,
                "branch_name": branch_name,
                "event_id": event_id,
                "commit_id": commit_id,
                "event_type": event_type,
                "event_data": json.dumps(event_data),
            },
        )
