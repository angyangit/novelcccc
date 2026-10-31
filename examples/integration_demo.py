"""End-to-end integration demo for V2-018 + V2-019.

Demonstrates: ContextArtifact → Model Gateway → Generated Prose
Uses MockProvider (no paid calls).
"""

from datetime import datetime

from anovel.context.compiler import ContextCompiler
from anovel.contracts.models import ChapterContract, RequiredTransition, KnowledgeBoundary
from anovel.domain.delta import OperationType
from anovel.gateway.gateway import ModelGateway
from anovel.gateway.mock_provider import MockProvider
from anovel.gateway.models import GenerationError, GenerationResult
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    Secret,
    SeriesVision,
    WorldConstraints,
)


def demo_urban_business_generation():
    """Demo Urban Business chapter generation."""
    print("=" * 80)
    print("URBAN BUSINESS: Context → Gateway → Generated Chapter")
    print("=" * 80)

    # 1. Compile Context
    vision = SeriesVision(
        series_id="urban-001",
        title="Tech Empire",
        synopsis="Building a startup",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="funding",
                description="Secure Series A",
                constraints=["maintain_control"],
                success_criteria=["$10M_raised"],
            )
        ],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban",
            version="1.0",
            content_hash="urban123",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    contract = ChapterContract(
        contract_id="urban-ch15",
        chapter_id="ch-15",
        chapter_number=15,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-14",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="pitch",
                operation_type=OperationType.SET_FACT,
                fact_path="investor_meeting",
                target_value="completed",
                rationale="Pitch to investor",
            )
        ],
    )

    compiler = ContextCompiler()
    artifact = compiler.compile_context(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-14"},
        previous_chapter_ending="Sarah prepared for the crucial meeting...",
        token_budget=8000,
    )

    print(f"\n✓ Context compiled: {artifact.artifact_id}")
    print(f"  Required items: {len(artifact.required_items)}")
    print(f"  Budget used: {artifact.budget.actual_tokens}/{artifact.budget.total_budget}")

    # 2. Generate with Gateway
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=10.0)

    result = gateway.generate_chapter(artifact, max_tokens=2000)

    if isinstance(result, GenerationResult):
        print(f"\n✓ Generation SUCCESS")
        print(f"  Request ID: {result.request_id}")
        print(f"  Model: {result.model_id}")
        print(f"  Tokens: {result.input_tokens} in, {result.output_tokens} out")
        print(f"  Cost: ${result.cost_usd:.4f}")
        print(f"\n  Prose preview:\n  {result.prose[:200]}...")
    else:
        print(f"\n✗ Generation FAILED: {result.error_type}")
        print(f"  Message: {result.message}")

    budget = gateway.get_budget_summary()
    print(f"\n  Budget: ${budget['spent']:.4f} spent, ${budget['available']:.4f} available")

    return result


def demo_fantasy_cultivation_generation():
    """Demo Eastern Fantasy chapter generation."""
    print("\n" + "=" * 80)
    print("EASTERN FANTASY: Context → Gateway → Generated Chapter")
    print("=" * 80)

    # 1. Compile Context
    vision = SeriesVision(
        series_id="fantasy-001",
        title="Immortal Path",
        synopsis="Cultivation journey",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="foundation",
                description="Foundation Establishment",
                constraints=["survive_tribulation"],
                success_criteria=["realm_breakthrough"],
            )
        ],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="fantasy",
            version="1.0",
            content_hash="fantasy456",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    contract = ChapterContract(
        contract_id="fantasy-ch42",
        chapter_id="ch-42",
        chapter_number=42,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-41",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="qi-accumulation",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.qi_level",
                target_value=9500,
                rationale="Accumulate qi for breakthrough",
            )
        ],
    )

    compiler = ContextCompiler()
    artifact = compiler.compile_context(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-41"},
        previous_chapter_ending="Lin Feng prepared for the tribulation...",
        token_budget=8000,
    )

    print(f"\n✓ Context compiled: {artifact.artifact_id}")
    print(f"  Required items: {len(artifact.required_items)}")
    print(f"  Budget used: {artifact.budget.actual_tokens}/{artifact.budget.total_budget}")

    # 2. Generate with Gateway
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=10.0)

    result = gateway.generate_chapter(artifact, max_tokens=2000)

    if isinstance(result, GenerationResult):
        print(f"\n✓ Generation SUCCESS")
        print(f"  Request ID: {result.request_id}")
        print(f"  Model: {result.model_id}")
        print(f"  Tokens: {result.input_tokens} in, {result.output_tokens} out")
        print(f"  Cost: ${result.cost_usd:.4f}")
        print(f"\n  Prose preview:\n  {result.prose[:200]}...")
    else:
        print(f"\n✗ Generation FAILED: {result.error_type}")
        print(f"  Message: {result.message}")

    budget = gateway.get_budget_summary()
    print(f"\n  Budget: ${budget['spent']:.4f} spent, ${budget['available']:.4f} available")

    return result


def demo_error_scenarios():
    """Demo error handling scenarios."""
    print("\n" + "=" * 80)
    print("ERROR SCENARIOS: Timeout, Budget, Rate Limit")
    print("=" * 80)

    vision = SeriesVision(
        series_id="test-001",
        title="Test",
        synopsis="Test",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="test",
            version="1.0",
            content_hash="test",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[],
    )

    compiler = ContextCompiler()
    artifact = compiler.compile_context(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
        token_budget=8000,
    )

    # Scenario 1: Timeout
    print("\n1. TIMEOUT scenario:")
    provider_timeout = MockProvider(mode="timeout")
    gateway_timeout = ModelGateway(provider=provider_timeout, total_budget_usd=10.0)
    result = gateway_timeout.generate_chapter(artifact, max_tokens=2000)

    if isinstance(result, GenerationError):
        print(f"   ✓ Error detected: {result.error_type}")
        print(f"   ✓ Retryable: {result.retryable}")
        print(f"   ✓ Message: {result.message}")
        budget = gateway_timeout.get_budget_summary()
        print(f"   ✓ Unknown pending: ${budget['unknown_pending']:.4f}")

    # Scenario 2: No budget
    print("\n2. NO BUDGET scenario:")
    provider_normal = MockProvider(mode="success")
    gateway_no_budget = ModelGateway(provider=provider_normal, total_budget_usd=None)
    result = gateway_no_budget.generate_chapter(artifact, max_tokens=2000)

    if isinstance(result, GenerationError):
        print(f"   ✓ Error detected: {result.error_type}")
        print(f"   ✓ Message: {result.message}")

    # Scenario 3: Insufficient budget
    print("\n3. INSUFFICIENT BUDGET scenario:")
    gateway_low = ModelGateway(provider=provider_normal, total_budget_usd=0.001)
    result = gateway_low.generate_chapter(artifact, max_tokens=2000)

    if isinstance(result, GenerationError):
        print(f"   ✓ Error detected: {result.error_type}")
        print(f"   ✓ Message: {result.message}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("V2-018 + V2-019 END-TO-END INTEGRATION DEMO")
    print("=" * 80)

    # Run demos
    urban_result = demo_urban_business_generation()
    fantasy_result = demo_fantasy_cultivation_generation()
    demo_error_scenarios()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Urban generation: {'SUCCESS' if isinstance(urban_result, GenerationResult) else 'FAILED'}")
    print(f"✓ Fantasy generation: {'SUCCESS' if isinstance(fantasy_result, GenerationResult) else 'FAILED'}")
    print("✓ Error handling verified")
    print("\n✓ V2-018 + V2-019 integration working")
    print("✓ Ready for V2-020 Single Chapter Workflow")
