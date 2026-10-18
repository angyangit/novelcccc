"""
ANovelOS V2 NarrativeDelta Domain Model.

This module implements finite change language and reducer preconditions for
narrative state changes. NarrativeDelta represents proposed changes, not Canon state.

Public API:
    Types:
        DeltaId, NarrativeDelta, Operation, OperationType
        Precondition (ExpectValue | ExpectAbsent | ExpectPresent | ExpectUnknown)
        SetFactOperation, EndFactOperation, UndoFactOperation
        EvidenceRef, FactPath, FactValue, ValidationResult

    Operations:
        validate_operation, evaluate_precondition

Invariants:
    - NarrativeDelta is proposal, not Canon state (no commit authority)
    - Operations are REGISTERED, VERSIONED, TYPED (finite registry)
    - Preconditions required for all SET_FACT (no implicit overwrite)
    - UNKNOWN (state value) ≠ NO_CHANGE (empty operations) ≠ UNDO_FACT (operation type)
    - Reducer pure, deterministic, fail-closed, provider-independent
    - No database access, no Canon persistence, no LLM provider calls

Contract: V2-008 Implementation per ADR-004
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal, NewType, Protocol

from .identity import EntityId, ProjectId

# --- Type Aliases ---

DeltaId = NewType("DeltaId", str)
"""Unique identifier for narrative deltas (UUID v4 format)."""

CommitId = NewType("CommitId", str)
"""Reference to Canon commit (for UNDO_FACT)."""

# --- Enums ---


class OperationType(Enum):
    """
    Registered operation types for V2-008.

    Only these three operations are registered in P1.
    Unregistered operations cannot become commit proposals.
    """
    SET_FACT = "SET_FACT"
    END_FACT = "END_FACT"
    UNDO_FACT = "UNDO_FACT"


class FactValue(Enum):
    """
    Special fact values with distinct semantics.

    UNKNOWN: Fact exists but value is unknown (not None, not absent).
    """
    UNKNOWN = "UNKNOWN"


# --- Evidence Reference ---


@dataclass(frozen=True)
class EvidenceRef:
    """
    Evidence reference for traceability.

    Points to source text or artifact with content hash for verification.

    Attributes:
        source_type: Evidence source type (TEXT or ARTIFACT)
        source_ref: Specific reference (e.g., "chapter_5:paragraph_3")
        content_hash: SHA-256 hash of source content
    """
    source_type: Literal["TEXT", "ARTIFACT"]
    source_ref: str
    content_hash: str


# --- Fact Path ---


@dataclass(frozen=True)
class FactPath:
    """
    Typed fact path for state access.

    Each path has a registered type. Value must match path type.

    Attributes:
        path: Dot-notation path (e.g., "characters.alice.age")
        expected_type: Python type for this path
    """
    path: str
    expected_type: type


# --- Precondition Types ---


@dataclass(frozen=True)
class ExpectValue:
    """
    Precondition: path must have specific value.

    Semantics: current_value == expected_value
    Failure: value mismatch → reject
    """
    expected_value: Any


@dataclass(frozen=True)
class ExpectAbsent:
    """
    Precondition: path must not exist.

    Semantics: path not in Canon
    Failure: path exists → reject
    Use case: prevent duplicate creation
    """
    pass


@dataclass(frozen=True)
class ExpectPresent:
    """
    Precondition: path must exist (any value).

    Semantics: path exists in Canon
    Failure: path absent → reject
    Use case: update existing fact
    """
    pass


@dataclass(frozen=True)
class ExpectUnknown:
    """
    Precondition: path value must be UNKNOWN.

    Semantics: path exists with value FactValue.UNKNOWN
    Failure: path absent or has known value → reject
    Use case: resolve previous UNKNOWN
    """
    pass


Precondition = ExpectValue | ExpectAbsent | ExpectPresent | ExpectUnknown
"""
Four-variant precondition algebra.

ExpectAny REJECTED: no implicit overwrite allowed.
"""


# --- Operation Base ---


@dataclass(frozen=True)
class Operation:
    """
    Base class for all operations (abstract).

    All operations must be REGISTERED, VERSIONED, TYPED.
    """
    operation_type: OperationType
    operation_version: str

    def validate_schema(self) -> None:
        """Validate operation payload completeness. Subclass override."""
        raise NotImplementedError


# --- SET_FACT Operation ---


@dataclass(frozen=True)
class SetFactOperation(Operation):
    """
    Set fact value operation.

    Required fields:
        subject: EntityId (fact owner)
        scope: ProjectId (project isolation)
        path: FactPath (typed fact path)
        value: Any (new value, must match path type, cannot be None)
        precondition: Precondition (required, no implicit overwrite)
        evidence: EvidenceRef (traceability)

    Invariants:
        - value cannot be None (use END_FACT for lifecycle termination)
        - precondition must exist (no ExpectAny, no implicit overwrite)
        - value type must match path.expected_type
    """
    operation_type: Literal[OperationType.SET_FACT] = OperationType.SET_FACT
    operation_version: str = "1.0.0"

    subject: EntityId | None = None
    scope: ProjectId | None = None
    path: FactPath | None = None
    value: Any = None
    precondition: Precondition | None = None
    evidence: EvidenceRef | None = None

    def validate_schema(self) -> None:
        """Validate SET_FACT payload completeness."""
        if self.subject is None:
            raise ValueError("SET_FACT missing required field: subject")
        if self.scope is None:
            raise ValueError("SET_FACT missing required field: scope")
        if self.path is None:
            raise ValueError("SET_FACT missing required field: path")
        if self.value is None:
            raise ValueError(
                "SET_FACT value cannot be None (use END_FACT instead)"
            )
        if self.precondition is None:
            raise ValueError(
                "SET_FACT missing required field: precondition "
                "(implicit overwrite not allowed)"
            )
        if self.evidence is None:
            raise ValueError("SET_FACT missing required field: evidence")


# --- END_FACT Operation ---


@dataclass(frozen=True)
class EndFactOperation(Operation):
    """
    End fact lifecycle operation (tombstone, not deletion).

    Required fields:
        subject: EntityId
        scope: ProjectId
        path: FactPath
        precondition: Precondition (must be ExpectPresent or ExpectValue)
        evidence: EvidenceRef

    Semantics:
        - Marks fact lifecycle ended (e.g., character death → age no longer updates)
        - Not physical deletion (history preserved)
        - Cannot END absent fact (ExpectAbsent rejected)
    """
    operation_type: Literal[OperationType.END_FACT] = OperationType.END_FACT
    operation_version: str = "1.0.0"

    subject: EntityId | None = None
    scope: ProjectId | None = None
    path: FactPath | None = None
    precondition: Precondition | None = None
    evidence: EvidenceRef | None = None

    def validate_schema(self) -> None:
        """Validate END_FACT payload completeness."""
        if self.subject is None:
            raise ValueError("END_FACT missing required field: subject")
        if self.scope is None:
            raise ValueError("END_FACT missing required field: scope")
        if self.path is None:
            raise ValueError("END_FACT missing required field: path")
        if self.precondition is None:
            raise ValueError("END_FACT missing required field: precondition")
        if isinstance(self.precondition, ExpectAbsent):
            raise ValueError(
                "END_FACT cannot have ExpectAbsent precondition "
                "(cannot end nonexistent fact)"
            )
        if self.evidence is None:
            raise ValueError("END_FACT missing required field: evidence")


# --- UNDO_FACT Operation ---


@dataclass(frozen=True)
class UndoFactOperation(Operation):
    """
    Undo previous fact setting (correction, not deletion).

    Required fields:
        subject: EntityId
        scope: ProjectId
        path: FactPath
        original_commit_ref: CommitId (specific commit being undone)
        precondition: ExpectValue (current value must equal undone value)
        evidence: EvidenceRef (undo reason)

    Semantics:
        - Reverts specific Canon commit
        - Not generic deletion, must reference original commit
        - Precondition must be ExpectValue (prevent undo of overwritten value)

    Distinction:
        - UNDO_FACT: correction ("previous setting was wrong")
        - END_FACT: lifecycle end ("fact was correct, now terminated")
    """
    operation_type: Literal[OperationType.UNDO_FACT] = OperationType.UNDO_FACT
    operation_version: str = "1.0.0"

    subject: EntityId | None = None
    scope: ProjectId | None = None
    path: FactPath | None = None
    original_commit_ref: CommitId | None = None
    precondition: ExpectValue | None = None
    evidence: EvidenceRef | None = None

    def validate_schema(self) -> None:
        """Validate UNDO_FACT payload completeness."""
        if self.subject is None:
            raise ValueError("UNDO_FACT missing required field: subject")
        if self.scope is None:
            raise ValueError("UNDO_FACT missing required field: scope")
        if self.path is None:
            raise ValueError("UNDO_FACT missing required field: path")
        if self.original_commit_ref is None:
            raise ValueError(
                "UNDO_FACT missing required field: original_commit_ref"
            )
        if self.precondition is None:
            raise ValueError("UNDO_FACT missing required field: precondition")
        if not isinstance(self.precondition, ExpectValue):
            raise ValueError(
                "UNDO_FACT precondition must be ExpectValue "
                "(current value must equal undone value)"
            )
        if self.evidence is None:
            raise ValueError("UNDO_FACT missing required field: evidence")


# --- NarrativeDelta ---


@dataclass(frozen=True)
class NarrativeDelta:
    """
    Narrative state change proposal (not Canon state).

    NarrativeDelta represents proposed changes that must be validated
    and authorized before Canon commit via CanonCommitService.

    Lifecycle: PROPOSED → VALIDATED → {ACCEPTED → COMMITTED | REJECTED}

    BASE fields (all persisted):
        delta_id: Unique identifier (UUID v4)
        project_id: Project isolation boundary
        operations: List of registered operations
        source_chapter: Source chapter reference (optional)
        created_at: Proposal creation timestamp
        authority: Proposal source identifier
        provenance: Structured provenance metadata

    Invariants:
        - delta_id is UUID v4 format
        - All operations are registered types
        - All operations in same project as delta
        - NarrativeDelta is immutable (frozen)
        - Empty operations list = NO_CHANGE (valid Delta)

    Authority:
        - NarrativeDelta = proposal permission, NOT commit permission
        - Only CanonCommitService can commit Delta to Canon
        - Delta can be rejected without affecting Canon
    """
    delta_id: DeltaId
    project_id: ProjectId
    operations: tuple[Operation, ...]  # Immutable sequence
    source_chapter: str | None
    created_at: datetime
    authority: str
    provenance: dict[str, str]

    def __post_init__(self) -> None:
        """Validate Delta invariants on construction."""
        # Validate delta_id format (UUID v4)
        try:
            uuid.UUID(self.delta_id, version=4)
        except ValueError as e:
            raise ValueError(f"delta_id must be UUID v4 format: {e}")

        # Validate all operations are registered types
        for op in self.operations:
            if not isinstance(op.operation_type, OperationType):
                raise ValueError(
                    f"Unregistered operation type: {op.operation_type}. "
                    f"Cannot include in commit proposal."
                )


# --- Validation Result ---


@dataclass(frozen=True)
class ValidationResult:
    """
    Operation validation result.

    Attributes:
        pass_: Validation passed (True) or failed (False)
        reason: Failure reason (if pass_=False)
    """
    pass_: bool
    reason: str = ""


# --- Operation Validation ---


def validate_operation(op: Operation) -> None:
    """
    Validate operation schema completeness.

    Checks:
        1. Operation type is registered
        2. Operation payload is complete

    Args:
        op: Operation to validate

    Raises:
        ValueError: If operation type unregistered or payload incomplete
    """
    # Check registration
    if not isinstance(op.operation_type, OperationType):
        raise ValueError(
            f"Operation type {op.operation_type} not registered. "
            f"Cannot include in commit proposal."
        )

    # Check payload completeness
    op.validate_schema()


# --- Precondition Evaluation ---


def evaluate_precondition(
    precondition: Precondition,
    current_value: Any,
    path_exists: bool,
) -> bool:
    """
    Evaluate precondition against current state.

    Args:
        precondition: Precondition to evaluate
        current_value: Current value at path (or None if absent)
        path_exists: Whether path exists in Canon

    Returns:
        True if precondition satisfied, False otherwise
    """
    if isinstance(precondition, ExpectValue):
        return path_exists and current_value == precondition.expected_value

    elif isinstance(precondition, ExpectAbsent):
        return not path_exists

    elif isinstance(precondition, ExpectPresent):
        return path_exists

    elif isinstance(precondition, ExpectUnknown):
        return path_exists and current_value == FactValue.UNKNOWN

    else:
        # Should not reach here with valid Precondition type
        raise TypeError(f"Unknown precondition type: {type(precondition)}")


# --- Reducer Protocol ---


class Reducer(Protocol):
    """
    Reducer protocol for applying operations to Canon state.

    Contract:
        1. Pure: no side effects, immutable input
        2. Deterministic: same input → same output
        3. Versioned: reducer version tracked
        4. Fail-closed: validation failure → reject entire Delta
        5. Provider-independent: no LLM provider calls

    Not allowed:
        - Modify canon_state input
        - Access external state (database, API, filesystem)
        - Depend on randomness or current time (unless explicit input)
        - Partial operation application (all-or-nothing)
        - Call LLM provider API
    """

    version: str

    def apply(
        self,
        canon_state: Any,  # CanonState from V2-009
        operation: Operation,
    ) -> Any:  # New CanonState
        """
        Apply operation to Canon state (pure function).

        Args:
            canon_state: Current Canon state (immutable)
            operation: Operation to apply

        Returns:
            New Canon state (if success)

        Raises:
            ReducerError: Operation failed (precondition, type error, etc.)
        """
        ...


# --- Reducer Error ---


class ReducerError(Exception):
    """Reducer operation application failed."""
    pass
