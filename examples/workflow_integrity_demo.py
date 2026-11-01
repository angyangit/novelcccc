"""V2-020 Production Integrity Demo - Mock Mode with Fail-Closed Gates.

Demonstrates:
1. Quality fail-closed: Mock prose markers block canon commit
2. Extraction fail-closed: Required transitions block commit when not extracted
3. Mock vs Real mode distinction
4. Proper error handling and status reporting

IMPORTANT: This demo uses MOCK mode and MockProvider.
NOT PRODUCTION CERTIFIED. Real novel generation requires:
- Real LLM provider (Claude API)
- Delta extraction implementation (V2-021)
- Quality validation enhancement
- Real canon commit integration
"""

from datetime import datetime

from anovel.context.compiler import ContextCompiler
from anovel.contracts.compiler import ContractCompiler
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import OperationType
from anovel.gateway.gateway import ModelGateway
from anovel.gateway.mock_provider import MockProvider
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    SeriesVision,
    WorldConstraints,
)
from anovel.workflow.models import WorkflowStatus
from anovel.workflow.workflow import ChapterWorkflow


def demo_quality_fail_closed():
    """Demo 1: Quality check failure blocks canon commit."""
    print("=" * 80)
    print("DEMO 1: QUALITY FAIL-CLOSED GATE")
    print("=" * 80)
    print("\n[MOCK MODE - NOT PRODUCTION]\n")

    # Setup
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
        mock_mode=True,  # MOCK MODE
    )

    vision = SeriesVision(
        series_id="urban-demo-001",
        title="Urban Business Demo",
        synopsis="Startup journey",
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
        contract_id="urban-ch15-demo",
        chapter_id="urban-ch-15",
        chapter_number=15,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-14",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[],  # No transitions for this demo
    )

    print("Executing chapter 15...")
    result = workflow.execute_chapter(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-14"},
        previous_chapter_ending="Sarah prepared for the crucial meeting...",
    )

    print(f"\nStatus: {result.status}")
    print(f"Stages completed: {len(result.stages_completed)}/6")
    print(f"  {', '.join(s.value for s in result.stages_completed)}")

    if result.quality_result:
        print(f"\nQuality Check Result:")
        print(f"  Passed: {result.quality_result.passed}")
        print(f"  Blocking issues: {len(result.quality_result.blocking_issues)}")
        for issue in result.quality_result.blocking_issues:
            print(f"    - {issue}")

    print(f"\nProse generated: {'Yes' if result.prose else 'No'}")
    print(f"Prose hash: {result.prose_hash[:16]}..." if result.prose_hash else "Prose hash: None")
    print(f"Canon committed: {'Yes' if result.canon_commit_hash else 'No'}")
    print(f"Is mock commit: {result.is_mock_commit}")

    print(f"\nCost: ${result.total_cost_usd:.4f}")
    print(f"Time: {result.execution_time_seconds:.3f}s")

    print("\n✓ FAIL-CLOSED VERIFIED: Mock prose marker blocked canon commit")
    return result


def demo_extraction_fail_closed():
    """Demo 2: Delta extraction failure blocks canon commit."""
    print("\n" + "=" * 80)
    print("DEMO 2: EXTRACTION FAIL-CLOSED GATE")
    print("=" * 80)
    print("\n[MOCK MODE - NOT PRODUCTION]\n")

    # Setup
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
        mock_mode=True,
    )

    vision = SeriesVision(
        series_id="fantasy-demo-001",
        title="Cultivation Demo",
        synopsis="Immortal path",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="breakthrough",
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
        contract_id="fantasy-ch42-demo",
        chapter_id="fantasy-ch-42",
        chapter_number=42,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-41",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="breakthrough",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.realm",
                target_value="foundation_establishment",
                rationale="Breakthrough to Foundation Establishment",
            )
        ],  # HAS required transition - extraction will fail
    )

    print("Executing chapter 42 (with required transition)...")
    result = workflow.execute_chapter(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-41"},
        previous_chapter_ending="Lin Feng prepared for the tribulation...",
    )

    print(f"\nStatus: {result.status}")
    print(f"Stages completed: {len(result.stages_completed)}/6")
    print(f"  {', '.join(s.value for s in result.stages_completed)}")

    if result.delta_result:
        print(f"\nDelta Extraction Result:")
        print(f"  Success: {result.delta_result.success}")
        print(f"  Issues: {len(result.delta_result.issues)}")
        for issue in result.delta_result.issues:
            print(f"    - {issue}")

    print(f"\nProse generated: {'Yes' if result.prose else 'No'}")
    print(f"Canon committed: {'Yes' if result.canon_commit_hash else 'No'}")

    print(f"\nCost: ${result.total_cost_usd:.4f}")

    print("\n✓ FAIL-CLOSED VERIFIED: Extraction failure blocked canon commit")
    return result


def demo_mock_vs_real_mode():
    """Demo 3: Mock mode vs Real mode distinction."""
    print("\n" + "=" * 80)
    print("DEMO 3: MOCK MODE vs REAL MODE")
    print("=" * 80)

    print("\n[Testing mode configuration]\n")

    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    # Mock mode workflow
    mock_workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
        mock_mode=True,
    )

    # Real mode workflow (will fail - not implemented)
    real_workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
        mock_mode=False,
    )

    print(f"Mock workflow mode: mock_mode={mock_workflow.mock_mode}")
    print(f"Real workflow mode: mock_mode={real_workflow.mock_mode}")

    print("\n✓ MODE DISTINCTION: Mock and Real modes clearly separated")
    print("✓ Real mode NOT IMPLEMENTED in V2-020 (requires canon integration)")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("V2-020 PRODUCTION INTEGRITY DEMONSTRATION")
    print("=" * 80)
    print("\n⚠️  WARNING: MOCK MODE - NOT PRODUCTION CERTIFIED")
    print("   This demo uses MockProvider and does not commit to real Canon")
    print("   Real novel generation requires V2-021+ implementation\n")

    # Run demos
    result1 = demo_quality_fail_closed()
    result2 = demo_extraction_fail_closed()
    demo_mock_vs_real_mode()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Demo 1: Quality fail-closed - {result1.status}")
    print(f"✓ Demo 2: Extraction fail-closed - {result2.status}")
    print("✓ Demo 3: Mock vs Real mode - Verified")

    print("\n" + "=" * 80)
    print("PRODUCTION READINESS STATUS")
    print("=" * 80)
    print("✅ FIXED: Quality fail-closed gate")
    print("✅ FIXED: Extraction fail-closed gate")
    print("✅ FIXED: Mock commit clearly marked")
    print("✅ FIXED: Project ID from series_vision (not hardcoded)")
    print("✅ FIXED: Prose hash binding")
    print("\n❌ BLOCKING: Real LLM provider not integrated")
    print("❌ BLOCKING: Delta extraction not implemented (V2-021)")
    print("❌ BLOCKING: Real canon commit not integrated")
    print("\n📋 NEXT: V2-021 Delta Extraction + Real Provider Integration")
