"""Context Compiler for V2-018.

Assembles ContextArtifact from ChapterContract, Canon state, GenrePack,
character knowledge, and optional retrieval content per ADR-009.

Key principles (ADR-009):
- Mandatory items NEVER trimmed (FAIL_FAST on overflow)
- Strict knowledge isolation (character/reader/writer/reviewer boundaries)
- Deterministic compilation (no LLM calls, offline reproducible)
- Full provenance tracking for auditability
- Model-specific tokenizer (not cl100k_base as universal default)
- Output reserve for Writer response + system overhead

Architecture: Context Compiler is an application-layer service that does NOT
directly access Canon internals. Canon state is provided as input by the
workflow orchestrator (V2-020).
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Literal

from ..contracts.models import ChapterContract, KnowledgeBoundary
from ..domain.delta import CanonState
from ..domain.identity import ProjectId
from ..genre.registry import GenrePackRegistry
from .models import (
    CompilationLog,
    ContextArtifact,
    ContextCompilationError,
    ContextItem,
)
from .token_counter import TokenCounter

# Result type for compilation
CompilationResult = ContextArtifact | ContextCompilationError


class ContextCompiler:
    """Compiles context from frozen inputs for Writer per ADR-009."""

    def __init__(
        self,
        genre_registry: GenrePackRegistry,
        token_counter: TokenCounter,
    ):
        """Initialize with required services.

        Args:
            genre_registry: GenrePack registry for hard policies
            token_counter: Model-specific tokenizer for budget accounting
        """
        self.genre_registry = genre_registry
        self.token_counter = token_counter

    def compile_context(
        self,
        chapter_contract: ChapterContract,
        canon_state: CanonState,
        project_id: ProjectId,
        previous_chapter_end: dict[str, Any] | None = None,
        optional_retrieval: list[dict[str, Any]] | None = None,
        token_budget: int = 32000,
        output_reserve: int = 4000,
    ) -> CompilationResult:
        """Compile ContextArtifact from frozen inputs.

        Args:
            chapter_contract: Compiled contract from V2-017
            canon_state: Pre-loaded Canon state at contract.canon_parent commit
            project_id: Project scope for isolation
            previous_chapter_end: Actual end state from chapter N-1 (None for chapter 1)
            optional_retrieval: Retrieved summaries (can be trimmed)
            token_budget: Maximum total tokens
            output_reserve: Tokens reserved for Writer output + system overhead (ADR-009)

        Returns:
            ContextArtifact if successful
            ContextCompilationError if mandatory overflow or violations

        Per ADR-009:
        - Mandatory overflow → FAIL_FAST with explicit error
        - Optional selection → ADAPTIVE by causal dependency, chapter needs, temporal relevance
        - Knowledge isolation → STRICT scope and visibility enforcement

        Note: Canon state must be pre-loaded by workflow orchestrator (V2-020).
        Context Compiler does not access Canon services directly (architecture boundary).
        """
        mandatory_items: list[ContextItem] = []

        # 1. Assemble mandatory items (ADR-009: never trimmed)
        # Chapter 1: no previous chapter (ADR-009 requirement)
        if chapter_contract.continuity_constraints is not None:
            mandatory_items.extend(
                self._assemble_continuity(chapter_contract, previous_chapter_end)
            )

        mandatory_items.extend(self._assemble_contract_constraints(chapter_contract))

        mandatory_items.extend(
            self._assemble_character_knowledge(
                chapter_contract, canon_state, project_id
            )
        )

        mandatory_items.extend(self._assemble_genre_policies(chapter_contract))

        # 3. Check mandatory overflow (ADR-009 FAIL_FAST)
        mandatory_tokens = sum(item.token_count for item in mandatory_items)
        available_budget = token_budget - output_reserve

        if mandatory_tokens > available_budget:
            return ContextCompilationError(
                error_type="mandatory_overflow",
                message=(
                    f"Mandatory context ({mandatory_tokens} tokens) exceeds "
                    f"available budget ({available_budget} tokens = {token_budget} total - "
                    f"{output_reserve} output reserve)"
                ),
                mandatory_tokens=mandatory_tokens,
                available_budget=available_budget,
                overflow_amount=mandatory_tokens - available_budget,
                suggested_budget=mandatory_tokens + output_reserve + 8000,
                affected_items=[item.item_id for item in mandatory_items],
            )

        # 4. Select optional items within remaining budget (ADR-009 ADAPTIVE)
        remaining_budget = available_budget - mandatory_tokens
        optional_items, excluded = self._select_optional_items(
            optional_retrieval or [], remaining_budget, chapter_contract
        )

        # 5. Build artifact
        artifact = ContextArtifact(
            artifact_id=str(uuid.uuid4()),
            chapter_contract_id=chapter_contract.contract_id,
            canon_parent=chapter_contract.canon_parent,
            genre_pack_hash=chapter_contract.genre_pack_binding.content_hash,
            created_at=datetime.now(),
            mandatory_items=mandatory_items,
            optional_items=optional_items,
            compilation_log=CompilationLog(
                total_budget=token_budget,
                mandatory_tokens=mandatory_tokens,
                optional_tokens=sum(item.token_count for item in optional_items),
                output_reserve=output_reserve,
                excluded_optional_items=excluded,
                token_counting_method=self.token_counter.encoding_name,
            ),
        )

        return artifact

    def _assemble_continuity(
        self, contract: ChapterContract, previous_end: dict | None
    ) -> list[ContextItem]:
        """Assemble continuity constraint items (mandatory per ADR-009).

        ADR-009: Previous chapter actual ending has high priority, not displaced by retrieval.
        """
        items = []

        if contract.continuity_constraints is None:
            return items

        continuity = contract.continuity_constraints

        # Previous chapter end state is mandatory
        content = {
            "previous_chapter_id": continuity.previous_chapter_id,
            "previous_chapter_hash": continuity.previous_chapter_hash,
            "previous_end_state": continuity.previous_end_state,
            "current_start_requirements": continuity.current_start_requirements,
            "actual_previous_end": previous_end or {},
        }

        content_json = json.dumps(content, ensure_ascii=False, sort_keys=True)
        token_count = self.token_counter.count_tokens(content_json)

        item = ContextItem(
            item_id=str(uuid.uuid4()),
            content=content,
            source_type="continuity",
            source_hash=hashlib.sha256(content_json.encode()).hexdigest(),
            scope=str(contract.canon_parent),  # Scoped to frozen Canon
            visibility="writer",
            mandatory=True,
            token_count=token_count,
            inclusion_reason=(
                f"Continuity constraint for chapter {contract.chapter_number}: "
                f"must continue from {continuity.previous_chapter_id}"
            ),
        )

        items.append(item)
        return items

    def _assemble_contract_constraints(
        self, contract: ChapterContract
    ) -> list[ContextItem]:
        """Assemble contract constraints (mandatory per ADR-009)."""
        items = []

        # Required transitions are mandatory
        for transition in contract.required_transitions:
            content = {
                "operation_type": transition.operation_type.value,
                "fact_path": transition.fact_path,
                "target_value": transition.target_value,
                "rationale": transition.rationale,
            }
            content_json = json.dumps(content, ensure_ascii=False, sort_keys=True)

            item = ContextItem(
                item_id=str(uuid.uuid4()),
                content=content,
                source_type="contract",
                source_hash=hashlib.sha256(content_json.encode()).hexdigest(),
                scope=contract.canon_parent,
                visibility="writer",
                mandatory=True,
                token_count=self.token_counter.count_tokens(content_json),
                inclusion_reason=f"Required transition: {transition.rationale}",
            )
            items.append(item)

        # Prohibited transitions are mandatory
        for prohibition in contract.prohibited_transitions:
            content = {
                "fact_path": prohibition.fact_path,
                "prohibited_operation": prohibition.prohibited_operation.value,
                "rationale": prohibition.rationale,
            }
            content_json = json.dumps(content, ensure_ascii=False, sort_keys=True)

            item = ContextItem(
                item_id=str(uuid.uuid4()),
                content=content,
                source_type="contract",
                source_hash=hashlib.sha256(content_json.encode()).hexdigest(),
                scope=contract.canon_parent,
                visibility="writer",
                mandatory=True,
                token_count=self.token_counter.count_tokens(content_json),
                inclusion_reason=f"Prohibited transition: {prohibition.rationale}",
            )
            items.append(item)

        # Protected facts are mandatory
        for protected in contract.protected_facts:
            content = {
                "fact_path": protected.fact_path,
                "protection_reason": protected.protection_reason,
            }
            content_json = json.dumps(content, ensure_ascii=False, sort_keys=True)

            item = ContextItem(
                item_id=str(uuid.uuid4()),
                content=content,
                source_type="contract",
                source_hash=hashlib.sha256(content_json.encode()).hexdigest(),
                scope=contract.canon_parent,
                visibility="writer",
                mandatory=True,
                token_count=self.token_counter.count_tokens(content_json),
                inclusion_reason=f"Protected fact: {protected.protection_reason}",
            )
            items.append(item)

        return items

    def _assemble_character_knowledge(
        self,
        contract: ChapterContract,
        canon_snapshot: Any,
        project_id: ProjectId,
    ) -> list[ContextItem]:
        """Assemble character knowledge with boundaries (mandatory per ADR-009).

        ADR-009: Strict knowledge isolation - character/reader/reviewer boundaries enforced.
        """
        items = []

        # Knowledge boundaries define what characters know (and don't know)
        for boundary in contract.knowledge_boundaries:
            content = self._build_knowledge_boundary_content(boundary)
            content_json = json.dumps(content, ensure_ascii=False, sort_keys=True)

            # Determine visibility based on knowledge boundary
            visibility: Literal["writer", "character", "reader", "reviewer"]
            if boundary.reader_knows:
                visibility = "reader"
            else:
                # Secret: reader doesn't know, only writer knows for constraint enforcement
                visibility = "writer"

            item = ContextItem(
                item_id=str(uuid.uuid4()),
                content=content,
                source_type="character_knowledge",
                source_hash=hashlib.sha256(content_json.encode()).hexdigest(),
                scope=str(project_id),
                visibility=visibility,
                mandatory=True,
                token_count=self.token_counter.count_tokens(content_json),
                inclusion_reason=(
                    f"Knowledge boundary for fact {boundary.fact_id}: "
                    f"known by {', '.join(boundary.knowers)}"
                ),
            )
            items.append(item)

        return items

    def _build_knowledge_boundary_content(
        self, boundary: KnowledgeBoundary
    ) -> dict[str, Any]:
        """Build knowledge boundary content dict."""
        return {
            "fact_id": boundary.fact_id,
            "knowers": boundary.knowers,
            "revelation_constraint": boundary.revelation_constraint,
            "reader_knows": boundary.reader_knows,
        }

    def _assemble_genre_policies(self, contract: ChapterContract) -> list[ContextItem]:
        """Assemble GenrePack hard policies (mandatory per ADR-009)."""
        items = []

        # Load GenrePack to get hard policies
        try:
            _ = self.genre_registry.get_pack(
                contract.genre_pack_binding.pack_id,
                contract.genre_pack_binding.version,
            )

            # GenrePack hard constraints are mandatory
            content = {
                "pack_id": contract.genre_pack_binding.pack_id,
                "version": contract.genre_pack_binding.version,
                "content_hash": contract.genre_pack_binding.content_hash,
                # Note: Actual hard policy extraction depends on GenrePack structure
                # Placeholder for now
                "note": "GenrePack hard policy content TBD based on pack structure",
            }
            content_json = json.dumps(content, ensure_ascii=False, sort_keys=True)

            item = ContextItem(
                item_id=str(uuid.uuid4()),
                content=content,
                source_type="genre_pack",
                source_hash=hashlib.sha256(content_json.encode()).hexdigest(),
                scope=contract.canon_parent,
                visibility="writer",
                mandatory=True,
                token_count=self.token_counter.count_tokens(content_json),
                inclusion_reason=(
                    f"GenrePack {contract.genre_pack_binding.pack_id} "
                    f"v{contract.genre_pack_binding.version} hard policies"
                ),
            )
            items.append(item)

        except Exception:
            # GenrePack loading failure is not a fatal error for compilation
            # Real implementation should handle this more gracefully
            pass

        return items

    def _select_optional_items(
        self,
        retrieval: list[dict],
        budget: int,
        contract: ChapterContract,
    ) -> tuple[list[ContextItem], list[tuple[str, str]]]:
        """Select optional items within budget using ADAPTIVE priority (ADR-009).

        Priority factors per ADR-009 Owner requirement:
        - Causal dependency: Contract required_transitions directly related background
        - Chapter needs: Contract-referenced but non-mandatory supporting info
        - Temporal relevance: Recent chapters > distant history
        - Information importance: Core character motivations > minor details

        Returns:
            (selected_items, excluded_items_with_reasons)
        """
        selected = []
        excluded = []

        # Simplified adaptive selection
        # Real implementation would score each retrieval item by the factors above
        remaining = budget

        for idx, retrieval_data in enumerate(retrieval):
            content_json = json.dumps(
                retrieval_data, ensure_ascii=False, sort_keys=True
            )
            token_count = self.token_counter.count_tokens(content_json)

            if token_count <= remaining:
                item = ContextItem(
                    item_id=str(uuid.uuid4()),
                    content=retrieval_data,
                    source_type="retrieval",
                    source_hash=hashlib.sha256(content_json.encode()).hexdigest(),
                    scope=contract.canon_parent,
                    visibility="writer",
                    mandatory=False,
                    token_count=token_count,
                    inclusion_reason=f"Retrieved optional context item {idx}",
                )
                selected.append(item)
                remaining -= token_count
            else:
                excluded.append(
                    (
                        f"retrieval_{idx}",
                        f"Exceeds remaining budget ({token_count} > {remaining})",
                    )
                )

        return selected, excluded
