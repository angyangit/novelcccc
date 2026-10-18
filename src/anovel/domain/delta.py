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

import copy
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Literal, NewType, Protocol

from .identity import EntityId, ProjectId

# --- Type Aliases ---

DeltaId = NewType("DeltaId", str)
"""Unique identifier for narrative deltas (UUID v4 format)."""

CommitId = NewType("CommitId", str)
"""Reference to Canon commit (for UNDO_FACT)."""


# --- Deep Copy Utility ---


def _deepcopy_value(value: Any) -> Any:
    """
    Deep copy a value to prevent mutable reference leaks.

    For nested dicts/lists, creates defensive copies.
    For immutable types (int, str, bool, None, Enum), returns as-is.
    For FactValue.UNKNOWN, returns as-is.

    Contract: Prevent nested mutable payload mutations from affecting immutable objects.
    """
    if value is None or isinstance(value, (int, str, bool, float, Enum)):
        return value
    if isinstance(value, FactValue):
        return value
    # Deep copy for mutable structures (dict, list, etc.)
    return copy.deepcopy(value)


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


# --- Trusted Fact Path Registry ---

# Minimal, genre-neutral registry of allowed fact paths per ADR-004 line 809.
# Read-only, trusted source of truth for path types.
# Prevents untrusted callers from specifying arbitrary expected_type.
_FACT_PATH_REGISTRY_INTERNAL = {
    "age": FactPath("age", int),
    "is_alive": FactPath("is_alive", bool),
    "name": FactPath("name", str),
    "description": FactPath("description", str),
}

FACT_PATH_REGISTRY: MappingProxyType[str, FactPath] = MappingProxyType(
    _FACT_PATH_REGISTRY_INTERNAL
)


def get_fact_path(path_str: str) -> FactPath:
    """
    Get FactPath from trusted registry.

    Args:
        path_str: Path string to look up

    Returns:
        Registered FactPath with authoritative type

    Raises:
        ValueError: Path not in registry (unregistered)

    Contract: ADR-004 line 809 - reject unregistered paths
    """
    if path_str not in FACT_PATH_REGISTRY:
        raise ValueError(f"Unregistered FactPath: {path_str}")

    return FACT_PATH_REGISTRY[path_str]


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
        - operation_type must be SET_FACT (no spoofing)
        - operation_version must be registered ("1.0.0")
    """

    operation_type: Literal[OperationType.SET_FACT] = OperationType.SET_FACT
    operation_version: str = "1.0.0"

    subject: EntityId | None = None
    scope: ProjectId | None = None
    path: FactPath | None = None
    value: Any = None
    precondition: Precondition | None = None
    evidence: EvidenceRef | None = None

    def __post_init__(self) -> None:
        """Validate operation type and version consistency, and deep copy mutable values."""
        if self.operation_type != OperationType.SET_FACT:
            raise ValueError(
                f"SetFactOperation must have operation_type=SET_FACT, got {self.operation_type}"
            )
        if self.operation_version not in ("1.0.0",):
            raise ValueError(
                f"Unregistered operation_version: {self.operation_version}. "
                f"Registered versions: 1.0.0"
            )

        # Deep copy value to prevent mutable reference leaks
        if self.value is not None and self.value != FactValue.UNKNOWN:
            copied_value = _deepcopy_value(self.value)
            object.__setattr__(self, "value", copied_value)

    def validate_schema(self) -> None:
        """Validate SET_FACT payload completeness."""
        if self.subject is None:
            raise ValueError("SET_FACT missing required field: subject")
        if self.scope is None:
            raise ValueError("SET_FACT missing required field: scope")
        if self.path is None:
            raise ValueError("SET_FACT missing required field: path")
        if self.value is None:
            raise ValueError("SET_FACT value cannot be None (use END_FACT instead)")
        if self.precondition is None:
            raise ValueError(
                "SET_FACT missing required field: precondition "
                "(implicit overwrite not allowed)"
            )
        if self.evidence is None:
            raise ValueError("SET_FACT missing required field: evidence")

        # Validate evidence format (LEVEL 1 & 2: field presence and format)
        if not self.evidence.source_ref:
            raise ValueError("Evidence source_ref cannot be empty")
        if not self.evidence.content_hash:
            raise ValueError("Evidence content_hash cannot be empty")
        if len(self.evidence.content_hash) != 64:
            raise ValueError(
                f"Evidence content_hash must be 64 characters (SHA-256), got {len(self.evidence.content_hash)}"
            )
        try:
            int(self.evidence.content_hash, 16)
        except ValueError as e:
            raise ValueError(
                f"Evidence content_hash must be hexadecimal, got '{self.evidence.content_hash}'"
            ) from e


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

    def __post_init__(self) -> None:
        """Validate operation type and version consistency."""
        if self.operation_type != OperationType.END_FACT:
            raise ValueError(
                f"EndFactOperation must have operation_type=END_FACT, got {self.operation_type}"
            )
        if self.operation_version not in ("1.0.0",):
            raise ValueError(
                f"Unregistered operation_version: {self.operation_version}. "
                f"Registered versions: 1.0.0"
            )

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

        # Validate evidence format (LEVEL 1 & 2: field presence and format)
        if not self.evidence.source_ref:
            raise ValueError("Evidence source_ref cannot be empty")
        if not self.evidence.content_hash:
            raise ValueError("Evidence content_hash cannot be empty")
        if len(self.evidence.content_hash) != 64:
            raise ValueError(
                f"Evidence content_hash must be 64 characters (SHA-256), got {len(self.evidence.content_hash)}"
            )
        try:
            int(self.evidence.content_hash, 16)
        except ValueError as e:
            raise ValueError(
                f"Evidence content_hash must be hexadecimal, got '{self.evidence.content_hash}'"
            ) from e


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

    def __post_init__(self) -> None:
        """Validate operation type and version consistency."""
        if self.operation_type != OperationType.UNDO_FACT:
            raise ValueError(
                f"UndoFactOperation must have operation_type=UNDO_FACT, got {self.operation_type}"
            )
        if self.operation_version not in ("1.0.0",):
            raise ValueError(
                f"Unregistered operation_version: {self.operation_version}. "
                f"Registered versions: 1.0.0"
            )

    def validate_schema(self) -> None:
        """Validate UNDO_FACT payload completeness."""
        if self.subject is None:
            raise ValueError("UNDO_FACT missing required field: subject")
        if self.scope is None:
            raise ValueError("UNDO_FACT missing required field: scope")
        if self.path is None:
            raise ValueError("UNDO_FACT missing required field: path")
        if self.original_commit_ref is None:
            raise ValueError("UNDO_FACT missing required field: original_commit_ref")
        if self.precondition is None:
            raise ValueError("UNDO_FACT missing required field: precondition")
        if not isinstance(self.precondition, ExpectValue):
            raise ValueError(
                "UNDO_FACT precondition must be ExpectValue "
                "(current value must equal undone value)"
            )
        if self.evidence is None:
            raise ValueError("UNDO_FACT missing required field: evidence")

        # Validate evidence format (LEVEL 1 & 2: field presence and format)
        if not self.evidence.source_ref:
            raise ValueError("Evidence source_ref cannot be empty")
        if not self.evidence.content_hash:
            raise ValueError("Evidence content_hash cannot be empty")
        if len(self.evidence.content_hash) != 64:
            raise ValueError(
                f"Evidence content_hash must be 64 characters (SHA-256), got {len(self.evidence.content_hash)}"
            )
        try:
            int(self.evidence.content_hash, 16)
        except ValueError as e:
            raise ValueError(
                f"Evidence content_hash must be hexadecimal, got '{self.evidence.content_hash}'"
            ) from e


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
    provenance: tuple[tuple[str, str], ...]  # Immutable provenance metadata

    def __post_init__(self) -> None:
        """Validate Delta invariants on construction."""
        # Validate delta_id format (UUID v4)
        try:
            parsed_uuid = uuid.UUID(self.delta_id)
            if parsed_uuid.version != 4:
                raise ValueError(
                    f"delta_id must be UUID v4, got version {parsed_uuid.version}"
                )
        except ValueError as e:
            raise ValueError(f"delta_id must be UUID v4 format: {e}") from e

        # Ensure operations is tuple (defensive copy)
        if not isinstance(self.operations, tuple):
            object.__setattr__(self, "operations", tuple(self.operations))

        # Ensure provenance is tuple (defensive copy)
        if not isinstance(self.provenance, tuple):
            if isinstance(self.provenance, dict):
                object.__setattr__(self, "provenance", tuple(self.provenance.items()))
            else:
                object.__setattr__(self, "provenance", tuple(self.provenance))

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


# --- Pure Domain Canon State (In-Memory Reference Implementation) ---


@dataclass(frozen=True)
class CommitChange:
    """
    Record of what a commit changed for UNDO_FACT restoration.

    Attributes:
        commit_id: The commit that made this change
        project_id: Project scope (must match operation scope)
        subject: Entity that was modified
        path: Fact path that was modified
        value_before: Value before commit (None if didn't exist)
        existed_before: Whether fact existed before commit
        value_after: Value after commit (None if deleted/ended)
        existed_after: Whether fact exists after commit
    """

    commit_id: CommitId
    project_id: ProjectId
    subject: EntityId
    path: str
    value_before: Any
    existed_before: bool
    value_after: Any
    existed_after: bool

    def __post_init__(self) -> None:
        """Deep copy mutable values to prevent reference leaks."""
        # Deep copy values to ensure immutability
        if self.value_before is not None:
            copied_before = _deepcopy_value(self.value_before)
            object.__setattr__(self, "value_before", copied_before)
        if self.value_after is not None:
            copied_after = _deepcopy_value(self.value_after)
            object.__setattr__(self, "value_after", copied_after)


@dataclass(frozen=True)
class CanonState:
    """
    Pure in-memory Canon state for V2-008 domain semantics.

    This is a reference implementation for testing reducer logic.
    NOT persistent storage (V2-009 will implement persistence).

    Attributes:
        project_id: Project isolation boundary
        facts: Immutable mapping of (subject, path) to values
        tombstones: Immutable set of ended facts (lifecycle terminated)
        commit_history: Immutable tuple of commit references for UNDO_FACT
        commit_changes: Immutable tuple tracking what each commit changed (for UNDO restoration)
    """

    project_id: ProjectId
    facts: tuple[tuple[tuple[EntityId, str], Any], ...]  # ((entity, path), value)
    tombstones: frozenset[tuple[EntityId, str]]  # ended facts
    commit_history: tuple[CommitId, ...]  # for UNDO_FACT validation
    commit_changes: tuple[CommitChange, ...] = ()  # commit change history for UNDO

    def __post_init__(self) -> None:
        """Deep copy all fact values to prevent mutable reference leaks."""
        # Deep copy all values in facts tuple
        copied_facts = tuple((key, _deepcopy_value(value)) for key, value in self.facts)
        object.__setattr__(self, "facts", copied_facts)

    def get_value(self, subject: EntityId, path: FactPath) -> tuple[Any, bool]:
        """
        Get current value at path.

        Returns:
            (value, exists): Value and existence flag (value is deep copied)
        """
        key = (subject, path.path)
        for k, v in self.facts:
            if k == key:
                # Deep copy to prevent mutation of stored value
                return (_deepcopy_value(v), True)
        return (None, False)

    def set_value(
        self,
        subject: EntityId,
        path: FactPath,
        value: Any,
        commit_id: CommitId | None = None,
    ) -> CanonState:
        """
        Return new state with value set (pure function).

        Does not modify self.

        Args:
            subject: Entity being modified
            path: Fact path
            value: New value (will be deep copied)
            commit_id: Optional commit ID to track this change for UNDO
        """
        key = (subject, path.path)

        # Get old value before change
        old_value, existed_before = self.get_value(subject, path)

        # Deep copy input value to prevent mutation
        copied_value = _deepcopy_value(value)

        # Remove old value if exists, add new value
        new_facts = tuple((k, v) for (k, v) in self.facts if k != key) + (
            (key, copied_value),
        )

        # Track commit change if commit_id provided
        new_changes = self.commit_changes
        if commit_id is not None:
            change = CommitChange(
                commit_id=commit_id,
                project_id=self.project_id,
                subject=subject,
                path=path.path,
                value_before=old_value,
                existed_before=existed_before,
                value_after=copied_value,
                existed_after=True,
            )
            new_changes = self.commit_changes + (change,)

        return CanonState(
            project_id=self.project_id,
            facts=new_facts,
            tombstones=self.tombstones,
            commit_history=self.commit_history,
            commit_changes=new_changes,
        )

    def end_fact(
        self, subject: EntityId, path: FactPath, commit_id: CommitId | None = None
    ) -> CanonState:
        """
        Return new state with fact ended (tombstone).

        Does not modify self.

        Args:
            subject: Entity being modified
            path: Fact path
            commit_id: Optional commit ID to track this change for UNDO
        """
        key = (subject, path.path)
        new_tombstones = self.tombstones | {key}

        # Track commit change if commit_id provided
        new_changes = self.commit_changes
        if commit_id is not None:
            old_value, existed_before = self.get_value(subject, path)
            change = CommitChange(
                commit_id=commit_id,
                project_id=self.project_id,
                subject=subject,
                path=path.path,
                value_before=old_value,
                existed_before=existed_before,
                value_after=None,
                existed_after=False,  # Ended means lifecycle terminated
            )
            new_changes = self.commit_changes + (change,)

        return CanonState(
            project_id=self.project_id,
            facts=self.facts,
            tombstones=new_tombstones,
            commit_history=self.commit_history,
            commit_changes=new_changes,
        )

    def is_ended(self, subject: EntityId, path: FactPath) -> bool:
        """Check if fact lifecycle has ended."""
        key = (subject, path.path)
        return key in self.tombstones

    def commit_exists(self, commit_ref: CommitId) -> bool:
        """Check if commit exists in history."""
        return commit_ref in self.commit_history

    def get_commit_change(
        self, commit_ref: CommitId, subject: EntityId, path: str
    ) -> CommitChange | None:
        """
        Get the change record for a specific commit, subject, and path.

        Returns:
            CommitChange if found, None otherwise
        """
        for change in self.commit_changes:
            if (
                change.commit_id == commit_ref
                and change.subject == subject
                and change.path == path
            ):
                return change
        return None

    def has_subsequent_modifications(
        self, commit_ref: CommitId, subject: EntityId, path: str
    ) -> bool:
        """
        Check if any commit after commit_ref modified the same subject:path.

        Used for ABA scenario detection in UNDO_FACT.

        Returns:
            True if subsequent commits modified this fact, False otherwise
        """
        # Find position of target commit in history
        try:
            target_idx = self.commit_history.index(commit_ref)
        except ValueError:
            # Commit not in history - fail closed
            return True

        # Check all commits after target_idx
        commits_after = self.commit_history[target_idx + 1 :]
        for later_commit in commits_after:
            for change in self.commit_changes:
                if (
                    change.commit_id == later_commit
                    and change.subject == subject
                    and change.path == path
                ):
                    return True
        return False


# --- Reference Reducer Implementation ---


class DeltaReducer:
    """
    Reference reducer implementation for V2-008.

    Pure domain reducer with deterministic, fail-closed semantics.
    No database, no Provider, no external state.
    """

    version: str = "1.0.0"

    def apply_delta(self, canon_state: CanonState, delta: NarrativeDelta) -> CanonState:
        """
        Apply entire Delta atomically (fail-closed).

        Args:
            canon_state: Current immutable state
            delta: Delta to apply

        Returns:
            New state with all operations applied

        Raises:
            ReducerError: Any operation failed → entire Delta rejected
        """
        # Validate project isolation
        if delta.project_id != canon_state.project_id:
            raise ReducerError(
                f"Delta project {delta.project_id} does not match "
                f"Canon project {canon_state.project_id}"
            )

        # Apply operations sequentially, fail-closed
        current_state = canon_state
        for op in delta.operations:
            current_state = self.apply_operation(current_state, op)

        return current_state

    def apply_operation(
        self, canon_state: CanonState, operation: Operation
    ) -> CanonState:
        """
        Apply single operation (pure function).

        Args:
            canon_state: Current immutable state
            operation: Operation to apply

        Returns:
            New state with operation applied

        Raises:
            ReducerError: Operation failed
        """
        # Validate operation schema
        operation.validate_schema()

        # Validate project isolation
        if isinstance(
            operation, (SetFactOperation, EndFactOperation, UndoFactOperation)
        ):
            if operation.scope != canon_state.project_id:
                raise ReducerError(
                    f"Operation scope {operation.scope} does not match "
                    f"Canon project {canon_state.project_id}"
                )

        # Dispatch to specific handler
        if isinstance(operation, SetFactOperation):
            return self._apply_set_fact(canon_state, operation)
        elif isinstance(operation, EndFactOperation):
            return self._apply_end_fact(canon_state, operation)
        elif isinstance(operation, UndoFactOperation):
            return self._apply_undo_fact(canon_state, operation)
        else:
            raise ReducerError(f"Unknown operation type: {operation.operation_type}")

    def _apply_set_fact(
        self, canon_state: CanonState, operation: SetFactOperation
    ) -> CanonState:
        """Apply SET_FACT operation."""
        # Check if fact has ended (tombstone)
        if canon_state.is_ended(operation.subject, operation.path):
            raise ReducerError(f"Cannot SET_FACT on ended fact: {operation.path.path}")

        # Get current value
        current_value, path_exists = canon_state.get_value(
            operation.subject, operation.path
        )

        # Evaluate precondition
        if not evaluate_precondition(
            operation.precondition, current_value, path_exists
        ):
            raise ReducerError(
                f"Precondition failed: {operation.precondition.__class__.__name__} "
                f"(current: {current_value}, exists: {path_exists})"
            )

        # Type check (basic)
        if operation.path.expected_type is not None:
            if operation.value != FactValue.UNKNOWN:
                if not isinstance(operation.value, operation.path.expected_type):
                    raise ReducerError(
                        f"Type mismatch: expected {operation.path.expected_type}, "
                        f"got {type(operation.value)}"
                    )

        # Apply state change (pure)
        return canon_state.set_value(operation.subject, operation.path, operation.value)

    def _apply_end_fact(
        self, canon_state: CanonState, operation: EndFactOperation
    ) -> CanonState:
        """Apply END_FACT operation (tombstone)."""
        # Get current value
        current_value, path_exists = canon_state.get_value(
            operation.subject, operation.path
        )

        # Evaluate precondition (must be ExpectPresent or ExpectValue)
        if not evaluate_precondition(
            operation.precondition, current_value, path_exists
        ):
            raise ReducerError(
                f"Precondition failed for END_FACT: "
                f"{operation.precondition.__class__.__name__}"
            )

        # Check not already ended
        if canon_state.is_ended(operation.subject, operation.path):
            raise ReducerError(f"Fact already ended: {operation.path.path}")

        # Apply tombstone (pure)
        return canon_state.end_fact(operation.subject, operation.path)

    def _apply_undo_fact(
        self, canon_state: CanonState, operation: UndoFactOperation
    ) -> CanonState:
        """Apply UNDO_FACT operation with proper restoration semantics."""
        # Validate commit reference exists
        if not canon_state.commit_exists(operation.original_commit_ref):
            raise ReducerError(
                f"Original commit not found: {operation.original_commit_ref}"
            )

        # Get the commit change record
        commit_change = canon_state.get_commit_change(
            operation.original_commit_ref, operation.subject, operation.path.path
        )

        if commit_change is None:
            raise ReducerError(
                f"No change record found for commit {operation.original_commit_ref} "
                f"on {operation.subject}:{operation.path.path}"
            )

        # Verify project_id matches (prevent cross-project UNDO)
        if commit_change.project_id != operation.scope:
            raise ReducerError(
                f"Cannot undo commit from different project: "
                f"commit project={commit_change.project_id}, operation scope={operation.scope}"
            )

        # Verify this commit actually modified this specific subject/path
        if (
            commit_change.subject != operation.subject
            or commit_change.path != operation.path.path
        ):
            raise ReducerError(
                f"Commit {operation.original_commit_ref} did not modify "
                f"{operation.subject}:{operation.path.path}"
            )

        # Check for subsequent modifications (ABA scenario protection)
        if canon_state.has_subsequent_modifications(
            operation.original_commit_ref, operation.subject, operation.path.path
        ):
            raise ReducerError(
                f"Cannot undo commit {operation.original_commit_ref}: "
                f"fact {operation.subject}:{operation.path.path} has been modified by subsequent commits"
            )

        # Get current value
        current_value, path_exists = canon_state.get_value(
            operation.subject, operation.path
        )

        # Precondition must be ExpectValue (current matches undone)
        if not isinstance(operation.precondition, ExpectValue):
            raise ReducerError(
                "UNDO_FACT precondition must be ExpectValue "
                "(this should have been caught by validate_schema)"
            )

        if not evaluate_precondition(
            operation.precondition, current_value, path_exists
        ):
            raise ReducerError(
                f"Cannot undo: current value does not match expected "
                f"(expected: {operation.precondition.expected_value}, "
                f"current: {current_value})"
            )

        # Restore to the state before the commit
        key = (operation.subject, operation.path.path)

        if commit_change.existed_before:
            # Fact existed before: restore to previous value
            new_facts = tuple((k, v) for (k, v) in canon_state.facts if k != key) + (
                (key, commit_change.value_before),
            )
        else:
            # Fact didn't exist before: remove it
            new_facts = tuple((k, v) for (k, v) in canon_state.facts if k != key)

        return CanonState(
            project_id=canon_state.project_id,
            facts=new_facts,
            tombstones=canon_state.tombstones,
            commit_history=canon_state.commit_history,
            commit_changes=canon_state.commit_changes,
        )
