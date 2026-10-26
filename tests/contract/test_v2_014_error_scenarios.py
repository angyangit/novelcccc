"""
V2-014 Error Scenario Reproduction Tests

These tests reproduce the three confirmed incorrect judgment paths
that must be fixed before final acceptance.
"""

import pytest

from anovel.genre.identity import GenrePackIdentity
from anovel.genre.policy import (
    FactContextType,
    GenreHardPolicyEngine,
    NarrativeFact,
    PolicyVerdict,
)
from anovel.genre.registry import GenrePackRegistry


@pytest.fixture
def registry():
    """Load real GenrePackRegistry."""
    from pathlib import Path

    return GenrePackRegistry.load_from_file(
        Path("specs/genres/registry.yaml"), Path("specs")
    )


@pytest.fixture
def urban_engine(registry):
    """Urban policy engine."""
    identity = GenrePackIdentity(
        pack_id="urban.business.realistic",
        version="1.0.0",
        content_hash="21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336",
    )
    return GenreHardPolicyEngine(registry, identity)


@pytest.fixture
def fantasy_engine(registry):
    """Fantasy policy engine."""
    identity = GenrePackIdentity(
        pack_id="fantasy.eastern.progression",
        version="1.0.0",
        content_hash="6e835c0a4197cbae2e88ee55b52201f7af47f3ca8bfb3088f776cc5e21598757",
    )
    return GenreHardPolicyEngine(registry, identity)


class TestScenarioA_UrbanBusinessNotFalseReject:
    """Scenario A: Urban business operations must not be falsely rejected."""

    def test_system_upgrade_not_game_system(self, urban_engine):
        """'系统性数字化升级' should not be rejected as game system."""
        fact = NarrativeFact(
            fact_id="error-a1",
            description="公司正在进行系统性数字化升级",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="test:line-1",
            fact_type="business_event",
        )

        judgment = urban_engine.judge_fact(fact)

        # Must NOT reject legitimate business terminology
        assert judgment.verdict != PolicyVerdict.REJECT, \
            f"Incorrectly rejected legitimate business term: {judgment.rationale}"

    def test_breakthrough_sales_not_cultivation(self, urban_engine):
        """'突破销售瓶颈' should not be rejected as cultivation breakthrough."""
        fact = NarrativeFact(
            fact_id="error-a2",
            description="他可以突破销售瓶颈，争取更好的经营业绩",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="test:line-2",
            fact_type="business_event",
        )

        judgment = urban_engine.judge_fact(fact)

        # Must NOT reject legitimate business metaphor
        assert judgment.verdict != PolicyVerdict.REJECT, \
            f"Incorrectly rejected business metaphor: {judgment.rationale}"


class TestScenarioB_ConfirmedSupernaturalMustReject:
    """Scenario B: Confirmed supernatural abilities in urban reality must be rejected."""

    def test_confirmed_cultivation_to_immortal_rejected(self, urban_engine):
        """'修炼成仙，正式获得了超自然能力' must be rejected."""
        fact = NarrativeFact(
            fact_id="error-b1",
            description="主角修炼成仙，正式获得了超自然能力",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="test:line-3",
            fact_type="character_ability",
        )

        judgment = urban_engine.judge_fact(fact)

        # Must REJECT confirmed supernatural abilities
        assert judgment.verdict == PolicyVerdict.REJECT, \
            f"Failed to reject confirmed supernatural: {judgment.verdict}"

    def test_unconfirmed_mechanism_requires_review(self, urban_engine):
        """Unconfirmed mechanisms must not auto-ALLOW."""
        fact = NarrativeFact(
            fact_id="error-b2",
            description="主角获得了特殊能力",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="test:line-4",
            fact_type="character_ability",
            metadata={},  # No certainty, ambiguous
        )

        judgment = urban_engine.judge_fact(fact)

        # Must NOT auto-allow unconfirmed mechanisms
        assert judgment.verdict != PolicyVerdict.ALLOW, \
            f"Incorrectly allowed unconfirmed mechanism: {judgment.rationale}"


class TestScenarioC_FantasyTradeNotFalseReject:
    """Scenario C: Fantasy trade/commerce must not be falsely rejected."""

    def test_spiritual_medicine_listing_not_ipo(self, fantasy_engine):
        """'商会将灵药上市售卖' should not be rejected as modern IPO."""
        fact = NarrativeFact(
            fact_id="error-c1",
            description="青云商会将新炼制的灵药上市售卖",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="test:line-5",
            fact_type="business_event",
        )

        judgment = fantasy_engine.judge_fact(fact)

        # Must NOT reject legitimate fantasy commerce
        assert judgment.verdict != PolicyVerdict.REJECT, \
            f"Incorrectly rejected fantasy commerce: {judgment.rationale}"

    def test_confirmed_modern_corporate_rejected(self, fantasy_engine):
        """'现代股份制公司，发行股票并建立董事会' must be rejected."""
        fact = NarrativeFact(
            fact_id="error-c2",
            description="宗门新增现代股份制公司，发行股票并建立董事会",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="test:line-6",
            fact_type="world_mechanism",
        )

        judgment = fantasy_engine.judge_fact(fact)

        # Must REJECT confirmed modern corporate mechanisms
        assert judgment.verdict == PolicyVerdict.REJECT, \
            f"Failed to reject modern corporate: {judgment.verdict}"
