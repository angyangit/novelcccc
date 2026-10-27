"""
V2-016 Eastern Fantasy Canon Extension Contract Tests.

Acceptance Tests:
    AT-V2-016-01: Realm/ability/resource/cost types with legal preconditions
    AT-V2-016-02: Fantasy commerce (merchant guilds) not rejected for business keywords
    AT-V2-016-03: Modern corporate (stock market) rejected in fantasy extension

Contract: fantasy.eastern.progression Pack enforces cultivation world mechanics.
Allows spiritual cultivation, resource trading, merchant guilds.
Rejects undeclared modern corporate/stock market structures.

Validates:
- Cultivation realm progression with sequential constraints
- Ability prerequisites based on cultivation level
- Resource costs for breakthroughs
- Dao comprehension thresholds
- Fantasy commerce allowed (spirit stones, auctions, guilds)
- Modern corporate structures rejected
"""

import pytest
from decimal import Decimal

from anovel.domain import EntityId, ProjectId
from anovel.genre.extensions.progression import (
    Ability,
    BreakthroughAttempt,
    BreakthroughPrecondition,
    CultivationLevel,
    CultivationRealm,
    CultivationResource,
    FactionAffiliation,
    FactionType,
    ProgressionStateValidator,
    RealmType,
    ResourceType,
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
    """Load real GenrePackRegistry."""
    from pathlib import Path

    return GenrePackRegistry.load_from_file(
        Path("specs/genres/registry.yaml"), Path("specs")
    )


@pytest.fixture
def fantasy_pack_identity():
    """Fantasy eastern progression Pack identity."""
    from anovel.genre.identity import GenrePackIdentity

    return GenrePackIdentity(
        pack_id="fantasy.eastern.progression",
        version="1.0.0",
        content_hash="6e835c0a4197cbae2e88ee55b52201f7af47f3ca8bfb3088f776cc5e21598757",
    )


@pytest.fixture
def policy_engine(registry, fantasy_pack_identity):
    """Policy engine for fantasy Pack."""
    return GenreHardPolicyEngine(registry, fantasy_pack_identity)


@pytest.fixture
def sample_realm():
    """Sample cultivation realm."""
    return CultivationRealm(
        character_id=EntityId("char_wang_lin"),
        realm_type=RealmType.MORTAL,
        cultivation_level=CultivationLevel.QI_REFINING,
        dao_comprehension=15,
        breakthrough_ready=False,
        achieved_at="year_1_month_3",
    )


@pytest.fixture
def sample_ability():
    """Sample ability."""
    return Ability(
        ability_id="ability_fireball",
        character_id=EntityId("char_wang_lin"),
        name="火球术",
        ability_type="technique",
        source="sect_manual",
        usage_cost={"spiritual_energy": Decimal("10")},
        min_realm_required=CultivationLevel.FOUNDATION_ESTABLISHMENT,
        acquired_at="year_1_month_5",
    )


@pytest.fixture
def sample_resource():
    """Sample cultivation resource."""
    return CultivationResource(
        resource_id="res_spirit_stones_01",
        owner_id=EntityId("char_wang_lin"),
        resource_type=ResourceType.SPIRIT_STONE,
        amount=Decimal("500"),
        unit="low-grade spirit stones",
        quality="low",
        last_updated="year_1_month_6",
    )


# --- AT-V2-016-01: Realm/ability/resource/cost types with legal preconditions ---


def test_cultivation_realm_has_required_types(sample_realm):
    """Cultivation realm has type, level, dao comprehension."""
    assert isinstance(sample_realm.realm_type, RealmType)
    assert isinstance(sample_realm.cultivation_level, CultivationLevel)
    assert 0 <= sample_realm.dao_comprehension <= 100
    assert sample_realm.character_id
    assert sample_realm.achieved_at


def test_dao_comprehension_constraints():
    """Dao comprehension must be 0-100."""
    # Valid
    valid_realm = CultivationRealm(
        character_id=EntityId("char_01"),
        realm_type=RealmType.MORTAL,
        cultivation_level=CultivationLevel.QI_REFINING,
        dao_comprehension=50,
        breakthrough_ready=False,
        achieved_at="year_1",
    )
    assert valid_realm.dao_comprehension == 50

    # Invalid: exceeds 100
    with pytest.raises(ValueError, match="0-100"):
        CultivationRealm(
            character_id=EntityId("char_02"),
            realm_type=RealmType.MORTAL,
            cultivation_level=CultivationLevel.QI_REFINING,
            dao_comprehension=150,
            breakthrough_ready=False,
            achieved_at="year_1",
        )

    # Invalid: negative
    with pytest.raises(ValueError, match="0-100"):
        CultivationRealm(
            character_id=EntityId("char_03"),
            realm_type=RealmType.MORTAL,
            cultivation_level=CultivationLevel.QI_REFINING,
            dao_comprehension=-10,
            breakthrough_ready=False,
            achieved_at="year_1",
        )


def test_cultivation_resource_explicit_units(sample_resource):
    """Cultivation resources have explicit amounts and units."""
    assert sample_resource.resource_type == ResourceType.SPIRIT_STONE
    assert sample_resource.amount == Decimal("500")
    assert sample_resource.unit == "low-grade spirit stones"
    assert sample_resource.quality == "low"


def test_cultivation_resource_non_negative():
    """Cultivation resource amounts cannot be negative."""
    with pytest.raises(ValueError, match="cannot be negative"):
        CultivationResource(
            resource_id="res_invalid",
            owner_id=EntityId("char_01"),
            resource_type=ResourceType.SPIRIT_STONE,
            amount=Decimal("-100"),
            unit="spirit stones",
            quality="low",
            last_updated="year_1",
        )


def test_ability_has_prerequisites(sample_ability):
    """Abilities have minimum realm requirements."""
    assert sample_ability.min_realm_required == CultivationLevel.FOUNDATION_ESTABLISHMENT
    assert sample_ability.usage_cost is not None
    assert "spiritual_energy" in sample_ability.usage_cost


def test_realm_progression_sequential():
    """Cultivation progression must be sequential."""
    validator = ProgressionStateValidator()

    # Valid: Qi Refining -> Foundation Establishment
    is_valid, error = validator.validate_realm_progression(
        CultivationLevel.QI_REFINING, CultivationLevel.FOUNDATION_ESTABLISHMENT
    )
    assert is_valid
    assert error is None

    # Invalid: Skip levels (Qi Refining -> Core Formation)
    is_valid, error = validator.validate_realm_progression(
        CultivationLevel.QI_REFINING, CultivationLevel.CORE_FORMATION
    )
    assert not is_valid
    assert "skip" in error.lower()

    # Invalid: Regression
    is_valid, error = validator.validate_realm_progression(
        CultivationLevel.FOUNDATION_ESTABLISHMENT, CultivationLevel.QI_REFINING
    )
    assert not is_valid
    assert "regress" in error.lower()


def test_breakthrough_preconditions_validated(sample_realm):
    """Breakthrough requires preconditions (dao comprehension, resources)."""
    validator = ProgressionStateValidator()

    # Attempt breakthrough with insufficient dao comprehension
    errors = validator.validate_breakthrough_preconditions(
        sample_realm, CultivationLevel.FOUNDATION_ESTABLISHMENT
    )

    # Should have error for insufficient dao comprehension (need 20, have 15)
    assert len(errors) > 0
    assert any("comprehension" in e.lower() for e in errors)


def test_resource_sufficiency_check(sample_resource):
    """Validate sufficient cultivation resources for breakthrough."""
    validator = ProgressionStateValidator()

    resources = [sample_resource]
    owner_id = sample_resource.owner_id

    # Sufficient resources
    required = {"spiritual_energy": Decimal("300")}
    # Note: sample_resource is SPIRIT_STONE, not SPIRITUAL_ENERGY
    # So this should fail
    sufficient, shortfalls = validator.validate_resource_sufficiency(
        resources, required, owner_id
    )
    assert not sufficient
    assert len(shortfalls) > 0

    # Test with matching resource type
    required_stones = {"spirit_stone": Decimal("400")}
    sufficient, shortfalls = validator.validate_resource_sufficiency(
        resources, required_stones, owner_id
    )
    assert sufficient
    assert len(shortfalls) == 0

    # Insufficient
    required_stones = {"spirit_stone": Decimal("600")}
    sufficient, shortfalls = validator.validate_resource_sufficiency(
        resources, required_stones, owner_id
    )
    assert not sufficient
    assert len(shortfalls) > 0


def test_ability_prerequisites_enforced(sample_ability, sample_realm):
    """Cannot use ability without meeting minimum realm."""
    validator = ProgressionStateValidator()

    # sample_ability requires Foundation Establishment
    # sample_realm is Qi Refining
    can_use, reason = validator.validate_ability_prerequisites(sample_ability, sample_realm)

    assert not can_use
    assert reason is not None
    assert "foundation_establishment" in reason.lower()


def test_breakthrough_attempt_structure():
    """Breakthrough attempt has preconditions and costs."""
    attempt = BreakthroughAttempt(
        attempt_id="breakthrough_001",
        character_id=EntityId("char_wang"),
        from_level=CultivationLevel.QI_REFINING,
        to_level=CultivationLevel.FOUNDATION_ESTABLISHMENT,
        resource_costs={"spiritual_energy": Decimal("1000"), "breakthrough_pill": Decimal("1")},
        preconditions=[
            BreakthroughPrecondition(
                condition_type="dao_comprehension",
                required_value="20",
                actual_value="25",
                satisfied=True,
            ),
            BreakthroughPrecondition(
                condition_type="sufficient_resources",
                required_value="true",
                actual_value="true",
                satisfied=True,
            ),
        ],
        success_probability=Decimal("0.7"),
        story_time="year_2_month_3",
        evidence_ref="chapter_10:para_50",
    )

    assert attempt.from_level == CultivationLevel.QI_REFINING
    assert attempt.to_level == CultivationLevel.FOUNDATION_ESTABLISHMENT
    assert len(attempt.preconditions) == 2
    assert all(p.satisfied for p in attempt.preconditions)


def test_faction_affiliation():
    """Faction affiliation has type and status."""
    faction = FactionAffiliation(
        affiliation_id="faction_001",
        character_id=EntityId("char_wang"),
        faction_name="青云宗",
        faction_type=FactionType.RIGHTEOUS,
        rank="外门弟子",
        joined_at="year_1_month_1",
        status="active",
    )

    assert faction.faction_type == FactionType.RIGHTEOUS
    assert faction.status == "active"
    assert faction.faction_name == "青云宗"


# --- AT-V2-016-02: Fantasy commerce not rejected for business keywords ---


def test_allow_spirit_stone_trade(policy_engine):
    """Spirit stone trading is allowed in fantasy world."""
    fact = NarrativeFact(
        fact_id="fact_trade_01",
        description="王林在坊市用500块下品灵石购买了筑基丹",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_5:para_20",
        fact_type="resource_transaction",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.ALLOW


def test_allow_merchant_guild_auction(policy_engine):
    """Merchant guild auctions allowed in fantasy."""
    fact = NarrativeFact(
        fact_id="fact_auction_01",
        description="天宝商会举办拍卖会，竞拍稀有法器",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_8:para_15",
        fact_type="world_event",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.ALLOW


def test_allow_sect_resource_trade(policy_engine):
    """Sect resource exchange is legal fantasy commerce."""
    fact = NarrativeFact(
        fact_id="fact_trade_02",
        description="宗门任务奖励100贡献点，可兑换灵石或丹药",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_3:para_8",
        fact_type="reward_system",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.ALLOW


def test_fantasy_commerce_validator():
    """Fantasy commerce validator allows spirit stones, guilds."""
    validator = ProgressionStateValidator()

    # Allowed
    assert validator.allow_fantasy_commerce("用灵石购买丹药")
    assert validator.allow_fantasy_commerce("商会拍卖法器")
    assert validator.allow_fantasy_commerce("merchant guild trade")
    assert validator.allow_fantasy_commerce("spirit stone market")

    # Rejected: modern corporate
    assert not validator.allow_fantasy_commerce("公司股份制改革")
    assert not validator.allow_fantasy_commerce("IPO上市计划")
    assert not validator.allow_fantasy_commerce("股票期权激励")


# --- AT-V2-016-03: Modern corporate rejected in fantasy extension ---


def test_reject_stock_market_in_fantasy(policy_engine):
    """Modern stock market structures rejected in fantasy world."""
    fact = NarrativeFact(
        fact_id="fact_corporate_01",
        description="宗门实行股份制改革，弟子可持有宗门股票",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_12:para_5",
        fact_type="world_mechanism",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.REJECT


def test_reject_modern_ipo_in_fantasy(policy_engine):
    """Modern IPO mechanisms rejected in fantasy."""
    fact = NarrativeFact(
        fact_id="fact_corporate_02",
        description="天宝商会计划在修真界IPO上市",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_15:para_10",
        fact_type="business_plan",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.REJECT


def test_fantasy_extension_does_not_reference_business_fields(sample_realm):
    """Fantasy extension uses cultivation namespace, not business fields."""
    # Cultivation realm has fantasy-specific attributes
    assert hasattr(sample_realm, "cultivation_level")
    assert hasattr(sample_realm, "dao_comprehension")
    assert hasattr(sample_realm, "realm_type")

    # Does NOT have business-specific attributes
    assert not hasattr(sample_realm, "company_type")
    assert not hasattr(sample_realm, "revenue_scale")
    assert not hasattr(sample_realm, "employee_count_tier")


def test_complete_cultivation_progression_scenario():
    """Complete cultivation progression with resources and costs."""
    # Initial state
    character_id = EntityId("wang_lin")

    initial_realm = CultivationRealm(
        character_id=character_id,
        realm_type=RealmType.MORTAL,
        cultivation_level=CultivationLevel.QI_REFINING,
        dao_comprehension=10,
        breakthrough_ready=False,
        achieved_at="year_1_month_1",
    )

    # After cultivation
    advanced_realm = CultivationRealm(
        character_id=character_id,
        realm_type=RealmType.MORTAL,
        cultivation_level=CultivationLevel.QI_REFINING,
        dao_comprehension=25,
        breakthrough_ready=True,
        achieved_at="year_1_month_1",
    )

    # Resources for breakthrough
    resources = [
        CultivationResource(
            resource_id="res_01",
            owner_id=character_id,
            resource_type=ResourceType.SPIRITUAL_ENERGY,
            amount=Decimal("1500"),
            unit="units",
            quality="standard",
            last_updated="year_2_month_1",
        ),
        CultivationResource(
            resource_id="res_02",
            owner_id=character_id,
            resource_type=ResourceType.PILL,
            amount=Decimal("2"),
            unit="breakthrough pills",
            quality="medium",
            last_updated="year_2_month_1",
        ),
    ]

    validator = ProgressionStateValidator()

    # Validate progression is legal
    is_valid, _ = validator.validate_realm_progression(
        initial_realm.cultivation_level, CultivationLevel.FOUNDATION_ESTABLISHMENT
    )
    assert is_valid

    # Validate preconditions met (dao comprehension sufficient)
    errors = validator.validate_breakthrough_preconditions(
        advanced_realm, CultivationLevel.FOUNDATION_ESTABLISHMENT
    )
    assert len(errors) == 0

    # Validate resources sufficient
    required = {"spiritual_energy": Decimal("1000"), "pill": Decimal("1")}
    sufficient, _ = validator.validate_resource_sufficiency(
        resources, required, character_id
    )
    assert sufficient


def test_fantasy_cultivation_world_fact_allowed(policy_engine):
    """Cultivation events allowed in fantasy world."""
    fact = NarrativeFact(
        fact_id="fact_cultivation_01",
        description="王林突破至筑基期，灵力暴涨",
        context_type=FactContextType.WORLD_FACT,
        source_evidence="chapter_10:para_30",
        fact_type="cultivation_breakthrough",
    )

    judgment = policy_engine.judge_fact(fact)

    assert judgment.verdict == PolicyVerdict.ALLOW
