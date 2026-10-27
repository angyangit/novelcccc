"""
V2-015 Urban Business Canon Extension Contract Tests.

Acceptance Tests:
    AT-V2-015-01: Company, equity, capital types and resource preconditions correct
    AT-V2-015-02: Reject realistic Anchor injection of rebirth/cultivation facts
    AT-V2-015-03: Legal business samples pass and don't read fantasy-only fields

Contract: urban.business.realistic Pack enforces realistic world mechanics.
No supernatural cultivation, magic, or rebirth systems in actual world facts.
Dialogue, dreams, novel references, and metaphors are legal expressions.

Validates:
- Company state with type and revenue scale
- Equity positions with percentage constraints
- Resource pools with explicit units
- Transaction preconditions
- Rejection of supernatural mechanisms in world facts
- Isolation from fantasy extension fields
"""

import pytest
from decimal import Decimal

from anovel.domain import EntityId, ProjectId
from anovel.genre.extensions.business import (
    BusinessStateValidator,
    BusinessTransaction,
    Company,
    CompanyType,
    EquityPosition,
    ResourcePool,
    ResourceType,
    RevenueScale,
    TransactionPrecondition,
    TransactionType,
)
from anovel.genre import (
    GenrePackRegistry,
    GenreHardPolicyEngine,
    NarrativeFact,
    FactContextType,
    PolicyVerdict,
)


# --- Fixtures ---


@pytest.fixture
def registry():
    """Load real GenrePackRegistry from specs/genres/registry.yaml."""
    from pathlib import Path

    return GenrePackRegistry.load_from_file(
        Path("specs/genres/registry.yaml"), Path("specs")
    )


@pytest.fixture
def urban_pack_identity():
    """Urban business realistic Pack identity."""
    from anovel.genre.identity import GenrePackIdentity

    return GenrePackIdentity(
        pack_id="urban.business.realistic",
        version="1.0.0",
        content_hash="21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336",
    )


@pytest.fixture
def policy_engine(registry, urban_pack_identity):
    """Policy engine for urban Pack."""
    return GenreHardPolicyEngine(registry, urban_pack_identity)


@pytest.fixture
def sample_company():
    """Sample startup company."""
    return Company(
        company_id=EntityId("company_001"),
        project_id=ProjectId("urban_story_01"),
        name="创新科技",
        company_type=CompanyType.STARTUP,
        revenue_scale=RevenueScale.SEED,
        created_at="2024-01-01",
    )


@pytest.fixture
def sample_equity_position(sample_company):
    """Sample equity position."""
    return EquityPosition(
        position_id="equity_001",
        company_id=sample_company.company_id,
        holder_id=EntityId("character_zhang"),
        percentage=Decimal("60.0"),
        acquired_at="2024-01-01",
    )


@pytest.fixture
def sample_resource_pool():
    """Sample capital resource pool."""
    return ResourcePool(
        pool_id="pool_001",
        owner_id=EntityId("company_001"),
        resource_type=ResourceType.CAPITAL,
        amount=Decimal("500000.00"),
        unit="USD",
        last_updated="2024-06-01",
    )


# --- AT-V2-015-01: Company, equity, capital types and resource preconditions ---


def test_company_has_required_types(sample_company):
    """Company entity has type, revenue scale, and identity."""
    assert isinstance(sample_company.company_type, CompanyType)
    assert isinstance(sample_company.revenue_scale, RevenueScale)
    assert sample_company.company_id
    assert sample_company.project_id
    assert sample_company.name == "创新科技"


def test_equity_position_percentage_constraints():
    """Equity percentage must be 0-100."""
    # Valid equity
    valid_equity = EquityPosition(
        position_id="eq_01",
        company_id=EntityId("comp_01"),
        holder_id=EntityId("char_01"),
        percentage=Decimal("45.5"),
        acquired_at="2024-01-01",
    )
    assert valid_equity.percentage == Decimal("45.5")

    # Invalid: exceeds 100%
    with pytest.raises(ValueError, match="0-100"):
        EquityPosition(
            position_id="eq_02",
            company_id=EntityId("comp_01"),
            holder_id=EntityId("char_02"),
            percentage=Decimal("150.0"),
            acquired_at="2024-01-01",
        )

    # Invalid: negative
    with pytest.raises(ValueError, match="0-100"):
        EquityPosition(
            position_id="eq_03",
            company_id=EntityId("comp_01"),
            holder_id=EntityId("char_03"),
            percentage=Decimal("-10.0"),
            acquired_at="2024-01-01",
        )


def test_resource_pool_explicit_units(sample_resource_pool):
    """Resource pools have explicit amounts and units."""
    assert sample_resource_pool.resource_type == ResourceType.CAPITAL
    assert sample_resource_pool.amount == Decimal("500000.00")
    assert sample_resource_pool.unit == "USD"


def test_resource_pool_non_negative():
    """Resource amounts cannot be negative."""
    with pytest.raises(ValueError, match="cannot be negative"):
        ResourcePool(
            pool_id="pool_invalid",
            owner_id=EntityId("comp_01"),
            resource_type=ResourceType.CAPITAL,
            amount=Decimal("-1000.00"),
            unit="USD",
            last_updated="2024-01-01",
        )


def test_company_preconditions_validated(sample_company):
    """Company creation preconditions are validated."""
    validator = BusinessStateValidator()
    errors = validator.validate_company_preconditions(sample_company)
    assert len(errors) == 0

    # Invalid company: no name
    invalid_company = Company(
        company_id=EntityId("comp_02"),
        project_id=ProjectId("proj_01"),
        name="",
        company_type=CompanyType.STARTUP,
        revenue_scale=RevenueScale.SEED,
        created_at="2024-01-01",
    )
    errors = validator.validate_company_preconditions(invalid_company)
    assert "name cannot be empty" in errors[0]


def test_equity_total_cannot_exceed_100_percent(sample_company):
    """Total equity for company cannot exceed 100%."""
    validator = BusinessStateValidator()

    positions = [
        EquityPosition(
            position_id="eq_01",
            company_id=sample_company.company_id,
            holder_id=EntityId("holder_01"),
            percentage=Decimal("60.0"),
            acquired_at="2024-01-01",
        ),
        EquityPosition(
            position_id="eq_02",
            company_id=sample_company.company_id,
            holder_id=EntityId("holder_02"),
            percentage=Decimal("50.0"),
            acquired_at="2024-02-01",
        ),
    ]

    errors = validator.validate_equity_transfer(positions, sample_company.company_id)
    assert len(errors) > 0
    assert "exceeds 100%" in errors[0]


def test_resource_sufficiency_check(sample_resource_pool):
    """Validate resource pool has sufficient amount."""
    validator = BusinessStateValidator()

    # Sufficient
    assert validator.validate_resource_sufficiency(
        sample_resource_pool, Decimal("300000.00")
    )

    # Insufficient
    assert not validator.validate_resource_sufficiency(
        sample_resource_pool, Decimal("600000.00")
    )


def test_transaction_preconditions():
    """Transaction preconditions are checked before execution."""
    transaction = BusinessTransaction(
        transaction_id="tx_001",
        transaction_type=TransactionType.CAPITAL_INJECTION,
        source_entity=EntityId("investor_01"),
        target_entity=EntityId("company_001"),
        resource_changes={"capital": Decimal("1000000.00")},
        preconditions=[
            TransactionPrecondition(
                condition_type="investor_verified",
                required_value="true",
                actual_value="true",
                satisfied=True,
            ),
            TransactionPrecondition(
                condition_type="minimum_valuation",
                required_value="5000000",
                actual_value="3000000",
                satisfied=False,
            ),
        ],
        story_time="2024-06-01",
        evidence_ref="chapter_5:paragraph_12",
    )

    validator = BusinessStateValidator()
    all_satisfied, unsatisfied = validator.validate_transaction_preconditions(
        transaction
    )

    assert not all_satisfied
    assert len(unsatisfied) == 1
    assert "minimum_valuation" in unsatisfied[0]


# --- AT-V2-015-02: Reject realistic Anchor injection of rebirth/cultivation ---


def test_reject_cultivation_in_realistic_world_fact(policy_engine):
    """Actual cultivation in realistic anchor is rejected."""
    fact = NarrativeFact(
        fact_id="fact_cult_01",
        description="张总成功突破到筑基期，灵力大涨",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_3:para_5",
        fact_type="character_ability",
        mechanism_type="supernatural_cultivation",
        mechanism_confirmed=True,
        mechanism_source="chapter_3:para_5",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.REJECT
    assert "supernatural" in judgment.rationale.lower() or "cultivation" in judgment.rationale.lower()


def test_reject_rebirth_system_in_realistic_world(policy_engine):
    """Rebirth system facts rejected in realistic anchor."""
    fact = NarrativeFact(
        fact_id="fact_rebirth_01",
        description="主角激活了重生系统，获得修炼加速",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_1:para_10",
        fact_type="world_mechanism",
        mechanism_type="rebirth_system",
        mechanism_confirmed=True,
        mechanism_source="chapter_1:para_10",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.REJECT


def test_allow_cultivation_in_character_dialogue(policy_engine):
    """Characters can discuss cultivation in dialogue (not world fact)."""
    fact = NarrativeFact(
        fact_id="fact_dialogue_01",
        description="'如果能修炼就好了'，张总感叹道",
        context_type=FactContextType.CHARACTER_DIALOGUE,
        source_evidence="chapter_2:para_3",
        fact_type="character_speech",
    )

    judgment = policy_engine.judge_fact(fact)

    # Dialogue is not world fact, should allow or require review
    assert judgment.verdict in [PolicyVerdict.ALLOW, PolicyVerdict.REVIEW_REQUIRED]


def test_allow_cultivation_in_dream_sequence(policy_engine):
    """Dreams about cultivation are legal (not actual world mechanics)."""
    fact = NarrativeFact(
        fact_id="fact_dream_01",
        description="梦中，李明成为修仙者，御剑飞行",
        context_type=FactContextType.DREAM_SEQUENCE,
        source_evidence="chapter_4:para_8",
        fact_type="character_experience",
    )

    judgment = policy_engine.judge_fact(fact)

    # Dream is not world fact
    assert judgment.verdict in [PolicyVerdict.ALLOW, PolicyVerdict.REVIEW_REQUIRED]


def test_allow_novel_reference_with_cultivation(policy_engine):
    """Characters reading/discussing fantasy novels is legal."""
    fact = NarrativeFact(
        fact_id="fact_novel_01",
        description="王经理正在读一本修真小说",
        context_type=FactContextType.NOVEL_REFERENCE,
        source_evidence="chapter_6:para_2",
        fact_type="character_activity",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict in [PolicyVerdict.ALLOW, PolicyVerdict.REVIEW_REQUIRED]


def test_allow_metaphor_with_breakthrough(policy_engine):
    """Metaphorical 'breakthrough' in business context is legal."""
    fact = NarrativeFact(
        fact_id="fact_metaphor_01",
        description="公司业务迎来突破，市场份额大涨",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_7:para_4",
        fact_type="business_event",
    )

    judgment = policy_engine.judge_fact(fact)

    # Business breakthrough is realistic, not cultivation
    assert judgment.verdict == PolicyVerdict.ALLOW


# --- AT-V2-015-03: Legal business samples pass and don't read fantasy fields ---


def test_legal_business_transaction_passes(sample_company, sample_resource_pool):
    """Legal business transactions are validated successfully."""
    validator = BusinessStateValidator()

    # Valid company
    errors = validator.validate_company_preconditions(sample_company)
    assert len(errors) == 0

    # Valid resource pool
    assert sample_resource_pool.amount > 0
    assert sample_resource_pool.unit == "USD"

    # Sufficient capital
    assert validator.validate_resource_sufficiency(
        sample_resource_pool, Decimal("100000.00")
    )


def test_business_extension_does_not_reference_fantasy_fields(sample_company):
    """Business extension uses business namespace, not fantasy fields."""
    # Company has business-specific attributes
    assert hasattr(sample_company, "company_type")
    assert hasattr(sample_company, "revenue_scale")

    # Company does NOT have fantasy-specific attributes
    assert not hasattr(sample_company, "cultivation_level")
    assert not hasattr(sample_company, "realm_type")
    assert not hasattr(sample_company, "magic_affinity")


def test_equity_transfer_scenario():
    """Complete equity transfer scenario with preconditions."""
    # Initial state: founder owns 100%
    company_id = EntityId("startup_tech_01")

    initial_position = EquityPosition(
        position_id="eq_founder",
        company_id=company_id,
        holder_id=EntityId("founder_zhang"),
        percentage=Decimal("100.0"),
        acquired_at="2024-01-01",
    )

    # Investment transaction: founder dilutes to 70%, investor gets 30%
    post_investment_positions = [
        EquityPosition(
            position_id="eq_founder_post",
            company_id=company_id,
            holder_id=EntityId("founder_zhang"),
            percentage=Decimal("70.0"),
            acquired_at="2024-01-01",
        ),
        EquityPosition(
            position_id="eq_investor",
            company_id=company_id,
            holder_id=EntityId("investor_wang"),
            percentage=Decimal("30.0"),
            acquired_at="2024-06-15"),
    ]

    validator = BusinessStateValidator()

    # Initial state valid
    errors = validator.validate_equity_transfer([initial_position], company_id)
    assert len(errors) == 0

    # Post-investment state valid (total = 100%)
    errors = validator.validate_equity_transfer(post_investment_positions, company_id)
    assert len(errors) == 0


def test_capital_expenditure_with_preconditions():
    """Capital expenditure requires sufficient resources."""
    capital_pool = ResourcePool(
        pool_id="pool_company_capital",
        owner_id=EntityId("company_tech_01"),
        resource_type=ResourceType.CAPITAL,
        amount=Decimal("200000.00"),
        unit="USD",
        last_updated="2024-06-01",
    )

    expenditure_tx = BusinessTransaction(
        transaction_id="tx_expansion",
        transaction_type=TransactionType.CAPITAL_EXPENDITURE,
        source_entity=EntityId("company_tech_01"),
        target_entity=None,
        resource_changes={"capital": Decimal("-150000.00")},
        preconditions=[
            TransactionPrecondition(
                condition_type="sufficient_capital",
                required_value="150000.00",
                actual_value="200000.00",
                satisfied=True,
            ),
            TransactionPrecondition(
                condition_type="board_approval",
                required_value="approved",
                actual_value="approved",
                satisfied=True,
            ),
        ],
        story_time="2024-07-01",
        evidence_ref="chapter_10:para_20",
    )

    validator = BusinessStateValidator()

    # Sufficient capital
    assert validator.validate_resource_sufficiency(capital_pool, Decimal("150000.00"))

    # All preconditions satisfied
    all_satisfied, _ = validator.validate_transaction_preconditions(expenditure_tx)
    assert all_satisfied


def test_realistic_business_world_fact_allowed(policy_engine):
    """Realistic business events without supernatural elements are allowed."""
    fact = NarrativeFact(
        fact_id="fact_business_01",
        description="公司完成A轮融资，估值达到5000万",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_8:para_15",
        fact_type="business_milestone",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.ALLOW
