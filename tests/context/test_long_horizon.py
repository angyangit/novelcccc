"""Long-horizon context compilation tests for V2-018.

Tests context compiler's ability to handle 1-1000+ chapter spans.
Focuses on memory retrieval, not actual novel generation.

Critical scenarios per Owner requirements:
- Test A: Long-term debt (ch12 → ch520)
- Test B: Character secret (ch8 → ch240 → ch300)
- Test C: Cross-hundred-chapter causality (ch30 → ch400)
- Test D: World rules (ch1 → ch800)
- Test E: Context budget management
- Test F: Cross-project isolation
"""

from datetime import datetime

import pytest

from anovel.context.compiler import ContextCompiler
from anovel.context.models import ContextCompilationError, ItemSource
from anovel.contracts.models import (
    ChapterContract,
    KnowledgeBoundary,
    ProtectedFact,
    RequiredTransition,
)
from anovel.domain.delta import OperationType
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    SeriesVision,
    WorldConstraints,
)


@pytest.fixture
def base_series_vision():
    """Minimal series vision for testing."""
    return SeriesVision(
        series_id="test-series-001",
        title="Test Long Novel",
        synopsis="A 1000-chapter test novel",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="goal-001",
                description="Test goal",
                constraints=[],
                success_criteria=[],
            )
        ],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="test-pack",
            version="1.0",
            content_hash="abc123",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )


@pytest.fixture
def base_contract(base_series_vision):
    """Minimal chapter contract."""

    def _make_contract(chapter_num: int):
        return ChapterContract(
            contract_id=f"contract-ch{chapter_num}",
            chapter_id=f"ch-{chapter_num}",
            chapter_number=chapter_num,
            plan_version="v1.0",
            created_at=datetime.utcnow(),
            canon_parent="canon-abc123",
            genre_pack_binding=base_series_vision.genre_pack_binding,
            required_transitions=[],
            prohibited_transitions=[],
            protected_facts=[],
            knowledge_boundaries=[],
        )

    return _make_contract


def test_scenario_a_long_term_debt_retrieval(base_series_vision, base_contract):
    """Test A: Long-term debt spanning ch12 → ch520.

    Debt established in ch12, not mentioned for hundreds of chapters,
    must be correctly retrieved in ch520 when creditor appears.
    """
    compiler = ContextCompiler()

    # Chapter 12: Establish debt
    compiler.memory.register_permanent_fact(
        fact_id="debt-001",
        fact_data={
            "debtor": "protagonist",
            "creditor": "merchant-wang",
            "amount": 50000,
            "currency": "yuan",
            "reason": "emergency business loan",
        },
        chapter_established=12,
        scope="test-series-001",
    )

    compiler.memory.register_state_change(
        fact_id="protagonist-cash",
        chapter=12,
        old_value=5000,
        new_value=55000,  # Received loan
        change_reason="debt-001 loan received",
    )

    # Chapters 13-519: Debt not mentioned (simulate with no relevant changes)

    # Chapter 520: Creditor appears, debt must be retrieved
    contract_520 = base_contract(520)
    contract_520 = ChapterContract(
        contract_id="contract-ch520",
        chapter_id="ch-520",
        chapter_number=520,
        plan_version="v1.0",
        created_at=datetime.utcnow(),
        canon_parent="canon-abc123",
        genre_pack_binding=base_series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="trans-520-debt",
                operation_type=OperationType.SET_FACT,
                fact_path="protagonist-cash",
                target_value=5000,  # After repayment
                rationale="Repay debt to merchant-wang",
            )
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
    )

    # Get current cash state at ch520
    current_cash = compiler.memory.get_current_state("protagonist-cash", 520)
    assert current_cash == 55000, "Cash state should persist from ch12"

    # Compile context for ch520
    result = compiler.compile_context(
        contract=contract_520,
        series_vision=base_series_vision,
        canon_snapshot={"commit_hash": "canon-520"},
        previous_chapter_ending="Previous chapter ended...",
        token_budget=10000,
    )

    # Must NOT be an error
    assert not isinstance(result, ContextCompilationError), (
        f"Compilation should succeed, got: {result}"
    )

    # Verify debt fact is included despite 500+ chapter gap
    debt_items = [
        item for item in result.required_items if "debt-001" in str(item.content)
    ]
    assert len(debt_items) > 0, "Debt established in ch12 must be retrieved in ch520"

    # Verify current cash state is available
    required_facts = compiler.memory.get_required_facts_for_chapter(
        chapter=520,
        scope="test-series-001",
        contract=contract_520,
    )
    assert any("debt" in str(f).lower() for f in required_facts), (
        "Long-term debt must appear in required facts"
    )


def test_scenario_b_character_secret_knowledge_boundary(
    base_series_vision, base_contract
):
    """Test B: Character secret spanning ch8 → ch240 → ch300.

    Ch8: Only protagonist knows secret
    Ch100: Protagonist should NOT leak secret
    Ch240: Second character learns secret
    Ch300: Both should know, compilation must respect updated boundary
    """
    compiler = ContextCompiler()

    # Ch8: Register secret
    secret_fact_id = "secret-protagonist-origin"
    compiler.memory.register_permanent_fact(
        fact_id=secret_fact_id,
        fact_data={
            "content": "Protagonist is actually the exiled prince",
            "sensitivity": "high",
        },
        chapter_established=8,
        scope="test-series-001",
    )

    # Ch8: Only protagonist knows
    compiler.memory._character_knowledge["protagonist"] = {secret_fact_id}

    # Ch100: Compile with knowledge boundary
    contract_100 = base_contract(100)
    contract_100 = ChapterContract(
        contract_id="contract-ch100",
        chapter_id="ch-100",
        chapter_number=100,
        plan_version="v1.0",
        created_at=datetime.utcnow(),
        canon_parent="canon-abc123",
        genre_pack_binding=base_series_vision.genre_pack_binding,
        required_transitions=[],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[
            KnowledgeBoundary(
                boundary_id="kb-secret-100",
                fact_id=secret_fact_id,
                knowers=["protagonist"],  # Only protagonist
                reader_knows=True,
            )
        ],
    )

    result_100 = compiler.compile_context(
        contract=contract_100,
        series_vision=base_series_vision,
        canon_snapshot={"commit_hash": "canon-100"},
        previous_chapter_ending=None,
        token_budget=10000,
    )

    assert not isinstance(result_100, ContextCompilationError)

    # Verify knowledge boundary is enforced
    kb_items = [
        item
        for item in result_100.required_items
        if item.source == ItemSource.CHARACTER_KNOWLEDGE
        and secret_fact_id in str(item.content)
    ]
    assert len(kb_items) > 0, "Knowledge boundary must be included"
    kb_item = kb_items[0]
    assert kb_item.character_visible == ["protagonist"], (
        "At ch100, only protagonist should know secret"
    )

    # Ch240: Second character learns secret
    compiler.memory._character_knowledge.setdefault("companion", set()).add(
        secret_fact_id
    )

    contract_300 = base_contract(300)
    contract_300 = ChapterContract(
        contract_id="contract-ch300",
        chapter_id="ch-300",
        chapter_number=300,
        plan_version="v1.0",
        created_at=datetime.utcnow(),
        canon_parent="canon-abc123",
        genre_pack_binding=base_series_vision.genre_pack_binding,
        required_transitions=[],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[
            KnowledgeBoundary(
                boundary_id="kb-secret-300",
                fact_id=secret_fact_id,
                knowers=["protagonist", "companion"],  # Both know now
                reader_knows=True,
            )
        ],
    )

    result_300 = compiler.compile_context(
        contract=contract_300,
        series_vision=base_series_vision,
        canon_snapshot={"commit_hash": "canon-300"},
        previous_chapter_ending=None,
        token_budget=10000,
    )

    assert not isinstance(result_300, ContextCompilationError)

    # Verify updated knowledge boundary
    kb_items_300 = [
        item
        for item in result_300.required_items
        if item.source == ItemSource.CHARACTER_KNOWLEDGE
        and secret_fact_id in str(item.content)
    ]
    assert len(kb_items_300) > 0
    kb_item_300 = kb_items_300[0]
    assert set(kb_item_300.character_visible) == {"protagonist", "companion"}, (
        "At ch300, both characters should know secret"
    )


def test_scenario_c_cross_hundred_chapter_promise(base_series_vision, base_contract):
    """Test C: Promise in ch30, fulfillment in ch400.

    Ch30: Character makes promise
    Ch400: Fulfillment condition appears, promise must be retrieved
    """
    compiler = ContextCompiler()

    # Ch30: Register promise
    compiler.memory.register_permanent_fact(
        fact_id="promise-mentor-001",
        fact_data={
            "promiser": "protagonist",
            "promisee": "dying-mentor",
            "promise": "Protect the village from bandits",
            "condition": "when bandits attack",
            "status": "unfulfilled",
        },
        chapter_established=30,
        scope="test-series-001",
    )

    # Ch400: Bandit attack triggers promise
    contract_400 = base_contract(400)
    contract_400 = ChapterContract(
        contract_id="contract-ch400",
        chapter_id="ch-400",
        chapter_number=400,
        plan_version="v1.0",
        created_at=datetime.utcnow(),
        canon_parent="canon-abc123",
        genre_pack_binding=base_series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="trans-400-promise",
                operation_type=OperationType.SET_FACT,
                fact_path="promise-mentor-001.status",
                target_value="fulfilled",
                rationale="Protagonist defends village, fulfilling promise from ch30",
            )
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
    )

    result = compiler.compile_context(
        contract=contract_400,
        series_vision=base_series_vision,
        canon_snapshot={"commit_hash": "canon-400"},
        previous_chapter_ending=None,
        token_budget=10000,
    )

    assert not isinstance(result, ContextCompilationError)

    # Promise from ch30 must be retrievable at ch400
    required_facts = compiler.memory.get_required_facts_for_chapter(
        chapter=400,
        scope="test-series-001",
        contract=contract_400,
    )

    promise_found = any("promise-mentor-001" in str(fact) for fact in required_facts)
    assert promise_found, (
        "Promise from ch30 must be retrieved at ch400 despite 370-chapter gap"
    )


def test_scenario_d_world_rule_persistence(base_series_vision, base_contract):
    """Test D: World rule from ch1 must constrain ch800.

    Ch1: Establish world rule (e.g., "no resurrection magic")
    Ch800: Rule must still apply even if not mentioned for 799 chapters
    """
    compiler = ContextCompiler()

    # Ch1: Establish world rule
    compiler.memory.register_permanent_fact(
        fact_id="world-rule-no-resurrection",
        fact_data={
            "rule": "No magic can resurrect the dead",
            "category": "world-constraint",
            "genre": "cultivation",
        },
        chapter_established=1,
        scope="test-series-001",
    )

    # Ch800: World rule must still be enforced
    contract_800 = base_contract(800)
    contract_800 = ChapterContract(
        contract_id="contract-ch800",
        chapter_id="ch-800",
        chapter_number=800,
        plan_version="v1.0",
        created_at=datetime.utcnow(),
        canon_parent="canon-abc123",
        genre_pack_binding=base_series_vision.genre_pack_binding,
        required_transitions=[],
        prohibited_transitions=[],
        protected_facts=[
            ProtectedFact(
                fact_id="world-rule-no-resurrection",
                fact_path="world.rules.resurrection",
                protection_reason="World constraint: no resurrection magic",
            )
        ],
        knowledge_boundaries=[],
    )

    result = compiler.compile_context(
        contract=contract_800,
        series_vision=base_series_vision,
        canon_snapshot={"commit_hash": "canon-800"},
        previous_chapter_ending=None,
        token_budget=10000,
    )

    assert not isinstance(result, ContextCompilationError)

    # World rule must be in required items
    protected_items = [
        item
        for item in result.required_items
        if "world-rule-no-resurrection" in str(item.content)
    ]
    assert len(protected_items) > 0, "World rule from ch1 must be enforced at ch800"


def test_scenario_e_budget_management_required_vs_optional(
    base_series_vision, base_contract
):
    """Test E: Context budget management.

    Required items get priority, optional items dropped if needed.
    If required items exceed budget, return diagnostic error.
    """
    compiler = ContextCompiler()

    # Create contract with many required transitions
    large_contract = base_contract(50)
    large_contract = ChapterContract(
        contract_id="contract-ch50",
        chapter_id="ch-50",
        chapter_number=50,
        plan_version="v1.0",
        created_at=datetime.utcnow(),
        canon_parent="canon-abc123",
        genre_pack_binding=base_series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id=f"trans-{i}",
                operation_type=OperationType.SET_FACT,
                fact_path=f"fact.path.{i}",
                target_value=f"value-{i}",
                rationale=f"Required change {i}" * 100,  # Make it large
            )
            for i in range(20)
        ],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
    )

    # Test with insufficient budget
    result_small = compiler.compile_context(
        contract=large_contract,
        series_vision=base_series_vision,
        canon_snapshot={"commit_hash": "canon-50"},
        previous_chapter_ending="Previous chapter ending text..." * 50,
        token_budget=500,  # Intentionally too small
    )

    # Must return diagnostic error, not silently drop required items
    assert isinstance(result_small, ContextCompilationError), (
        "Should return error when required items exceed budget"
    )
    assert result_small.error_type == "budget_exceeded"
    assert result_small.required_tokens > result_small.available_budget

    # Test with sufficient budget for required, but not all optional
    result_adequate = compiler.compile_context(
        contract=large_contract,
        series_vision=base_series_vision,
        canon_snapshot={"commit_hash": "canon-50"},
        previous_chapter_ending="Previous ending",
        token_budget=50000,  # Large enough for required
    )

    assert not isinstance(result_adequate, ContextCompilationError), (
        "Should succeed when budget covers required items"
    )

    # Optional items may be dropped
    assert result_adequate.budget.items_dropped >= 0, "Optional items can be dropped"
    assert not result_adequate.budget.budget_exceeded, (
        "Budget should not be marked as exceeded when compilation succeeds"
    )


def test_scenario_f_cross_project_isolation(base_series_vision, base_contract):
    """Test F: Cross-project isolation.

    Urban business novel should not access Eastern fantasy novel's data.
    """
    compiler = ContextCompiler()

    # Register facts for two different projects
    compiler.memory.register_permanent_fact(
        fact_id="urban-company-001",
        fact_data={
            "company": "TechStart Inc",
            "industry": "software",
        },
        chapter_established=1,
        scope="urban-business-001",
    )

    compiler.memory.register_permanent_fact(
        fact_id="fantasy-cultivation-realm",
        fact_data={
            "realm": "Golden Core Stage",
            "power": "immense",
        },
        chapter_established=1,
        scope="eastern-fantasy-001",
    )

    # Create urban novel series vision
    urban_vision = SeriesVision(
        series_id="urban-business-001",
        title="Urban Business Novel",
        synopsis="A business story",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban-pack",
            version="1.0",
            content_hash="urban-123",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    urban_contract = ChapterContract(
        contract_id="contract-urban-ch10",
        chapter_id="urban-ch-10",
        chapter_number=10,
        plan_version="v1.0",
        created_at=datetime.utcnow(),
        canon_parent="canon-urban",
        genre_pack_binding=urban_vision.genre_pack_binding,
        required_transitions=[],
        prohibited_transitions=[],
        protected_facts=[],
        knowledge_boundaries=[],
    )

    # Get required facts for urban novel
    urban_facts = compiler.memory.get_required_facts_for_chapter(
        chapter=10,
        scope="urban-business-001",
        contract=urban_contract,
    )

    # Verify no fantasy facts leak into urban context
    fantasy_leak = any(
        "cultivation" in str(fact).lower() or "realm" in str(fact).lower()
        for fact in urban_facts
    )
    assert not fantasy_leak, (
        "Fantasy novel facts must not leak into urban novel context"
    )

    # Verify urban facts are included
    urban_found = any(
        "TechStart" in str(fact) or "company" in str(fact).lower()
        for fact in urban_facts
    )
    assert urban_found, "Urban novel facts should be present in urban context"
