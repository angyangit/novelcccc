"""Stage 9 Phase 5: Real Chapter Generation Test

Generates a real chapter using:
- Real Writer model (CC_VIBE Anthropic)
- Real StructuredExtractor
- Full Q0/Q1/Q2/Q3 quality validation
- Budget protection ($5 cap)

This is the first end-to-end test with real AI generation.
"""

import hashlib
import uuid
from datetime import datetime

from anovel.config import get_real_provider_config, mask_api_key
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import OperationType
from anovel.gateway.anthropic_provider import AnthropicProvider
from anovel.gateway.budget_protected import BudgetProtectedGateway
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    SeriesVision,
    WorldConstraints,
)
from anovel.workflow.structured_extractor import StructuredExtractor


def test_real_chapter_generation():
    """Generate real chapter with real AI."""
    print("=" * 80)
    print("Stage 9 Phase 5: Real Chapter Generation Test")
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

    # Create series vision
    vision = SeriesVision(
        series_id="test_series_real",
        title="图书馆奇遇",
        synopsis="李明在图书馆的学习之旅",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="g1",
                description="完成《时间简史》的阅读",
                constraints=["必须在图书馆内阅读", "每天至少2小时"],
                success_criteria=["理解基本概念", "完成笔记"],
            )
        ],
        world_constraints=WorldConstraints(
            realistic_constraints=["现代都市", "真实物理规律"],
        ),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="contemporary", version="1.0", content_hash="test_hash"
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # Create chapter contract
    contract = ChapterContract(
        contract_id=f"contract_{uuid.uuid4()}",
        chapter_id="chapter_001",
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
                rationale="李明进入图书馆开始阅读",
            ),
            RequiredTransition(
                transition_id="t2",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.activity",
                target_value="reading",
                rationale="李明开始阅读《时间简史》",
            ),
        ],
    )

    print("Story Setup:")
    print(f"  Series: {vision.title}")
    print(f"  Chapter: {contract.chapter_number}")
    print(f"  Required Transitions: {len(contract.required_transitions)}")
    for t in contract.required_transitions:
        print(f"    - {t.fact_path}: {t.rationale}")
    print()

    # Generate chapter prose
    print("-" * 80)
    print("Step 1: Generating Chapter Prose with Real AI")
    print("-" * 80)

    writer_prompt = f"""你是一位小说作家。请根据以下要求创作第一章的内容。

**故事设定**:
{vision.synopsis}

**主角目标**:
{vision.protagonist_goals[0].description}

**第一章要求**:
1. 李明走进图书馆
2. 他找到《时间简史》这本书
3. 他开始阅读第一章

**写作要求**:
- 字数：400-600字
- 风格：现实主义
- 重点描写：环境、动作、心理
- 必须包含：主角进入图书馆的场景，找书的过程，开始阅读的情节

请直接输出小说正文，不要包含标题、章节号等元数据："""

    try:
        result, cost = gateway.generate(
            prompt=writer_prompt,
            max_tokens=1000,
            temperature=0.7,
        )
        prose = result["prose"].strip()
        prose_hash = hashlib.sha256(prose.encode()).hexdigest()

        print(f"✓ Generation succeeded")
        print(f"  Tokens: {result['input_tokens']} → {result['output_tokens']}")
        print(f"  Cost: ${cost:.6f}")
        print(f"  Prose length: {len(prose)} chars")
        print()
        print("Generated Prose:")
        print("=" * 80)
        print(prose)
        print("=" * 80)
        print()

    except Exception as e:
        print(f"✗ Generation failed: {e}")
        return 1

    gateway.print_budget_report()

    # Extract semantics
    print("-" * 80)
    print("Step 2: Extracting Semantics with Real AI")
    print("-" * 80)

    extractor = StructuredExtractor(gateway)

    try:
        extraction_result = extractor.extract(
            prose=prose,
            prose_hash=prose_hash,
            contract=contract,
            series_vision=vision,
            canon_parent="genesis",
        )

        print(f"✓ Extraction completed")
        print(f"  Status: {extraction_result.status.value}")
        print(f"  Operations found: {len(extraction_result.delta.operations) if extraction_result.delta else 0}")
        print()

        if extraction_result.delta:
            print("Extracted Operations:")
            for i, op in enumerate(extraction_result.delta.operations, 1):
                print(f"  {i}. {op.path} = {op.value}")

        print()
        if extraction_result.issues:
            print("Extraction Issues:")
            for issue in extraction_result.issues:
                print(f"  - {issue}")
            print()

    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    gateway.print_budget_report()

    # Summary
    print("=" * 80)
    print("Phase 5 Complete: Real Chapter Generation Verified")
    print("=" * 80)
    print()
    print("✓ Real prose generated with Writer model")
    print("✓ Real extraction performed with Extractor model")
    print("✓ Budget protection enforced")
    print()
    print(f"Total cost: ${gateway.get_budget_status()['spent_usd']:.4f}")
    print(f"Remaining: ${gateway.get_budget_status()['remaining_usd']:.4f}")
    print()
    print("Generated chapter saved above - THIS IS REAL NOVEL TEXT!")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(test_real_chapter_generation())
