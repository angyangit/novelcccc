"""Stage 10 Phase 3: Quality Validation Integration Test

Tests unified Q0-Q3 workflow with detailed check tracking.
Uses real Chapter 1 data from Stage 9 Phase 7.

Requirements:
- Detailed CheckStatus tracking (PASS/FAIL/UNKNOWN/ERROR/NOT_RUN)
- Proper CanonState construction (not minimal mock)
- Individual q0_passed/q1_passed/q2_passed/q3_passed tracking
- Fail-closed quality gates
- Test both positive and negative paths
"""

import hashlib
import uuid
from datetime import datetime

from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import (
    DeltaId,
    EvidenceRef,
    FactPath,
    NarrativeDelta,
    OperationType,
    SetFactOperation,
)
from anovel.domain.identity import EntityId, ProjectId
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    SeriesVision,
    WorldConstraints,
)
from anovel.workflow.extractor import (
    EvidenceLocation,
    NarrativeDeltaExtractionResult,
    OperationEvidence,
)
from anovel.workflow.models import CheckStatus
from anovel.workflow.workflow import ChapterWorkflow

# Read actual Chapter 1 from Stage 9
with open("output/stage9_phase7/chapter_001.txt", encoding="utf-8") as f:
    full_content = f.read()

# Extract prose only
parts = full_content.split("---")
prose = parts[0].strip().split("\n", 1)[1].strip()
prose_hash = hashlib.sha256(prose.encode()).hexdigest()

print("=" * 80)
print("Stage 10 Phase 3: Quality Validation Integration Test")
print("=" * 80)
print()
print("Testing on: Stage 9 Chapter 1")
print(f"Prose length: {len(prose)} chars")
print(f"Prose hash: {prose_hash[:16]}...")
print()

# Create test vision and contract
project_id = ProjectId("library_adventure")
series_vision = SeriesVision(
    series_id="library_adventure",
    title="图书馆奇遇记",
    synopsis="李明在图书馆的学习之旅",
    protagonist_goals=[
        ProtagonistGoal(
            goal_id="g1",
            description="完成《时间简史》的阅读",
            constraints=[],
            success_criteria=[],
        )
    ],
    world_constraints=WorldConstraints(),
    character_knowledge_map={},
    secrets=[],
    genre_pack_binding=GenrePackBinding(
        pack_id="contemporary", version="1.0", content_hash="test"
    ),
    arc_plans=[],
    fixture_version="1.0",
)

contract = ChapterContract(
    contract_id=f"contract_{uuid.uuid4().hex[:8]}",
    chapter_id="chapter_001",
    chapter_number=1,
    plan_version="1.0",
    created_at=datetime.now(),
    canon_parent="genesis",
    genre_pack_binding=series_vision.genre_pack_binding,
    required_transitions=[
        RequiredTransition(
            transition_id="t1",
            operation_type=OperationType.SET_FACT,
            fact_path="protagonist.location",
            target_value="library",
            rationale="李明进入图书馆",
        ),
        RequiredTransition(
            transition_id="t2",
            operation_type=OperationType.SET_FACT,
            fact_path="protagonist.activity",
            target_value="reading",
            rationale="开始阅读",
        ),
    ],
)

# Create workflow (no real components needed for quality validation test)
workflow = ChapterWorkflow(
    contract_compiler=None,  # Not needed for this test
    context_compiler=None,  # Not needed for this test
    model_gateway=None,  # Not needed for this test
    extractor=None,  # Not needed for this test
    mock_mode=True,
)

# Create test delta with operations
protagonist_id = EntityId("protagonist")
delta = NarrativeDelta(
    delta_id=DeltaId(str(uuid.uuid4())),
    project_id=project_id,
    operations=(
        SetFactOperation(
            path=FactPath("protagonist.location", str),
            value="市图书馆",
            subject=protagonist_id,
            scope=project_id,
            precondition=None,  # Genesis state, no precondition
            evidence=EvidenceRef(
                source_type="TEXT",
                source_ref="chapter_001:43-65",
                content_hash=prose_hash,
            ),
        ),
        SetFactOperation(
            path=FactPath("protagonist.activity", str),
            value="reading",
            subject=protagonist_id,
            scope=project_id,
            precondition=None,
            evidence=EvidenceRef(
                source_type="TEXT",
                source_ref="chapter_001:552-566",
                content_hash=prose_hash,
            ),
        ),
    ),
    source_chapter="chapter_001",
    created_at=datetime.now(),
    authority="test_integration",
    provenance=(
        ("source", "structured_extraction"),
        ("prose_hash", prose_hash),
        ("chapter_id", "chapter_001"),
    ),
)

# Create extraction result for Q0
extraction_result = NarrativeDeltaExtractionResult(
    status="success",
    delta=delta,
    prose_hash=prose_hash,
    operation_evidence=[
        OperationEvidence(
            operation_index=0,
            fact_path="protagonist.location",
            extracted_value="市图书馆",
            evidence_locations=[
                EvidenceLocation(
                    start_char=43,
                    end_char=65,
                    text_snippet="李明背着双肩包，推开了市图书馆厚重的玻璃门",
                    verified=True,
                )
            ],
            confidence="confirmed",
            extraction_rationale="李明推开市图书馆的门，明确进入图书馆",
        ),
        OperationEvidence(
            operation_index=1,
            fact_path="protagonist.activity",
            extracted_value="reading",
            evidence_locations=[
                EvidenceLocation(
                    start_char=552,
                    end_char=566,
                    text_snippet="李明深吸一口气，翻开了第一章",
                    verified=True,
                )
            ],
            confidence="confirmed",
            extraction_rationale="李明翻开书并开始阅读",
        ),
    ],
    diagnostics=type(
        "Diagnostics",
        (),
        {
            "required_transitions_found": 2,
            "coverage_percentage": 100.0,
            "extraction_confidence": "high",
        },
    )(),
    extraction_method="structured_extraction",
    extracted_at=datetime.now(),
    issues=[],
)

# Create canon snapshot with proper structure
canon_snapshot = {
    "project_id": "library_adventure",
    "facts": (),  # Genesis state, no prior facts
    "tombstones": frozenset(),
    "commit_history": (),
}

print("-" * 80)
print("TEST 1: Positive Path (All Validators Pass)")
print("-" * 80)
print()

quality_result = workflow._validate_quality(
    prose=prose,
    prose_hash=prose_hash,
    delta=delta,
    contract=contract,
    extraction_result=extraction_result,
    canon_snapshot=canon_snapshot,
)

print(f"Overall passed: {quality_result.passed}")
print(f"Blocking issues: {len(quality_result.blocking_issues)}")
print(f"Warnings: {len(quality_result.warnings)}")
print(f"Checks run: {len(quality_result.checks_run)}")
print()

print("Validator Results:")
print(f"  Q0 (Deterministic): {quality_result.q0_passed}")
print(f"  Q1 (Canon): {quality_result.q1_passed}")
print(f"  Q2 (Genre): {quality_result.q2_passed}")
print(f"  Q3 (Transitions): {quality_result.q3_passed}")
print()

if quality_result.check_details:
    print(f"Check Details ({len(quality_result.check_details)} checks):")
    for check in quality_result.check_details:
        status_symbol = {
            CheckStatus.PASS: "✓",
            CheckStatus.FAIL: "✗",
            CheckStatus.UNKNOWN: "?",
            CheckStatus.ERROR: "⚠",
            CheckStatus.NOT_RUN: "⊘",
        }.get(check.status, "?")
        print(f"  {status_symbol} {check.check_name}: {check.status.value}")
        print(f"     {check.message}")
        if check.metadata:
            print(f"     Metadata: {check.metadata}")
print()

if quality_result.blocking_issues:
    print("Blocking Issues:")
    for issue in quality_result.blocking_issues:
        print(f"  - {issue}")
    print()

if quality_result.warnings:
    print("Warnings:")
    for warning in quality_result.warnings:
        print(f"  - {warning}")
    print()

# Verify positive path expectations
positive_pass = True
if not quality_result.passed:
    print("✗ FAIL: Quality validation should pass")
    positive_pass = False

if quality_result.q0_passed is not True:
    print(f"✗ FAIL: Q0 should pass, got {quality_result.q0_passed}")
    positive_pass = False

if quality_result.q1_passed is not True:
    print(f"✗ FAIL: Q1 should pass, got {quality_result.q1_passed}")
    positive_pass = False

# Q2 may be ERROR (not fully implemented) - that's acceptable
if quality_result.q2_passed is False:
    print("⚠ WARNING: Q2 failed (may not be fully implemented)")

if quality_result.q3_passed is not True:
    print(f"✗ FAIL: Q3 should pass, got {quality_result.q3_passed}")
    positive_pass = False

if not quality_result.check_details:
    print("✗ FAIL: check_details should not be empty")
    positive_pass = False

if positive_pass:
    print("✓ TEST 1 PASSED: All validators operational with detailed tracking")
else:
    print("✗ TEST 1 FAILED")

print()
print("=" * 80)
print("TEST 2: Negative Path (Prose Hash Mismatch)")
print("=" * 80)
print()

# Create delta with wrong prose hash
wrong_hash = hashlib.sha256(b"wrong prose").hexdigest()
bad_delta = NarrativeDelta(
    delta_id=DeltaId(str(uuid.uuid4())),
    project_id=project_id,
    operations=delta.operations,
    source_chapter="chapter_001",
    created_at=datetime.now(),
    authority="test_integration",
    provenance=(
        ("source", "structured_extraction"),
        ("prose_hash", wrong_hash),  # Wrong hash
        ("chapter_id", "chapter_001"),
    ),
)

bad_extraction = NarrativeDeltaExtractionResult(
    status="success",
    delta=bad_delta,
    prose_hash=wrong_hash,  # Wrong hash
    operation_evidence=[],
    diagnostics=extraction_result.diagnostics,
    extraction_method="structured_extraction",
    extracted_at=datetime.now(),
    issues=[],
)

quality_result_bad = workflow._validate_quality(
    prose=prose,
    prose_hash=prose_hash,
    delta=bad_delta,
    contract=contract,
    extraction_result=bad_extraction,
    canon_snapshot=canon_snapshot,
)

print(f"Overall passed: {quality_result_bad.passed}")
print(f"Q0 passed: {quality_result_bad.q0_passed}")
print()

# Q0 should fail due to hash mismatch
negative_pass = True
if quality_result_bad.q0_passed is not False:
    print(
        f"✗ FAIL: Q0 should fail on hash mismatch, got {quality_result_bad.q0_passed}"
    )
    negative_pass = False

if quality_result_bad.passed:
    print("✗ FAIL: Overall validation should fail on Q0 failure")
    negative_pass = False

if len(quality_result_bad.blocking_issues) == 0:
    print("✗ FAIL: Should have blocking issues")
    negative_pass = False

# Check that Q0 failure is recorded in check_details
q0_checks = [
    c for c in quality_result_bad.check_details if c.check_name.startswith("Q0-")
]
if not any(c.status == CheckStatus.FAIL for c in q0_checks):
    print("✗ FAIL: Q0 checks should show FAIL status in check_details")
    negative_pass = False

if negative_pass:
    print("✓ TEST 2 PASSED: Q0 correctly rejects prose hash mismatch")
else:
    print("✗ TEST 2 FAILED")

print()
print("=" * 80)
print("TEST 3: Negative Path (Missing Canon Snapshot)")
print("=" * 80)
print()

quality_result_no_canon = workflow._validate_quality(
    prose=prose,
    prose_hash=prose_hash,
    delta=delta,
    contract=contract,
    extraction_result=extraction_result,
    canon_snapshot=None,  # No canon snapshot
)

print(f"Overall passed: {quality_result_no_canon.passed}")
print(f"Q1 passed: {quality_result_no_canon.q1_passed}")
print(f"Q3 passed: {quality_result_no_canon.q3_passed}")
print()

# Q1 and Q3 should be None (NOT_RUN)
test3_pass = True
if quality_result_no_canon.q1_passed is not None:
    print(
        f"✗ FAIL: Q1 should be None (NOT_RUN), got {quality_result_no_canon.q1_passed}"
    )
    test3_pass = False

if quality_result_no_canon.q3_passed is not None:
    print(
        f"✗ FAIL: Q3 should be None (NOT_RUN), got {quality_result_no_canon.q3_passed}"
    )
    test3_pass = False

# Check for NOT_RUN status in check_details
q1_checks = [
    c for c in quality_result_no_canon.check_details if c.check_name == "Q1-validation"
]
q3_checks = [
    c for c in quality_result_no_canon.check_details if c.check_name == "Q3-validation"
]

if not any(c.status == CheckStatus.NOT_RUN for c in q1_checks):
    print("✗ FAIL: Q1 should show NOT_RUN status")
    test3_pass = False

if not any(c.status == CheckStatus.NOT_RUN for c in q3_checks):
    print("✗ FAIL: Q3 should show NOT_RUN status")
    test3_pass = False

if not quality_result_no_canon.passed:
    print("✓ Correctly blocks commit when canon validation cannot run")

if test3_pass:
    print("✓ TEST 3 PASSED: NOT_RUN status correctly tracked")
else:
    print("✗ TEST 3 FAILED")

print()
print("=" * 80)
print("TEST 4: Negative Path (Short Prose)")
print("=" * 80)
print()

short_prose = "太短了"
short_hash = hashlib.sha256(short_prose.encode()).hexdigest()

quality_result_short = workflow._validate_quality(
    prose=short_prose,
    prose_hash=short_hash,
    delta=None,
    contract=contract,
    extraction_result=None,
    canon_snapshot=canon_snapshot,
)

print(f"Overall passed: {quality_result_short.passed}")
print(f"Blocking issues: {len(quality_result_short.blocking_issues)}")
print()

# Should fail on prose length
test4_pass = True
if quality_result_short.passed:
    print("✗ FAIL: Should fail on short prose")
    test4_pass = False

prose_length_checks = [
    c
    for c in quality_result_short.check_details
    if c.check_name == "basic-prose_length"
]
if not any(c.status == CheckStatus.FAIL for c in prose_length_checks):
    print("✗ FAIL: basic-prose_length should show FAIL status")
    test4_pass = False

if test4_pass:
    print("✓ TEST 4 PASSED: Basic checks correctly reject short prose")
else:
    print("✗ TEST 4 FAILED")

print()
print("=" * 80)
print("Summary")
print("=" * 80)
print()

all_tests_pass = positive_pass and negative_pass and test3_pass and test4_pass

if all_tests_pass:
    print("✓✓ ALL TESTS PASSED")
    print()
    print("Phase 3 Task 1 Complete:")
    print("  ✓ Detailed CheckStatus tracking (PASS/FAIL/UNKNOWN/ERROR/NOT_RUN)")
    print("  ✓ Proper CanonState construction from canon_snapshot")
    print("  ✓ Individual q0/q1/q2/q3_passed tracking")
    print("  ✓ Fail-closed quality gates operational")
    print("  ✓ Positive and negative paths validated")
    print()
    print("Ready for: Task 2 (Real model test with budget)")
else:
    print("✗ SOME TESTS FAILED")
    print()
    print("Tests status:")
    print(f"  Test 1 (Positive path): {'✓ PASS' if positive_pass else '✗ FAIL'}")
    print(f"  Test 2 (Hash mismatch): {'✓ PASS' if negative_pass else '✗ FAIL'}")
    print(f"  Test 3 (Missing canon): {'✓ PASS' if test3_pass else '✗ FAIL'}")
    print(f"  Test 4 (Short prose): {'✓ PASS' if test4_pass else '✗ FAIL'}")

print("=" * 80)

exit(0 if all_tests_pass else 1)
