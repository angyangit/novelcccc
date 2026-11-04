"""Context Compiler models for V2-018.

Defines ContextArtifact, ContextItem, and compilation diagnostics per ADR-009.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

@dataclass(frozen=True)
class ContextItem:
    """Single item in compiled context with full provenance.

    Per ADR-009: Every item must have traceable source, visibility,
    mandatory classification, and inclusion reason.
    """

    item_id: str  # UUID
    content: str | dict[str, Any]  # Actual context content
    source_type: Literal["canon", "contract", "genre_pack",
                         "character_knowledge", "continuity", "retrieval"]
    source_hash: str  # SHA-256 of source content
    scope: str  # project_id for isolation
    visibility: Literal["writer", "character", "reader", "reviewer"]
    mandatory: bool  # Cannot be trimmed for budget
    token_count: int
    inclusion_reason: str  # Explainability requirement

@dataclass(frozen=True)
class CompilationLog:
    """Records context compilation decisions for audit per ADR-009."""

    total_budget: int
    mandatory_tokens: int
    optional_tokens: int
    output_reserve: int  # Tokens reserved for Writer output + system overhead
    excluded_optional_items: list[tuple[str, str]]  # (item_id, exclusion_reason)
    token_counting_method: str  # Model-specific tokenizer (e.g., "cl100k_base")

@dataclass(frozen=True)
class ContextArtifact:
    """Compiled context ready for Writer consumption per ADR-009."""

    artifact_id: str
    chapter_contract_id: str
    canon_parent: str  # Frozen Canon commit hash
    genre_pack_hash: str
    created_at: datetime

    mandatory_items: list[ContextItem]
    optional_items: list[ContextItem]

    compilation_log: CompilationLog

@dataclass(frozen=True)
class ContextCompilationError:
    """Error when context cannot be compiled within constraints.

    Per ADR-009 FAIL_FAST: Explicit error when mandatory items overflow budget.
    """

    error_type: Literal["mandatory_overflow", "scope_violation", "missing_input"]
    message: str
    mandatory_tokens: int | None = None
    available_budget: int | None = None  # total_budget - output_reserve
    overflow_amount: int | None = None
    suggested_budget: int | None = None
    affected_items: list[str] = field(default_factory=list)
