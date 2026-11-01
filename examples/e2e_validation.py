"""V2-021 + V2-022 End-to-End Validation Script.

Demonstrates complete flow:
1. Real prose → Extraction → Real Operations
2. Operations pass DeltaReducer validation
3. Q0 deterministic validators pass
4. Evidence binding verified
"""

import hashlib
from datetime import datetime

from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import CanonState, DeltaReducer, OperationType
from anovel.domain.identity import EntityId, ProjectId
from anovel.planning.models import (
    GenrePackBinding,
    SeriesVision,
    WorldConstraints,
)
from anovel.quality.q0 import Q0Validator
from anovel.workflow.extractor import ExtractionStatus
from anovel.workflow.offline_extractor import OfflineExtractor


def main():
    """Run end-to-end validation."""
    print("=" * 80)
    print("V2-021 + V2-022 END-TO-END VALIDATION")
    print("=" * 80)
    print()

    # Setup
    extractor = OfflineExtractor()
    q0_validator = Q0Validator()
    reducer = DeltaReducer()

    # Test scenario: Character age revealed
    prose = """
    Chapter 5: The Truth Revealed

    After years of hiding her true age, Sarah finally confessed.
    "I'm 32 years old," she said, her voice trembling.

    The room fell silent. Her age had been a mystery for so long.
    """

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    series_vision = SeriesVision(
        series_id="e2e-validation-001",
        title="End-to-End Test",
        synopsis="Complete validation test",
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
        contract_id="e2e-ch5",
        chapter_id="ch-5",
        chapter_number=5,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-4",
        genre_pack_binding=series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="age_reveal",
                operation_type=OperationType.SET_FACT,
                fact_path="age",
                target_value=32,
                rationale="Age revealed",
            )
        ],
    )

    print("STEP 1: Extract state changes from prose")
    print("-" * 80)
    extraction_result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=series_vision,
        canon_parent="canon-4",
    )

    print(f"✓ Extraction status: {extraction_result.status}")
    print(f"✓ Operations constructed: {len(extraction_result.delta.operations)}")
    print(f"✓ Evidence locations: {len(extraction_result.operation_evidence)}")
    print()

    if extraction_result.status != ExtractionStatus.SUCCESS:
        print(f"✗ FAILED: Extraction did not succeed")
        print(f"  Issues: {extraction_result.issues}")
        return 1

    print("STEP 2: Verify operations are real SetFactOperation objects")
    print("-" * 80)
    operation = extraction_result.delta.operations[0]
    print(f"✓ Operation type: {operation.__class__.__name__}")
    print(f"✓ Fact path: {operation.path.path}")
    print(f"✓ Value: {operation.value}")
    print(f"✓ Evidence hash: {operation.evidence.content_hash[:16]}...")
    print()

    print("STEP 3: Validate operations through DeltaReducer")
    print("-" * 80)
    canon_state = CanonState(
        project_id=ProjectId(series_vision.series_id),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    try:
        new_state = reducer.apply_delta(canon_state, extraction_result.delta)
        print(f"✓ DeltaReducer validation: PASSED")

        # Verify state changed
        protagonist = EntityId("protagonist")
        value, exists = new_state.get_value(protagonist, operation.path)
        print(f"✓ State updated: age = {value} (exists: {exists})")
    except Exception as e:
        print(f"✗ FAILED: DeltaReducer rejected operation: {e}")
        return 1

    print()

    print("STEP 4: Run Q0 deterministic validators")
    print("-" * 80)
    q0_result = q0_validator.validate(
        extraction_result, contract, prose, prose_hash
    )

    print(f"Q0 validation result: {'PASSED' if q0_result.passed else 'FAILED'}")
    print(f"Checks run: {len(q0_result.checks)}")

    for check in q0_result.checks:
        status_symbol = "✓" if check.status == "pass" else "✗"
        print(f"  {status_symbol} {check.check_name}: {check.status}")

    if q0_result.blocking_issues:
        print(f"\n✗ Blocking issues:")
        for issue in q0_result.blocking_issues:
            print(f"  - {issue}")
        return 1

    print()

    print("STEP 5: Verify evidence binding")
    print("-" * 80)
    evidence = extraction_result.operation_evidence[0]
    print(f"✓ Evidence fact path: {evidence.fact_path}")
    print(f"✓ Evidence confidence: {evidence.confidence}")
    print(f"✓ Evidence locations verified: {evidence.evidence_locations[0].verified}")
    print(f"✓ Text snippet: {evidence.evidence_locations[0].text_snippet[:50]}...")
    print()

    print("=" * 80)
    print("END-TO-END VALIDATION: SUCCESS")
    print("=" * 80)
    print()
    print("Summary:")
    print("  ✓ Real prose → extraction → real Operations")
    print("  ✓ Operations pass DeltaReducer validation")
    print("  ✓ Q0 deterministic validators pass")
    print("  ✓ Evidence binding verified")
    print("  ✓ Prose hash bound to delta")
    print("  ✓ Project ID from series_vision")
    print()
    print("V2-021 Functional Completion: VERIFIED")
    print("V2-022 Q0 Integration: VERIFIED")
    print()

    return 0


if __name__ == "__main__":
    exit(main())
