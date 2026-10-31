"""Contract models for V2-017 Contract Compiler.

Defines ChapterContract and related constraint types.
Contracts express planning intent and validation rules, not execution state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..domain.delta import OperationType
from ..planning.models import GenrePackBinding


@dataclass(frozen=True)
class RequiredTransition:
    """State change that MUST occur in this chapter.

    Uses NarrativeDelta OperationType semantics (ADR-004).
    """

    transition_id: str
    operation_type: OperationType
    fact_path: str  # Path to fact being modified
    target_value: Any | None = None  # Expected value after transition
    preconditions: list[Any] = field(
        default_factory=list
    )  # Precondition objects from delta
    rationale: str = ""  # Why required (from protagonist goal, etc.)


@dataclass(frozen=True)
class ProhibitedTransition:
    """State change that MUST NOT occur in this chapter."""

    prohibition_id: str
    fact_path: str
    prohibited_operation: OperationType
    rationale: str


@dataclass(frozen=True)
class ProtectedFact:
    """Fact that cannot be changed without violating world constraints."""

    fact_id: str
    fact_path: str
    protection_reason: str  # References world constraint


@dataclass(frozen=True)
class KnowledgeBoundary:
    """Who knows what, when revelation allowed."""

    boundary_id: str
    fact_id: str
    knowers: list[str]  # Character IDs who know this fact
    revelation_constraint: str | None = None  # e.g., "not_before_chapter_5"
    reader_knows: bool = False


@dataclass(frozen=True)
class ContinuityConstraint:
    """Binds chapter to previous chapter's actual end state."""

    previous_chapter_id: str | None  # None only for chapter 1
    previous_chapter_hash: str | None  # Content hash of prior chapter prose
    previous_end_state: dict[str, Any]  # Key facts from chapter N-1
    current_start_requirements: list[str]  # What must be true at chapter start


@dataclass(frozen=True)
class ChapterContract:
    """Compiled contract for one chapter.

    Expresses planning intent, validation rules, and continuity constraints.
    Does NOT execute state changes or modify Canon.
    """

    contract_id: str
    chapter_id: str
    chapter_number: int
    plan_version: str
    created_at: datetime

    # Frozen inputs binding
    canon_parent: str  # Frozen Canon commit hash
    genre_pack_binding: GenrePackBinding

    # Constraints
    required_transitions: list[RequiredTransition]
    prohibited_transitions: list[ProhibitedTransition] = field(default_factory=list)
    protected_facts: list[ProtectedFact] = field(default_factory=list)
    knowledge_boundaries: list[KnowledgeBoundary] = field(default_factory=list)
    continuity_constraints: ContinuityConstraint | None = None

    # Validation metadata
    fixture_ref: str | None = None  # Story fixture this compiled from
    human_review_ref: str | None = None  # Fixture approval reference


@dataclass(frozen=True)
class CompilationDiagnostic:
    """Diagnostic returned when contract compilation fails.

    Compiler returns diagnostics, NEVER auto-modifies Canon or plans.
    """

    diagnostic_id: str
    error_type: (
        str  # "conflicting_constraints", "unsatisfiable", "version_expired", etc.
    )
    message: str
    conflicts: list[str] = field(default_factory=list)
    affected_chapters: list[str] = field(default_factory=list)
    suggested_resolution: str | None = None
