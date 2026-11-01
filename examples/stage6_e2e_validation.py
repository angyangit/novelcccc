"""Stage 6: Offline End-to-End Validation

Owner要求: 两个完整场景通过Q0→Q1→Q2→Q3→DeltaReducer验证链。
覆盖所有失败模式，仅模拟（不修改生产Canon）。

Scenarios:
1. Urban Business - 成功路径（所有质量门通过）
2. Genre Violation - 失败路径（Q2阻断）
"""

import hashlib
import uuid
from datetime import datetime

from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import (
    CanonState,
    DeltaReducer,
    OperationType,
)
from anovel.domain.identity import ProjectId
from anovel.planning.models import (
    GenrePackBinding,
    SeriesVision,
    WorldConstraints,
)
from anovel.quality.q0 import Q0Validator
from anovel.quality.q1 import Q1CanonValidator
from anovel.quality.q2 import Q2GenreValidator
from anovel.quality.q3 import Q3TransitionValidator
from anovel.workflow.offline_extractor import OfflineExtractor


def scenario_1_success_all_gates_pass():
    """Scenario 1: Urban Business - 所有质量门通过."""
    print("=" * 80)
    print("Scenario 1: Urban Business Success - Full Quality Gate Chain")
    print("=" * 80)

    extractor = OfflineExtractor()
    q0 = Q0Validator()
    q1 = Q1CanonValidator()
    q2 = Q2GenreValidator()
    q3 = Q3TransitionValidator()
    reducer = DeltaReducer()

    prose = """
    第10章：融资到账

    经过艰苦谈判，Sarah的公司终于获得了红杉资本的投资。

    "funding_amount是500万美元。" 投资人说。

    合同签署后，公司账户余额变为5000000美元。

    这轮funding_round标记为"Series A"完成。
    """

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    series_vision = SeriesVision(
        series_id="urban-startup-01",
        title="硅谷创业梦",
        synopsis="都市商业小说",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban",
            version="1.0",
            content_hash="urban-pack-hash",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    contract = ChapterContract(
        contract_id="urban-ch10",
        chapter_id="ch-10",
        chapter_number=10,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-9",
        genre_pack_binding=series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="funding",
                operation_type=OperationType.SET_FACT,
                fact_path="funding_amount",
                target_value=5000000,
                rationale="Investment received",
            ),
            RequiredTransition(
                transition_id="round",
                operation_type=OperationType.SET_FACT,
                fact_path="funding_round",
                target_value="Series A",
                rationale="Round completed",
            ),
        ],
    )

    canon_state = CanonState(
        project_id=ProjectId(series_vision.series_id),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Step 1: Extract
    print("\n[Step 1] Extraction...")
    extraction_result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=series_vision,
        canon_parent="canon-9",
    )
    print(f"  Status: {extraction_result.status}")
    print(f"  Operations: {len(extraction_result.delta.operations)}")

    # Step 2: Q0 Deterministic Validation
    print("\n[Step 2] Q0 Deterministic Checks...")
    q0_result = q0.validate(extraction_result, contract, prose, prose_hash)
    print(f"  Passed: {q0_result.passed}")
    if not q0_result.passed:
        print("  ❌ Q0 FAILED:")
        for issue in q0_result.blocking_issues:
            print(f"    - {issue}")
        return False

    # Step 3: Q1 Canon Consistency
    print("\n[Step 3] Q1 Canon Consistency...")
    q1_result = q1.validate(extraction_result.delta, canon_state, contract)
    print(f"  Passed: {q1_result.passed}")
    if not q1_result.passed:
        print("  ❌ Q1 FAILED:")
        for issue in q1_result.blocking_issues:
            print(f"    - {issue}")
        return False

    # Step 4: Q2 Genre Consistency
    print("\n[Step 4] Q2 Genre Consistency...")
    q2_result = q2.validate(extraction_result.delta, contract)
    print(f"  Passed: {q2_result.passed}")
    if not q2_result.passed:
        print("  ❌ Q2 FAILED:")
        for issue in q2_result.blocking_issues:
            print(f"    - {issue}")
        return False

    # Step 5: Q3 Transition Coverage
    print("\n[Step 5] Q3 Transition Coverage...")
    q3_result = q3.validate(extraction_result.delta, canon_state, contract)
    print(f"  Passed: {q3_result.passed}")
    if not q3_result.passed:
        print("  ❌ Q3 FAILED:")
        for issue in q3_result.blocking_issues:
            print(f"    - {issue}")
        return False

    # Step 6: DeltaReducer Apply (Simulation Only)
    print("\n[Step 6] DeltaReducer Apply (Simulation)...")
    try:
        new_canon = reducer.apply_delta(canon_state, extraction_result.delta)
        print(f"  ✓ Successfully applied to Canon")
        print(f"  New Canon: {len(new_canon.facts)} facts")
    except Exception as e:
        print(f"  ❌ DeltaReducer FAILED: {e}")
        return False

    print("\n✅ Scenario 1 SUCCESS: All quality gates passed")
    print("   Q0 ✓ | Q1 ✓ | Q2 ✓ | Q3 ✓ | Reducer ✓")
    return True


def scenario_2_genre_violation_blocked():
    """Scenario 2: GenrePack缺失 - Q2阻断."""
    print("\n" + "=" * 80)
    print("Scenario 2: Genre Violation - Q2 Should Block")
    print("=" * 80)

    extractor = OfflineExtractor()
    q0 = Q0Validator()
    q1 = Q1CanonValidator()
    q2 = Q2GenreValidator()

    prose = """
    第5章：商业谈判

    Sarah与投资人进行谈判，age是28岁。
    """

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    series_vision = SeriesVision(
        series_id="test-genre-violation",
        title="Test",
        synopsis="Test",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban",
            version="1.0",
            content_hash="test",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # Contract缺失GenrePack binding - 模拟配置错误
    contract = ChapterContract(
        contract_id="test-ch5",
        chapter_id="ch-5",
        chapter_number=5,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-4",
        genre_pack_binding=None,  # Missing!
        required_transitions=[
            RequiredTransition(
                transition_id="age",
                operation_type=OperationType.SET_FACT,
                fact_path="age",
                target_value=28,
                rationale="Age reveal",
            ),
        ],
    )

    canon_state = CanonState(
        project_id=ProjectId(series_vision.series_id),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Step 1: Extract
    print("\n[Step 1] Extraction...")
    extraction_result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=series_vision,
        canon_parent="canon-4",
    )
    print(f"  Status: {extraction_result.status}")

    # Step 2: Q0
    print("\n[Step 2] Q0...")
    q0_result = q0.validate(extraction_result, contract, prose, prose_hash)
    print(f"  Passed: {q0_result.passed}")

    if not q0_result.passed:
        print("  Note: Q0 failed (unexpected in this scenario)")
        return False

    # Step 3: Q1
    print("\n[Step 3] Q1...")
    q1_result = q1.validate(extraction_result.delta, canon_state, contract)
    print(f"  Passed: {q1_result.passed}")

    if not q1_result.passed:
        print("  Note: Q1 failed (unexpected in this scenario)")
        return False

    # Step 4: Q2 - Should FAIL due to missing GenrePack binding
    print("\n[Step 4] Q2 (Expected to FAIL)...")
    q2_result = q2.validate(extraction_result.delta, contract)
    print(f"  Passed: {q2_result.passed}")

    if q2_result.passed:
        print("  ❌ TEST FAILED: Q2 should have blocked missing GenrePack")
        return False

    print("  ✓ Q2 correctly blocked:")
    for issue in q2_result.blocking_issues:
        print(f"    - {issue}")

    print("\n✅ Scenario 2 SUCCESS: Q2 correctly blocked genre violation")
    print("   Q0 ✓ | Q1 ✓ | Q2 ✗ (Expected) | Pipeline Blocked ✓")
    return True


def main():
    print()
    print("=" * 80)
    print("Stage 6: Offline End-to-End Validation")
    print("=" * 80)
    print()
    print("Full quality gate chain: Extraction → Q0 → Q1 → Q2 → Q3 → DeltaReducer")
    print("Simulation only - no production Canon modification")
    print()

    results = []
    results.append(("Success Path", scenario_1_success_all_gates_pass()))
    results.append(("Genre Violation", scenario_2_genre_violation_blocked()))

    print()
    print("=" * 80)
    print("Stage 6 Summary")
    print("=" * 80)
    print()
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")

    print()
    all_passed = all(r[1] for r in results)
    if all_passed:
        print("✅ Stage 6 Complete: All scenarios validated")
        print()
        print("Proven:")
        print("  - Success path: Q0→Q1→Q2→Q3→DeltaReducer chain works")
        print("  - Failure path: Q2 blocks genre violations")
        print("  - No production Canon modification (simulation only)")
        print()
        return 0
    else:
        print("❌ Stage 6 Failed: Some scenarios did not pass")
        return 1


if __name__ == "__main__":
    exit(main())
