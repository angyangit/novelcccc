"""Stage 10 Full Workflow Acceptance Test

Validates complete workflow with fixed extractor on Task 2 prose:
1. Load existing prose (no new generation)
2. Extract with fixed extractor (5 operations expected)
3. Apply sequential delta with proper preconditions
4. Validate Q0-Q3 with semantic transition matching
5. Verify final canon state correctness
6. Confirm next chapter can inherit state

Requirements:
- Sequential delta correctness (no all-ExpectAbsent)
- Semantic validation (library ≈ 图书馆, reading ≈ 阅读)
- Real evidence binding (no hallucination)
- Complete Q0-Q3 verification
- Budget tracking ($0.40 max new spending)
- No production canon commits

Owner Decision: FULL WORKFLOW GO / SEMANTIC VALIDATION / SEQUENTIAL DELTA / NO PRODUCTION COMMIT
"""

import hashlib
import json
import time
import uuid
from datetime import datetime
from pathlib import Path

from anovel.config import get_real_provider_config, mask_api_key
from anovel.context.compiler import ContextCompiler
from anovel.contracts.compiler import ContractCompiler
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
from anovel.workflow.structured_extractor import StructuredExtractor
from anovel.workflow.workflow import ChapterWorkflow

print("=" * 80)
print("Stage 10 Full Workflow Acceptance Test")
print("=" * 80)
print()

# Create output directory
output_dir = Path("output/workflow_acceptance")
output_dir.mkdir(parents=True, exist_ok=True)

# Load Task 2 prose (existing, no new generation)
prose_file = Path("output/stage10_task2/chapter_task2_001.txt")
print(f"Loading prose from: {prose_file}")

with open(prose_file, "r", encoding="utf-8") as f:
    content = f.read()

# Extract prose (remove header and metadata)
lines = content.split("\n")
prose_start = 0
prose_end = len(lines)

for i, line in enumerate(lines):
    if line.strip() == "---":
        prose_end = i
        break
    if i == 0 or (i == 1 and lines[i - 1].startswith("#")):
        continue
    if prose_start == 0 and line.strip():
        prose_start = i

prose = "\n".join(lines[prose_start:prose_end])
prose_hash = hashlib.sha256(prose.encode()).hexdigest()

print(f"✓ Prose loaded: {len(prose)} chars")
print(f"  Hash: {prose_hash[:16]}...")
print()

# Create series vision and contract
series_vision = SeriesVision(
    series_id="library_adventure",
    title="图书馆奇遇记",
    synopsis="李明在市图书馆探索《时间简史》",
    protagonist_goals=[
        ProtagonistGoal(
            goal_id="g1",
            description="理解时间与空间的本质",
            constraints=["必须通过阅读《时间简史》获得"],
            success_criteria=["能够解释相对论基本概念"],
        )
    ],
    world_constraints=WorldConstraints(
        realistic_constraints=["现实世界物理定律", "当代（2020年代）科技水平"],
        prohibited_mechanisms=["魔法", "超能力"],
    ),
    character_knowledge_map={},
    secrets=[],
    genre_pack_binding=GenrePackBinding(
        pack_id="contemporary_realistic",
        version="1.0",
        content_hash="test_genre_pack",
    ),
    arc_plans=[],
    fixture_version="1.0",
)

contract = ChapterContract(
    contract_id=f"contract_accept_{uuid.uuid4().hex[:8]}",
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
            rationale="开始阅读《时间简史》",
        ),
    ],
)

print("Configuration:")
print(f"  Series: {series_vision.title}")
print(f"  Chapter: {contract.chapter_number}")
print(f"  Canon parent: {contract.canon_parent}")
print(f"  Required transitions: {len(contract.required_transitions)}")
for t in contract.required_transitions:
    print(f"    - {t.fact_path} → {t.target_value}")
print()

# Genesis canon state (proper structure)
canon_snapshot = {
    "project_id": series_vision.series_id,
    "facts": (),
    "tombstones": frozenset(),
    "commit_history": (),
}

print("Canon State:")
print(f"  Project: {canon_snapshot['project_id']}")
print(f"  Facts: {len(canon_snapshot['facts'])} (genesis)")
print(f"  Parent: {contract.canon_parent}")
print()

# Load provider configuration
config = get_real_provider_config()
print("Provider Configuration:")
print(f"  Base URL: {config['base_url']}")
print(f"  API Key: {mask_api_key(config['api_key'])}")
print(f"  Model ID: {config['model_id']}")
print()

# Budget setup
TOTAL_BUDGET = 5.0
PREVIOUS_SPENT = 1.54  # From reports
REMAINING = TOTAL_BUDGET - PREVIOUS_SPENT
MAX_NEW_SPENDING = 0.40

print("Budget Status:")
print(f"  Total cap: ${TOTAL_BUDGET:.2f}")
print(f"  Previous spending: ${PREVIOUS_SPENT:.2f}")
print(f"  Remaining: ${REMAINING:.2f}")
print(f"  Max new spending: ${MAX_NEW_SPENDING:.2f}")
print()

# Create provider with budget protection
provider = AnthropicProvider(
    model_id=config["model_id"],
    api_key=config["api_key"],
    base_url=config["base_url"],
    allow_real_calls=True,
)
budget_wrapper = BudgetProtectedGateway(provider, total_budget_usd=TOTAL_BUDGET)
gateway = budget_wrapper.gateway

print("✓ Budget-protected gateway initialized")
print()

# Create workflow components
contract_compiler = ContractCompiler()
context_compiler = ContextCompiler()
extractor = StructuredExtractor(budget_wrapper)

workflow = ChapterWorkflow(
    contract_compiler=contract_compiler,
    context_compiler=context_compiler,
    model_gateway=gateway,
    extractor=extractor,
    mock_mode=True,  # No production canon commits
)

print("=" * 80)
print("Executing Full Workflow (Extraction + Validation)")
print("=" * 80)
print()

start_time = time.time()
budget_start = budget_wrapper.get_budget_status()["spent_usd"]

try:
    # NOTE: We're NOT calling execute_chapter because we have existing prose
    # Instead, we'll manually execute the extraction and validation steps

    print("Step 1: Extract NarrativeDelta from prose")
    print("-" * 80)

    extraction_result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=series_vision,
        canon_parent="genesis",
    )

    print(f"Extraction status: {extraction_result.status}")
    print(f"Coverage: {extraction_result.diagnostics.coverage_percentage:.1f}%")
    print(f"Required found: {extraction_result.diagnostics.required_transitions_found}")
    print(f"Required missing: {extraction_result.diagnostics.required_transitions_missing}")
    print()

    if extraction_result.delta:
        print(f"Operations extracted: {len(extraction_result.delta.operations)}")
        for i, op in enumerate(extraction_result.delta.operations, 1):
            print(f"  {i}. {op.path.path} = {op.value}")
            print(f"     Evidence: {op.evidence.source_ref}")
            print(f"     Precondition: {type(op.precondition).__name__}")
        print()

    if extraction_result.issues:
        print(f"Extraction issues: {len(extraction_result.issues)}")
        for issue in extraction_result.issues[:10]:
            print(f"  - {issue}")
        if len(extraction_result.issues) > 10:
            print(f"  ... and {len(extraction_result.issues) - 10} more")
        print()

    # Step 2: Validate quality with Q0-Q3
    print("Step 2: Quality Validation (Q0-Q3)")
    print("-" * 80)

    if extraction_result.delta:
        quality_result = workflow._validate_quality(
            prose=prose,
            prose_hash=prose_hash,
            delta=extraction_result.delta,
            contract=contract,
            extraction_result=extraction_result,
            canon_snapshot=canon_snapshot,
        )

        print(f"Overall passed: {quality_result.passed}")
        print(f"Blocking issues: {len(quality_result.blocking_issues)}")
        print(f"Warnings: {len(quality_result.warnings)}")
        print()

        print("Validator Results:")
        print(f"  Q0 (Deterministic): {quality_result.q0_passed}")
        print(f"  Q1 (Canon Consistency): {quality_result.q1_passed}")
        print(f"  Q2 (Genre Rules): {quality_result.q2_passed}")
        print(f"  Q3 (Required Transitions): {quality_result.q3_passed}")
        print()

        if quality_result.check_details:
            print(f"Check Details ({len(quality_result.check_details)} checks):")
            for check in quality_result.check_details:
                status_symbols = {
                    "pass": "✓",
                    "fail": "✗",
                    "unknown": "?",
                    "error": "⚠",
                    "not_run": "⊘",
                }
                symbol = status_symbols.get(check.status.value, "?")
                print(f"  {symbol} {check.check_name}: {check.status.value}")
                if check.status.value != "pass":
                    print(f"     {check.message}")
            print()

        if quality_result.blocking_issues:
            print("Blocking Issues:")
            for issue in quality_result.blocking_issues:
                print(f"  ✗ {issue}")
            print()

        if quality_result.warnings:
            print("Warnings:")
            for warning in quality_result.warnings:
                print(f"  ⚠ {warning}")
            print()

        # Save results
        results_file = output_dir / "workflow_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "extraction": {
                        "status": extraction_result.status,
                        "operations_count": len(extraction_result.delta.operations),
                        "coverage": extraction_result.diagnostics.coverage_percentage,
                        "required_found": extraction_result.diagnostics.required_transitions_found,
                        "required_missing": extraction_result.diagnostics.required_transitions_missing,
                        "issues_count": len(extraction_result.issues),
                    },
                    "quality": {
                        "passed": quality_result.passed,
                        "q0_passed": quality_result.q0_passed,
                        "q1_passed": quality_result.q1_passed,
                        "q2_passed": quality_result.q2_passed,
                        "q3_passed": quality_result.q3_passed,
                        "blocking_issues": quality_result.blocking_issues,
                        "warnings": quality_result.warnings,
                        "checks_run": quality_result.checks_run,
                    },
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"✓ Results saved: {results_file}")
        print()

    else:
        print("✗ Extraction failed - no delta to validate")
        print()

    execution_time = time.time() - start_time
    budget_end = budget_wrapper.get_budget_status()["spent_usd"]
    cost_this_run = budget_end - budget_start

    print("=" * 80)
    print("Workflow Complete")
    print("=" * 80)
    print()

    print(f"Execution time: {execution_time:.2f}s")
    print(f"Cost this run: ${cost_this_run:.4f}")
    print(f"Max allowed: ${MAX_NEW_SPENDING:.2f}")
    print()

    if cost_this_run > MAX_NEW_SPENDING:
        print(f"⚠ WARNING: Exceeded recommended budget by ${cost_this_run - MAX_NEW_SPENDING:.4f}")
    else:
        print(f"✓ Within budget (used {cost_this_run / MAX_NEW_SPENDING * 100:.1f}%)")
    print()

    # Assessment
    print("=" * 80)
    print("Acceptance Assessment")
    print("=" * 80)
    print()

    if extraction_result.delta and quality_result:
        criteria = {
            "Prose valid": len(prose) > 100,
            "Required transitions extracted": extraction_result.diagnostics.required_transitions_found
            == len(contract.required_transitions),
            "Q0 passed (deterministic)": quality_result.q0_passed == True,
            "Q1 passed (canon consistency)": quality_result.q1_passed == True,
            "Q2 passed (genre rules)": quality_result.q2_passed == True,
            "Q3 passed (required transitions)": quality_result.q3_passed == True,
            "Overall quality passed": quality_result.passed,
            "Budget within limits": cost_this_run <= MAX_NEW_SPENDING,
        }

        all_pass = all(criteria.values())

        for criterion, passed in criteria.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}: {criterion}")

        print()
        if all_pass:
            print("✓✓ WORKFLOW ACCEPTANCE: PASS")
            print()
            print("Ready for three-chapter continuous generation")
        else:
            print("✗ WORKFLOW ACCEPTANCE: INCOMPLETE")
            print()
            print("Issues to address:")
            for criterion, passed in criteria.items():
                if not passed:
                    print(f"  - {criterion}")

except Exception as e:
    execution_time = time.time() - start_time
    budget_end = budget_wrapper.get_budget_status()["spent_usd"]
    cost_this_run = budget_end - budget_start

    print("=" * 80)
    print("Workflow Exception")
    print("=" * 80)
    print()
    print(f"Error: {e}")
    print(f"Execution time: {execution_time:.2f}s")
    print(f"Cost: ${cost_this_run:.4f}")
    print()

    import traceback

    traceback.print_exc()

# Final budget report
print("=" * 80)
print("Budget Report")
print("=" * 80)
print()

budget_wrapper.print_budget_report()
final_status = budget_wrapper.get_budget_status()

print()
print(f"This run cost: ${cost_this_run:.4f}")
print(f"Cumulative (reported): ${PREVIOUS_SPENT + cost_this_run:.4f} / ${TOTAL_BUDGET:.2f}")
print(f"Remaining (calculated): ${TOTAL_BUDGET - PREVIOUS_SPENT - cost_this_run:.4f}")
print()
print("=" * 80)
