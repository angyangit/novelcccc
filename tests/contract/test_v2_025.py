"""Acceptance tests for V2-025 Q3 Transition Validators.

Tests Required Transitions and protected facts checks.
"""

import uuid
from datetime import datetime

from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import (
    CanonState,
    DeltaId,
    EvidenceRef,
    NarrativeDelta,
    OperationType,
    SetFactOperation,
    get_fact_path,
)
from anovel.domain.identity import EntityId, ProjectId
from anovel.planning.models import GenrePackBinding
from anovel.quality.q3 import Q3TransitionValidator


def test_at_v2_025_01_all_required_transitions_present():
    """AT-V2-025-01: Delta with all required transitions must pass."""
    validator = Q3TransitionValidator()

    project_id = ProjectId("test-q3-project")
    canon_state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Create operations matching required transitions
    operations = [
        SetFactOperation(
            operation_type=OperationType.SET_FACT,
            operation_version="1.0.0",
            subject=EntityId("protagonist"),
            scope=project_id,
            path=get_fact_path("age"),
            value=30,
            precondition=None,
            evidence=EvidenceRef(
                source_type="TEXT",
                source_ref="ch-1:0-10",
                content_hash="0" * 64,
            ),
        ),
        SetFactOperation(
            operation_type=OperationType.SET_FACT,
            operation_version="1.0.0",
            subject=EntityId("protagonist"),
            scope=project_id,
            path=get_fact_path("name"),
            value="Alice",
            precondition=None,
            evidence=EvidenceRef(
                source_type="TEXT",
                source_ref="ch-1:10-20",
                content_hash="0" * 64,
            ),
        ),
    ]

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=tuple(operations),
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
        required_transitions=[
            RequiredTransition(
                transition_id="t1",
                operation_type=OperationType.SET_FACT,
                fact_path="age",
                target_value=30,
                rationale="Age change",
            ),
            RequiredTransition(
                transition_id="t2",
                operation_type=OperationType.SET_FACT,
                fact_path="name",
                target_value="Alice",
                rationale="Name reveal",
            ),
        ],
    )

    result = validator.validate(delta, canon_state, contract)

    # Must pass - all required transitions present
    assert result.passed is True
    assert len(result.blocking_issues) == 0


def test_at_v2_025_02_missing_required_transition_fails():
    """AT-V2-025-02: Delta missing required transition must fail."""
    validator = Q3TransitionValidator()

    project_id = ProjectId("test-q3-project")
    canon_state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Only one operation, missing the second required transition
    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId("protagonist"),
        scope=project_id,
        path=get_fact_path("age"),
        value=30,
        precondition=None,
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
        required_transitions=[
            RequiredTransition(
                transition_id="t1",
                operation_type=OperationType.SET_FACT,
                fact_path="age",
                target_value=30,
                rationale="Age change",
            ),
            RequiredTransition(
                transition_id="t2",
                operation_type=OperationType.SET_FACT,
                fact_path="name",
                target_value="Bob",
                rationale="Name reveal",
            ),
        ],
    )

    result = validator.validate(delta, canon_state, contract)

    # Must fail - missing "name" transition
    assert result.passed is False
    assert any(
        "missing" in issue.lower() and "name" in issue.lower()
        for issue in result.blocking_issues
    )


def test_at_v2_025_03_quiet_chapter_allowed():
    """AT-V2-025-03: Chapters with no required transitions (quiet chapters) are allowed."""
    validator = Q3TransitionValidator()

    project_id = ProjectId("test-q3-project")
    canon_state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Empty delta - no operations
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
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
        required_transitions=[],  # No required transitions - quiet chapter
    )

    result = validator.validate(delta, canon_state, contract)

    # Must pass - quiet chapters are allowed
    assert result.passed is True
    assert any("quiet chapter" in check.message.lower() for check in result.checks)
