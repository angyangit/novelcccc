"""Q0 Fail-Open负例测试 - Owner要求的严格验证

证明Q0修复确实阻断错误证据。
"""

import hashlib
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
from anovel.quality.q0 import Q0Validator
from anovel.workflow.extractor import (
    EvidenceLocation,
    ExtractionDiagnostic,
    ExtractionStatus,
    NarrativeDeltaExtractionResult,
    OperationEvidence,
)


def test_q0_fail_open_01_wrong_evidence_hash():
    """Q0 Fail-Open-01: Operation evidence hash与prose_hash不匹配必须拒绝."""
    validator = Q0Validator()

    prose = "Sarah is 25 years old."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-fo-ch1",
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

    # 构造Operation with wrong evidence hash
    wrong_hash = "0" * 64
    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId("protagonist"),
        scope=ProjectId("test-fo-001"),
        path=get_fact_path("age"),
        value=25,
        precondition=None,
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-1:0-10",
            content_hash=wrong_hash,  # 错误hash
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("test-fo-001"),
        operations=(operation,),
        source_chapter="ch-1",
        created_at=datetime.now(),
        authority="test",
        provenance=(("prose_hash", prose_hash),),
    )

    extraction_result = NarrativeDeltaExtractionResult(
        status=ExtractionStatus.SUCCESS,
        delta=delta,
        prose_hash=prose_hash,
        operation_evidence=[
            OperationEvidence(
                operation_index=0,
                fact_path="age",
                extracted_value=25,
                evidence_locations=[
                    EvidenceLocation(
                        start_char=10,
                        end_char=12,
                        text_snippet="25",
                        verified=True,
                    )
                ],
                confidence="confirmed",
                extraction_rationale="Test",
            )
        ],
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

    # 必须失败
    assert result.passed is False
    assert any(
        "content_hash" in issue.lower() or "prose_hash" in issue.lower()
        for issue in result.blocking_issues
    )


def test_q0_fail_open_02_evidence_location_out_of_range():
    """Q0 Fail-Open-02: Evidence位置超出正文范围必须拒绝."""
    validator = Q0Validator()

    prose = "Short text."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-fo-ch2",
        chapter_id="ch-2",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId("protagonist"),
        scope=ProjectId("test-fo-002"),
        path=get_fact_path("age"),
        value=25,
        precondition=None,
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-2:0-10",
            content_hash=prose_hash,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("test-fo-002"),
        operations=(operation,),
        source_chapter="ch-2",
        created_at=datetime.now(),
        authority="test",
        provenance=(("prose_hash", prose_hash),),
    )

    # Evidence位置超出范围
    extraction_result = NarrativeDeltaExtractionResult(
        status=ExtractionStatus.SUCCESS,
        delta=delta,
        prose_hash=prose_hash,
        operation_evidence=[
            OperationEvidence(
                operation_index=0,
                fact_path="age",
                extracted_value=25,
                evidence_locations=[
                    EvidenceLocation(
                        start_char=0,
                        end_char=999,  # 超出正文长度
                        text_snippet="invalid",
                        verified=True,
                    )
                ],
                confidence="confirmed",
                extraction_rationale="Test",
            )
        ],
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

    # 必须失败
    assert result.passed is False
    assert any(
        "exceeds prose length" in issue.lower() for issue in result.blocking_issues
    )


def test_q0_fail_open_03_evidence_snippet_mismatch():
    """Q0 Fail-Open-03: Evidence片段与实际正文不匹配必须拒绝."""
    validator = Q0Validator()

    prose = "Sarah is 25 years old."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-fo-ch3",
        chapter_id="ch-3",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId("protagonist"),
        scope=ProjectId("test-fo-003"),
        path=get_fact_path("age"),
        value=25,
        precondition=None,
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-3:0-10",
            content_hash=prose_hash,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("test-fo-003"),
        operations=(operation,),
        source_chapter="ch-3",
        created_at=datetime.now(),
        authority="test",
        provenance=(("prose_hash", prose_hash),),
    )

    # Evidence片段与位置不匹配
    extraction_result = NarrativeDeltaExtractionResult(
        status=ExtractionStatus.SUCCESS,
        delta=delta,
        prose_hash=prose_hash,
        operation_evidence=[
            OperationEvidence(
                operation_index=0,
                fact_path="age",
                extracted_value=25,
                evidence_locations=[
                    EvidenceLocation(
                        start_char=10,
                        end_char=12,
                        text_snippet="99",  # 实际是"25"，这里写错
                        verified=True,
                    )
                ],
                confidence="confirmed",
                extraction_rationale="Test",
            )
        ],
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

    # 必须失败
    assert result.passed is False
    assert any(
        "text_snippet does not match" in issue.lower()
        for issue in result.blocking_issues
    )


def test_q0_fail_open_04_operation_evidence_count_mismatch():
    """Q0 Fail-Open-04: Operation与OperationEvidence数量不匹配必须拒绝."""
    validator = Q0Validator()

    prose = "Sarah is 25 years old."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="test-fo-ch4",
        chapter_id="ch-4",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=GenrePackBinding(
            pack_id="test", version="1.0", content_hash="test"
        ),
        required_transitions=[],
    )

    operation = SetFactOperation(
        operation_type=OperationType.SET_FACT,
        operation_version="1.0.0",
        subject=EntityId("protagonist"),
        scope=ProjectId("test-fo-004"),
        path=get_fact_path("age"),
        value=25,
        precondition=None,
        evidence=EvidenceRef(
            source_type="TEXT",
            source_ref="ch-4:0-10",
            content_hash=prose_hash,
        ),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("test-fo-004"),
        operations=(operation,),  # 1个operation
        source_chapter="ch-4",
        created_at=datetime.now(),
        authority="test",
        provenance=(("prose_hash", prose_hash),),
    )

    # 但OperationEvidence为空
    extraction_result = NarrativeDeltaExtractionResult(
        status=ExtractionStatus.SUCCESS,
        delta=delta,
        prose_hash=prose_hash,
        operation_evidence=[],  # 空列表，与operations数量不匹配
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

    # 必须失败
    assert result.passed is False
    assert any(
        "count" in issue.lower() and "match" in issue.lower()
        for issue in result.blocking_issues
    )
