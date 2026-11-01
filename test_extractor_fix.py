"""Test extractor fixes on Task 2 prose WITHOUT real model calls.

This replays the extraction on the existing 1,483 char prose to verify:
1. Improved prompt (removed quote restrictions, enhanced activity detection)
2. Fixed coverage calculation (matches transitions, not just operation count)
3. Evidence verification works with proper prose text

Uses REAL MODEL to test extraction quality.
"""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

from anovel.config import get_real_provider_config, mask_api_key
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import OperationType
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

print("=" * 80)
print("Extractor Fix Verification on Task 2 Prose")
print("=" * 80)
print()

# Read Task 2 prose
prose_file = Path("output/stage10_task2/chapter_task2_001.txt")
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

print(f"Prose loaded: {len(prose)} chars")
print(f"Prose hash: {prose_hash[:16]}...")
print()

# Create test configuration
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
    contract_id=f"contract_test_{uuid.uuid4().hex[:8]}",
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

print("Contract:")
print(f"  Required transitions: {len(contract.required_transitions)}")
for t in contract.required_transitions:
    print(f"    - {t.fact_path} → {t.target_value}")
print()

# Load real provider
config = get_real_provider_config()
print("Provider Configuration:")
print(f"  Base URL: {config['base_url']}")
print(f"  API Key: {mask_api_key(config['api_key'])}")
print(f"  Model ID: {config['model_id']}")
print()

# Create budget-protected gateway
provider = AnthropicProvider(
    model_id=config["model_id"],
    api_key=config["api_key"],
    base_url=config["base_url"],
    allow_real_calls=True,
)
budget_wrapper = BudgetProtectedGateway(provider, total_budget_usd=5.0)
print("✓ Budget-protected gateway initialized")
print()

# Create extractor with fixed prompt
extractor = StructuredExtractor(budget_wrapper)

print("=" * 80)
print("Running Extraction (REAL MODEL)")
print("=" * 80)
print()

budget_before = budget_wrapper.get_budget_status()["spent_usd"]

try:
    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=series_vision,
        canon_parent="genesis",
    )

    budget_after = budget_wrapper.get_budget_status()["spent_usd"]
    extraction_cost = budget_after - budget_before

    print("=" * 80)
    print("Extraction Complete")
    print("=" * 80)
    print()

    print(f"Status: {result.status}")
    print(f"Cost: ${extraction_cost:.4f}")
    print()

    print("Diagnostics:")
    print(f"  Coverage: {result.diagnostics.coverage_percentage:.1f}%")
    print(f"  Required transitions found: {result.diagnostics.required_transitions_found}")
    print(f"  Required transitions missing: {result.diagnostics.required_transitions_missing}")
    print(f"  Issues: {len(result.issues)}")
    print()

    if result.delta:
        print(f"Operations Extracted: {len(result.delta.operations)}")
        for i, op in enumerate(result.delta.operations, 1):
            print(f"  {i}. {op.path.path} = {op.value}")
            print(f"     Subject: {op.subject}")
            print(f"     Scope: {op.scope}")
            print(f"     Evidence: {op.evidence.source_ref}")
        print()

        # Check which required transitions were found
        found_paths = {op.path.path for op in result.delta.operations}
        required_paths = {t.fact_path for t in contract.required_transitions}

        print("Required Transition Coverage:")
        for req in contract.required_transitions:
            status = "✓ FOUND" if req.fact_path in found_paths else "✗ MISSING"
            print(f"  {status}: {req.fact_path}")
        print()
    else:
        found_paths = set()

    if result.issues:
        print(f"Extraction Issues ({len(result.issues)}):")
        for issue in result.issues[:15]:
            print(f"  - {issue}")
        if len(result.issues) > 15:
            print(f"  ... and {len(result.issues) - 15} more")
        print()

    # Save results
    output_dir = Path("output/extractor_fix_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    result_file = output_dir / "extraction_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "status": result.status,
                "cost": extraction_cost,
                "operations_count": len(result.delta.operations) if result.delta else 0,
                "required_transitions": len(contract.required_transitions),
                "coverage_percentage": result.diagnostics.coverage_percentage,
                "required_found": result.diagnostics.required_transitions_found,
                "required_missing": result.diagnostics.required_transitions_missing,
                "issues_count": len(result.issues),
                "operations": [
                    {
                        "fact_path": op.path.path,
                        "value": op.value,
                        "evidence": op.evidence.source_ref,
                    }
                    for op in result.delta.operations
                ]
                if result.delta
                else [],
                "issues": result.issues,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"✓ Results saved: {result_file}")
    print()

    # Final assessment
    print("=" * 80)
    print("Assessment")
    print("=" * 80)
    print()

    success_criteria = {
        "protagonist.location extracted": "protagonist.location" in found_paths
        if result.delta
        else False,
        "protagonist.activity extracted": "protagonist.activity" in found_paths
        if result.delta
        else False,
        "All required transitions found": result.diagnostics.required_transitions_found
        == len(contract.required_transitions),
        "Cost within budget": extraction_cost < 0.20,
    }

    all_pass = all(success_criteria.values())

    for criterion, passed in success_criteria.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {criterion}")

    print()
    if all_pass:
        print("✓✓ EXTRACTOR FIX SUCCESSFUL")
        print()
        print("Ready for:")
        print("  - Full workflow re-test with Q0-Q3 validation")
        print("  - Three-chapter continuous generation")
    else:
        print("✗ EXTRACTOR FIX INCOMPLETE")
        print()
        if not success_criteria["protagonist.activity extracted"]:
            print("Root cause: Activity detection still failing")
            print("Next steps:")
            print("  1. Review LLM extraction response")
            print("  2. Check if prompt changes were effective")
            print("  3. Consider additional prompt refinement")

except Exception as e:
    budget_after = budget_wrapper.get_budget_status()["spent_usd"]
    extraction_cost = budget_after - budget_before

    print("=" * 80)
    print("Extraction Failed")
    print("=" * 80)
    print()
    print(f"Error: {e}")
    print(f"Cost: ${extraction_cost:.4f}")
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
print(f"This test cost: ${extraction_cost:.4f}")
print(f"Budget remaining: ${final_status['remaining_usd']:.4f}")
print()
print("=" * 80)
