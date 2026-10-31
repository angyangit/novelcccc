"""Context models for V2-018 Context Compiler.

Defines ContextArtifact and related types for chapter writing context.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ItemPriority(StrEnum):
    """Priority classification for context items."""

    REQUIRED = "required"  # Must be included, budget failure if can't fit
    OPTIONAL = "optional"  # Include if budget allows, drop if needed


class ItemSource(StrEnum):
    """Source of context item."""

    CONTRACT = "contract"  # From ChapterContract
    CANON = "canon"  # From Canon repository
    PREVIOUS_CHAPTER = "previous_chapter"  # From prior chapter prose
    PLAN = "plan"  # From planning data
    GENRE_PACK = "genre_pack"  # From GenrePack
    CHARACTER_KNOWLEDGE = "character_knowledge"  # From character knowledge boundaries


@dataclass(frozen=True)
class ContextItem:
    """Single item in compiled context.

    Tracks provenance, priority, and budget impact.
    """

    item_id: str
    content: str | dict[str, Any]  # Text or structured data
    source: ItemSource
    priority: ItemPriority
    source_ref: str  # Hash, ID, or path to source
    scope: str  # Project scope (story_id)
    character_visible: list[str]  # Character IDs who can know this
    rationale: str  # Why included
    estimated_tokens: int  # Token count estimate


@dataclass(frozen=True)
class BudgetReport:
    """Token budget allocation report."""

    total_budget: int
    required_tokens: int
    optional_tokens: int
    actual_tokens: int
    items_included: int
    items_dropped: int
    budget_exceeded: bool


@dataclass(frozen=True)
class ContextArtifact:
    """Compiled context for chapter writing.

    Pure compilation result - no side effects, deterministic from frozen inputs.
    """

    artifact_id: str
    chapter_id: str
    chapter_number: int
    compiled_at: datetime

    # Frozen inputs binding
    contract_id: str
    canon_parent: str  # Canon commit hash
    genre_pack_hash: str
    plan_version: str

    # Context items by priority
    required_items: list[ContextItem]
    optional_items: list[ContextItem]

    # Budget tracking
    budget: BudgetReport

    # Metadata
    compilation_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextCompilationError:
    """Error when context cannot be compiled within constraints."""

    error_id: str
    error_type: str  # "budget_exceeded", "missing_required", etc.
    message: str
    required_tokens: int
    available_budget: int
    missing_items: list[str] = field(default_factory=list)
    suggested_resolution: str | None = None
