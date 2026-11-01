"""Acceptance tests for V2-024 Q2 Genre Validators.

Tests Genre consistency checks.
"""

import uuid
from datetime import datetime

from anovel.contracts.models import ChapterContract
from anovel.domain.delta import (
    DeltaId,
    EvidenceRef,
    NarrativeDelta,
    OperationType,
    SetFactOperation,
    get_fact_path,
)
from anovel.domain.identity import EntityId, ProjectId
from anovel.planning.models import GenrePackBinding
from anovel.quality.q2 import Q2GenreValidator


def test_at_v2_024_01_genre_pack_version_verified():
    """AT-V2-024-01: Contract with valid GenrePack binding must pass."""
    validator = Q2GenreValidator()

    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId("protagonist"),
        scope=ProjectId("test-q2-project"),
        path=get_fact_path("age"),
        value=25,
        precondition=None,
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash="0" * 64,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("test-q2-project"),
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
            pack_id="urban",
            version="1.0",
            content_hash="abc123",
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, contract)

    # Must pass with valid GenrePack binding
    assert result.passed is True
    assert len(result.blocking_issues) == 0


def test_at_v2_024_02_missing_genre_pack_binding_fails():
    """AT-V2-024-02: Contract without GenrePack binding must fail."""
    validator = Q2GenreValidator()

    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId("protagonist"),
        scope=ProjectId("test-q2-project"),
        path=get_fact_path("age"),
        value=25,
        precondition=None,
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash="0" * 64,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("test-q2-project"),
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
        genre_pack_binding=None,  # Missing!
        required_transitions=[],
    )

    result = validator.validate(delta, contract)

    # Must fail - no GenrePack binding
    assert result.passed is False
    assert any("genrepack binding" in issue.lower() for issue in result.blocking_issues)


def test_at_v2_024_03_incomplete_genre_pack_binding_fails():
    """AT-V2-024-03: GenrePack binding missing required fields must fail."""
    validator = Q2GenreValidator()

    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId("protagonist"),
        scope=ProjectId("test-q2-project"),
        path=get_fact_path("age"),
        value=25,
        precondition=None,
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash="0" * 64,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("test-q2-project"),
        operations=(operation,),
        source_chapter="ch-1",
        created_at=datetime.now(),
        authority="test",
        provenance=(("test", "test"),),
    )

    # Test missing pack_id
    contract_no_pack_id = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="",  # Empty!
            version="1.0",
            content_hash="abc123",
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, contract_no_pack_id)
    assert result.passed is False
    assert any("pack_id" in issue.lower() for issue in result.blocking_issues)

    # Test missing version
    contract_no_version = ChapterContract(
        contract_id="test-ch2",
        chapter_id="ch-2",
        chapter_number=2,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="urban",
            version="",  # Empty!
            content_hash="abc123",
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, contract_no_version)
    assert result.passed is False
    assert any("version" in issue.lower() for issue in result.blocking_issues)

    # Test missing content_hash
    contract_no_hash = ChapterContract(
        contract_id="test-ch3",
        chapter_id="ch-3",
        chapter_number=3,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="urban",
            version="1.0",
            content_hash="",  # Empty!
        ),
        required_transitions=[],
    )

    result = validator.validate(delta, contract_no_hash)
    assert result.passed is False
    assert any("content_hash" in issue.lower() for issue in result.blocking_issues)
