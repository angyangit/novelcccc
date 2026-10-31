"""Planning models for V2-017 Contract Compiler.

Defines data structures for story planning: SeriesVision, ArcPlan, ChapterPlan.
These models represent human-authored planning intent, not execution state.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class SceneType(StrEnum):
    """Chapter scene classification."""

    ACTION = "action"
    DIALOGUE = "dialogue"
    REVELATION = "revelation"
    QUIET_RELATIONSHIP = "quiet_relationship"
    INTERNAL_CONFLICT = "internal_conflict"
    INVESTIGATION = "investigation"
    PREPARATION = "preparation"


@dataclass(frozen=True)
class GenrePackBinding:
    """Binds plan to specific GenrePack version."""

    pack_id: str
    version: str
    content_hash: str


@dataclass(frozen=True)
class ProtagonistGoal:
    """Protagonist's primary objective with constraints."""

    goal_id: str
    description: str
    constraints: list[str]
    success_criteria: list[str]
    timeline: str | None = None


@dataclass(frozen=True)
class WorldConstraints:
    """World rules that cannot be violated."""

    realistic_constraints: list[str] = field(default_factory=list)
    cultivation_constraints: list[str] = field(default_factory=list)
    progression_rules: list[str] = field(default_factory=list)
    prohibited_mechanisms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CharacterKnowledge:
    """What a character knows at story start."""

    character_id: str
    known_facts: list[str]
    goals: list[str]
    personality_traits: list[str]


@dataclass(frozen=True)
class Secret:
    """Information known only to specific characters."""

    secret_id: str
    content: str
    knowers: list[str]  # Character IDs who know
    potential_reveal_chapter: int | None = None
    reader_knows: bool = False


@dataclass(frozen=True)
class EscalationPattern:
    """How conflict intensifies across arc."""

    pattern_type: str  # "linear", "exponential", "crisis_driven"
    key_escalation_points: list[str]


@dataclass(frozen=True)
class ChapterPlan:
    """Single chapter planning intent."""

    chapter_id: str
    chapter_number: int
    goals: list[str]
    required_state_changes: list[str]
    character_focus: list[str]
    scene_type: SceneType
    content_description: str | None = None


@dataclass(frozen=True)
class ArcPlan:
    """Multi-chapter story arc."""

    arc_id: str
    arc_title: str
    chapters: list[ChapterPlan]
    arc_goal: str
    escalation_pattern: EscalationPattern


@dataclass(frozen=True)
class SeriesVision:
    """Top-level story plan from human input (Story Fixture)."""

    series_id: str
    title: str
    synopsis: str

    # Core planning elements
    protagonist_goals: list[ProtagonistGoal]
    world_constraints: WorldConstraints
    character_knowledge_map: dict[str, CharacterKnowledge]
    secrets: list[Secret]

    # Genre binding
    genre_pack_binding: GenrePackBinding

    # Story structure
    arc_plans: list[ArcPlan]

    # Metadata
    fixture_version: str
    human_review_ref: str | None = None
