"""Acceptance tests for V2-023 Q1 Canon Validators.

Tests Canon state consistency checks.
"""

import uuid
from datetime import datetime

import pytest

from anovel.contracts.models import ChapterContract
from anovel.domain.delta import (
    CanonState,
    CommitId,
    DeltaId,
    EvidenceRef,
    ExpectAbsent,
    ExpectValue,
    FactValue,
    NarrativeDelta,
    OperationType,
    SetFactOperation,
    get_fact_path,
)
from anovel.domain.identity import EntityId, ProjectId
from anovel.planning.models import GenrePackBinding
from anovel.quality.q1 import Q1CanonValidator, Q1CheckStatus


@pytest.fixture
def base_canon_state():
    """Base Canon state for tests."""
    return CanonState(
        project_id=ProjectId("test-q1-project"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )


def test_at_v2_023_01_project_isolation_enforced(base_canon_state):
    """AT-V2-023-01: Cross-project operations must be rejected."""
    validator = Q1CanonValidator()

    # Create delta with wrong project_id
    wrong_project_delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("wrong-project"),  # Different from canon
        operations=(),
        source_chapter="ch-1",
        created_at=datetime.now(),
        authority="test",
        provenance=(("test", "test"),),
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    result = validator.validate(wrong_project_delta, base_canon_state, contract)

    # Must fail on project mismatch
    assert result.passed is False
    assert any("project" in issue.lower() for issue in result.blocking_issues)


def test_at_v2_023_02_precondition_mismatch_rejected():
    """AT-V2-023-02: Operations with wrong preconditions must be rejected."""
    validator = Q1CanonValidator()

    project_id = ProjectId("test-q1-project")

    # Canon has age=25
    entity = EntityId("protagonist")
    age_path = get_fact_path("age")

    canon_with_age = CanonState(
        project_id=project_id,
        facts=(((entity, "age"), 25),),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Operation expects age to be absent
    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=entity,
        scope=project_id,
        path=age_path,
        value=30,
        precondition=ExpectAbsent(),  # Wrong! age=25 exists
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash="0" * 64,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(operation,),
        source_chapter="ch-1",
        created_at=datetime.now(),
        authority="test",
        provenance=(("test", "test"),),
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, canon_with_age, contract)

    # Must fail on precondition mismatch
    assert result.passed is False
    assert any("expects absent" in issue.lower() or "precondition" in issue.lower() for issue in result.blocking_issues)


def test_at_v2_023_03_correct_precondition_passes():
    """AT-V2-023-03: Operations with correct preconditions must pass."""
    validator = Q1CanonValidator()

    project_id = ProjectId("test-q1-project")
    entity = EntityId("protagonist")
    age_path = get_fact_path("age")

    # Canon has age=25
    canon_with_age = CanonState(
        project_id=project_id,
        facts=(((entity, "age"), 25),),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Operation expects age=25 (correct)
    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=entity,
        scope=project_id,
        path=age_path,
        value=26,
        precondition=ExpectValue(expected_value=25),  # Correct!
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash="0" * 64,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(operation,),
        source_chapter="ch-1",
        created_at=datetime.now(),
        authority="test",
        provenance=(("test", "test"),),
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, canon_with_age, contract)

    # Must pass
    assert result.passed is True
    assert len(result.blocking_issues) == 0


def test_at_v2_023_04_dead_character_cannot_act():
    """AT-V2-023-04: Dead characters cannot have new facts set."""
    validator = Q1CanonValidator()

    project_id = ProjectId("test-q1-project")
    entity = EntityId("character-1")
    age_path = get_fact_path("age")

    # Canon has character marked as not alive
    canon_with_dead = CanonState(
        project_id=project_id,
        facts=(
            ((entity, "is_alive"), False),  # Dead
            ((entity, "age"), 30),
        ),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Try to update age of dead character
    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=entity,
        scope=project_id,
        path=age_path,
        value=31,
        precondition=ExpectValue(expected_value=30),
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash="0" * 64,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(operation,),
        source_chapter="ch-1",
        created_at=datetime.now(),
        authority="test",
        provenance=(("test", "test"),),
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, canon_with_dead, contract)

    # Must fail - dead characters cannot act
    assert result.passed is False
    assert any("not alive" in issue.lower() for issue in result.blocking_issues)


def test_at_v2_023_05_resurrection_allowed():
    """AT-V2-023-05: Explicit resurrection (is_alive: False → True) is allowed."""
    validator = Q1CanonValidator()

    project_id = ProjectId("test-q1-project")
    entity = EntityId("character-1")
    is_alive_path = get_fact_path("is_alive")

    # Canon has character marked as not alive
    canon_with_dead = CanonState(
        project_id=project_id,
        facts=(((entity, "is_alive"), False),),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Explicit resurrection operation
    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=entity,
        scope=project_id,
        path=is_alive_path,
        value=True,  # Resurrection
        precondition=ExpectValue(expected_value=False),
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash="0" * 64,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(operation,),
        source_chapter="ch-1",
        created_at=datetime.now(),
        authority="test",
        provenance=(("test", "test"),),
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, canon_with_dead, contract)

    # Must pass - explicit resurrection allowed
    assert result.passed is True
    assert len(result.blocking_issues) == 0


def test_at_v2_023_06_alive_character_can_act():
    """AT-V2-023-06: Alive characters can have facts updated."""
    validator = Q1CanonValidator()

    project_id = ProjectId("test-q1-project")
    entity = EntityId("character-1")
    age_path = get_fact_path("age")

    # Canon has character alive
    canon_with_alive = CanonState(
        project_id=project_id,
        facts=(
            ((entity, "is_alive"), True),  # Alive
            ((entity, "age"), 30),
        ),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Update age of alive character
    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=entity,
        scope=project_id,
        path=age_path,
        value=31,
        precondition=ExpectValue(expected_value=30),
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash="0" * 64,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(operation,),
        source_chapter="ch-1",
        created_at=datetime.now(),
        authority="test",
        provenance=(("test", "test"),),
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, canon_with_alive, contract)

    # Must pass - alive characters can act
    assert result.passed is True
    assert len(result.blocking_issues) == 0
