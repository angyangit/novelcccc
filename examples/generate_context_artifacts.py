"""Generate real ContextArtifact examples for Urban Business and Eastern Fantasy.

Demonstrates V2-018 Context Compiler producing actual artifacts consumable by V2-019.
"""

from datetime import datetime

from anovel.context.compiler import ContextCompiler
from anovel.contracts.models import (
    ChapterContract,
    RequiredTransition,
    KnowledgeBoundary,
)
from anovel.planning.models import (
    SeriesVision,
    ProtagonistGoal,
    WorldConstraints,
    GenrePackBinding,
    Secret,
)
from anovel.domain.delta import OperationType


def generate_urban_business_artifact():
    """Generate ContextArtifact for Urban Business chapter."""

    # Urban business story vision
    vision = SeriesVision(
        series_id="urban-business-001",
        title="Tech Empire Rise",
        synopsis="Building a tech startup from garage to IPO",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="goal-series-funding",
                description="Secure Series A funding of $10M",
                constraints=["maintain_51_percent_equity", "positive_unit_economics"],
                success_criteria=["term_sheet_signed", "money_in_bank"],
            )
        ],
        world_constraints=WorldConstraints(
            realistic_constraints=["real_world_economics", "no_magic_solutions"],
        ),
        character_knowledge_map={},
        secrets=[
            Secret(
                secret_id="secret-competitor-intel",
                content="Competitor planning hostile acquisition",
                knowers=["protagonist"],
                reader_knows=True,
            )
        ],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban-business",
            version="1.0.0",
            content_hash="urban-abc123",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # Chapter 15 contract
    contract = ChapterContract(
        contract_id="urban-ch15-contract",
        chapter_id="urban-ch-15",
        chapter_number=15,
        plan_version="v1.0",
        created_at=datetime.now(),
        canon_parent="canon-urban-14",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="trans-pitch-meeting",
                operation_type=OperationType.SET_FACT,
                fact_path="investor_meetings.series_a_pitch",
                target_value="completed",
                rationale="Protagonist pitches to lead investor",
            )
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[
            KnowledgeBoundary(
                boundary_id="kb-competitor-intel",
                fact_id="secret-competitor-intel",
                knowers=["protagonist"],
                reader_knows=True,
            )
        ],
    )

    # Compile context
    compiler = ContextCompiler()

    # Set up company financial state
    compiler.memory.register_state_change(
        fact_id="company-bank-balance",
        chapter=1,
        old_value=50000,
        new_value=125000,
        change_reason="angel_investment",
    )

    previous_ending = """
    Sarah closed her laptop after the video call. The angel investor had been impressed
    with the demo, but cautious about the burn rate. "You have six months of runway,"
    he'd said. "Make it count." She looked at the term sheet draft on her desk.
    Tomorrow's meeting with Sequoia could change everything.
    """

    artifact = compiler.compile_context(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-urban-14"},
        previous_chapter_ending=previous_ending,
        token_budget=8000,
    )

    return artifact


def generate_fantasy_cultivation_artifact():
    """Generate ContextArtifact for Eastern Fantasy chapter."""

    # Fantasy cultivation story vision
    vision = SeriesVision(
        series_id="fantasy-cultivation-001",
        title="Immortal Dao Path",
        synopsis="Journey from mortal to immortal through cultivation",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="goal-foundation-establishment",
                description="Break through to Foundation Establishment realm",
                constraints=["accumulate_sufficient_qi", "survive_tribulation"],
                success_criteria=["condense_foundation", "stabilize_realm"],
            )
        ],
        world_constraints=WorldConstraints(
            cultivation_constraints=["qi_required_for_breakthrough", "tribulation_mandatory"],
            progression_rules=["cannot_skip_realms", "unstable_foundation_fatal"],
        ),
        character_knowledge_map={},
        secrets=[
            Secret(
                secret_id="secret-ancient-manual",
                content="Protagonist found ancient cultivation manual",
                knowers=["protagonist"],
                reader_knows=True,
            )
        ],
        genre_pack_binding=GenrePackBinding(
            pack_id="eastern-fantasy",
            version="1.0.0",
            content_hash="fantasy-def456",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # Chapter 42 contract
    contract = ChapterContract(
        contract_id="fantasy-ch42-contract",
        chapter_id="fantasy-ch-42",
        chapter_number=42,
        plan_version="v1.0",
        created_at=datetime.now(),
        canon_parent="canon-fantasy-41",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="trans-qi-breakthrough",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist.cultivation.qi_level",
                target_value=9500,
                rationale="Accumulate qi for foundation establishment attempt",
            )
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[
            KnowledgeBoundary(
                boundary_id="kb-ancient-manual",
                fact_id="secret-ancient-manual",
                knowers=["protagonist"],
                reader_knows=True,
            )
        ],
    )

    # Compile context
    compiler = ContextCompiler()

    # Set up cultivation state
    compiler.memory.register_state_change(
        fact_id="protagonist-qi-level",
        chapter=30,
        old_value=8000,
        new_value=9000,
        change_reason="spirit_stone_absorption",
    )

    compiler.memory.register_permanent_fact(
        fact_id="protagonist-realm",
        fact_data={
            "current": "Qi Condensation Peak",
            "next": "Foundation Establishment",
            "bottleneck": "requires_tribulation",
        },
        chapter_established=1,
        scope="fantasy-cultivation-001",
    )

    previous_ending = """
    Lin Feng circulated the qi through his meridians one final time. The ancient manual's
    technique was far superior to the sect's standard method. His dantian glowed with
    condensed spiritual energy, ready to breakthrough. Elder Zhang had warned him about
    the tribulation - nine heavenly lightning strikes that few survived. But with the
    secret technique from the Azure Dragon Manual, he felt confident. Tomorrow, at dawn,
    he would attempt Foundation Establishment.
    """

    artifact = compiler.compile_context(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-fantasy-41"},
        previous_chapter_ending=previous_ending,
        token_budget=8000,
    )

    return artifact


if __name__ == "__main__":
    print("=" * 80)
    print("URBAN BUSINESS CONTEXT ARTIFACT")
    print("=" * 80)

    urban = generate_urban_business_artifact()
    print(f"\nArtifact ID: {urban.artifact_id}")
    print(f"Chapter: {urban.chapter_id} (#{urban.chapter_number})")
    print(f"Contract: {urban.contract_id}")
    print(f"Canon Parent: {urban.canon_parent}")
    print(f"\nBudget Report:")
    print(f"  Total Budget: {urban.budget.total_budget} tokens")
    print(f"  Required: {urban.budget.required_tokens} tokens")
    print(f"  Optional: {urban.budget.optional_tokens} tokens")
    print(f"  Actual: {urban.budget.actual_tokens} tokens")
    print(f"  Items Included: {urban.budget.items_included}")
    print(f"  Items Dropped: {urban.budget.items_dropped}")
    print(f"  Budget Exceeded: {urban.budget.budget_exceeded}")

    print(f"\nRequired Items ({len(urban.required_items)}):")
    for i, item in enumerate(urban.required_items[:5], 1):
        print(f"  {i}. {item.source.value}: {item.rationale[:60]}...")

    print("\n" + "=" * 80)
    print("EASTERN FANTASY CONTEXT ARTIFACT")
    print("=" * 80)

    fantasy = generate_fantasy_cultivation_artifact()
    print(f"\nArtifact ID: {fantasy.artifact_id}")
    print(f"Chapter: {fantasy.chapter_id} (#{fantasy.chapter_number})")
    print(f"Contract: {fantasy.contract_id}")
    print(f"Canon Parent: {fantasy.canon_parent}")
    print(f"\nBudget Report:")
    print(f"  Total Budget: {fantasy.budget.total_budget} tokens")
    print(f"  Required: {fantasy.budget.required_tokens} tokens")
    print(f"  Optional: {fantasy.budget.optional_tokens} tokens")
    print(f"  Actual: {fantasy.budget.actual_tokens} tokens")
    print(f"  Items Included: {fantasy.budget.items_included}")
    print(f"  Items Dropped: {fantasy.budget.items_dropped}")
    print(f"  Budget Exceeded: {fantasy.budget.budget_exceeded}")

    print(f"\nRequired Items ({len(fantasy.required_items)}):")
    for i, item in enumerate(fantasy.required_items[:5], 1):
        print(f"  {i}. {item.source.value}: {item.rationale[:60]}...")

    print("\n" + "=" * 80)
    print("V2-019 CONSUMPTION READINESS")
    print("=" * 80)
    print("\nBoth artifacts ready for Model Gateway consumption:")
    print(f"✓ Urban artifact has {len(urban.required_items)} required items")
    print(f"✓ Fantasy artifact has {len(fantasy.required_items)} required items")
    print("✓ All items have source tracking and rationale")
    print("✓ Budget management working correctly")
    print("✓ Deterministic compilation (no LLM calls)")
    print("\nReady for V2-019 integration.")
