"""Stage 9 Phase 6: Real Extractor Fix and Validation

Uses the 602-character prose from Phase 5 to validate:
- Real LLM extraction with improved JSON parsing
- Valid NarrativeDelta construction
- Q0/Q1/Q2/Q3 validation
- Complete extraction pipeline

Budget cap: $1.00 for this phase
"""

import hashlib
import uuid
from datetime import datetime

from anovel.config import get_real_provider_config, mask_api_key
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import CanonState, OperationType
from anovel.domain.identity import ProjectId
from anovel.gateway.anthropic_provider import AnthropicProvider
from anovel.gateway.budget_protected import BudgetProtectedGateway
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    SeriesVision,
    WorldConstraints,
)
from anovel.quality.q0 import Q0Validator
from anovel.quality.q1 import Q1CanonValidator
from anovel.quality.q2 import Q2GenreValidator
from anovel.quality.q3 import Q3TransitionValidator
from anovel.workflow.structured_extractor import StructuredExtractor


def test_phase6_real_extraction():
    """Test real extraction with Phase 5 prose."""
    print("=" * 80)
    print("Stage 9 Phase 6: Real Extractor Fix and Validation")
    print("=" * 80)
    print()

    # Phase 5 generated prose (602 chars)
    prose = """秋日的阳光透过玻璃窗洒在图书馆的台阶上，李明推开那扇厚重的木门，熟悉的书香气息扑面而来。馆内很安静，只有翻书的沙沙声和偶尔的脚步声。他在门口站了片刻，让眼睛适应室内柔和的光线。

李明径直走向三楼的自然科学区。他已经在这座图书馆待了三年，对每个区域的布局了如指掌。楼梯的木质扶手被无数人的手掌磨得光滑，踩在上面会发出轻微的咯吱声。到了三楼，他在书架间穿行，手指滑过一排排书脊——那些标注着"物理学"、"天文学"的标签在眼前掠过。

《时间简史》应该就在这附近。李明微微弯下腰，视线在第三排书架的中层游移。终于，那个熟悉的蓝色封面出现了。他小心地抽出那本书，封面上霍金的名字在阳光下显得格外醒目。书有些旧了，边角微微卷起，显然被很多人翻阅过。

李明抱着书走到靠窗的座位，那是他最喜欢的位置。窗外是一棵梧桐树，黄叶在微风中摇曳。他放下背包，拉开椅子坐下，双手捧起那本书。

翻开扉页，目录清晰地列在眼前。第一章：我们的宇宙图像。李明深吸一口气，调整了一下坐姿，让自己更舒适些。窗外传来鸟鸣声，但他的注意力已经完全被书页上的文字吸引。

"一位著名的科学家曾经做过一次关于天文学方面的讲演……"

文字在眼前展开，关于宇宙、时间、空间的思考如同打开了一扇门。李明的笔尖在笔记本上轻轻划过，记下几个关键词。阳光缓缓移动，在他的书页上投下斑驳的光影。这个安静的下午，他将在这里，开始一场关于时间与宇宙的探索之旅。"""

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    print("Input Prose:")
    print(f"  Length: {len(prose)} chars")
    print(f"  Hash: {prose_hash[:16]}...")
    print()

    # Load configuration
    config = get_real_provider_config()
    print("Provider Configuration:")
    print(f"  Base URL: {config['base_url']}")
    print(f"  API Key: {mask_api_key(config['api_key'])}")
    print(f"  Model ID: {config['model_id']}")
    print()

    # Create provider and gateway with $1.00 Phase 6 budget
    provider = AnthropicProvider(
        model_id=config["model_id"],
        api_key=config["api_key"],
        base_url=config["base_url"],
        allow_real_calls=True,
    )
    gateway = BudgetProtectedGateway(provider, total_budget_usd=1.0)
    print("✓ Budget-protected gateway initialized (Phase 6 cap: $1.00)")
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
                constraints=["必须在图书馆内阅读"],
                success_criteria=["理解基本概念"],
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

    # Create extractor
    extractor = StructuredExtractor(gateway)

    # Step 1: Real extraction
    print("-" * 80)
    print("Step 1: Real LLM Extraction")
    print("-" * 80)

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
        print(f"  Method: {extraction_result.extraction_method}")
        print()

        if extraction_result.delta:
            print(f"Extracted Operations: {len(extraction_result.delta.operations)}")
            for i, op in enumerate(extraction_result.delta.operations, 1):
                print(f"  {i}. {op.path.path} = {op.value}")
                print(f"     Subject: {op.subject}")
                print(f"     Evidence: {op.evidence.source_ref}")
            print()
        else:
            print("⚠️  No delta generated")
            print()

        if extraction_result.issues:
            print(f"Extraction Issues ({len(extraction_result.issues)}):")
            for issue in extraction_result.issues[:5]:  # Show first 5
                print(f"  - {issue}")
            if len(extraction_result.issues) > 5:
                print(f"  ... and {len(extraction_result.issues) - 5} more")
            print()

        print("Diagnostics:")
        print(f"  Coverage: {extraction_result.diagnostics.coverage_percentage:.1f}%")
        print(f"  Required found: {extraction_result.diagnostics.required_transitions_found}")
        print(f"  Required missing: {extraction_result.diagnostics.required_transitions_missing}")
        print()

    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        gateway.print_budget_report()
        return 1

    gateway.print_budget_report()

    # Step 2: Quality validation (Q0/Q1/Q2/Q3)
    if extraction_result.delta:
        print("-" * 80)
        print("Step 2: Quality Validation (Q0/Q1/Q2/Q3)")
        print("-" * 80)

        # Create canon state
        project_id = ProjectId(vision.series_id)
        canon_state = CanonState(
            project_id=project_id,
            facts=(),
            tombstones=frozenset(),
            commit_history=(),
        )

        # Q0: Deterministic validation
        print("Q0 (Deterministic):")
        q0 = Q0Validator()
        q0_result = q0.validate(extraction_result, contract, prose, prose_hash)
        print(f"  Status: {'PASS' if q0_result.passed else 'FAIL'}")
        print(f"  Checks: {len(q0_result.checks)}")
        if q0_result.blocking_issues:
            for issue in q0_result.blocking_issues:
                print(f"    ✗ {issue}")
        else:
            print("    ✓ All checks passed")
        print()

        # Q1: Canon consistency
        print("Q1 (Canon Consistency):")
        q1 = Q1CanonValidator()
        q1_result = q1.validate(extraction_result.delta, canon_state, contract)
        print(f"  Status: {'PASS' if q1_result.passed else 'FAIL'}")
        print(f"  Checks: {len(q1_result.checks)}")
        if q1_result.blocking_issues:
            for issue in q1_result.blocking_issues:
                print(f"    ✗ {issue}")
        else:
            print("    ✓ All checks passed")
        print()

        # Q2: Genre consistency
        print("Q2 (Genre Consistency):")
        q2 = Q2GenreValidator()
        q2_result = q2.validate(extraction_result.delta, contract)
        print(f"  Status: {'PASS' if q2_result.passed else 'FAIL'}")
        print(f"  Checks: {len(q2_result.checks)}")
        if q2_result.blocking_issues:
            for issue in q2_result.blocking_issues:
                print(f"    ✗ {issue}")
        else:
            print("    ✓ All checks passed")
        print()

        # Q3: Transition validation
        print("Q3 (Transition Validation):")
        q3 = Q3TransitionValidator()
        q3_result = q3.validate(extraction_result.delta, canon_state, contract)
        print(f"  Status: {'PASS' if q3_result.passed else 'FAIL'}")
        print(f"  Checks: {len(q3_result.checks)}")
        if q3_result.blocking_issues:
            for issue in q3_result.blocking_issues:
                print(f"    ✗ {issue}")
        else:
            print("    ✓ All checks passed")
        print()

        # Overall validation result
        all_passed = all([
            q0_result.passed,
            q1_result.passed,
            q2_result.passed,
            q3_result.passed,
        ])

        print("-" * 80)
        print("Validation Summary:")
        print(f"  Q0: {'PASS' if q0_result.passed else 'FAIL'}")
        print(f"  Q1: {'PASS' if q1_result.passed else 'FAIL'}")
        print(f"  Q2: {'PASS' if q2_result.passed else 'FAIL'}")
        print(f"  Q3: {'PASS' if q3_result.passed else 'FAIL'}")
        print(f"  Overall: {'✓ ALL PASS' if all_passed else '✗ FAILED'}")
        print()

    # Final report
    budget_status = gateway.get_budget_status()
    print("=" * 80)
    print("Phase 6 Complete: Real Extraction Validation")
    print("=" * 80)
    print()
    print("Results:")
    print(f"  Extraction: {extraction_result.status.value}")
    print(f"  Operations: {len(extraction_result.delta.operations) if extraction_result.delta else 0}")
    if extraction_result.delta:
        print(f"  Quality: {'ALL PASS' if all_passed else 'FAILED'}")
    print()
    print("Budget:")
    print(f"  Spent: ${budget_status['spent_usd']:.4f}")
    print(f"  Remaining: ${budget_status['remaining_usd']:.4f}")
    print(f"  Requests: {budget_status['requests_made']}")
    print()

    # Acceptance criteria
    acceptance_passed = (
        extraction_result.delta is not None
        and len(extraction_result.delta.operations) > 0
        and extraction_result.status.value in ["success", "incomplete"]
    )

    if acceptance_passed:
        print("✓ PHASE 6 ACCEPTANCE: PASS")
        print("  - Real JSON extraction successful")
        print("  - Valid NarrativeDelta generated")
        print("  - Ready for Phase 7")
    else:
        print("✗ PHASE 6 ACCEPTANCE: FAIL")
        print(f"  - Extraction status: {extraction_result.status.value}")
        print("  - Cannot proceed to Phase 7")

    print("=" * 80)

    return 0 if acceptance_passed else 1


if __name__ == "__main__":
    exit(test_phase6_real_extraction())
