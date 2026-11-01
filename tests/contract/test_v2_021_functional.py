"""V2-021 Functional Tests - Real Operations Construction and Validation.

Tests that extracted operations are real, valid Operations that pass DeltaReducer.
"""

import hashlib
from datetime import datetime

import pytest

from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import (
    CanonState,
    DeltaReducer,
    OperationType,
    SetFactOperation,
)
from anovel.domain.identity import EntityId, ProjectId
from anovel.planning.models import (
    GenrePackBinding,
    SeriesVision,
    WorldConstraints,
)
from anovel.workflow.extractor import ExtractionStatus
from anovel.workflow.offline_extractor import OfflineExtractor


@pytest.fixture
def base_vision():
    """Base series vision for tests."""
    return SeriesVision(
        series_id="test-functional-001",
        title="Functional Test",
        synopsis="Testing real operations",
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


def test_extracted_operations_are_real_setfact_operations(base_vision):
    """V2-021 Functional: Extracted operations must be real SetFactOperation objects."""
    extractor = OfflineExtractor()

    prose = """
    Chapter 1: The funding milestone.

    After negotiations, the funding_amount reached $5,000,000.
    """

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-func-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="funding",
                operation_type=OperationType.SET_FACT,
                fact_path="funding_amount",
                target_value=5000000,
                rationale="Funding secured",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Must have delta with operations
    assert result.delta is not None
    assert len(result.delta.operations) == 1

    # Operation must be SetFactOperation
    op = result.delta.operations[0]
    assert isinstance(op, SetFactOperation)
    assert op.operation_type == OperationType.SET_FACT
    assert op.path.path == "funding_amount"
    assert op.value == 5000000


def test_extracted_operations_pass_deltaReducer_validation(base_vision):
    """V2-021 Functional: Operations must pass DeltaReducer validation."""
    extractor = OfflineExtractor()

    prose = """
    Chapter 1: Age revealed.

    The character's age is now 25 years old.
    """

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-func-ch2",
        chapter_id="ch-2",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="age",
                operation_type=OperationType.SET_FACT,
                fact_path="age",
                target_value=25,
                rationale="Age revealed",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Setup Canon state
    canon_state = CanonState(
        project_id=ProjectId(base_vision.series_id),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Apply delta through reducer
    reducer = DeltaReducer()

    # Must not raise ReducerError
    new_state = reducer.apply_delta(canon_state, result.delta)

    # Verify state changed
    protagonist = EntityId("protagonist")
    value, exists = new_state.get_value(protagonist, result.delta.operations[0].path)
    assert exists
    assert value == 25


def test_operations_have_evidence_with_prose_hash(base_vision):
    """V2-021 Functional: All operations must have evidence with correct prose hash."""
    extractor = OfflineExtractor()

    prose = "The name is Alice."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-func-ch3",
        chapter_id="ch-3",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="name",
                operation_type=OperationType.SET_FACT,
                fact_path="name",
                target_value="Alice",
                rationale="Name revealed",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Check operation evidence
    assert len(result.delta.operations) == 1
    op = result.delta.operations[0]

    assert op.evidence is not None
    assert op.evidence.content_hash == prose_hash
    assert op.evidence.source_type == "TEXT"
    assert "ch-3" in op.evidence.source_ref


def test_no_operations_when_no_required_transitions(base_vision):
    """V2-021 Functional: Delta with no required transitions produces empty operations."""
    extractor = OfflineExtractor()

    prose = "Nothing happens."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-func-ch4",
        chapter_id="ch-4",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],  # No transitions
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Should be NO_CHANGES with empty operations
    assert result.status == ExtractionStatus.NO_CHANGES
    assert result.delta is not None
    assert len(result.delta.operations) == 0


def test_unregistered_fact_path_produces_issue(base_vision):
    """V2-021 Functional: Unregistered fact paths produce issues but don't crash."""
    extractor = OfflineExtractor()

    prose = "The unregistered_fact_path is mentioned here."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-func-ch5",
        chapter_id="ch-5",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="unregistered",
                operation_type=OperationType.SET_FACT,
                fact_path="unregistered_fact_path",
                target_value="value",
                rationale="Test unregistered",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Should have issues
    assert len(result.issues) > 0
    assert any("unregistered" in issue.lower() for issue in result.issues)

    # Status should reflect failure
    assert result.status in [ExtractionStatus.INCOMPLETE, ExtractionStatus.FAILED]
