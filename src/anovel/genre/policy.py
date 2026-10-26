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
    """

    fact_id: str
    description: str
    context_type: FactContextType
    source_evidence: str
    fact_type: str
    metadata: dict[str, str] | None = None


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
        # Keywords suggesting supernatural abilities in reality (English + Chinese)
        supernatural_keywords = [
            # English
            "cultivat",  # matches cultivate, cultivation
            "spiritual energy",
            "qi",
            "breakthrough",
            "realm",
            "immortal",
            "magic",
            "spell",
            "enchant",
            "transmigrat",
            "reincarnate",
            "level up",
            # Chinese
            "修炼",
            "修仙",
            "灵气",
            "突破",
            "筑基",
            "金丹",
            "元婴",
            "化神",
            "境界",
            "仙",
            "内功",
            "任督二脉",
            "真气",
            "法术",
            "神通",
        ]

        fact_lower = fact.description.lower()

        # Check for supernatural ability claims
        for keyword in supernatural_keywords:
            if (
                keyword in fact_lower or keyword in fact.description
            ):  # Check both cases for Chinese
                # Check if this is about ability/mechanism vs just terminology
                ability_indicators = [
                    # English
                    "can",
                    "able to",
                    "power",
                    "ability",
                    "skill",
                    "energy",
                    "channel",
                    "absorb",
                    "refine",
                    "breakthrough to",
                    # Chinese
                    "能够",
                    "可以",
                    "拥有",
                    "吸收",
                    "打通",
                    "发现自己",
                ]

                is_ability_claim = any(
                    indicator in fact_lower or indicator in fact.description
                    for indicator in ability_indicators
                )

                if is_ability_claim:
                    return PolicyJudgment(
                        verdict=PolicyVerdict.REJECT,
                        fact_id=fact.fact_id,
                        rule_id="urban.business.realistic:no-supernatural",
                        rationale=f"Urban reality does not permit actual supernatural abilities (found: {keyword})",
                        conflicting_mechanics=["world_mechanics.realistic_constraints"],
                        diagnostic={"keyword": keyword, "fact_type": fact.fact_type},
                    )

        # Check for system/status window mechanics (English + Chinese)
        system_keywords = [
            "status window",
            "system window",
            "game system",
            "状态窗口",
            "系统",
            "游戏系统",
        ]
        for keyword in system_keywords:
            if keyword in fact_lower or keyword in fact.description:
                return PolicyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    fact_id=fact.fact_id,
                    rule_id="urban.business.realistic:no-supernatural",
                    rationale=f"Urban reality does not permit game system mechanics (found: {keyword})",
                    conflicting_mechanics=["world_mechanics.realistic_constraints"],
                    diagnostic={"keyword": keyword, "fact_type": fact.fact_type},
                )

        # If semantic judgment is uncertain, require review
        # (This is where more sophisticated analysis would go in production)
        if fact.fact_type in ["character_ability", "world_mechanism"]:
            # Check if we have sufficient evidence to make definitive judgment
            # Exception: if metadata has certainty OR description contains clear realistic skill indicators
            has_certainty = fact.metadata and "certainty" in fact.metadata

            # Realistic skill indicators (learning, practice, mentorship)
            realistic_skill_indicators = [
                "practice",
                "mentorship",
                "learned",
                "studied",
                "trained",
                "mastered",
            ]
            has_realistic_context = any(
                indicator in fact_lower for indicator in realistic_skill_indicators
            )

            if not has_certainty and not has_realistic_context:
                return PolicyJudgment(
                    verdict=PolicyVerdict.REVIEW_REQUIRED,
                    fact_id=fact.fact_id,
                    rule_id=None,
                    rationale="Insufficient evidence to definitively judge world mechanics compliance",
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

        # Modern corporate mechanisms that conflict with fantasy setting (English + Chinese)
        modern_corporate_keywords = [
            # English
            "stock",
            "equity",
            "shareholder",
            "corporation",
            "board of directors",
            "quarterly earnings",
            "ipo",
            "venture capital",
            "startup funding",
            # Chinese
            "股份制",
            "股票",
            "股权",
            "董事会",
            "上市",
            "风险投资",
            "现代股份",
        ]

        # Check for undeclared modern corporate mechanisms
        for keyword in modern_corporate_keywords:
            if keyword in fact_lower or keyword in fact.description:
                return PolicyJudgment(
                    verdict=PolicyVerdict.REJECT,
                    fact_id=fact.fact_id,
                    rule_id="fantasy.eastern.progression:no-modern-corporate",
                    rationale=f"Fantasy eastern world does not include modern corporate mechanisms (found: {keyword})",
                    conflicting_mechanics=["world_mechanics.social_structure"],
                    diagnostic={"keyword": keyword, "fact_type": fact.fact_type},
                )

        # Cultivation/fantasy mechanics are allowed (English + Chinese)
        fantasy_keywords = [
            # English
            "cultivate",
            "cultivation",
            "spiritual energy",
            "qi",
            "breakthrough",
            "realm",
            "sect",
            "dao",
            "immortal",
            "nascent soul",
            # Chinese
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
        ]

        for keyword in fantasy_keywords:
            if keyword in fact_lower or keyword in fact.description:
                return PolicyJudgment(
                    verdict=PolicyVerdict.ALLOW,
                    fact_id=fact.fact_id,
                    rule_id="fantasy.eastern.progression:cultivation-mechanics",
                    rationale=f"Cultivation mechanics allowed in fantasy eastern Pack (found: {keyword})",
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
