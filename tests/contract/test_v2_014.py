"""
V2-014 Genre Hard Policy Engine Contract Tests.

Validates AT-V2-014 acceptance criteria:
- AT-V2-014-01: Urban reality rejects actual cultivation, allows normal events
- AT-V2-014-02: Dialogue/dreams/references don't become world facts
- AT-V2-014-03: Semantic uncertainty returns explicit REVIEW_REQUIRED
- AT-V2-014-04: Optional strategies conflict rejection, no-match preserves Pack identity

Test structure:
- Each test class corresponds to one AT scenario
- Tests use real GenrePackRegistry and frozen Anchors
- Verdicts are explicit and traceable
"""

import pytest

from anovel.genre.identity import GenrePackIdentity
from anovel.genre.policy import (
    FactContextType,
    GenreHardPolicyEngine,
    NarrativeFact,
    OptionalStrategy,
    PolicyVerdict,
)
from anovel.genre.registry import GenrePackRegistry

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
    return GenrePackIdentity(
        pack_id="urban.business.realistic",
        version="1.0.0",
        content_hash="21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336",
    )


@pytest.fixture
def fantasy_pack_identity():
    """Fantasy eastern progression Pack identity."""
    return GenrePackIdentity(
        pack_id="fantasy.eastern.progression",
        version="1.0.0",
        content_hash="6e835c0a4197cbae2e88ee55b52201f7af47f3ca8bfb3088f776cc5e21598757",
    )


@pytest.fixture
def urban_engine(registry, urban_pack_identity):
    """Genre policy engine for urban.business.realistic."""
    return GenreHardPolicyEngine(registry, urban_pack_identity)


@pytest.fixture
def fantasy_engine(registry, fantasy_pack_identity):
    """Genre policy engine for fantasy.eastern.progression."""
    return GenreHardPolicyEngine(registry, fantasy_pack_identity)


# --- AT-V2-014-01: Urban reality rejects actual cultivation ---


class TestUrbanRealityRejectsCultivation:
    """AT-V2-014-01: Urban reality rejects actual supernatural abilities."""

    def test_reject_actual_cultivation_ability(self, urban_engine):
        """Actual cultivation ability in urban reality is rejected."""
        fact = NarrativeFact(
            fact_id="urban-001",
            description="Chen Wei can cultivate spiritual energy from the surroundings",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-3:line-45",
            fact_type="character_ability",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert judgment.rule_id == "urban.business.realistic:no-supernatural"
        assert "supernatural" in judgment.rationale.lower()
        assert judgment.conflicting_mechanics is not None
        assert len(judgment.conflicting_mechanics) > 0

    def test_reject_qi_breakthrough(self, urban_engine):
        """Qi breakthrough in urban reality is rejected."""
        fact = NarrativeFact(
            fact_id="urban-002",
            description="After absorbing qi, she achieved breakthrough to Foundation Establishment",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-5:line-112",
            fact_type="character_ability",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert "urban.business.realistic:no-supernatural" in judgment.rule_id

    def test_reject_system_status_window(self, urban_engine):
        """System/status window mechanics in urban reality rejected."""
        fact = NarrativeFact(
            fact_id="urban-003",
            description="A translucent status window appeared before his eyes showing his level",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-1:line-20",
            fact_type="world_mechanism",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REJECT

    def test_allow_realistic_business_success(self, urban_engine):
        """Normal business success in urban reality is allowed."""
        fact = NarrativeFact(
            fact_id="urban-004",
            description="After months of hard work, the startup secured Series A funding",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-10:line-200",
            fact_type="business_event",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.rule_id == "urban.business.realistic:realistic-mechanics"

    def test_allow_realistic_character_growth(self, urban_engine):
        """Realistic character skill development allowed."""
        fact = NarrativeFact(
            fact_id="urban-005",
            description="Through practice and mentorship, she mastered financial modeling",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-7:line-89",
            fact_type="character_ability",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW


# --- AT-V2-014-02: Dialogue/dreams don't become world facts ---


class TestNarrativeContextBoundaries:
    """AT-V2-014-02: Character dialogue, dreams, novel references don't establish world facts."""

    def test_character_discussing_cultivation_novel(self, urban_engine):
        """Character discussing cultivation novel is allowed in urban reality."""
        fact = NarrativeFact(
            fact_id="context-001",
            description="Li Ming told his friend about the cultivation novel he was reading",
            context_type=FactContextType.CHARACTER_DIALOGUE,
            source_evidence="chapter-2:line-55",
            fact_type="dialogue",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert "context" in judgment.rationale.lower()
        assert judgment.diagnostic["context_type"] == "CHARACTER_DIALOGUE"

    def test_character_dreaming_of_flying(self, urban_engine):
        """Character dreaming of supernatural abilities is allowed."""
        fact = NarrativeFact(
            fact_id="context-002",
            description="In his dream, he could fly and shoot fire from his hands",
            context_type=FactContextType.DREAM_SEQUENCE,
            source_evidence="chapter-4:line-78",
            fact_type="dream_content",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.diagnostic["context_type"] == "DREAM_SEQUENCE"

    def test_metaphorical_breakthrough(self, urban_engine):
        """Metaphorical 'breakthrough' language is allowed."""
        fact = NarrativeFact(
            fact_id="context-003",
            description="It was a breakthrough moment in negotiations, like breaking through a barrier",
            context_type=FactContextType.METAPHOR,
            source_evidence="chapter-6:line-134",
            fact_type="metaphor",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW

    def test_character_speculation_about_magic(self, urban_engine):
        """Character speculating about impossible things is allowed."""
        fact = NarrativeFact(
            fact_id="context-004",
            description="'What if magic was real?' she wondered, not believing it for a moment",
            context_type=FactContextType.SPECULATION,
            source_evidence="chapter-8:line-167",
            fact_type="speculation",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW

    def test_fantasy_character_discussing_business(self, fantasy_engine):
        """Fantasy character discussing business in dialogue is allowed."""
        fact = NarrativeFact(
            fact_id="context-005",
            description="The merchant explained the caravan trade routes to the cultivator",
            context_type=FactContextType.CHARACTER_DIALOGUE,
            source_evidence="chapter-5:line-90",
            fact_type="dialogue",
        )

        judgment = fantasy_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW


# --- AT-V2-014-03: Semantic uncertainty requires explicit review ---


class TestSemanticUncertaintyHandling:
    """AT-V2-014-03: When semantic judgment is uncertain, return explicit REVIEW_REQUIRED."""

    def test_unknown_context_requires_review(self, urban_engine):
        """Unknown narrative context requires human review."""
        fact = NarrativeFact(
            fact_id="uncertain-001",
            description="Energy filled the room",
            context_type=FactContextType.UNKNOWN,
            source_evidence="chapter-9:line-45",
            fact_type="ambiguous_event",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REVIEW_REQUIRED
        assert judgment.rule_id is None
        assert "cannot determine" in judgment.rationale.lower()
        assert judgment.diagnostic["reason"] == "unknown_context"

    def test_ambiguous_ability_claim_requires_review(self, urban_engine):
        """Ambiguous ability claim without certainty metadata requires review."""
        fact = NarrativeFact(
            fact_id="uncertain-002",
            description="He possessed unusual abilities in reading people",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-11:line-234",
            fact_type="character_ability",
            metadata={},  # No certainty field
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REVIEW_REQUIRED
        assert "insufficient evidence" in judgment.rationale.lower()
        assert judgment.diagnostic["reason"] == "semantic_uncertainty"

    def test_explicit_certainty_allows_judgment(self, urban_engine):
        """Fact with explicit certainty metadata allows definitive judgment."""
        fact = NarrativeFact(
            fact_id="uncertain-003",
            description="He has exceptional negotiation skills",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-12:line-89",
            fact_type="character_ability",
            metadata={"certainty": "high", "evidence": "demonstrated in 3 scenes"},
        )

        judgment = urban_engine.judge_fact(fact)

        # With certainty metadata and realistic skill, should ALLOW
        assert judgment.verdict == PolicyVerdict.ALLOW


# --- AT-V2-014-04: Optional strategy handling ---


class TestOptionalStrategyJudgment:
    """AT-V2-014-04: Optional strategy conflicts rejected, no-match preserves Pack identity."""

    def test_reject_supernatural_strategy_in_urban(self, urban_engine):
        """Optional strategy introducing cultivation in urban Pack is rejected."""
        strategy = OptionalStrategy(
            strategy_id="strat-001",
            description="Add cultivation subplot",
            source="retrieval:similar_stories",
            proposed_mechanics={
                "cultivation": "qi_refining",
                "breakthrough": "enabled",
            },
        )

        judgment = urban_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert "supernatural" in judgment.rationale.lower()
        assert judgment.pack_identity_preserved is True

    def test_reject_corporate_strategy_in_fantasy(self, fantasy_engine):
        """Optional strategy introducing modern corporate mechanics in fantasy rejected."""
        strategy = OptionalStrategy(
            strategy_id="strat-002",
            description="Add startup equity subplot",
            source="template:modern_business",
            proposed_mechanics={
                "corporate_structure": "C-corp",
                "equity_system": "cap_table",
            },
        )

        judgment = fantasy_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert "modern corporate" in judgment.rationale.lower()
        assert judgment.pack_identity_preserved is True

    def test_no_match_strategy_preserves_identity(self, urban_engine):
        """Strategy with no match preserves Pack identity, doesn't create world rules."""
        strategy = OptionalStrategy(
            strategy_id="strat-003",
            description="Introduce mentor character archetype",
            source="retrieval:story_patterns",
            proposed_mechanics={},  # No mechanics proposed
        )

        judgment = urban_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.pack_identity_preserved is True
        assert (
            "compatible" in judgment.rationale.lower()
            or "preserved" in judgment.rationale.lower()
        )

    def test_compatible_strategy_allowed(self, fantasy_engine):
        """Strategy compatible with Pack mechanics is allowed."""
        strategy = OptionalStrategy(
            strategy_id="strat-004",
            description="Add sect competition arc",
            source="template:eastern_fantasy",
            proposed_mechanics={"sect_rivalry": "enabled"},
        )

        judgment = fantasy_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.pack_identity_preserved is True


# --- Dual Anchor Isolation ---


class TestDualAnchorIsolation:
    """Verify urban and fantasy Anchors enforce different world mechanics."""

    def test_cultivation_allowed_in_fantasy_rejected_in_urban(
        self, urban_engine, fantasy_engine
    ):
        """Cultivation fact: rejected in urban, allowed in fantasy."""
        urban_fact = NarrativeFact(
            fact_id="dual-001-urban",
            description="The protagonist can absorb spiritual energy to cultivate",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-1:line-10",
            fact_type="character_ability",
        )

        fantasy_fact = NarrativeFact(
            fact_id="dual-001-fantasy",
            description="The protagonist can absorb spiritual energy to cultivate",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-1:line-10",
            fact_type="character_ability",
        )

        urban_judgment = urban_engine.judge_fact(urban_fact)
        fantasy_judgment = fantasy_engine.judge_fact(fantasy_fact)

        assert urban_judgment.verdict == PolicyVerdict.REJECT
        assert fantasy_judgment.verdict == PolicyVerdict.ALLOW

    def test_business_competition_allowed_in_both(self, urban_engine, fantasy_engine):
        """Business competition: allowed in urban, allowed in fantasy (trade/commerce legal)."""
        urban_fact = NarrativeFact(
            fact_id="dual-002-urban",
            description="Two companies compete for the same market segment",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-5:line-67",
            fact_type="business_event",
        )

        fantasy_fact = NarrativeFact(
            fact_id="dual-002-fantasy",
            description="Two merchant clans compete for the same trade route",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-5:line-67",
            fact_type="business_event",
        )

        urban_judgment = urban_engine.judge_fact(urban_fact)
        fantasy_judgment = fantasy_engine.judge_fact(fantasy_fact)

        assert urban_judgment.verdict == PolicyVerdict.ALLOW
        assert fantasy_judgment.verdict == PolicyVerdict.ALLOW

    def test_modern_equity_allowed_in_urban_rejected_in_fantasy(
        self, urban_engine, fantasy_engine
    ):
        """Modern equity mechanics: allowed in urban, rejected in fantasy."""
        urban_fact = NarrativeFact(
            fact_id="dual-003-urban",
            description="The board approved a new equity compensation plan",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-8:line-123",
            fact_type="business_mechanism",
        )

        fantasy_fact = NarrativeFact(
            fact_id="dual-003-fantasy",
            description="The sect established an equity-based reward system",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-8:line-123",
            fact_type="world_mechanism",
        )

        urban_judgment = urban_engine.judge_fact(urban_fact)
        fantasy_judgment = fantasy_engine.judge_fact(fantasy_fact)

        assert urban_judgment.verdict == PolicyVerdict.ALLOW
        assert fantasy_judgment.verdict == PolicyVerdict.REJECT


# --- Pack Identity Preservation ---


class TestPackIdentityPreservation:
    """Verify Pack identity (id, version, content_hash) remains frozen."""

    def test_pack_identity_immutable(self, urban_engine, urban_pack_identity):
        """Engine preserves frozen Pack identity."""
        assert urban_engine.pack_identity == urban_pack_identity
        assert urban_engine.pack_identity.pack_id == "urban.business.realistic"
        assert urban_engine.pack_identity.version == "1.0.0"
        assert (
            urban_engine.pack_identity.content_hash
            == "21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336"
        )

    def test_strategy_rejection_preserves_pack(
        self, fantasy_engine, fantasy_pack_identity
    ):
        """Rejecting conflicting strategy doesn't change Pack identity."""
        strategy = OptionalStrategy(
            strategy_id="preserve-001",
            description="Switch to urban business mechanics",
            source="fallback",
            proposed_mechanics={"corporate_structure": "enabled"},
        )

        judgment = fantasy_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert judgment.pack_identity_preserved is True
        assert fantasy_engine.pack_identity == fantasy_pack_identity


# --- Canon Safety Boundary ---


class TestCanonSafetyBoundary:
    """Verify policy engine does not write to Canon or issue CommitPermits."""

    def test_judgment_does_not_modify_canon(self, urban_engine):
        """Policy judgment is read-only, does not write to Canon."""
        fact = NarrativeFact(
            fact_id="safety-001",
            description="Test fact for safety verification",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="test:line-1",
            fact_type="test",
        )

        judgment = urban_engine.judge_fact(fact)

        # Judgment returns a verdict, but doesn't produce CommitPermit or Canon state
        assert isinstance(judgment.verdict, PolicyVerdict)
        # No permit, no Canon modification - just judgment
        assert hasattr(judgment, "verdict")
        assert hasattr(judgment, "rule_id")
        assert hasattr(judgment, "rationale")

    def test_engine_has_no_canon_write_methods(self, urban_engine):
        """Policy engine does not expose Canon write methods."""
        assert not hasattr(urban_engine, "commit_to_canon")
        assert not hasattr(urban_engine, "issue_permit")
        assert not hasattr(urban_engine, "write_canon")


# --- Verdict Traceability ---


class TestVerdictTraceability:
    """Verify all verdicts include rule_id, rationale, and diagnostic info."""

    def test_reject_verdict_has_full_traceability(self, urban_engine):
        """REJECT verdict includes rule_id, rationale, conflicting_mechanics."""
        fact = NarrativeFact(
            fact_id="trace-001",
            description="Character can sense qi fluctuations",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-2:line-34",
            fact_type="character_ability",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert judgment.rule_id is not None
        assert len(judgment.rationale) > 0
        assert judgment.conflicting_mechanics is not None
        assert len(judgment.conflicting_mechanics) > 0

    def test_allow_verdict_has_rule_provenance(self, fantasy_engine):
        """ALLOW verdict includes rule_id and rationale."""
        fact = NarrativeFact(
            fact_id="trace-002",
            description="Elder Zhang achieved Core Formation realm",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-10:line-200",
            fact_type="character_progression",
        )

        judgment = fantasy_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.rule_id is not None
        assert len(judgment.rationale) > 0

    def test_review_required_has_diagnostic(self, urban_engine):
        """REVIEW_REQUIRED verdict includes diagnostic reason."""
        fact = NarrativeFact(
            fact_id="trace-003",
            description="Strange phenomena occurred",
            context_type=FactContextType.UNKNOWN,
            source_evidence="chapter-7:line-89",
            fact_type="ambiguous",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REVIEW_REQUIRED
        assert judgment.rule_id is None
        assert len(judgment.rationale) > 0
        assert judgment.diagnostic is not None
        assert "reason" in judgment.diagnostic


# --- Chinese Novel Judgment Tests ---


class TestChineseUrbanRealismJudgment:
    """Chinese urban realistic novel judgment scenarios."""

    def test_reject_chinese_cultivation_in_urban(self, urban_engine):
        """都市现实世界中，主角实际吸收灵气、突破筑基：REJECT"""
        fact = NarrativeFact(
            fact_id="zh-urban-001",
            description="陈伟能够吸收周围的灵气，突破到了筑基期",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-3:line-100",
            fact_type="character_ability",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert "urban.business.realistic:no-supernatural" in judgment.rule_id
        assert judgment.conflicting_mechanics is not None

    def test_allow_chinese_dream_cultivation(self, urban_engine):
        """都市角色梦见御剑飞行：不得视为真实世界污染"""
        fact = NarrativeFact(
            fact_id="zh-urban-002",
            description="在梦中，李明御剑飞行，穿梭于云海之间",
            context_type=FactContextType.DREAM_SEQUENCE,
            source_evidence="chapter-5:line-67",
            fact_type="dream_content",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert "context" in judgment.rationale.lower()
        assert judgment.diagnostic["context_type"] == "DREAM_SEQUENCE"

    def test_allow_chinese_discussing_cultivation_novel(self, urban_engine):
        """都市角色讨论修仙小说：不得误拒绝"""
        fact = NarrativeFact(
            fact_id="zh-urban-003",
            description="王浩向同事推荐了一本修仙小说，讲述主角从凡人修炼到仙帝的故事",
            context_type=FactContextType.CHARACTER_DIALOGUE,
            source_evidence="chapter-2:line-45",
            fact_type="dialogue",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.diagnostic["context_type"] == "CHARACTER_DIALOGUE"

    def test_allow_chinese_realistic_business_financing(self, urban_engine):
        """都市世界真实公司融资及股权调整：ALLOW"""
        fact = NarrativeFact(
            fact_id="zh-urban-004",
            description="经过三轮谈判，公司完成了A轮融资，投资方获得了20%的股权",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-8:line-123",
            fact_type="business_event",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.rule_id == "urban.business.realistic:realistic-mechanics"

    def test_review_required_chinese_ambiguous_ability(self, urban_engine):
        """机制未知、事实来源不可信或证据不足：REVIEW_REQUIRED"""
        fact = NarrativeFact(
            fact_id="zh-urban-005",
            description="张三拥有某种特殊的能力",
            context_type=FactContextType.UNKNOWN,
            source_evidence="chapter-4:line-90",
            fact_type="character_ability",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REVIEW_REQUIRED
        assert judgment.diagnostic["reason"] == "unknown_context"


class TestChineseFantasyEasternJudgment:
    """Chinese fantasy eastern novel judgment scenarios."""

    def test_allow_chinese_cultivation_in_fantasy(self, fantasy_engine):
        """玄幻世界合法境界修炼：不得误拒绝"""
        fact = NarrativeFact(
            fact_id="zh-fantasy-001",
            description="经过三个月闭关修炼，林峰终于突破到了金丹期",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-10:line-200",
            fact_type="character_progression",
        )

        judgment = fantasy_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert "cultivation" in judgment.rule_id or "fantasy" in judgment.rule_id

    def test_allow_chinese_merchant_guild_trade(self, fantasy_engine):
        """玄幻世界商会交易：不得误拒绝"""
        fact = NarrativeFact(
            fact_id="zh-fantasy-002",
            description="天宝商会在拍卖会上以五百万灵石的价格拍下了这把仙剑",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-7:line-156",
            fact_type="business_event",
        )

        judgment = fantasy_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW

    def test_reject_chinese_modern_corporate_in_fantasy(self, fantasy_engine):
        """玄幻世界确定引入未声明的现代公司股权机制：REJECT"""
        fact = NarrativeFact(
            fact_id="zh-fantasy-003",
            description="宗门建立了现代股份制公司，长老会成为董事会，发行股票融资",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-12:line-234",
            fact_type="world_mechanism",
        )

        judgment = fantasy_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert (
            "modern" in judgment.rationale.lower()
            or "corporate" in judgment.rationale.lower()
        )
        assert judgment.conflicting_mechanics is not None

    def test_allow_chinese_sect_competition(self, fantasy_engine):
        """玄幻世界宗门竞争与资源争夺：ALLOW"""
        fact = NarrativeFact(
            fact_id="zh-fantasy-004",
            description="青云宗与天剑门为了争夺灵脉资源，在边境发生了激烈冲突",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-15:line-300",
            fact_type="faction_conflict",
        )

        judgment = fantasy_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW

    def test_chinese_cross_genre_pollution_detection(
        self, urban_engine, fantasy_engine
    ):
        """验证中文场景下的跨题材污染检测"""
        # Urban world: reject cultivation ability
        urban_cultivation = NarrativeFact(
            fact_id="zh-cross-001",
            description="主角发现自己可以修炼内功，打通了任督二脉",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-1:line-50",
            fact_type="character_ability",
        )

        # Fantasy world: allow cultivation
        fantasy_cultivation = NarrativeFact(
            fact_id="zh-cross-002",
            description="主角发现自己可以修炼内功，打通了任督二脉",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-1:line-50",
            fact_type="character_ability",
        )

        urban_judgment = urban_engine.judge_fact(urban_cultivation)
        fantasy_judgment = fantasy_engine.judge_fact(fantasy_cultivation)

        # Same content, different verdicts based on Pack
        assert urban_judgment.verdict == PolicyVerdict.REJECT
        assert fantasy_judgment.verdict == PolicyVerdict.ALLOW


class TestMixedMechanicsConflictDetection:
    """Test that conflicts are detected even when mixed with legitimate content."""

    def test_fantasy_commerce_with_stock_trading_rejected(self, fantasy_engine):
        """Fantasy commerce + modern stock mechanisms must reject the conflict."""
        fact = NarrativeFact(
            fact_id="mixed-001",
            description="青云商会以灵石结算股票交易，并设立现代股东大会",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-10:line-200",
            fact_type="world_mechanism",
        )

        judgment = fantasy_engine.judge_fact(fact)

        # Must REJECT due to modern corporate mechanisms, not ALLOW due to commerce context
        assert judgment.verdict == PolicyVerdict.REJECT
        assert "stock" in judgment.rationale.lower() or "股票" in judgment.rationale

    def test_fantasy_legitimate_spirit_stone_trade_allowed(self, fantasy_engine):
        """Pure fantasy commerce without modern mechanisms should be allowed."""
        fact = NarrativeFact(
            fact_id="mixed-002",
            description="青云商会以灵石结算灵药交易",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-10:line-100",
            fact_type="business_event",
        )

        judgment = fantasy_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW

    def test_urban_systematic_upgrade_with_game_system_rejected(self, urban_engine):
        """Legitimate business term + game system must reject the game system."""
        fact = NarrativeFact(
            fact_id="mixed-003",
            description="公司完成系统性数字化升级后，主角开启游戏系统，获得超自然属性面板",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-5:line-100",
            fact_type="world_mechanism",
        )

        judgment = urban_engine.judge_fact(fact)

        # Must REJECT due to game system, despite "系统性" being present
        assert judgment.verdict == PolicyVerdict.REJECT
        assert (
            "game system" in judgment.rationale.lower()
            or "游戏系统" in judgment.rationale
        )

    def test_urban_pure_systematic_upgrade_allowed(self, urban_engine):
        """Pure business digitization without game mechanics should be allowed."""
        fact = NarrativeFact(
            fact_id="mixed-004",
            description="公司完成系统性数字化升级",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-5:line-50",
            fact_type="business_event",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW


class TestUnknownMechanismHandling:
    """Test that unknown mechanisms do not auto-ALLOW."""

    def test_confirmed_mechanism_without_source_requires_review(self, urban_engine):
        """Confirmed mechanism lacking source cannot be verified."""
        fact = NarrativeFact(
            fact_id="unknown-mech-001",
            description="Character exhibits unusual behavior",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-3:line-50",
            fact_type="character_ability",
            mechanism_type="unverified_ability",
            mechanism_confirmed=True,
            mechanism_source=None,  # Missing source
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REVIEW_REQUIRED
        assert judgment.diagnostic["reason"] == "missing_mechanism_source"

    def test_unknown_mechanism_type_requires_review(self, urban_engine):
        """Unknown mechanism_type cannot be verified against Pack rules."""
        fact = NarrativeFact(
            fact_id="unknown-mech-002",
            description="Character uses quantum entanglement abilities",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-4:line-80",
            fact_type="character_ability",
            mechanism_type="quantum_mechanics",
            mechanism_confirmed=True,
            mechanism_source="chapter-4:verified",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.REVIEW_REQUIRED
        assert judgment.diagnostic["reason"] == "unknown_mechanism_type"

    def test_verified_realistic_mechanism_allowed(self, urban_engine):
        """Properly verified realistic mechanism is allowed."""
        fact = NarrativeFact(
            fact_id="unknown-mech-003",
            description="Character masters negotiation skills",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-5:line-100",
            fact_type="character_ability",
            mechanism_type="realistic_skill",
            mechanism_confirmed=True,
            mechanism_source="chapter-5:training-arc",
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.diagnostic["mechanism_type"] == "realistic_skill"


class TestStrategyMatchTypeDisambiguation:
    """Test that strategy results clearly distinguish match types."""

    def test_conflicting_strategy_rejected(self, urban_engine):
        """Conflicting strategy returns CONFLICT match type."""
        strategy = OptionalStrategy(
            strategy_id="strat-conflict",
            description="Introduce cultivation system",
            source="retrieval:template-123",
            proposed_mechanics={"cultivation": "qi_absorption"},
        )

        judgment = urban_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.REJECT
        assert judgment.diagnostic["match_type"] == "CONFLICT"
        assert judgment.pack_identity_preserved

    def test_compatible_strategy_verified(self, urban_engine):
        """Compatible strategy returns VERIFIED_COMPATIBLE match type."""
        strategy = OptionalStrategy(
            strategy_id="strat-compatible",
            description="Enhance business operations",
            source="retrieval:template-456",
            proposed_mechanics={"business_operations": "supply_chain_optimization"},
        )

        judgment = urban_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.diagnostic["match_type"] == "VERIFIED_COMPATIBLE"
        assert judgment.pack_identity_preserved

    def test_no_match_strategy_identified(self, urban_engine):
        """Strategy with no applicable mechanics returns NO_MATCH."""
        strategy = OptionalStrategy(
            strategy_id="strat-no-match",
            description="Unrelated narrative device",
            source="retrieval:template-789",
            proposed_mechanics={},  # No mechanics
        )

        judgment = urban_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.diagnostic["match_type"] == "NO_MATCH"
        assert judgment.pack_identity_preserved

    def test_unknown_mechanics_flagged(self, urban_engine):
        """Strategy with unknown mechanics returns UNKNOWN match type."""
        strategy = OptionalStrategy(
            strategy_id="strat-unknown",
            description="Introduce alien technology",
            source="retrieval:template-999",
            proposed_mechanics={"alien_tech": "faster_than_light"},
        )

        judgment = urban_engine.judge_optional_strategy(strategy)

        assert judgment.verdict == PolicyVerdict.ALLOW
        assert judgment.diagnostic["match_type"] == "UNKNOWN"
        assert judgment.pack_identity_preserved
        assert "unknown" in judgment.rationale.lower()


class TestErrorScenarioRegression:
    """Regression tests for previously identified semantic errors."""

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

        assert judgment.verdict != PolicyVerdict.REJECT, (
            f"Incorrectly rejected legitimate business term: {judgment.rationale}"
        )

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

        assert judgment.verdict != PolicyVerdict.REJECT, (
            f"Incorrectly rejected business metaphor: {judgment.rationale}"
        )

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

        assert judgment.verdict == PolicyVerdict.REJECT, (
            f"Failed to reject confirmed supernatural: {judgment.verdict}"
        )

    def test_unconfirmed_mechanism_requires_review(self, urban_engine):
        """Unconfirmed mechanisms must not auto-ALLOW."""
        fact = NarrativeFact(
            fact_id="error-b2",
            description="主角获得了特殊能力",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="test:line-4",
            fact_type="character_ability",
            metadata={},
        )

        judgment = urban_engine.judge_fact(fact)

        assert judgment.verdict != PolicyVerdict.ALLOW, (
            f"Incorrectly allowed unconfirmed mechanism: {judgment.rationale}"
        )

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

        assert judgment.verdict != PolicyVerdict.REJECT, (
            f"Incorrectly rejected fantasy commerce: {judgment.rationale}"
        )

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

        assert judgment.verdict == PolicyVerdict.REJECT, (
            f"Failed to reject modern corporate: {judgment.verdict}"
        )
