"""Acceptance tests for V2-022 Q0 Deterministic Validators.

Tests zero-cost deterministic quality checks per ADR-011.
"""

import hashlib
from datetime import datetime

import pytest

from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import DeltaId, EvidenceRef, NarrativeDelta, OperationType
from anovel.domain.identity import ProjectId
from anovel.planning.models import (
    GenrePackBinding,
    SeriesVision,
    WorldConstraints,
)
from anovel.quality.q0 import Q0CheckStatus, Q0Validator
from anovel.workflow.extractor import (
    EvidenceLocation,
    ExtractionDiagnostic,
    ExtractionStatus,
    NarrativeDeltaExtractionResult,
    OperationEvidence,
)
from anovel.workflow.offline_extractor import OfflineExtractor


@pytest.fixture
def base_vision():
    """Base series vision for tests."""
    return SeriesVision(
        series_id="test-q0-001",
        title="Q0 Test",
        synopsis="Testing Q0 validators",
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


def test_at_v2_022_01_prose_hash_mismatch_fails(base_vision):
    """AT-V2-022-01: Prose hash mismatch must fail Q0 validation."""
    validator = Q0Validator()
    extractor = OfflineExtractor()

    prose = "Chapter 1: Test content."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-q0-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    extraction_result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    # Validate with WRONG hash
    wrong_hash = "0" * 64
    result = validator.validate(extraction_result, contract, prose, wrong_hash)

    # Must fail
    assert result.passed is False
    assert len(result.blocking_issues) > 0
    assert any("prose hash" in issue.lower() for issue in result.blocking_issues)


def test_at_v2_022_02_missing_artifacts_fails(base_vision):
    """AT-V2-022-02: Missing required artifacts must fail Q0 validation."""
    validator = Q0Validator()

    prose = "Chapter 1."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-q0-ch2",
        chapter_id="ch-2",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    # Create minimal extraction result
    extraction_result = NarrativeDeltaExtractionResult(
        status=ExtractionStatus.NO_CHANGES,
        delta=None,
        prose_hash=prose_hash,
        operation_evidence=[],
        diagnostics=ExtractionDiagnostic(
            coverage_percentage=0.0,
            required_transitions_found=0,
            required_transitions_missing=0,
            unexpected_changes_found=0,
            conflicting_evidence_count=0,
            uncertain_extractions=[],
            issues=[],
        ),
        extraction_method="test",
        extracted_at=datetime.now(),
        issues=[],
    )

    # Validate with empty prose
    result = validator.validate(extraction_result, contract, "", prose_hash)

    # Must fail
    assert result.passed is False
    assert any("empty" in issue.lower() for issue in result.blocking_issues)


def test_at_v2_022_03_delta_provenance_missing_prose_hash_fails(base_vision):
    """AT-V2-022-03: Delta without prose_hash in provenance must fail."""
    validator = Q0Validator()

    prose = "Chapter 1."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-q0-ch3",
        chapter_id="ch-3",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    # Create delta WITHOUT prose_hash in provenance
    import uuid

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId(base_vision.series_id),
        operations=(),
        source_chapter="ch-3",
        created_at=datetime.now(),
        authority="test",
        provenance=(
            ("extraction_method", "test"),
            # Missing prose_hash!
        ),
    )

    extraction_result = NarrativeDeltaExtractionResult(
        status=ExtractionStatus.NO_CHANGES,
        delta=delta,
        prose_hash=prose_hash,
        operation_evidence=[],
        diagnostics=ExtractionDiagnostic(
            coverage_percentage=100.0,
            required_transitions_found=0,
            required_transitions_missing=0,
            unexpected_changes_found=0,
            conflicting_evidence_count=0,
            uncertain_extractions=[],
            issues=[],
        ),
        extraction_method="test",
        extracted_at=datetime.now(),
        issues=[],
    )

    result = validator.validate(extraction_result, contract, prose, prose_hash)

    # Must fail
    assert result.passed is False
    assert any("prose_hash" in issue.lower() for issue in result.blocking_issues)


def test_at_v2_022_04_unverified_evidence_locations_fail(base_vision):
    """AT-V2-022-04: Unverified evidence locations must fail Q0."""
    validator = Q0Validator()

    prose = "Chapter 1."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-q0-ch4",
        chapter_id="ch-4",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    # Create evidence with unverified location
    evidence = OperationEvidence(
        operation_index=0,
        fact_path="test.path",
        extracted_value="value",
        evidence_locations=[
            EvidenceLocation(
                start_char=0,
                end_char=10,
                text_snippet="Chapter 1.",
                verified=False,  # NOT VERIFIED
            )
        ],
        confidence="uncertain",
        extraction_rationale="Test",
    )

    import uuid

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId(base_vision.series_id),
        operations=(),
        source_chapter="ch-4",
        created_at=datetime.now(),
        authority="test",
        provenance=(
            ("extraction_method", "test"),
            ("prose_hash", prose_hash),
        ),
    )

    extraction_result = NarrativeDeltaExtractionResult(
        status=ExtractionStatus.SUCCESS,
        delta=delta,
        prose_hash=prose_hash,
        operation_evidence=[evidence],
        diagnostics=ExtractionDiagnostic(
            coverage_percentage=100.0,
            required_transitions_found=1,
            required_transitions_missing=0,
            unexpected_changes_found=0,
            conflicting_evidence_count=0,
            uncertain_extractions=[],
            issues=[],
        ),
        extraction_method="test",
        extracted_at=datetime.now(),
        issues=[],
    )

    result = validator.validate(extraction_result, contract, prose, prose_hash)

    # Must fail
    assert result.passed is False
    assert any("not verified" in issue.lower() for issue in result.blocking_issues)


def test_at_v2_022_05_valid_extraction_passes(base_vision):
    """AT-V2-022-05: Valid extraction with all checks must pass Q0."""
    validator = Q0Validator()
    extractor = OfflineExtractor()

    prose = """
    Chapter 1: Age revealed.

    The character's age is 30.
    """

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-q0-ch5",
        chapter_id="ch-5",
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
                target_value=30,
                rationale="Age revealed",
            )
        ],
    )

    extraction_result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=base_vision,
        canon_parent="canon-0",
    )

    result = validator.validate(extraction_result, contract, prose, prose_hash)

    # Must pass all checks
    assert result.passed is True
    assert len(result.blocking_issues) == 0
    assert all(check.status == Q0CheckStatus.PASS for check in result.checks)


def test_at_v2_022_06_operations_without_evidence_fail(base_vision):
    """AT-V2-022-06: Operations without evidence must fail Q0."""
    validator = Q0Validator()

    prose = "Chapter 1."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-q0-ch6",
        chapter_id="ch-6",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    # Create a mock operation without evidence (by creating a minimal object)
    # Note: This is artificial since real Operations require evidence, but we test the validator
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class MockOperation:
        operation_type: OperationType = OperationType.SET_FACT
        operation_version: str = "1.0.0"
        evidence = None  # Missing evidence

    import uuid

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId(base_vision.series_id),
        operations=(MockOperation(),),  # type: ignore
        source_chapter="ch-6",
        created_at=datetime.now(),
        authority="test",
        provenance=(
            ("extraction_method", "test"),
            ("prose_hash", prose_hash),
        ),
    )

    extraction_result = NarrativeDeltaExtractionResult(
        status=ExtractionStatus.SUCCESS,
        delta=delta,
        prose_hash=prose_hash,
        operation_evidence=[],
        diagnostics=ExtractionDiagnostic(
            coverage_percentage=100.0,
            required_transitions_found=0,
            required_transitions_missing=0,
            unexpected_changes_found=0,
            conflicting_evidence_count=0,
            uncertain_extractions=[],
            issues=[],
        ),
        extraction_method="test",
        extracted_at=datetime.now(),
        issues=[],
    )

    result = validator.validate(extraction_result, contract, prose, prose_hash)

    # Must fail
    assert result.passed is False
    assert any("evidence" in issue.lower() for issue in result.blocking_issues)
