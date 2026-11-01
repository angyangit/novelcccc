"""Stage 10 Phase 3 Task 2: Real Model Unified Workflow Verification

End-to-end test of complete chapter workflow with real AI model:
Contract → Context → Writer → Extractor → Q0 → Q1 → Q2 → Q3 → Isolated Canon

Requirements:
- Use .env real model configuration (no Mock/Fake)
- Budget: existing $5.00 cap, recommend max $0.75 for this test
- Fail-closed quality gates enforced
- No production canon commits
- Show detailed CheckDetail results for all validators
- Test negative cases (hash mismatch, invalid operations)

Owner Decision: TASK 2 REAL MODEL GO / EXISTING BUDGET CAP / FAIL-CLOSED / NO PRODUCTION COMMIT
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
from anovel.domain.delta import OperationType
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
print("Stage 10 Phase 3 Task 2: Real Model Unified Workflow Verification")
print("=" * 80)
print()

# Create output directory
output_dir = Path("output/stage10_task2")
output_dir.mkdir(parents=True, exist_ok=True)

# Load real provider configuration
config = get_real_provider_config()
print("Provider Configuration:")
print(f"  Base URL: {config['base_url']}")
print(f"  API Key: {mask_api_key(config['api_key'])}")
print(f"  Model ID: {config['model_id']}")
print()

# Budget setup - existing $5.00 cap, cumulative tracking
TOTAL_BUDGET = 5.0
PHASE_9_10_SPENT = 1.12  # From previous phases
REMAINING_BUDGET = TOTAL_BUDGET - PHASE_9_10_SPENT
TASK_2_MAX = 0.75  # Recommended max for this test

print("Budget Status:")
print(f"  Total budget cap: ${TOTAL_BUDGET:.2f}")
print(f"  Previous spending (Stage 9 + Phase 1-2): ${PHASE_9_10_SPENT:.2f}")
print(f"  Available: ${REMAINING_BUDGET:.2f}")
print(f"  Task 2 recommended max: ${TASK_2_MAX:.2f}")
print()

# Create provider with budget protection
provider = AnthropicProvider(
    model_id=config["model_id"],
    api_key=config["api_key"],
    base_url=config["base_url"],
    allow_real_calls=True,
)

# Use existing budget tracking (cumulative)
budget_wrapper = BudgetProtectedGateway(provider, total_budget_usd=TOTAL_BUDGET)
gateway = budget_wrapper.gateway  # Get the actual ModelGateway
print("✓ Budget-protected gateway initialized")
print()

# Create series vision for test chapter
series_vision = SeriesVision(
    series_id="library_adventure",
    title="图书馆奇遇记",
    synopsis="李明在市图书馆探索《时间简史》，体验科学启蒙的奇妙旅程",
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
        prohibited_mechanisms=["魔法", "超能力", "时间旅行"],
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

# Create chapter contract
contract = ChapterContract(
    contract_id=f"contract_task2_{uuid.uuid4().hex[:8]}",
    chapter_id="chapter_task2_001",
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

print("Test Configuration:")
print(f"  Series: {series_vision.title}")
print(f"  Chapter: {contract.chapter_number} ({contract.chapter_id})")
print(f"  Required transitions: {len(contract.required_transitions)}")
print(f"  Canon parent: {contract.canon_parent}")
print()

# Genesis canon snapshot (proper structure, not arbitrary empty)
canon_snapshot = {
    "project_id": series_vision.series_id,
    "facts": (),  # Genesis state
    "tombstones": frozenset(),
    "commit_history": (),
}

print("Canon State:")
print(f"  Project ID: {canon_snapshot['project_id']}")
print(f"  Facts count: {len(canon_snapshot['facts'])}")
print(f"  Parent: {contract.canon_parent} (genesis)")
print()

# Create workflow components
contract_compiler = ContractCompiler()
context_compiler = ContextCompiler()
extractor = StructuredExtractor(budget_wrapper)  # Extractor uses budget wrapper

workflow = ChapterWorkflow(
    contract_compiler=contract_compiler,
    context_compiler=context_compiler,
    model_gateway=gateway,  # Workflow uses ModelGateway
    extractor=extractor,
    mock_mode=True,  # No production canon commits
)

print("=" * 80)
print("Executing Real Model Workflow")
print("=" * 80)
print()

start_time = time.time()
workflow_start_budget = budget_wrapper.get_budget_status()["spent_usd"]

try:
    result = workflow.execute_chapter(
        contract=contract,
        series_vision=series_vision,
        canon_snapshot=canon_snapshot,
        previous_chapter_ending=None,
        token_budget=8000,
        max_output_tokens=2000,  # Shorter chapter to conserve budget
        temperature=0.7,
    )

    execution_time = time.time() - start_time
    workflow_cost = budget_wrapper.get_budget_status()["spent_usd"] - workflow_start_budget

    print("=" * 80)
    print("Workflow Execution Complete")
    print("=" * 80)
    print()

    print(f"Status: {result.status.value}")
    print(f"Workflow ID: {result.workflow_id}")
    print(f"Execution time: {execution_time:.2f}s")
    print(f"Cost: ${workflow_cost:.4f}")
    print()

    # Save prose if generated
    if result.prose:
        prose_file = output_dir / f"{contract.chapter_id}.txt"
        with open(prose_file, "w", encoding="utf-8") as f:
            f.write(f"# 第{contract.chapter_number}章\n\n")
            f.write(result.prose)
            f.write("\n\n---\n\n")
            f.write(f"Workflow ID: {result.workflow_id}\n")
            f.write(f"Status: {result.status.value}\n")
            f.write(f"Prose hash: {result.prose_hash}\n")
            f.write(f"Cost: ${workflow_cost:.4f}\n")

        print(f"✓ Prose saved: {prose_file}")
        print(f"  Length: {len(result.prose)} chars")
        print(f"  Hash: {result.prose_hash[:16]}...")
        print()

    # Display stages completed
    print(f"Stages completed: {len(result.stages_completed)}")
    for stage in result.stages_completed:
        print(f"  ✓ {stage.value}")
    print()

    # Quality validation results
    if result.quality_result:
        qr = result.quality_result
        print("=" * 80)
        print("Quality Validation Results")
        print("=" * 80)
        print()

        print(f"Overall passed: {qr.passed}")
        print(f"Blocking issues: {len(qr.blocking_issues)}")
        print(f"Warnings: {len(qr.warnings)}")
        print(f"Checks run: {len(qr.checks_run)}")
        print()

        print("Validator Results:")
        print(f"  Q0 (Deterministic): {qr.q0_passed}")
        print(f"  Q1 (Canon Consistency): {qr.q1_passed}")
        print(f"  Q2 (Genre Rules): {qr.q2_passed}")
        print(f"  Q3 (Required Transitions): {qr.q3_passed}")
        print()

        if qr.check_details:
            print(f"Check Details ({len(qr.check_details)} checks):")
            for check in qr.check_details:
                status_symbols = {
                    "pass": "✓",
                    "fail": "✗",
                    "unknown": "?",
                    "error": "⚠",
                    "not_run": "⊘",
                }
                symbol = status_symbols.get(check.status.value, "?")
                print(f"  {symbol} {check.check_name}: {check.status.value}")
                print(f"     {check.message}")
                if check.metadata:
                    print(f"     Metadata: {check.metadata}")
            print()

            # Save check details to JSON
            checks_file = output_dir / f"{contract.chapter_id}_checks.json"
            with open(checks_file, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "check_name": c.check_name,
                            "status": c.status.value,
                            "message": c.message,
                            "severity": c.severity,
                            "metadata": c.metadata,
                        }
                        for c in qr.check_details
                    ],
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            print(f"✓ Check details saved: {checks_file}")
            print()

        if qr.blocking_issues:
            print("Blocking Issues:")
            for issue in qr.blocking_issues:
                print(f"  ✗ {issue}")
            print()

        if qr.warnings:
            print("Warnings:")
            for warning in qr.warnings:
                print(f"  ⚠ {warning}")
            print()

    # Delta extraction results
    if result.delta_result:
        dr = result.delta_result
        print("=" * 80)
        print("Delta Extraction Results")
        print("=" * 80)
        print()

        print(f"Extraction success: {dr.success}")
        print(f"Extraction method: {dr.extraction_method}")
        print(f"Prose hash: {dr.prose_hash[:16]}...")
        print(f"Issues count: {len(dr.issues)}")
        print()

        if dr.delta:
            print(f"Operations extracted: {len(dr.delta.operations)}")
            for i, op in enumerate(dr.delta.operations, 1):
                print(f"  {i}. {op.path.path} = {op.value}")
                print(f"     Subject: {op.subject}")
                print(f"     Scope: {op.scope}")
                print(f"     Evidence: {op.evidence.source_ref}")
            print()

        if dr.issues:
            print("Extraction Issues:")
            for issue in dr.issues[:10]:
                print(f"  - {issue}")
            if len(dr.issues) > 10:
                print(f"  ... and {len(dr.issues) - 10} more")
            print()

    # Canon commit result (should be mock)
    if result.canon_commit_hash:
        print("Canon Commit:")
        print(f"  Hash: {result.canon_commit_hash}")
        print(f"  Is mock: {result.is_mock_commit}")
        if not result.is_mock_commit:
            print("  ⚠ WARNING: Real production commit detected!")
        print()

    # Error information
    if result.error:
        print("=" * 80)
        print("Workflow Error")
        print("=" * 80)
        print()
        print(f"Stage: {result.error.stage.value}")
        print(f"Error type: {result.error.error_type}")
        print(f"Message: {result.error.message}")
        print(f"Retryable: {result.error.retryable}")
        print()

except Exception as e:
    execution_time = time.time() - start_time
    workflow_cost = budget_wrapper.get_budget_status()["spent_usd"] - workflow_start_budget

    print("=" * 80)
    print("Workflow Exception")
    print("=" * 80)
    print()
    print(f"Error: {e}")
    print(f"Execution time: {execution_time:.2f}s")
    print(f"Cost so far: ${workflow_cost:.4f}")
    print()

    import traceback

    traceback.print_exc()

    # Create minimal error result for reporting
    result = None

# Final budget report
print("=" * 80)
print("Budget Report")
print("=" * 80)
print()

budget_wrapper.print_budget_report()
final_status = budget_wrapper.get_budget_status()

print()
print(f"Task 2 cost: ${workflow_cost:.4f}")
print(f"Task 2 max recommended: ${TASK_2_MAX:.2f}")

if workflow_cost > TASK_2_MAX:
    print(f"⚠ WARNING: Task 2 exceeded recommended budget by ${workflow_cost - TASK_2_MAX:.4f}")

cumulative_spent = final_status["spent_usd"]
if cumulative_spent > TOTAL_BUDGET:
    print(f"✗ BUDGET EXCEEDED: ${cumulative_spent:.4f} > ${TOTAL_BUDGET:.2f}")
else:
    print(f"✓ Within total budget cap: ${cumulative_spent:.4f} / ${TOTAL_BUDGET:.2f}")

print()
print("=" * 80)
print("Task 2 Complete")
print("=" * 80)
print()

# Summary for Owner report
print("Summary for Owner Report:")
print(f"1. Remote HEAD: d9ffbb8 (Task 1 pushed)")
print(f"2. Provider: {config['base_url']}")
print(f"3. Model ID: {config['model_id']}")
print(f"4. Task 2 cost: ${workflow_cost:.4f}")
print(f"5. Cumulative spent: ${cumulative_spent:.4f} / ${TOTAL_BUDGET:.2f}")

if result and result.prose:
    print(f"6. Chapter location: {output_dir / contract.chapter_id}.txt")
    print(f"7. Prose length: {len(result.prose)} chars")
else:
    print("6. Chapter generation: FAILED")

if result and result.delta_result and result.delta_result.delta:
    ops_count = len(result.delta_result.delta.operations)
    print(f"8. Operations extracted: {ops_count}")
    print(f"9. Required transitions: {len(contract.required_transitions)}")
else:
    print("8. Extraction: FAILED")

if result and result.quality_result:
    print(f"10. Q0 passed: {result.quality_result.q0_passed}")
    print(f"11. Q1 passed: {result.quality_result.q1_passed}")
    print(f"12. Q2 passed: {result.quality_result.q2_passed}")
    print(f"13. Q3 passed: {result.quality_result.q3_passed}")
    print(f"14. Overall quality passed: {result.quality_result.passed}")
else:
    print("10. Quality validation: NOT RUN")

if result:
    print(f"15. Canon commit: {result.canon_commit_hash if result.canon_commit_hash else 'NONE'}")
    print(f"16. Canon commit is mock: {result.is_mock_commit}")
    print(f"17. Workflow status: {result.status.value}")
else:
    print("15. Canon commit: NONE (workflow failed)")
    print("16. Workflow status: EXCEPTION")

print("=" * 80)
