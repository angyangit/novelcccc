"""Replanning proposals and invalidation logic.

When Canon, GenrePack, or plan inputs change, existing contracts become invalid.
This module generates ReplanProposal records for Owner approval.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InvalidationRecord:
    """Record of why and when a contract was invalidated."""

    contract_id: str
    invalidation_reason: (
        str  # "canon_parent_changed", "pack_upgraded", "prior_chapter_revised"
    )
    invalidated_at: datetime
    affected_inputs: dict[
        str, str
    ]  # e.g., {"old_parent": "abc123", "new_parent": "def456"}
    replan_proposal_id: str | None = None


@dataclass(frozen=True)
class InvalidationScope:
    """Determines which contracts are affected by input changes."""

    invalidation_id: str
    change_type: str  # "canon_advance", "pack_upgrade", "chapter_revision"
    affected_chapters: list[str]  # Chapter IDs requiring recompilation
    rationale: str


@dataclass(frozen=True)
class ReplanProposal:
    """Proposal for re-planning after invalidation (requires Owner approval)."""

    proposal_id: str
    created_at: datetime
    invalidation_record: InvalidationRecord
    proposed_changes: str  # Human-readable description
    affected_chapters: list[str]
    new_plan_version: str  # Proposed version identifier
    approval_status: str = "pending"  # "pending", "approved", "rejected"
    approved_by: str | None = None
    approved_at: datetime | None = None


def generate_invalidation_scope(
    change_type: str,
    changed_input: str,
    all_contracts: list[dict],  # Simplified contract representation
) -> InvalidationScope:
    """
    Determine scope of invalidation based on input change.

    ADR-008 Decision 4 (Invalidation Scope Rules):
    1. Canon parent change invalidates contracts bound to old parent
    2. GenrePack upgrade invalidates contracts using old hash
    3. Prior chapter revision invalidates dependent chapters
    4. Plan supersession invalidates contracts referencing old version
    5. Fixture content change invalidates all contracts from that fixture
    """
    affected_chapters = []

    if change_type == "canon_advance":
        # Rule 1: Invalidate contracts bound to old Canon parent
        for contract in all_contracts:
            if contract.get("canon_parent") == changed_input:
                affected_chapters.append(contract["chapter_id"])

    elif change_type == "pack_upgrade":
        # Rule 2: Invalidate contracts using old GenrePack hash
        for contract in all_contracts:
            pack_binding = contract.get("genre_pack_binding", {})
            if pack_binding.get("content_hash") == changed_input:
                affected_chapters.append(contract["chapter_id"])

    elif change_type == "chapter_revision":
        # Rule 3: Invalidate subsequent chapters depending on revised chapter
        revised_chapter_num = int(changed_input.split("_")[-1])
        for contract in all_contracts:
            chapter_num = contract.get("chapter_number", 0)
            if chapter_num > revised_chapter_num:
                affected_chapters.append(contract["chapter_id"])

    elif change_type == "plan_supersession":
        # Rule 4: Invalidate contracts referencing old plan version
        old_version = changed_input
        for contract in all_contracts:
            if contract.get("plan_version") == old_version:
                affected_chapters.append(contract["chapter_id"])

    elif change_type == "fixture_change":
        # Rule 5: Invalidate all contracts from changed fixture
        fixture_id = changed_input
        for contract in all_contracts:
            if contract.get("fixture_ref") == fixture_id:
                affected_chapters.append(contract["chapter_id"])

    return InvalidationScope(
        invalidation_id=f"inv_{datetime.now().isoformat()}",
        change_type=change_type,
        affected_chapters=affected_chapters,
        rationale=f"Input change: {change_type} affected {len(affected_chapters)} chapters",
    )


def create_replan_proposal(
    invalidation: InvalidationRecord,
    scope: InvalidationScope,
    current_version: str,
) -> ReplanProposal:
    """
    Create replan proposal requiring Owner approval.

    Contract Compiler generates proposals, does NOT auto-rewrite Canon or plans.
    """
    next_version = _increment_version(current_version)

    return ReplanProposal(
        proposal_id=f"replan_{datetime.now().isoformat()}",
        created_at=datetime.now(),
        invalidation_record=invalidation,
        proposed_changes=f"Recompile {len(scope.affected_chapters)} chapters due to {scope.change_type}",
        affected_chapters=scope.affected_chapters,
        new_plan_version=next_version,
    )


def _increment_version(version: str) -> str:
    """Increment version string (v1 -> v2, v2 -> v3, etc.)."""
    if version.startswith("v"):
        try:
            num = int(version[1:])
            return f"v{num + 1}"
        except ValueError:
            return f"{version}_v2"
    return f"{version}_v2"
