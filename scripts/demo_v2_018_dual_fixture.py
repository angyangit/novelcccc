#!/usr/bin/env python3
"""Dual-fixture demonstration for V2-018 Context Compiler.

Generates ContextArtifact for chapter 1 of both fixtures:
- Urban business startup
- Eastern fantasy cultivation
"""

import json
import uuid
from datetime import datetime
from unittest.mock import Mock

from anovel.context.compiler import ContextCompiler
from anovel.context.token_counter import TokenCounter
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import OperationType
from anovel.domain.identity import ProjectId
from anovel.planning.models import GenrePackBinding


class SimpleTokenCounter(TokenCounter):
    """Simple token counter for demo (4 chars per token)."""

    @property
    def encoding_name(self) -> str:
        return "simple-demo-tokenizer"

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


def create_urban_business_contract():
    """Create chapter 1 contract for urban business fixture."""
    return ChapterContract(
        contract_id=str(uuid.uuid4()),
        chapter_id="urban-ch1",
        chapter_number=1,
        plan_version="v1.0",
        created_at=datetime.now(),
        canon_parent="urban-canon-init",
        genre_pack_binding=GenrePackBinding(
            pack_id="urban-business-startup",
            version="1.0",
            content_hash="urban-hash-v1",
        ),
        required_transitions=[
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.startup_idea",
                target_value="AI-powered task management platform",
                rationale="Establish protagonist's core business vision",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.funding_status",
                target_value="bootstrapped",
                rationale="Initial funding constraint for story tension",
            ),
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
        continuity_constraints=None,  # Chapter 1
    )


def create_fantasy_cultivation_contract():
    """Create chapter 1 contract for eastern fantasy fixture."""
    return ChapterContract(
        contract_id=str(uuid.uuid4()),
        chapter_id="fantasy-ch1",
        chapter_number=1,
        plan_version="v1.0",
        created_at=datetime.now(),
        canon_parent="fantasy-canon-init",
        genre_pack_binding=GenrePackBinding(
            pack_id="eastern-fantasy-cultivation",
            version="1.0",
            content_hash="fantasy-hash-v1",
        ),
        required_transitions=[
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.cultivation_realm",
                target_value="Qi Condensation Stage 1",
                rationale="Establish protagonist's starting cultivation level",
            ),
            RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.has_heavenly_manual",
                target_value=True,
                rationale="Core advantage that drives story progression",
            ),
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
        continuity_constraints=None,  # Chapter 1
    )


def main():
    """Generate dual-fixture ContextArtifacts."""
    # Setup mocked services
    from anovel.domain.delta import CanonState

    mock_canon_state = CanonState(
        project_id=ProjectId("demo-project"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    mock_genre = Mock()
    mock_genre.get_pack = Mock(return_value=Mock())

    token_counter = SimpleTokenCounter()
    compiler = ContextCompiler(mock_genre, token_counter)

    print("=" * 80)
    print("V2-018 Context Compiler - Dual-Fixture Demonstration")
    print("=" * 80)

    # Urban Business Fixture
    print("\n[1/2] Urban Business Startup - Chapter 1")
    print("-" * 80)

    urban_contract = create_urban_business_contract()
    urban_result = compiler.compile_context(
        chapter_contract=urban_contract,
        canon_state=mock_canon_state,
        project_id=ProjectId("urban-business-001"),
        token_budget=10000,
        output_reserve=2000,
    )

    print(f"Contract ID: {urban_contract.contract_id}")
    print(f"Chapter: {urban_contract.chapter_number}")
    print(f"Genre Pack: {urban_contract.genre_pack_binding.pack_id}")
    print(f"Required Transitions: {len(urban_contract.required_transitions)}")

    if hasattr(urban_result, "artifact_id"):
        print(f"\n✅ Compilation SUCCESS")
        print(f"Artifact ID: {urban_result.artifact_id}")
        print(f"Mandatory Items: {len(urban_result.mandatory_items)}")
        print(f"Optional Items: {len(urban_result.optional_items)}")
        print(f"Mandatory Tokens: {urban_result.compilation_log.mandatory_tokens}")
        print(f"Optional Tokens: {urban_result.compilation_log.optional_tokens}")
        print(f"Output Reserve: {urban_result.compilation_log.output_reserve}")
        print(f"Token Method: {urban_result.compilation_log.token_counting_method}")

        print(f"\nSample Mandatory Items:")
        for i, item in enumerate(urban_result.mandatory_items[:3], 1):
            print(f"  {i}. {item.source_type} - {item.inclusion_reason[:60]}...")
    else:
        print(f"\n❌ Compilation FAILED: {urban_result.error_type}")
        print(f"Message: {urban_result.message}")

    # Eastern Fantasy Fixture
    print("\n[2/2] Eastern Fantasy Cultivation - Chapter 1")
    print("-" * 80)

    fantasy_contract = create_fantasy_cultivation_contract()
    fantasy_result = compiler.compile_context(
        chapter_contract=fantasy_contract,
        canon_state=mock_canon_state,
        project_id=ProjectId("fantasy-cultivation-001"),
        token_budget=10000,
        output_reserve=2000,
    )

    print(f"Contract ID: {fantasy_contract.contract_id}")
    print(f"Chapter: {fantasy_contract.chapter_number}")
    print(f"Genre Pack: {fantasy_contract.genre_pack_binding.pack_id}")
    print(f"Required Transitions: {len(fantasy_contract.required_transitions)}")

    if hasattr(fantasy_result, "artifact_id"):
        print(f"\n✅ Compilation SUCCESS")
        print(f"Artifact ID: {fantasy_result.artifact_id}")
        print(f"Mandatory Items: {len(fantasy_result.mandatory_items)}")
        print(f"Optional Items: {len(fantasy_result.optional_items)}")
        print(f"Mandatory Tokens: {fantasy_result.compilation_log.mandatory_tokens}")
        print(f"Optional Tokens: {fantasy_result.compilation_log.optional_tokens}")
        print(f"Output Reserve: {fantasy_result.compilation_log.output_reserve}")
        print(f"Token Method: {fantasy_result.compilation_log.token_counting_method}")

        print(f"\nSample Mandatory Items:")
        for i, item in enumerate(fantasy_result.mandatory_items[:3], 1):
            print(f"  {i}. {item.source_type} - {item.inclusion_reason[:60]}...")
    else:
        print(f"\n❌ Compilation FAILED: {fantasy_result.error_type}")
        print(f"Message: {fantasy_result.message}")

    print("\n" + "=" * 80)
    print("Dual-Fixture Demonstration Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
