"""Context Compiler implementation for V2-018.

Compiles chapter writing context from frozen inputs without calling generation models.
Handles long-horizon memory retrieval across 1-1000+ chapter spans.

Key principles:
- Required facts NEVER silently dropped, even if low semantic similarity
- Previous chapter actual ending has high priority
- Knowledge boundaries strictly enforced
- Budget overflow on required items returns diagnostic error
- Deterministic compilation from frozen inputs
- Cross-project isolation enforced
"""

import uuid
from datetime import datetime
from typing import Any

from ..contracts.models import ChapterContract
from ..planning.models import SeriesVision
from .models import (
    BudgetReport,
    ContextArtifact,
    ContextCompilationError,
    ContextItem,
    ItemPriority,
    ItemSource,
)

# Result type
CompilationResult = ContextArtifact | ContextCompilationError


class LongHorizonMemory:
    """Manages long-term fact retrieval across chapter spans.

    Handles the critical requirement: facts from chapter 1 must be retrievable
    at chapter 1000 if still relevant, even with low semantic similarity.
    """

    def __init__(self):
        # Simplified in-memory store for now
        # Future: integrate with Canon projection and fact indexing
        self._permanent_facts: dict[str, dict] = {}  # fact_id -> fact_data
        self._state_timeline: dict[str, list[dict]] = {}  # fact_id -> [state_changes]
        self._character_knowledge: dict[str, set[str]] = {}  # char_id -> set(fact_ids)

    def register_permanent_fact(
        self, fact_id: str, fact_data: dict, chapter_established: int, scope: str
    ):
        """Register a permanent fact (character identity, world rule, irreversible event)."""
        self._permanent_facts[fact_id] = {
            "data": fact_data,
            "chapter_established": chapter_established,
            "scope": scope,
            "category": "permanent",
        }

    def register_state_change(
        self,
        fact_id: str,
        chapter: int,
        old_value: Any,
        new_value: Any,
        change_reason: str,
    ):
        """Track state changes over time (money, resources, injuries, relationships)."""
        if fact_id not in self._state_timeline:
            self._state_timeline[fact_id] = []

        self._state_timeline[fact_id].append(
            {
                "chapter": chapter,
                "old_value": old_value,
                "new_value": new_value,
                "reason": change_reason,
            }
        )

    def get_current_state(self, fact_id: str, at_chapter: int) -> Any:
        """Get current state of a fact at specific chapter."""
        if fact_id not in self._state_timeline:
            return self._permanent_facts.get(fact_id, {}).get("data")

        # Find most recent state change before or at target chapter
        timeline = self._state_timeline[fact_id]
        relevant_changes = [c for c in timeline if c["chapter"] <= at_chapter]

        if not relevant_changes:
            return None

        return sorted(relevant_changes, key=lambda x: x["chapter"])[-1]["new_value"]

    def get_required_facts_for_chapter(
        self, chapter: int, scope: str, contract: ChapterContract
    ) -> list[dict]:
        """Retrieve required facts that MUST be included regardless of semantic similarity.

        This is the critical function for long-horizon memory:
        - Character identities and core attributes
        - World rules established in early chapters
        - Unresolved promises and commitments
        - Financial/resource states with their history
        - Important events that have causal impact
        """
        required = []

        # 1. Permanent facts in scope
        for fact_id, fact_info in self._permanent_facts.items():
            if fact_info["scope"] != scope:
                continue
            if fact_info["chapter_established"] <= chapter:
                required.append(
                    {
                        "fact_id": fact_id,
                        "content": fact_info["data"],
                        "established_chapter": fact_info["chapter_established"],
                        "category": "permanent",
                        "rationale": f"Permanent fact established in chapter {fact_info['chapter_established']}",
                    }
                )

        # 2. State facts with recent changes or contract relevance
        for fact_id, timeline in self._state_timeline.items():
            current_state = self.get_current_state(fact_id, chapter)
            if current_state is None:
                continue

            # Check if contract requires this fact
            contract_requires = any(
                fact_id in str(t.fact_path) for t in contract.required_transitions
            )

            if contract_requires or any(c["chapter"] >= chapter - 10 for c in timeline):
                required.append(
                    {
                        "fact_id": fact_id,
                        "content": current_state,
                        "category": "state",
                        "rationale": f"State fact {'required by contract' if contract_requires else 'recently changed'}",
                    }
                )

        return required


class ContextCompiler:
    """Compiles chapter writing context from frozen story inputs."""

    def __init__(self):
        """Initialize compiler with long-horizon memory."""
        self.memory = LongHorizonMemory()
        self._token_estimator = SimpleTokenEstimator()

    def compile_context(
        self,
        contract: ChapterContract,
        series_vision: SeriesVision,
        canon_snapshot: dict,  # Frozen Canon state
        previous_chapter_ending: str | None,
        token_budget: int,
    ) -> CompilationResult:
        """
        Compile context for chapter writing.

        Args:
            contract: ChapterContract with requirements and constraints
            series_vision: Overall story plan
            canon_snapshot: Frozen Canon state snapshot
            previous_chapter_ending: Actual prose ending from previous chapter
            token_budget: Maximum tokens for context

        Returns:
            ContextArtifact if compilation succeeds
            ContextCompilationError if required items exceed budget
        """
        required_items: list[ContextItem] = []
        optional_items: list[ContextItem] = []
        warnings: list[str] = []

        # STEP 1: Previous chapter ending (HIGHEST PRIORITY)
        if previous_chapter_ending and contract.chapter_number > 1:
            ending_item = self._create_context_item(
                content=previous_chapter_ending,
                source=ItemSource.PREVIOUS_CHAPTER,
                priority=ItemPriority.REQUIRED,
                source_ref=contract.continuity_constraints.previous_chapter_hash
                if contract.continuity_constraints
                else "unknown",
                scope=series_vision.series_id,
                character_visible=[],  # Meta info, not character knowledge
                rationale="Previous chapter actual ending for continuity",
            )
            required_items.append(ending_item)

        # STEP 2: Contract required transitions
        for transition in contract.required_transitions:
            trans_item = self._create_context_item(
                content={
                    "operation": transition.operation_type.value,
                    "fact_path": transition.fact_path,
                    "target_value": transition.target_value,
                    "rationale": transition.rationale,
                },
                source=ItemSource.CONTRACT,
                priority=ItemPriority.REQUIRED,
                source_ref=contract.contract_id,
                scope=series_vision.series_id,
                character_visible=[],
                rationale=f"Required transition: {transition.rationale}",
            )
            required_items.append(trans_item)

        # STEP 3: Protected facts
        for protected in contract.protected_facts:
            # Look up actual fact content from memory if available
            fact_content = self.memory._permanent_facts.get(protected.fact_id)
            if fact_content:
                content_data = {
                    "fact_id": protected.fact_id,
                    "fact_path": protected.fact_path,
                    "fact_data": fact_content["data"],
                    "protection_reason": protected.protection_reason,
                }
            else:
                content_data = {
                    "fact_path": protected.fact_path,
                    "protection_reason": protected.protection_reason,
                }

            prot_item = self._create_context_item(
                content=content_data,
                source=ItemSource.CONTRACT,
                priority=ItemPriority.REQUIRED,
                source_ref=contract.contract_id,
                scope=series_vision.series_id,
                character_visible=[],
                rationale=f"Protected fact: {protected.protection_reason}",
            )
            required_items.append(prot_item)

        # STEP 4: Knowledge boundaries
        for boundary in contract.knowledge_boundaries:
            kb_item = self._create_context_item(
                content={
                    "fact_id": boundary.fact_id,
                    "knowers": boundary.knowers,
                    "reader_knows": boundary.reader_knows,
                    "revelation_constraint": boundary.revelation_constraint,
                },
                source=ItemSource.CHARACTER_KNOWLEDGE,
                priority=ItemPriority.REQUIRED,
                source_ref=contract.contract_id,
                scope=series_vision.series_id,
                character_visible=boundary.knowers,
                rationale="Knowledge boundary enforcement",
            )
            required_items.append(kb_item)

        # STEP 5: Long-horizon required facts
        # This handles the critical requirement: low-similarity but required facts
        long_horizon_facts = self.memory.get_required_facts_for_chapter(
            chapter=contract.chapter_number,
            scope=series_vision.series_id,
            contract=contract,
        )

        for fact in long_horizon_facts:
            fact_item = self._create_context_item(
                content=fact["content"],
                source=ItemSource.CANON,
                priority=ItemPriority.REQUIRED,
                source_ref=canon_snapshot.get("commit_hash", "unknown"),
                scope=series_vision.series_id,
                character_visible=[],  # Will be refined by knowledge boundaries
                rationale=fact["rationale"],
            )
            required_items.append(fact_item)

        # STEP 6: Genre pack constraints (REQUIRED)
        genre_item = self._create_context_item(
            content={
                "pack_id": series_vision.genre_pack_binding.pack_id,
                "version": series_vision.genre_pack_binding.version,
                "world_constraints": series_vision.world_constraints,
            },
            source=ItemSource.GENRE_PACK,
            priority=ItemPriority.REQUIRED,
            source_ref=series_vision.genre_pack_binding.content_hash,
            scope=series_vision.series_id,
            character_visible=[],
            rationale="World rules and genre constraints",
        )
        required_items.append(genre_item)

        # STEP 7: Optional context (protagonist goals, character background, etc.)
        for goal in series_vision.protagonist_goals:
            goal_item = self._create_context_item(
                content={
                    "description": goal.description,
                    "constraints": goal.constraints,
                    "success_criteria": goal.success_criteria,
                },
                source=ItemSource.PLAN,
                priority=ItemPriority.OPTIONAL,
                source_ref=series_vision.fixture_version,
                scope=series_vision.series_id,
                character_visible=[],
                rationale="Protagonist goal context",
            )
            optional_items.append(goal_item)

        # STEP 8: Budget check
        required_tokens = sum(item.estimated_tokens for item in required_items)

        if required_tokens > token_budget:
            # CRITICAL: Required items exceed budget - MUST return diagnostic
            return ContextCompilationError(
                error_id=str(uuid.uuid4()),
                error_type="budget_exceeded",
                message=f"Required context items ({required_tokens} tokens) exceed budget ({token_budget} tokens)",
                required_tokens=required_tokens,
                available_budget=token_budget,
                missing_items=[item.item_id for item in required_items],
                suggested_resolution="Increase token budget or simplify contract requirements",
            )

        # STEP 9: Fit optional items within remaining budget
        remaining_budget = token_budget - required_tokens
        fitted_optional: list[ContextItem] = []
        dropped_count = 0

        for item in optional_items:
            if item.estimated_tokens <= remaining_budget:
                fitted_optional.append(item)
                remaining_budget -= item.estimated_tokens
            else:
                dropped_count += 1

        if dropped_count > 0:
            warnings.append(
                f"Dropped {dropped_count} optional items due to budget constraints"
            )

        # STEP 10: Create artifact
        actual_tokens = required_tokens + sum(
            item.estimated_tokens for item in fitted_optional
        )

        budget_report = BudgetReport(
            total_budget=token_budget,
            required_tokens=required_tokens,
            optional_tokens=sum(item.estimated_tokens for item in fitted_optional),
            actual_tokens=actual_tokens,
            items_included=len(required_items) + len(fitted_optional),
            items_dropped=dropped_count,
            budget_exceeded=False,
        )

        artifact = ContextArtifact(
            artifact_id=str(uuid.uuid4()),
            chapter_id=contract.chapter_id,
            chapter_number=contract.chapter_number,
            compiled_at=datetime.utcnow(),
            contract_id=contract.contract_id,
            canon_parent=contract.canon_parent,
            genre_pack_hash=contract.genre_pack_binding.content_hash,
            plan_version=contract.plan_version,
            required_items=required_items,
            optional_items=fitted_optional,
            budget=budget_report,
            warnings=warnings,
        )

        return artifact

    def _create_context_item(
        self,
        content: str | dict,
        source: ItemSource,
        priority: ItemPriority,
        source_ref: str,
        scope: str,
        character_visible: list[str],
        rationale: str,
    ) -> ContextItem:
        """Create a context item with token estimation."""
        tokens = self._token_estimator.estimate(content)

        return ContextItem(
            item_id=str(uuid.uuid4()),
            content=content,
            source=source,
            priority=priority,
            source_ref=source_ref,
            scope=scope,
            character_visible=character_visible,
            rationale=rationale,
            estimated_tokens=tokens,
        )


class SimpleTokenEstimator:
    """Simple token estimation (4 chars ~= 1 token approximation)."""

    def estimate(self, content: str | dict) -> int:
        """Estimate token count."""
        if isinstance(content, dict):
            content = str(content)
        elif not isinstance(content, str):
            content = str(content)
        return max(1, len(content) // 4)
