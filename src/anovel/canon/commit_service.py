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
    CanonState,
    CommitId,
    DeltaId,
    DeltaReducer,
    EndFactOperation,
    EvidenceRef,
    ExpectAbsent,
    ExpectPresent,
    ExpectUnknown,
    ExpectValue,
    FactValue,
    NarrativeDelta,
    OperationType,
    Precondition,
    SetFactOperation,
    UndoFactOperation,
    get_fact_path,
)
from ..domain.identity import EntityId, ProjectId
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

        Single transaction eliminating TOCTOU races:
        1. Validate permit (external, no database state)
        2. Normalize and compute payload hash
        3. BEGIN TRANSACTION
        4. Check idempotency (same scope+key)
        5. If exists: validate payload hash, return receipt (skip validation)
        6. Lock execution_control, validate version
        7. Get and verify expected branch HEAD
        8. Reconstruct CanonState from HEAD in this transaction view
        9. Validate NarrativeDelta with DeltaReducer (preconditions, types)
        10. INSERT canon_commit
        11. INSERT canon_event
        12. UPDATE branch_head (CAS)
        13. COMMIT and return receipt

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
        # Step 1: Validate permit (no database access)
        self._validate_permit(request.permit, request.project_id, request.branch_name)

        # Step 2: Compute payload hash (deterministic, no database access)
        payload_hash = self._compute_payload_hash(request.narrative_delta)

        # Step 3-13: Single atomic transaction
        commit_id = f"commit-{uuid.uuid4().hex[:12]}"
        event_id = f"event-{uuid.uuid4().hex[:12]}"

        with self.repository.transaction() as session:
            # Step 4-5: Check idempotency FIRST
            from sqlalchemy import text

            existing = session.execute(
                text(
                    """
                    SELECT commit_id, payload_hash, committed_at
                    FROM canon_commit
                    WHERE project_id = :project_id
                      AND branch_name = :branch_name
                      AND idempotency_key = :idempotency_key
                """
                ),
                {
                    "project_id": request.project_id,
                    "branch_name": request.branch_name,
                    "idempotency_key": request.idempotency_key,
                },
            ).fetchone()

            if existing:
                existing_commit_id, existing_payload_hash, existing_committed_at = (
                    existing
                )
                # Same key + same payload = idempotent retry
                if existing_payload_hash == payload_hash:
                    return CommitReceipt(
                        commit_id=existing_commit_id,
                        project_id=request.project_id,
                        branch_name=request.branch_name,
                        idempotency_key=request.idempotency_key,
                        committed_at=existing_committed_at,
                        payload_hash=payload_hash,
                        recovered=True,
                    )
                # Same key + different payload = conflict
                else:
                    from .repository import IdempotencyConflictError

                    raise IdempotencyConflictError(
                        f"Idempotency key {request.idempotency_key} already used with different payload"
                    )

            # Step 6: Lock execution_control and validate version
            from .repository import ExecutionVersionMismatchError

            current_version = self.repository.get_execution_version(
                session, request.project_id, request.branch_name, lock=True
            )
            if current_version is None:
                raise CanonRepositoryError(
                    f"Execution control not initialized for {request.project_id}/{request.branch_name}"
                )
            if current_version != request.permit.execution_version:
                raise ExecutionVersionMismatchError(
                    f"Execution version mismatch: expected {request.permit.execution_version}, found {current_version}"
                )

            # Step 7: Get expected branch HEAD
            current_head = self.repository.get_branch_head(
                session, request.project_id, request.branch_name
            )
            if current_head != request.parent_commit_id:
                raise CanonRepositoryError(
                    f"Parent commit mismatch: expected {request.parent_commit_id}, current HEAD is {current_head}"
                )

            # Step 8: Reconstruct Canon state from HEAD within this transaction
            canon_state = self._reconstruct_canon_state_transactional(
                session, request.project_id, request.branch_name
            )

            # Step 9: Validate NarrativeDelta structure and preconditions
            self._validate_narrative_delta(request.narrative_delta, canon_state)

            # Step 10: INSERT canon_commit
            if request.parent_commit_id is None:
                self.repository.create_root_commit(
                    session,
                    request.project_id,
                    request.branch_name,
                    commit_id,
                    request.idempotency_key,
                    payload_hash,
                    self._serialize_delta(request.narrative_delta),
                    request.permit.permit_id,
                )
            else:
                self.repository.create_commit(
                    session,
                    request.project_id,
                    request.branch_name,
                    commit_id,
                    request.parent_commit_id,
                    request.idempotency_key,
                    payload_hash,
                    self._serialize_delta(request.narrative_delta),
                    request.permit.permit_id,
                )

            # Get committed_at timestamp
            committed_at = session.execute(
                text(
                    """
                    SELECT committed_at FROM canon_commit
                    WHERE project_id = :project_id
                      AND branch_name = :branch_name
                      AND commit_id = :commit_id
                """
                ),
                {
                    "project_id": request.project_id,
                    "branch_name": request.branch_name,
                    "commit_id": commit_id,
                },
            ).scalar()

            # Step 11: Create canon event for new commit
            self._create_canon_event(
                session=session,
                project_id=request.project_id,
                branch_name=request.branch_name,
                event_id=event_id,
                commit_id=commit_id,
                event_type="NARRATIVE_COMMIT",
                event_data={"delta_id": str(request.narrative_delta.delta_id)},
            )

            # Step 12: Advance HEAD (CAS)
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

        # Step 13: Transaction committed, return receipt
        return CommitReceipt(
            commit_id=commit_id,
            project_id=request.project_id,
            branch_name=request.branch_name,
            idempotency_key=request.idempotency_key,
            committed_at=committed_at,
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

    def _reconstruct_canon_state_transactional(
        self, session: Any, project_id: str, branch_name: str
    ) -> CanonState:
        """Reconstruct Canon state from branch HEAD within active transaction.

        Args:
            session: Active database session (within transaction)
            project_id: Project ID
            branch_name: Branch name

        Returns:
            CanonState reconstructed from all commits up to HEAD

        Raises:
            CanonRepositoryError: If state reconstruction fails
        """
        # Get current HEAD
        head_commit_id = self.repository.get_branch_head(
            session, project_id, branch_name
        )

        # Initialize empty Canon state
        canon_state = CanonState(
            project_id=ProjectId(project_id),
            facts=(),
            tombstones=frozenset(),
            commit_history=(),
            commit_changes=(),
        )

        # If no HEAD, return empty state
        if head_commit_id is None:
            return canon_state

        # Traverse commit chain from HEAD to root
        commit_chain: list[str] = []
        current_commit_id = head_commit_id
        seen_commits: set[str] = set()

        while current_commit_id is not None:
            # Detect cycles
            if current_commit_id in seen_commits:
                raise CanonRepositoryError(
                    f"Commit cycle detected at {current_commit_id}"
                )
            seen_commits.add(current_commit_id)
            commit_chain.append(current_commit_id)

            # Limit chain length to prevent infinite loops
            if len(commit_chain) > 10000:
                raise CanonRepositoryError(
                    "Commit chain exceeds maximum length of 10000"
                )

            commit = self.repository.get_commit(
                session, project_id, branch_name, current_commit_id
            )
            if commit is None:
                raise CanonRepositoryError(
                    f"Commit not found in chain: {current_commit_id}"
                )
            current_commit_id = commit["parent_commit_id"]

        # Reverse to get root-to-HEAD order
        commit_chain.reverse()

        # Apply commits in order with domain constraint enforcement
        for commit_id in commit_chain:
            commit = self.repository.get_commit(
                session, project_id, branch_name, commit_id
            )
            if commit is None:
                raise CanonRepositoryError(f"Commit disappeared: {commit_id}")

            # Deserialize changeset
            changeset = commit["changeset"]
            if isinstance(changeset, str):
                changeset = json.loads(changeset)

            # Skip root commits (they have no operations)
            if changeset.get("type") == "root":
                # Add to commit history for UNDO_FACT tracking
                canon_state = CanonState(
                    project_id=canon_state.project_id,
                    facts=canon_state.facts,
                    tombstones=canon_state.tombstones,
                    commit_history=canon_state.commit_history + (CommitId(commit_id),),
                    commit_changes=canon_state.commit_changes,
                )
                continue

            # Reconstruct NarrativeDelta from changeset
            delta = self._deserialize_delta(changeset)

            # Add commit to history BEFORE applying operations
            canon_state = CanonState(
                project_id=canon_state.project_id,
                facts=canon_state.facts,
                tombstones=canon_state.tombstones,
                commit_history=canon_state.commit_history + (CommitId(commit_id),),
                commit_changes=canon_state.commit_changes,
            )

            # Apply operations using proper domain logic with CommitChange tracking
            # For historical reconstruction, we trust the stored operations were valid
            # when originally committed, but still enforce domain constraints
            try:
                for op in delta.operations:
                    if isinstance(op, SetFactOperation):
                        # Check domain constraints without re-validating preconditions
                        # (preconditions were valid at commit time, state has changed since)
                        if canon_state.is_ended(op.subject, op.path):
                            raise CanonRepositoryError(
                                f"Historical replay: cannot SET_FACT on ended fact {op.path.path}"
                            )
                        # Apply with CommitChange tracking
                        canon_state = canon_state.set_value(
                            op.subject, op.path, op.value, CommitId(commit_id)
                        )

                    elif isinstance(op, EndFactOperation):
                        # Verify fact exists before ending
                        current_value, path_exists = canon_state.get_value(
                            op.subject, op.path
                        )
                        if not path_exists:
                            raise CanonRepositoryError(
                                f"Historical replay: cannot END_FACT on non-existent fact {op.path.path}"
                            )
                        if canon_state.is_ended(op.subject, op.path):
                            raise CanonRepositoryError(
                                f"Historical replay: fact already ended {op.path.path}"
                            )
                        # Apply with CommitChange tracking
                        canon_state = canon_state.end_fact(
                            op.subject, op.path, CommitId(commit_id)
                        )

                    elif isinstance(op, UndoFactOperation):
                        # UNDO_FACT: Restore to state before original commit
                        # Verify original commit exists in history
                        if not canon_state.commit_exists(op.original_commit_ref):
                            raise CanonRepositoryError(
                                f"Historical replay: original commit not found {op.original_commit_ref}"
                            )

                        # Get the CommitChange record
                        change = canon_state.get_commit_change(
                            op.original_commit_ref, op.subject, op.path.path
                        )
                        if change is None:
                            raise CanonRepositoryError(
                                f"Historical replay: no CommitChange for UNDO_FACT "
                                f"{op.original_commit_ref}:{op.subject}:{op.path.path}"
                            )

                        # Verify project scope
                        if change.project_id != canon_state.project_id:
                            raise CanonRepositoryError(
                                "Historical replay: cannot undo commit from different project"
                            )

                        # Check for subsequent modifications (ABA protection)
                        if canon_state.has_subsequent_modifications(
                            op.original_commit_ref, op.subject, op.path.path
                        ):
                            raise CanonRepositoryError(
                                f"Historical replay: cannot undo {op.original_commit_ref}, "
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

            except Exception as e:
                raise CanonRepositoryError(
                    f"Failed to reconstruct state at commit {commit_id}: {e}"
                ) from e

        return canon_state

    def _deserialize_delta(self, changeset: dict[str, Any]) -> NarrativeDelta:
        """Deserialize NarrativeDelta from changeset dict.

        Args:
            changeset: Serialized delta from database

        Returns:
            Reconstructed NarrativeDelta

        Raises:
            InvalidDeltaError: If deserialization fails
        """
        try:
            # Deserialize operations
            operations: list[
                SetFactOperation | EndFactOperation | UndoFactOperation
            ] = []
            for op_data in changeset.get("operations", []):
                op_type = OperationType(op_data["operation_type"])

                if op_type == OperationType.SET_FACT:
                    # Deserialize precondition
                    precond_data = op_data.get("precondition")
                    if precond_data is None:
                        raise InvalidDeltaError("SET_FACT missing precondition")

                    precondition = self._deserialize_precondition(precond_data)

                    # Deserialize value
                    value = op_data["value"]
                    if value == "UNKNOWN":
                        value = FactValue.UNKNOWN

                    operation = SetFactOperation(
                        subject=EntityId(op_data["subject"]),
                        scope=ProjectId(op_data["scope"]),
                        path=get_fact_path(op_data["path"]["path"]),
                        value=value,
                        precondition=precondition,
                        evidence=EvidenceRef(
                            source_type=op_data["evidence"]["source_type"],
                            source_ref=op_data["evidence"]["source_ref"],
                            content_hash=op_data["evidence"]["content_hash"],
                        ),
                    )
                    operations.append(operation)

                elif op_type == OperationType.END_FACT:
                    precond_data = op_data.get("precondition")
                    if precond_data is None:
                        raise InvalidDeltaError("END_FACT missing precondition")

                    precondition = self._deserialize_precondition(precond_data)

                    end_operation = EndFactOperation(
                        subject=EntityId(op_data["subject"]),
                        scope=ProjectId(op_data["scope"]),
                        path=get_fact_path(op_data["path"]["path"]),
                        precondition=precondition,
                        evidence=EvidenceRef(
                            source_type=op_data["evidence"]["source_type"],
                            source_ref=op_data["evidence"]["source_ref"],
                            content_hash=op_data["evidence"]["content_hash"],
                        ),
                    )
                    operations.append(end_operation)

                elif op_type == OperationType.UNDO_FACT:
                    precond_data = op_data.get("precondition")
                    if (
                        precond_data is None
                        or precond_data.get("type") != "ExpectValue"
                    ):
                        raise InvalidDeltaError(
                            "UNDO_FACT must have ExpectValue precondition"
                        )

                    undo_operation = UndoFactOperation(
                        subject=EntityId(op_data["subject"]),
                        scope=ProjectId(op_data["scope"]),
                        path=get_fact_path(op_data["path"]["path"]),
                        original_commit_ref=CommitId(op_data["original_commit_ref"]),
                        precondition=ExpectValue(precond_data["expected_value"]),
                        evidence=EvidenceRef(
                            source_type=op_data["evidence"]["source_type"],
                            source_ref=op_data["evidence"]["source_ref"],
                            content_hash=op_data["evidence"]["content_hash"],
                        ),
                    )
                    operations.append(undo_operation)

            # Reconstruct NarrativeDelta
            return NarrativeDelta(
                delta_id=DeltaId(changeset["delta_id"]),
                project_id=ProjectId(changeset["project_id"]),
                operations=tuple(operations),
                source_chapter=changeset.get("source_chapter"),
                created_at=datetime.fromisoformat(changeset["created_at"]),
                authority=changeset["authority"],
                provenance=tuple(tuple(kv) for kv in changeset.get("provenance", [])),
            )

        except (KeyError, ValueError, TypeError) as e:
            raise InvalidDeltaError(f"Failed to deserialize delta: {e}") from e

    def _deserialize_precondition(self, precond_data: dict[str, Any]) -> Precondition:
        """Deserialize precondition from dict.

        Args:
            precond_data: Serialized precondition

        Returns:
            Precondition instance

        Raises:
            InvalidDeltaError: If deserialization fails
        """
        precond_type = precond_data.get("type")
        if precond_type == "ExpectValue":
            return ExpectValue(precond_data["expected_value"])
        elif precond_type == "ExpectAbsent":
            return ExpectAbsent()
        elif precond_type == "ExpectPresent":
            return ExpectPresent()
        elif precond_type == "ExpectUnknown":
            return ExpectUnknown()
        else:
            raise InvalidDeltaError(f"Unknown precondition type: {precond_type}")

    def _validate_narrative_delta(
        self, delta: NarrativeDelta, canon_state: CanonState
    ) -> None:
        """Validate NarrativeDelta structure, project scope, and preconditions.

        Args:
            delta: NarrativeDelta to validate
            canon_state: Current Canon state for precondition evaluation

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

        # Validate preconditions against current Canon state
        from ..domain.delta import ReducerError

        reducer = DeltaReducer()
        try:
            reducer.apply_delta(canon_state, delta)
        except ReducerError as e:
            raise InvalidDeltaError(f"Delta precondition validation failed: {e}") from e

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
        serialized_ops = []
        for op in delta.operations:
            if isinstance(op, (SetFactOperation, EndFactOperation, UndoFactOperation)):
                serialized_ops.append(self._serialize_operation(op))
            else:
                raise InvalidDeltaError(f"Unknown operation type: {type(op)}")

        return {
            "delta_id": str(delta.delta_id),
            "project_id": str(delta.project_id),
            "source_chapter": delta.source_chapter,
            "created_at": delta.created_at.isoformat(),
            "authority": delta.authority,
            "provenance": [list(kv) for kv in delta.provenance],
            "operations": serialized_ops,
        }

    def _serialize_operation(
        self, op: SetFactOperation | EndFactOperation | UndoFactOperation
    ) -> dict[str, Any]:
        """Serialize operation with all required fields.

        Args:
            op: Operation to serialize

        Returns:
            Dictionary with complete operation data
        """
        base: dict[str, Any] = {
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

        return base

    def _serialize_value(self, value: Any) -> Any:
        """Serialize fact value, handling special types.

        Args:
            value: Value to serialize

        Returns:
            JSON-serializable value

        Raises:
            InvalidDeltaError: If value type not supported
        """
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
        # Reject unsupported types
        raise InvalidDeltaError(
            f"Unsupported value type for serialization: {type(value)}"
        )

    def _serialize_precondition(self, precondition: Any) -> dict[str, Any] | None:
        """Serialize precondition variant.

        Args:
            precondition: Precondition to serialize

        Returns:
            Dictionary with precondition type and data
        """
        if precondition is None:
            return None

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
            text(
                """
                INSERT INTO canon_event
                (project_id, branch_name, event_id, commit_id, event_type, event_data)
                VALUES (:project_id, :branch_name, :event_id, :commit_id, :event_type, :event_data)
            """
            ),
            {
                "project_id": project_id,
                "branch_name": branch_name,
                "event_id": event_id,
                "commit_id": commit_id,
                "event_type": event_type,
                "event_data": json.dumps(event_data),
            },
        )
