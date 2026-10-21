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
    PermitVerifier: Permit verification interface
    NoPermitError: Raised when valid permit missing
    InvalidDeltaError: Raised when NarrativeDelta validation fails

Contract: V2-010 per ADR-006 and 03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from ..domain.delta import (
    EndFactOperation,
    NarrativeDelta,
    OperationType,
    SetFactOperation,
    UndoFactOperation,
)
from .hash import canonical_hash
from .repository import (
    CanonRepository,
    CanonRepositoryError,
)


class NoPermitError(Exception):
    """Raised when commit attempted without valid execution permit."""

    pass


class InvalidDeltaError(Exception):
    """Raised when NarrativeDelta validation fails."""

    pass


class PermitVerifier(Protocol):
    """Protocol for verifying execution permits.

    Implementations must validate permit authenticity, scope, and validity.
    Must fail-closed: reject when verification uncertain or unavailable.
    """

    def verify_permit(
        self, permit_id: str, project_id: str, branch_name: str, execution_version: int
    ) -> bool:
        """Verify permit is valid for given scope.

        Args:
            permit_id: Permit identifier to verify
            project_id: Target project ID
            branch_name: Target branch name
            execution_version: Expected execution version

        Returns:
            True if permit is valid for the given scope

        Raises:
            NoPermitError: If permit verification fails or is unavailable
        """
        ...


@dataclass(frozen=True)
class ExecutionPermit:
    """Execution permit authorizing Canon commits.

    NOTE: This dataclass is for structured permit representation only.
    Validity must be verified through PermitVerifier, not self-asserted.
    """

    permit_id: str
    project_id: str
    branch_name: str
    execution_version: int
    issued_at: datetime


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
    - Execution permit validation via PermitVerifier
    - NarrativeDelta business validation
    - Atomic commit + event + HEAD transaction
    - Idempotent receipt recovery
    - Execution version fencing

    Reuses CanonRepository for all PostgreSQL operations.
    """

    def __init__(self, repository: CanonRepository, permit_verifier: PermitVerifier):
        """Initialize service with Canon repository and permit verifier.

        Args:
            repository: CanonRepository instance for database operations
            permit_verifier: PermitVerifier for validating execution permits
        """
        self.repository = repository
        self.permit_verifier = permit_verifier

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
        """Validate execution permit via PermitVerifier.

        Args:
            permit: Execution permit to validate
            project_id: Target project ID
            branch_name: Target branch name

        Raises:
            NoPermitError: If permit invalid or verification fails
        """
        # Verify permit scope matches request
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

        # Verify permit through verifier (fail-closed)
        try:
            is_valid = self.permit_verifier.verify_permit(
                permit.permit_id, project_id, branch_name, permit.execution_version
            )
            if not is_valid:
                raise NoPermitError(f"Permit {permit.permit_id} verification failed")
        except NoPermitError:
            raise
        except Exception as e:
            raise NoPermitError(
                f"Permit verification error for {permit.permit_id}: {e}"
            ) from e

    def _validate_narrative_delta(self, delta: NarrativeDelta) -> None:
        """Validate NarrativeDelta structure and project scope.

        Args:
            delta: NarrativeDelta to validate

        Raises:
            InvalidDeltaError: If validation fails
        """
        # Validate all operations are registered types
        for op in delta.operations:
            if op.operation_type not in OperationType:
                raise InvalidDeltaError(
                    f"Unregistered operation type: {op.operation_type}"
                )

            # Validate operation schema completeness
            try:
                op.validate_schema()
            except ValueError as e:
                raise InvalidDeltaError(f"Operation validation failed: {e}") from e

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
        """Serialize NarrativeDelta to complete, deterministic dict.

        Preserves all novel facts, operation details, and metadata.
        Must be reversible for state reconstruction.

        Args:
            delta: NarrativeDelta to serialize

        Returns:
            Dictionary with complete delta representation
        """
        return {
            "delta_id": str(delta.delta_id),
            "project_id": str(delta.project_id),
            "source_chapter": delta.source_chapter,
            "created_at": delta.created_at.isoformat(),
            "authority": delta.authority,
            "provenance": [list(kv) for kv in delta.provenance],
            "operations": [self._serialize_operation(op) for op in delta.operations],
        }

    def _serialize_operation(self, op: Any) -> dict[str, Any]:
        """Serialize operation with all required fields.

        Args:
            op: Operation to serialize (SetFactOperation, EndFactOperation, or UndoFactOperation)

        Returns:
            Dictionary with complete operation data
        """
        base = {
            "operation_type": op.operation_type.value,
            "operation_version": op.operation_version,
        }

        if isinstance(op, SetFactOperation):
            # Serialize SetFactOperation with all fields
            base.update(
                {
                    "subject": str(op.subject) if op.subject else None,
                    "scope": str(op.scope) if op.scope else None,
                    "path": {
                        "path": op.path.path if op.path else None,
                        "expected_type": op.path.expected_type.__name__
                        if op.path
                        else None,
                    },
                    "value": self._serialize_value(op.value),
                    "precondition": self._serialize_precondition(op.precondition),
                    "evidence": {
                        "source_type": op.evidence.source_type if op.evidence else None,
                        "source_ref": op.evidence.source_ref if op.evidence else None,
                        "content_hash": op.evidence.content_hash
                        if op.evidence
                        else None,
                    },
                }
            )
        elif isinstance(op, EndFactOperation):
            base.update(
                {
                    "subject": str(op.subject) if op.subject else None,
                    "scope": str(op.scope) if op.scope else None,
                    "path": {
                        "path": op.path.path if op.path else None,
                        "expected_type": op.path.expected_type.__name__
                        if op.path
                        else None,
                    },
                    "precondition": self._serialize_precondition(op.precondition),
                    "evidence": {
                        "source_type": op.evidence.source_type if op.evidence else None,
                        "source_ref": op.evidence.source_ref if op.evidence else None,
                        "content_hash": op.evidence.content_hash
                        if op.evidence
                        else None,
                    },
                }
            )
        elif isinstance(op, UndoFactOperation):
            base.update(
                {
                    "subject": str(op.subject) if op.subject else None,
                    "scope": str(op.scope) if op.scope else None,
                    "path": {
                        "path": op.path.path if op.path else None,
                        "expected_type": op.path.expected_type.__name__
                        if op.path
                        else None,
                    },
                    "original_commit_ref": str(op.original_commit_ref)
                    if hasattr(op, "original_commit_ref") and op.original_commit_ref
                    else None,
                    "evidence": {
                        "source_type": op.evidence.source_type if op.evidence else None,
                        "source_ref": op.evidence.source_ref if op.evidence else None,
                        "content_hash": op.evidence.content_hash
                        if op.evidence
                        else None,
                    },
                }
            )

        return base

    def _serialize_value(self, value: Any) -> Any:
        """Serialize fact value, handling special types.

        Args:
            value: Value to serialize

        Returns:
            JSON-serializable value
        """
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
        # For other types, convert to string
        return str(value)

    def _serialize_precondition(self, precondition: Any) -> dict[str, Any] | None:
        """Serialize precondition variant.

        Args:
            precondition: Precondition to serialize

        Returns:
            Dictionary with precondition type and data
        """
        if precondition is None:
            return None

        from ..domain.delta import (
            ExpectAbsent,
            ExpectPresent,
            ExpectUnknown,
            ExpectValue,
        )

        if isinstance(precondition, ExpectValue):
            return {
                "type": "ExpectValue",
                "expected_value": self._serialize_value(precondition.expected_value),
            }
        elif isinstance(precondition, ExpectAbsent):
            return {"type": "ExpectAbsent"}
        elif isinstance(precondition, ExpectPresent):
            return {"type": "ExpectPresent"}
        elif isinstance(precondition, ExpectUnknown):
            return {"type": "ExpectUnknown"}
        else:
            return {"type": "Unknown"}

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
