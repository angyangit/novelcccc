"""
Genre Hard Policy Engine.

Implements V2-014 world rule judgment for structured narrative candidates.
Distinguishes real world facts from dialogue, dreams, metaphors, and speculation.
Returns explicit verdicts: ALLOW, REJECT, REVIEW_REQUIRED.

Core responsibilities:
- Judge whether narrative facts violate frozen Pack world mechanics
- Distinguish actual world events from character dialogue, dreams, novel references
- Enforce anchor boundaries (urban.business.realistic vs fantasy.eastern.progression)
- Reject optional strategies that conflict with frozen world mechanics
- Return structured, traceable verdicts with rule provenance

Out of scope:
- Does NOT issue CommitPermits (CanonCommitService responsibility)
- Does NOT write to Canon directly
- Does NOT replace Q2 quality gates
- Does NOT implement general semantic understanding of free text
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from anovel.genre.identity import GenrePackIdentity
from anovel.genre.registry import GenrePackRegistry

# --- Verdict Types ---


class PolicyVerdict(StrEnum):
    """Policy judgment verdict."""

    ALLOW = "ALLOW"
    REJECT = "REJECT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class FactContextType(StrEnum):
    """Type of narrative context for a fact claim."""

    WORLD_FACT = "WORLD_FACT"  # Actual event in story world
    CHARACTER_DIALOGUE = "CHARACTER_DIALOGUE"  # What a character says
    CHARACTER_THOUGHT = "CHARACTER_THOUGHT"  # What a character thinks/believes
    DREAM_SEQUENCE = "DREAM_SEQUENCE"  # Dream or vision
    NOVEL_REFERENCE = "NOVEL_REFERENCE"  # Character reading/discussing fiction
    METAPHOR = "METAPHOR"  # Figurative language
    SPECULATION = "SPECULATION"  # Hypothesis, rumor, unconfirmed claim
    UNKNOWN = "UNKNOWN"  # Context cannot be determined


# --- Input Structures ---


@dataclass(frozen=True)
class NarrativeFact:
    """
    Structured narrative fact for policy judgment.

    Attributes:
        fact_id: Unique identifier for this fact claim
        description: Human-readable fact description
        context_type: Narrative context (world fact, dialogue, dream, etc.)
        source_evidence: Where this fact comes from (chapter_id, line_range, etc.)
        fact_type: Category of fact (character_ability, world_mechanism, etc.)
        metadata: Additional context (character_id, belief_holder, etc.)
        mechanism_type: Optional explicit mechanism declaration (e.g., "supernatural_cultivation", "realistic_business")
        mechanism_confirmed: Whether mechanism is explicitly confirmed in source (not inference)
        mechanism_source: Evidence source for mechanism claim (if mechanism_type provided)
    """

    fact_id: str
    description: str
    context_type: FactContextType
    source_evidence: str
    fact_type: str
    metadata: dict[str, str] | None = None
    mechanism_type: str | None = None
    mechanism_confirmed: bool = False
    mechanism_source: str | None = None


@dataclass(frozen=True)
class OptionalStrategy:
    """
    Optional narrative strategy to be evaluated against frozen Pack mechanics.

    Attributes:
        strategy_id: Unique identifier
        description: What the strategy proposes
        source: Where this strategy comes from (retrieval, template, etc.)
        proposed_mechanics: World mechanics changes this would introduce
    """

    strategy_id: str
    description: str
    source: str
    proposed_mechanics: dict[str, str]


# --- Output Structures ---


@dataclass(frozen=True)
class PolicyJudgment:
    """
    Structured policy judgment result.

    Attributes:
        verdict: ALLOW, REJECT, or REVIEW_REQUIRED
        fact_id: Reference to judged fact
        rule_id: Which Pack rule was applied (or None if review needed)
        rationale: Human-readable explanation
        conflicting_mechanics: What world mechanics would be violated (if REJECT)
        diagnostic: Additional structured diagnostic information
    """

    verdict: PolicyVerdict
    fact_id: str
    rule_id: str | None
    rationale: str
    conflicting_mechanics: list[str] | None = None
    diagnostic: dict[str, str] | None = None


@dataclass(frozen=True)
class StrategyJudgment:
    """
    Judgment on optional narrative strategy.

    Attributes:
        verdict: ALLOW or REJECT (strategies requiring review are rejected)
        strategy_id: Reference to judged strategy
        rule_id: Which Pack rule was applied
        rationale: Why strategy is allowed or conflicts
        pack_identity_preserved: Whether Pack identity remains unchanged
    """

    verdict: Literal[PolicyVerdict.ALLOW, PolicyVerdict.REJECT]
    strategy_id: str
    rule_id: str | None
    rationale: str
    pack_identity_preserved: bool


# --- Policy Engine ---


class GenreHardPolicyEngine:
    """
    Genre Hard Policy Engine for world rule enforcement.

    Evaluates narrative facts and optional strategies against frozen
    GenrePack world mechanics. Returns explicit, traceable verdicts.

    Usage:
        registry = GenrePackRegistry.from_yaml("specs/genres/registry.yaml")
        pack_identity = GenrePackIdentity("urban.business.realistic", "1.0.0", hash)
        engine = GenreHardPolicyEngine(registry, pack_identity)

        fact = NarrativeFact(
            fact_id="fact-001",
            description="Character cultivates spiritual energy",
            context_type=FactContextType.WORLD_FACT,
            source_evidence="chapter-3:line-45",
            fact_type="character_ability"
        )
        judgment = engine.judge_fact(fact)
    """

    def __init__(self, registry: GenrePackRegistry, pack_identity: GenrePackIdentity):
        """
        Initialize policy engine with Pack identity.

        Args:
            registry: GenrePackRegistry for loading Pack metadata
            pack_identity: Frozen Pack identity (id, version, content_hash)

        Raises:
            GenrePackRegistryError: If Pack cannot be loaded or verified
        """
        self.registry = registry
        self.pack_identity = pack_identity

        # Load Pack metadata
        self.pack_metadata = registry.get_pack(
            pack_identity.pack_id,
            pack_identity.version,
            pack_identity.content_hash,
        )

        # Extract pack_id for rule routing
        self.pack_id = pack_identity.pack_id

    def judge_fact(self, fact: NarrativeFact) -> PolicyJudgment:
        """
        Judge whether a narrative fact violates frozen Pack world mechanics.

        Args:
            fact: Structured narrative fact with context

        Returns:
            PolicyJudgment with verdict, rule_id, and rationale
        """
        # UNKNOWN context requires review (check this BEFORE other context checks)
        if fact.context_type == FactContextType.UNKNOWN:
            return PolicyJudgment(
                verdict=PolicyVerdict.REVIEW_REQUIRED,
                fact_id=fact.fact_id,
                rule_id=None,
                rationale="Cannot determine if fact is actual world event or narrative context",
                diagnostic={"reason": "unknown_context"},
            )

        # Non-world-fact contexts are generally allowed
        # (dialogue, dreams, metaphors don't change world mechanics)
        if fact.context_type != FactContextType.WORLD_FACT:
            return PolicyJudgment(
                verdict=PolicyVerdict.ALLOW,
                fact_id=fact.fact_id,
                rule_id=f"{self.pack_id}:context-boundary",
                rationale=f"Context type {fact.context_type.value} does not establish world facts",
                diagnostic={"context_type": fact.context_type.value},
            )

        # Route to Pack-specific world mechanics enforcement
        if self.pack_id == "urban.business.realistic":
            return self._judge_urban_reality(fact)
        elif self.pack_id == "fantasy.eastern.progression":
            return self._judge_fantasy_eastern(fact)
        else:
            # Unknown Pack - should not happen if registry is correct
            return PolicyJudgment(
                verdict=PolicyVerdict.REVIEW_REQUIRED,
                fact_id=fact.fact_id,
                rule_id=None,
                rationale=f"Unknown Pack ID: {self.pack_id}",
                diagnostic={"reason": "unknown_pack"},
            )

    def _judge_urban_reality(self, fact: NarrativeFact) -> PolicyJudgment:
        """
        Judge fact against urban.business.realistic world mechanics.

        Urban reality anchor: strict real-world mechanics, no supernatural abilities.
        """
        fact_lower = fact.description.lower()

        # Step 1: Check explicit mechanism declarations first
        if fact.mechanism_type and fact.mechanism_confirmed:
            if fact.mechanism_type in [
                "supernatural_cultivation",
                "supernatural_ability",
                "game_system",
                "transmigration",
                "reincarnation",
                "magic_system",
            ]:
                return PolicyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    fact_id=fact.fact_id,
                    rule_id="urban.business.realistic:no-supernatural",
                    rationale=f"Urban reality does not permit confirmed {fact.mechanism_type}",
                    conflicting_mechanics=["world_mechanics.realistic_constraints"],
                    diagnostic={
                        "mechanism_type": fact.mechanism_type,
                        "mechanism_source": fact.mechanism_source or "unknown",
                    },
                )
            elif fact.mechanism_type in ["realistic_business", "realistic_skill"]:
                return PolicyJudgment(
                    verdict=PolicyVerdict.ALLOW,
                    fact_id=fact.fact_id,
                    rule_id="urban.business.realistic:realistic-mechanics",
                    rationale=f"Confirmed {fact.mechanism_type} consistent with urban reality",
                    diagnostic={"mechanism_type": fact.mechanism_type},
                )

        # Step 2: Check for explicit supernatural language (confirmed even without mechanism_type)
        confirmed_supernatural_phrases = [
            "修炼成仙",
            "获得了超自然能力",
            "获得超自然能力",
            "cultivate to immortal",
            "gained supernatural",
            "acquired supernatural",
            "possess supernatural",
        ]
        for phrase in confirmed_supernatural_phrases:
            if phrase in fact.description or phrase in fact_lower:
                return PolicyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    fact_id=fact.fact_id,
                    rule_id="urban.business.realistic:no-supernatural",
                    rationale=f"Urban reality does not permit confirmed supernatural abilities (found: {phrase})",
                    conflicting_mechanics=["world_mechanics.realistic_constraints"],
                    diagnostic={
                        "confirmed_phrase": phrase,
                        "fact_type": fact.fact_type,
                    },
                )

        # Step 3: Context-aware keyword filtering (keywords as auxiliary hints only)
        # Check for strong cultivation indicators first (these override business context)

        strong_cultivation_keywords = [
            "修炼",
            "修仙",
            "灵气",
            "筑基",
            "金丹",
            "元婴",
            "化神",
            "内功",
            "任督二脉",
            "真气",
            "法术",
            "神通",
            "cultivat",
            "spiritual energy",
            "foundation establishment",
            "golden core",
            "nascent soul",
            "qi",  # Added standalone qi
        ]

        ability_indicators = [
            "能够",
            "可以",
            "能够吸收",
            "可以吸收",
            "吸收灵气",
            "吸收 qi",
            "打通任督",
            "发现自己可以",
            "can cultivate",
            "can sense",
            "can absorb",
            "absorb qi",
            "absorbing qi",
            "achieved breakthrough",
            "sense qi",
            "channel",
            "possess",
            "possessed",
        ]

        # Check for cultivation + ability claim combination
        found_cultivation = any(
            kw in fact.description or kw in fact_lower
            for kw in strong_cultivation_keywords
        )
        found_ability = any(
            ind in fact.description or ind in fact_lower for ind in ability_indicators
        )

        if found_cultivation and found_ability:
            return PolicyJudgment(
                verdict=PolicyVerdict.REJECT,
                fact_id=fact.fact_id,
                rule_id="urban.business.realistic:no-supernatural",
                rationale="Urban reality does not permit supernatural cultivation abilities",
                conflicting_mechanics=["world_mechanics.realistic_constraints"],
                diagnostic={
                    "detection_method": "keyword_hint",
                    "fact_type": fact.fact_type,
                },
            )

        # Business-specific false positive filtering
        # Only filter "突破" in business metaphor context, not general cultivation
        business_metaphor_patterns = [
            ("突破", ["销售瓶颈", "业绩", "市场"]),
            ("系统", ["系统性", "数字化升级"]),
        ]

        for keyword, business_indicators in business_metaphor_patterns:
            if keyword in fact.description:
                # Check if this is business metaphor usage
                is_business_metaphor = any(
                    bi in fact.description for bi in business_indicators
                )
                if is_business_metaphor:
                    # This is a false positive - business metaphor, not cultivation
                    continue  # Don't reject

        # Check for game system mechanics (avoid false positive from "系统性")
        game_system_phrases = [
            "状态窗口",
            "游戏系统",
            "status window",
            "game system",
            "system window",
        ]
        # Only reject if it's game system, not "系统性" business term
        if "系统性" not in fact.description:
            for phrase in game_system_phrases:
                if phrase in fact.description or phrase in fact_lower:
                    return PolicyJudgment(
                        verdict=PolicyVerdict.REJECT,
                        fact_id=fact.fact_id,
                        rule_id="urban.business.realistic:no-supernatural",
                        rationale=f"Urban reality does not permit game system mechanics (found: {phrase})",
                        conflicting_mechanics=["world_mechanics.realistic_constraints"],
                        diagnostic={"keyword": phrase, "fact_type": fact.fact_type},
                    )

        # Step 4: Handle ambiguous ability claims - require review instead of auto-allow
        if fact.fact_type in ["character_ability", "world_mechanism"]:
            # If mechanism is explicitly unconfirmed or no mechanism declaration at all
            if not fact.mechanism_confirmed:
                # Check for ambiguous ability language (including English "unusual abilities")
                ambiguous_ability_indicators = [
                    "特殊能力",
                    "获得了能力",
                    "unusual abilit",
                    "special ability",
                    "gained ability",
                    "acquired power",
                    "possessed",
                ]
                has_ambiguous_ability = any(
                    indicator in fact.description or indicator in fact_lower
                    for indicator in ambiguous_ability_indicators
                )

                if has_ambiguous_ability:
                    return PolicyJudgment(
                        verdict=PolicyVerdict.REVIEW_REQUIRED,
                        fact_id=fact.fact_id,
                        rule_id=None,
                        rationale="Insufficient evidence to definitively judge mechanism compliance",
                        diagnostic={
                            "reason": "semantic_uncertainty",
                            "fact_type": fact.fact_type,
                        },
                    )

        # Default: allow realistic urban/business facts
        return PolicyJudgment(
            verdict=PolicyVerdict.ALLOW,
            fact_id=fact.fact_id,
            rule_id="urban.business.realistic:realistic-mechanics",
            rationale="Fact consistent with realistic urban business world mechanics",
        )

    def _judge_fantasy_eastern(self, fact: NarrativeFact) -> PolicyJudgment:
        """
        Judge fact against fantasy.eastern.progression world mechanics.

        Fantasy eastern anchor: allows cultivation, sects, realms per declared mechanics.
        """
        fact_lower = fact.description.lower()

        # Step 1: Check explicit mechanism declarations first
        if fact.mechanism_type and fact.mechanism_confirmed:
            if fact.mechanism_type in [
                "modern_corporate",
                "modern_finance",
                "stock_market",
                "venture_capital",
            ]:
                return PolicyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    fact_id=fact.fact_id,
                    rule_id="fantasy.eastern.progression:no-modern-corporate",
                    rationale=f"Fantasy eastern world does not permit confirmed {fact.mechanism_type}",
                    conflicting_mechanics=["world_mechanics.social_structure"],
                    diagnostic={
                        "mechanism_type": fact.mechanism_type,
                        "mechanism_source": fact.mechanism_source or "unknown",
                    },
                )
            elif fact.mechanism_type in [
                "cultivation_system",
                "fantasy_commerce",
                "sect_organization",
            ]:
                return PolicyJudgment(
                    verdict=PolicyVerdict.ALLOW,
                    fact_id=fact.fact_id,
                    rule_id="fantasy.eastern.progression:cultivation-mechanics",
                    rationale=f"Confirmed {fact.mechanism_type} consistent with fantasy eastern world",
                    diagnostic={"mechanism_type": fact.mechanism_type},
                )

        # Step 2: Check for confirmed modern corporate mechanisms
        confirmed_modern_corporate = [
            "现代股份制公司",
            "发行股票",
            "建立董事会",
            "成为董事会",
            "风险投资",
            "venture capital",
            "modern corporation",
            "stock issuance",
            "board of directors",
        ]
        for phrase in confirmed_modern_corporate:
            if phrase in fact.description or phrase in fact_lower:
                return PolicyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    fact_id=fact.fact_id,
                    rule_id="fantasy.eastern.progression:no-modern-corporate",
                    rationale=f"Fantasy eastern world does not permit modern corporate mechanisms (found: {phrase})",
                    conflicting_mechanics=["world_mechanics.social_structure"],
                    diagnostic={
                        "confirmed_phrase": phrase,
                        "fact_type": fact.fact_type,
                    },
                )

        # Step 3: Context-aware keyword filtering
        # Fantasy commerce context (legitimate trade) vs modern corporate context

        fantasy_commerce_context = [
            "商会",
            "拍卖",
            "售卖",
            "交易",
            "灵石",
            "灵药",
            "仙剑",
            "法宝",
            "merchant guild",
            "auction",
            "trade",
            "spiritual stone",
        ]
        has_fantasy_commerce = any(
            indicator in fact.description or indicator in fact_lower
            for indicator in fantasy_commerce_context
        )

        # If it's fantasy commerce (e.g., "灵药上市售卖"), don't reject as modern IPO
        # "上市" in fantasy context means "put on market/listing for sale", not stock IPO
        if has_fantasy_commerce:
            # Allow fantasy commerce - "上市" here means marketplace listing
            return PolicyJudgment(
                verdict=PolicyVerdict.ALLOW,
                fact_id=fact.fact_id,
                rule_id="fantasy.eastern.progression:fantasy-commerce",
                rationale="Fantasy commerce and trade allowed in fantasy eastern Pack",
                diagnostic={"context": "fantasy_commerce"},
            )

        # Modern corporate keywords (only check if NOT fantasy commerce context)
        modern_corporate_keywords = [
            "股份制",
            "股票",
            "董事会",
            "风险投资",
            "现代公司",
            "stock",
            "shareholder",
            "corporation",
            "board of directors",
            "venture capital",
            "ipo",
            "equity",  # Added equity as modern corporate keyword
        ]

        for keyword in modern_corporate_keywords:
            if keyword in fact_lower or keyword in fact.description:
                return PolicyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    fact_id=fact.fact_id,
                    rule_id="fantasy.eastern.progression:no-modern-corporate",
                    rationale=f"Fantasy eastern world does not permit modern corporate mechanisms (found: {keyword})",
                    conflicting_mechanics=["world_mechanics.social_structure"],
                    diagnostic={"keyword": keyword, "fact_type": fact.fact_type},
                )

        # Step 4: Allow cultivation/fantasy mechanics
        fantasy_keywords = [
            "修炼",
            "修仙",
            "灵气",
            "突破",
            "境界",
            "宗门",
            "道",
            "仙",
            "金丹",
            "元婴",
            "闭关",
            "cultivate",
            "cultivation",
            "spiritual energy",
            "qi",
            "breakthrough",
            "realm",
            "sect",
            "dao",
            "immortal",
        ]

        for keyword in fantasy_keywords:
            if keyword in fact_lower or keyword in fact.description:
                return PolicyJudgment(
                    verdict=PolicyVerdict.ALLOW,
                    fact_id=fact.fact_id,
                    rule_id="fantasy.eastern.progression:cultivation-mechanics",
                    rationale="Cultivation mechanics allowed in fantasy eastern Pack",
                    diagnostic={"keyword": keyword},
                )

        # Default: allow if consistent with fantasy world
        return PolicyJudgment(
            verdict=PolicyVerdict.ALLOW,
            fact_id=fact.fact_id,
            rule_id="fantasy.eastern.progression:fantasy-mechanics",
            rationale="Fact consistent with fantasy eastern world mechanics",
        )

    def judge_optional_strategy(self, strategy: OptionalStrategy) -> StrategyJudgment:
        """
        Judge whether an optional narrative strategy conflicts with frozen Pack mechanics.

        If strategy has no match, Pack identity is preserved (no automatic fallback).
        If strategy conflicts with world mechanics, it is rejected.

        Args:
            strategy: Optional narrative strategy to evaluate

        Returns:
            StrategyJudgment with verdict and Pack identity preservation status
        """
        # Check if strategy proposes mechanics that conflict with Pack
        if self.pack_id == "urban.business.realistic":
            # Reject strategies introducing supernatural mechanics
            if any(
                key in strategy.proposed_mechanics
                for key in ["cultivation", "magic_system", "supernatural_abilities"]
            ):
                return StrategyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    strategy_id=strategy.strategy_id,
                    rule_id="urban.business.realistic:no-supernatural-strategies",
                    rationale="Strategy introduces supernatural mechanics conflicting with realistic world",
                    pack_identity_preserved=True,
                )

        elif self.pack_id == "fantasy.eastern.progression":
            # Reject strategies introducing modern corporate mechanics
            if any(
                key in strategy.proposed_mechanics
                for key in ["corporate_structure", "equity_system", "modern_finance"]
            ):
                return StrategyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    strategy_id=strategy.strategy_id,
                    rule_id="fantasy.eastern.progression:no-modern-corporate-strategies",
                    rationale="Strategy introduces modern corporate mechanics conflicting with fantasy world",
                    pack_identity_preserved=True,
                )

        # Strategy has no match or is compatible - Pack identity preserved
        return StrategyJudgment(
            verdict=PolicyVerdict.ALLOW,
            strategy_id=strategy.strategy_id,
            rule_id=f"{self.pack_id}:strategy-compatible",
            rationale="Strategy compatible with Pack mechanics or has no match (Pack identity preserved)",
            pack_identity_preserved=True,
        )
