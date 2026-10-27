"""
Eastern Fantasy Progression Extension (V2-016).

Implements world state tracking for fantasy.eastern.progression GenrePack.
Tracks cultivation realms, abilities, resources, costs, and faction relationships.

Core capabilities:
- Cultivation realm progression with preconditions
- Ability acquisition and usage constraints
- Cultivation resource tracking and consumption
- Breakthrough costs and requirements
- Faction/sect relationships
- Commerce and trade (allowed in fantasy world)

State types:
    CultivationRealm: Progression stage with advancement rules
    Ability: Character ability with source and constraints
    CultivationResource: Spirit stones, pills, materials with units
    BreakthroughAttempt: Realm advancement with preconditions and costs
    FactionAffiliation: Sect/organization membership

Contract: V2-016 Implementation per ADR-007
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from anovel.domain import EntityId


class RealmType(StrEnum):
    """Cultivation realm classification per Pack schema."""

    MORTAL = "mortal"
    SPIRITUAL = "spiritual"
    IMMORTAL = "immortal"
    DIVINE = "divine"


class CultivationLevel(StrEnum):
    """Cultivation stage per Pack schema."""

    QI_REFINING = "qi_refining"
    FOUNDATION_ESTABLISHMENT = "foundation_establishment"
    CORE_FORMATION = "core_formation"
    NASCENT_SOUL = "nascent_soul"
    SPIRIT_SEVERING = "spirit_severing"


class ResourceType(StrEnum):
    """Cultivation resource types."""

    SPIRITUAL_ENERGY = "spiritual_energy"
    SPIRIT_STONE = "spirit_stone"
    PILL = "pill"
    MATERIAL = "material"
    TECHNIQUE = "technique"


class FactionType(StrEnum):
    """Sect/faction affiliation per Pack schema."""

    RIGHTEOUS = "righteous"
    DEMONIC = "demonic"
    NEUTRAL = "neutral"
    INDEPENDENT = "independent"


# --- State Types ---


@dataclass(frozen=True)
class CultivationRealm:
    """
    Character cultivation realm state.

    Attributes:
        character_id: Character with this realm
        realm_type: Overall realm classification
        cultivation_level: Specific cultivation stage
        dao_comprehension: Dao understanding level (0-100)
        breakthrough_ready: Whether prerequisites met for next level
        achieved_at: Story time when reached this level
    """

    character_id: EntityId
    realm_type: RealmType
    cultivation_level: CultivationLevel
    dao_comprehension: int
    breakthrough_ready: bool
    achieved_at: str

    def __post_init__(self):
        if not (0 <= self.dao_comprehension <= 100):
            raise ValueError(
                f"Dao comprehension must be 0-100, got {self.dao_comprehension}"
            )


@dataclass(frozen=True)
class Ability:
    """
    Character ability or technique.

    Attributes:
        ability_id: Unique ability identifier
        character_id: Character possessing this ability
        name: Ability name
        ability_type: Category (technique, innate, learned)
        source: How ability was acquired
        usage_cost: Resource cost per use
        min_realm_required: Minimum cultivation level to use
        acquired_at: Story time of acquisition
    """

    ability_id: str
    character_id: EntityId
    name: str
    ability_type: str
    source: str
    usage_cost: dict[str, Decimal] | None
    min_realm_required: CultivationLevel | None
    acquired_at: str


@dataclass(frozen=True)
class CultivationResource:
    """
    Cultivation resources with explicit units.

    Attributes:
        resource_id: Unique resource pool identifier
        owner_id: Entity owning this resource
        resource_type: Type of cultivation resource
        amount: Quantity
        unit: Unit of measurement (low-grade spirit stones, pills, etc.)
        quality: Resource quality grade (low, medium, high, supreme)
        last_updated: Story time of last change
    """

    resource_id: str
    owner_id: EntityId
    resource_type: ResourceType
    amount: Decimal
    unit: str
    quality: str | None
    last_updated: str

    def __post_init__(self):
        if self.amount < Decimal("0"):
            raise ValueError(f"Resource amount cannot be negative: {self.amount}")


@dataclass(frozen=True)
class BreakthroughPrecondition:
    """
    Precondition for cultivation breakthrough.

    Attributes:
        condition_type: Type of precondition
        required_value: Value that must be satisfied
        actual_value: Current value (None if not evaluated)
        satisfied: Whether condition is met
    """

    condition_type: str
    required_value: str
    actual_value: str | None = None
    satisfied: bool = False


@dataclass(frozen=True)
class BreakthroughAttempt:
    """
    Cultivation realm advancement attempt.

    Attributes:
        attempt_id: Unique attempt identifier
        character_id: Character attempting breakthrough
        from_level: Current cultivation level
        to_level: Target cultivation level
        resource_costs: Resources consumed in attempt
        preconditions: Required conditions
        success_probability: Estimated success rate (if known)
        story_time: When attempt occurs
        evidence_ref: Source evidence in narrative
    """

    attempt_id: str
    character_id: EntityId
    from_level: CultivationLevel
    to_level: CultivationLevel
    resource_costs: dict[str, Decimal]
    preconditions: list[BreakthroughPrecondition]
    success_probability: Decimal | None
    story_time: str
    evidence_ref: str


@dataclass(frozen=True)
class FactionAffiliation:
    """
    Character sect or faction membership.

    Attributes:
        affiliation_id: Unique affiliation identifier
        character_id: Character with this affiliation
        faction_name: Name of sect/faction
        faction_type: Category of faction
        rank: Position within faction
        joined_at: Story time of joining
        status: Current membership status (active, expelled, retired)
    """

    affiliation_id: str
    character_id: EntityId
    faction_name: str
    faction_type: FactionType
    rank: str | None
    joined_at: str
    status: Literal["active", "expelled", "retired"]


# --- Validation Logic ---


class ProgressionStateValidator:
    """
    Validates cultivation progression and world rules.

    Enforces fantasy.eastern.progression anchor boundaries:
    - Cultivation realms with explicit progression rules
    - Resource costs for breakthroughs
    - Ability acquisition sources
    - Commerce allowed (spirit stones, merchant guilds)
    - Reject modern corporate/stock market mechanisms
    """

    # Defined progression order
    CULTIVATION_ORDER = [
        CultivationLevel.QI_REFINING,
        CultivationLevel.FOUNDATION_ESTABLISHMENT,
        CultivationLevel.CORE_FORMATION,
        CultivationLevel.NASCENT_SOUL,
        CultivationLevel.SPIRIT_SEVERING,
    ]

    @staticmethod
    def validate_realm_progression(
        current: CultivationLevel, target: CultivationLevel
    ) -> tuple[bool, str | None]:
        """
        Validate cultivation level progression is sequential.

        Args:
            current: Current cultivation level
            target: Target cultivation level

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            current_idx = ProgressionStateValidator.CULTIVATION_ORDER.index(current)
            target_idx = ProgressionStateValidator.CULTIVATION_ORDER.index(target)

            if target_idx == current_idx + 1:
                return True, None
            elif target_idx <= current_idx:
                return False, f"Cannot regress from {current} to {target}"
            else:
                return (
                    False,
                    f"Cannot skip levels from {current} to {target} (must progress sequentially)",
                )
        except ValueError as e:
            return False, f"Invalid cultivation level: {e}"

    @staticmethod
    def validate_breakthrough_preconditions(
        realm: CultivationRealm, target_level: CultivationLevel
    ) -> list[str]:
        """
        Validate preconditions for breakthrough attempt.

        Returns:
            List of unsatisfied preconditions (empty if all satisfied)
        """
        errors = []

        # Check sequential progression
        is_valid, error = ProgressionStateValidator.validate_realm_progression(
            realm.cultivation_level, target_level
        )
        if not is_valid:
            errors.append(error or "Invalid progression")

        # Check dao comprehension threshold (example: need 20+ for Foundation)
        if target_level == CultivationLevel.FOUNDATION_ESTABLISHMENT:
            if realm.dao_comprehension < 20:
                errors.append(
                    f"Dao comprehension {realm.dao_comprehension} < 20 required for Foundation Establishment"
                )

        return errors

    @staticmethod
    def validate_resource_sufficiency(
        resources: list[CultivationResource],
        required: dict[str, Decimal],
        owner_id: EntityId,
    ) -> tuple[bool, list[str]]:
        """
        Check if character has sufficient cultivation resources.

        Args:
            resources: Available resource pools
            required: Required amounts by resource type
            owner_id: Resource owner to check

        Returns:
            Tuple of (sufficient, list of shortfalls)
        """
        shortfalls = []

        for resource_type, required_amount in required.items():
            owner_pools = [
                r
                for r in resources
                if r.owner_id == owner_id and r.resource_type == resource_type
            ]

            total_available = sum(p.amount for p in owner_pools)

            if total_available < required_amount:
                shortfalls.append(
                    f"{resource_type}: have {total_available}, need {required_amount}"
                )

        return len(shortfalls) == 0, shortfalls

    @staticmethod
    def validate_ability_prerequisites(
        ability: Ability, current_realm: CultivationRealm
    ) -> tuple[bool, str | None]:
        """
        Validate character can use ability given current realm.

        Args:
            ability: Ability to validate
            current_realm: Character's current cultivation realm

        Returns:
            Tuple of (can_use, reason)
        """
        if ability.min_realm_required is None:
            return True, None

        try:
            required_idx = ProgressionStateValidator.CULTIVATION_ORDER.index(
                ability.min_realm_required
            )
            current_idx = ProgressionStateValidator.CULTIVATION_ORDER.index(
                current_realm.cultivation_level
            )

            if current_idx >= required_idx:
                return True, None
            else:
                return (
                    False,
                    f"Requires {ability.min_realm_required}, currently {current_realm.cultivation_level}",
                )
        except ValueError as e:
            return False, f"Invalid realm level: {e}"

    @staticmethod
    def allow_fantasy_commerce(description: str) -> bool:
        """
        Check if commerce description is valid in fantasy world.

        Fantasy worlds can have trade, merchant guilds, auctions, spirit stone exchange.
        Modern corporate structures (股份制公司, 股票市场) are NOT part of fantasy.eastern.progression.

        Args:
            description: Transaction or commerce description

        Returns:
            True if allowed fantasy commerce
        """
        # Modern corporate mechanisms (not in fantasy world)
        modern_corporate = [
            "股份制",
            "股票",
            "上市",
            "IPO",
            "证券",
            "securities",
            "股权激励",
            "stock option",
            "董事会",
            "board of directors",
        ]

        desc_lower = description.lower()

        has_modern = any(
            kw in description or kw in desc_lower for kw in modern_corporate
        )
        # Reject if modern corporate detected
        if has_modern:
            return False

        # Allow if fantasy commerce detected or no specific markers
        return True


# --- Public API ---

__all__ = [
    "RealmType",
    "CultivationLevel",
    "ResourceType",
    "FactionType",
    "CultivationRealm",
    "Ability",
    "CultivationResource",
    "BreakthroughPrecondition",
    "BreakthroughAttempt",
    "FactionAffiliation",
    "ProgressionStateValidator",
]
