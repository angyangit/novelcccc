"""V2-020 Chapter Workflow end-to-end demo.

Demonstrates: Contract → Context → Gateway → Delta → Quality → Canon
"""

from datetime import datetime

from anovel.context.compiler import ContextCompiler
from anovel.contracts.compiler import ContractCompiler
from anovel.contracts.models import ChapterContract, KnowledgeBoundary, RequiredTransition
from anovel.domain.delta import OperationType
from anovel.gateway.gateway import ModelGateway
from anovel.gateway.mock_provider import MockProvider
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    SeriesVision,
    WorldConstraints,
)
from anovel.workflow.workflow import ChapterWorkflow
from anovel.workflow.models import WorkflowStatus


def demo_single_chapter_workflow():
    """Demo single chapter complete workflow."""
    print("=" * 80)
    print("V2-020 SINGLE CHAPTER WORKFLOW DEMO")
    print("=" * 80)

    # Setup components
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
    )

    # Create test series vision
    vision = SeriesVision(
        series_id="urban-empire-001",
        title="Tech Empire: Rise of Innovation",
        synopsis="A talented engineer builds a tech startup from garage to IPO",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="series-a-funding",
                description="Secure Series A funding to scale the product",
                constraints=["maintain_majority_control", "avoid_toxic_investors"],
                success_criteria=["$10M_raised", "board_seats_retained"],
            )
        ],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban-business",
            version="1.0",
            content_hash="urban-business-v1",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # Create chapter contract
    contract = ChapterContract(
        contract_id="urban-ch15-contract",
        chapter_id="urban-ch-15",
        chapter_number=15,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-ch-14",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="investor-pitch-complete",
                operation_type=OperationType.SET_FACT,
                fact_path="events.investor_pitch_meeting",
                target_value="completed",
                rationale="Sarah completes pitch to Sequoia partner",
            ),
            RequiredTransition(
                transition_id="term-sheet-offered",
                operation_type=OperationType.SET_FACT,
                fact_path="events.term_sheet_status",
                target_value="offered",
                rationale="Investor offers term sheet after successful pitch",
            ),
        ],
        knowledge_boundaries=[
            KnowledgeBoundary(
                boundary_id="sarah-knowledge-ch15",
                fact_id="competitor_acquisition_offer",
                knowers=["investor_partner"],
                revelation_constraint="not_before_chapter_20",
                reader_knows=False,
            )
        ],
    )

    print("\n1. EXECUTING CHAPTER 15 WORKFLOW")
    print("-" * 80)

    result = workflow.execute_chapter(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-ch-14", "chapter_count": 14},
        previous_chapter_ending="Sarah took a deep breath outside the Sequoia office. This was the moment everything had been building toward.",
        token_budget=8000,
        max_output_tokens=4000,
        temperature=0.7,
    )

    print(f"\nWorkflow ID: {result.workflow_id}")
    print(f"Status: {result.status.value.upper()}")
    print(f"Chapter: {result.chapter_number} ({result.chapter_id})")
    print(f"Execution time: {result.execution_time_seconds:.2f}s")
    print(f"Total cost: ${result.total_cost_usd:.4f}")

    print(f"\nStages completed: {len(result.stages_completed)}/6")
    for stage in result.stages_completed:
        print(f"  ✓ {stage.value}")

    if result.status == WorkflowStatus.SUCCESS:
        print(f"\n✓ CHAPTER GENERATION SUCCESS")
        print(f"  Canon commit: {result.canon_commit_hash}")
        print(f"  Prose length: {len(result.prose)} chars")
        print(f"  Quality issues: {len(result.metadata.get('quality_issues', []))}")

        if result.prose:
            print(f"\n  Prose preview:")
            print(f"  {result.prose[:300]}...")
    else:
        print(f"\n✗ WORKFLOW FAILED")
        if result.error:
            print(f"  Stage: {result.error.stage.value}")
            print(f"  Error: {result.error.error_type}")
            print(f"  Message: {result.error.message}")

    budget = gateway.get_budget_summary()
    print(f"\nBudget status:")
    print(f"  Total: ${budget['total']:.2f}")
    print(f"  Spent: ${budget['spent']:.4f}")
    print(f"  Available: ${budget['available']:.4f}")

    return result


def demo_three_chapter_sequence():
    """Demo 3-chapter continuous generation."""
    print("\n" + "=" * 80)
    print("V2-020 THREE-CHAPTER SEQUENCE DEMO")
    print("=" * 80)

    # Setup
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
    )

    vision = SeriesVision(
        series_id="fantasy-immortal-001",
        title="Immortal Ascension Path",
        synopsis="A cultivation journey from mortal to immortal",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="foundation-establishment",
                description="Break through to Foundation Establishment",
                constraints=["survive_heavenly_tribulation"],
                success_criteria=["realm_breakthrough", "dao_heart_stable"],
            )
        ],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="eastern-fantasy",
            version="1.0",
            content_hash="fantasy-v1",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    chapters = [
        {
            "number": 40,
            "id": "fantasy-ch-40",
            "transitions": [
                RequiredTransition(
                    transition_id="qi-gathering",
                    operation_type=OperationType.SET_FACT,
                    fact_path="protagonist.qi_level",
                    target_value=9000,
                    rationale="Lin Feng gathers qi for breakthrough",
                )
            ],
            "ending": None,
        },
        {
            "number": 41,
            "id": "fantasy-ch-41",
            "transitions": [
                RequiredTransition(
                    transition_id="tribulation-begins",
                    operation_type=OperationType.SET_FACT,
                    fact_path="events.tribulation_status",
                    target_value="in_progress",
                    rationale="Heavenly tribulation begins",
                )
            ],
            "ending": None,
        },
        {
            "number": 42,
            "id": "fantasy-ch-42",
            "transitions": [
                RequiredTransition(
                    transition_id="breakthrough-success",
                    operation_type=OperationType.SET_FACT,
                    fact_path="protagonist.realm",
                    target_value="foundation_establishment",
                    rationale="Lin Feng succeeds in breakthrough",
                )
            ],
            "ending": None,
        },
    ]

    results = []
    canon_snapshot = {"commit_hash": "canon-ch-39", "chapter_count": 39}
    previous_ending = "Lin Feng closed his eyes and began to circulate his qi. The moment of breakthrough was near."

    for chapter_spec in chapters:
        print(f"\n{'-' * 80}")
        print(f"GENERATING CHAPTER {chapter_spec['number']}")
        print(f"{'-' * 80}")

        contract = ChapterContract(
            contract_id=f"{chapter_spec['id']}-contract",
            chapter_id=chapter_spec['id'],
            chapter_number=chapter_spec['number'],
            plan_version="v1",
            created_at=datetime.now(),
            canon_parent=canon_snapshot["commit_hash"],
            genre_pack_binding=vision.genre_pack_binding,
            required_transitions=chapter_spec['transitions'],
        )

        result = workflow.execute_chapter(
            contract=contract,
            series_vision=vision,
            canon_snapshot=canon_snapshot,
            previous_chapter_ending=previous_ending,
            token_budget=8000,
            max_output_tokens=4000,
        )

        print(f"  Status: {result.status.value.upper()}")
        print(f"  Time: {result.execution_time_seconds:.2f}s")
        print(f"  Cost: ${result.total_cost_usd:.4f}")

        if result.status == WorkflowStatus.SUCCESS:
            print(f"  ✓ Canon commit: {result.canon_commit_hash}")
            # Update for next chapter
            canon_snapshot = {"commit_hash": result.canon_commit_hash, "chapter_count": chapter_spec['number']}
            # Extract last sentence as ending
            if result.prose:
                sentences = result.prose.strip().split(".")
                previous_ending = sentences[-2] + "." if len(sentences) > 1 else result.prose[:200]
        else:
            print(f"  ✗ Failed at stage: {result.error.stage.value if result.error else 'unknown'}")

        results.append(result)

    # Summary
    print("\n" + "=" * 80)
    print("SEQUENCE SUMMARY")
    print("=" * 80)

    success_count = sum(1 for r in results if r.status == WorkflowStatus.SUCCESS)
    total_cost = sum(r.total_cost_usd for r in results)
    total_time = sum(r.execution_time_seconds for r in results)

    print(f"Chapters generated: {success_count}/{len(results)}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per chapter: {total_time / len(results):.2f}s")

    budget = gateway.get_budget_summary()
    print(f"\nFinal budget:")
    print(f"  Spent: ${budget['spent']:.4f}")
    print(f"  Available: ${budget['available']:.4f}")

    return results


if __name__ == "__main__":
    # Run single chapter demo
    single_result = demo_single_chapter_workflow()

    # Run 3-chapter sequence demo
    sequence_results = demo_three_chapter_sequence()

    print("\n" + "=" * 80)
    print("V2-020 WORKFLOW READY")
    print("=" * 80)
    print("✓ Single chapter: Contract → Context → Gateway → Delta → Quality → Canon")
    print("✓ Multi-chapter: Continuous generation with canon progression")
    print("✓ Budget tracking: Admission control and cost monitoring")
    print("✓ Error handling: Graceful failure with retry information")
    print("\n✓ Ready for real novel generation with actual LLM providers")
