"""Stage 9 Phase 3: StructuredExtractor Real Execution Test

Tests real LLM extraction of state changes from prose.
"""

from anovel.config import get_real_provider_config, mask_api_key
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.gateway.anthropic_provider import AnthropicProvider
from anovel.gateway.budget_protected import BudgetProtectedGateway
from anovel.planning.models import SeriesVision
from anovel.workflow.structured_extractor import StructuredExtractor


def test_structured_extraction():
    """Test structured extraction with real LLM."""
    print("=" * 80)
    print("Stage 9 Phase 3: StructuredExtractor Real Execution Test")
    print("=" * 80)
    print()

    # Load configuration
    config = get_real_provider_config()
    print("Provider Configuration:")
    print(f"  Base URL: {config['base_url']}")
    print(f"  API Key: {mask_api_key(config['api_key'])}")
    print(f"  Model ID: {config['model_id']}")
    print()

    # Create provider and gateway
    provider = AnthropicProvider(
        model_id=config["model_id"],
        api_key=config["api_key"],
        base_url=config["base_url"],
        allow_real_calls=True,
    )
    gateway = BudgetProtectedGateway(provider, total_budget_usd=5.0)
    print("✓ Budget-protected gateway initialized")
    print()

    # Create test data
    sample_prose = """李明走进图书馆，找到了《时间简史》这本书。他坐在窗边的座位上，开始阅读第一章。

读了两个小时后，李明合上书本，感到收获很大。他把书放进背包，准备明天继续来读。

走出图书馆时，天色已晚。李明决定去校园食堂吃晚饭。"""

    import hashlib

    prose_hash = hashlib.sha256(sample_prose.encode()).hexdigest()

    # Create test vision
    from anovel.domain.delta import OperationType
    from datetime import datetime
    from anovel.planning.models import GenrePackBinding, ProtagonistGoal, WorldConstraints

    vision = SeriesVision(
        series_id="test_series",
        title="测试系列",
        synopsis="现代校园学习故事",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="g1",
                description="学习与成长",
                constraints=[],
                success_criteria=["完成学业"],
            )
        ],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="contemporary", version="1.0", content_hash="test"
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # Create test contract
    contract = ChapterContract(
        contract_id="test_contract_001",
        chapter_id="test_chapter_001",
        chapter_number=1,
        plan_version="1.0",
        created_at=datetime.now(),
        canon_parent="genesis",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="t1",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.location",
                target_value="library",
                rationale="李明进入图书馆",
            ),
            RequiredTransition(
                transition_id="t2",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.activity",
                target_value="reading",
                rationale="李明开始读书",
            ),
        ],
    )

    print("Test Data:")
    print(f"  Prose Length: {len(sample_prose)} chars")
    print(f"  Prose Hash: {prose_hash[:16]}...")
    print(f"  Required Transitions: {len(contract.required_transitions)}")
    print()

    # Create extractor
    extractor = StructuredExtractor(gateway)
    print("✓ StructuredExtractor initialized")
    print()

    # Run extraction
    print("-" * 80)
    print("Running Real LLM Extraction")
    print("-" * 80)
    try:
        result = extractor.extract(
            prose=sample_prose,
            prose_hash=prose_hash,
            contract=contract,
            series_vision=vision,
            canon_parent="genesis",
        )

        print(f"✓ Extraction completed")
        print()
        print("Extraction Result:")
        print(f"  Status: {result.status.value}")
        print(f"  Method: {result.extraction_method}")
        print(f"  Operations Found: {len(result.delta.operations) if result.delta else 0}")
        print()

        if result.delta:
            print("Operations:")
            for i, op in enumerate(result.delta.operations):
                print(f"  {i+1}. {op.path} = {op.value}")
                print(f"     Evidence: {op.evidence.source_ref}")

        print()
        print("Diagnostics:")
        print(f"  Coverage: {result.diagnostics.coverage_percentage:.1f}%")
        print(
            f"  Required Found: {result.diagnostics.required_transitions_found}/{contract.required_transitions.__len__()}"
        )
        if result.issues:
            print(f"  Issues: {len(result.issues)}")
            for issue in result.issues:
                print(f"    - {issue}")

        print()

    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        import traceback

        traceback.print_exc()

    # Print budget report
    gateway.print_budget_report()

    print("=" * 80)
    print("Phase 3 Complete: StructuredExtractor Real Execution Verified")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(test_structured_extraction())
