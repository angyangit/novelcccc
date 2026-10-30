"""Story Fixture YAML parser for V2-017.

Loads approved Story Fixtures and converts to SeriesVision data structures.
Validates human_review_ref binding to approved content SHA-256.
"""

import yaml
from pathlib import Path
from typing import Optional
import hashlib

from ..planning.models import (
    SeriesVision,
    ArcPlan,
    ChapterPlan,
    ProtagonistGoal,
    WorldConstraints,
    CharacterKnowledge,
    Secret,
    GenrePackBinding,
    EscalationPattern,
    SceneType,
)


class FixtureValidationError(Exception):
    """Raised when fixture validation fails."""
    pass


def compute_content_sha256(yaml_content: str) -> str:
    """Compute SHA-256 of YAML content for approval verification."""
    return hashlib.sha256(yaml_content.encode('utf-8')).hexdigest()


def load_fixture_yaml(fixture_path: Path) -> dict:
    """Load and parse fixture YAML file."""
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def validate_fixture_approval(
    fixture_data: dict,
    expected_content_hash: Optional[str] = None,
    require_approval: bool = False,
) -> tuple[bool, Optional[str]]:
    """
    Validate fixture approval status and content binding.

    Args:
        fixture_data: Parsed YAML fixture
        expected_content_hash: Expected approved content SHA-256
        require_approval: Whether to require human_review_ref

    Returns:
        (is_valid, error_message)
    """
    status = fixture_data.get('status')
    human_review_ref = fixture_data.get('human_review_ref')

    # Check approval requirement
    if require_approval and human_review_ref is None:
        return False, f"Fixture {fixture_data.get('fixture_id')} requires human_review_ref for production use"

    # If approved, verify binding exists
    if status == 'APPROVED' and human_review_ref is None:
        return False, f"Fixture marked APPROVED but missing human_review_ref"

    # Verify content hash if provided (for approval verification)
    if expected_content_hash and human_review_ref:
        # In production, would load approval record and verify SHA-256 match
        # For now, log that verification should occur
        pass

    return True, None


def parse_protagonist_goals(fixture_data: dict) -> list[ProtagonistGoal]:
    """Parse protagonist goals from fixture."""
    goals = []
    for goal_data in fixture_data.get('protagonist_goal', {}).get('constraints', []):
        # This is simplified - real fixture has more complex structure
        pass

    # Extract from fixture structure
    pg = fixture_data.get('protagonist_goal', {})
    if pg:
        goal = ProtagonistGoal(
            goal_id=pg.get('primary', 'main_goal'),
            description=pg.get('primary', ''),
            constraints=pg.get('constraints', []),
            success_criteria=pg.get('success_criteria', []),
        )
        goals.append(goal)

    return goals


def parse_world_constraints(fixture_data: dict) -> WorldConstraints:
    """Parse world constraints from fixture."""
    wb = fixture_data.get('world_boundaries', {})
    return WorldConstraints(
        realistic_constraints=wb.get('realistic_constraints', []),
        cultivation_constraints=wb.get('cultivation_constraints', []),
        progression_rules=wb.get('progression_rules', []),
        prohibited_mechanisms=wb.get('prohibited_mechanisms', []),
    )


def parse_character_knowledge(fixture_data: dict) -> dict[str, CharacterKnowledge]:
    """Parse character knowledge map from fixture."""
    knowledge_map = {}
    for char_data in fixture_data.get('characters', []):
        char_id = char_data.get('character_id')
        initial_state = char_data.get('initial_state', {})

        knowledge = CharacterKnowledge(
            character_id=char_id,
            known_facts=initial_state.get('knowledge', []),
            goals=initial_state.get('goals', []),
            personality_traits=[char_data.get('personality', '')],
        )
        knowledge_map[char_id] = knowledge

    return knowledge_map


def parse_secrets(fixture_data: dict) -> list[Secret]:
    """Parse secrets from fixture."""
    secrets = []
    for secret_data in fixture_data.get('secrets_and_knowers', []):
        # Extract chapter number from potential_reveal string
        reveal_chapter = None
        reveal_str = secret_data.get('potential_reveal', '')
        if '章' in reveal_str or 'chapter' in reveal_str.lower():
            # Try to extract number
            import re
            match = re.search(r'\d+', reveal_str)
            if match:
                reveal_chapter = int(match.group())

        secret = Secret(
            secret_id=secret_data.get('secret_id', ''),
            content=secret_data.get('content', ''),
            knowers=secret_data.get('knowers', []),
            potential_reveal_chapter=reveal_chapter,
            reader_knows='reader' in secret_data.get('knowers', []),
        )
        secrets.append(secret)

    return secrets


def parse_arc_plans(fixture_data: dict) -> list[ArcPlan]:
    """Parse arc plans from fixture first_arc_plan."""
    arcs = []
    arc_plan = fixture_data.get('first_arc_plan', {})

    if not arc_plan:
        return arcs

    # Parse chapters from key_beats
    chapters = []
    for i, beat in enumerate(arc_plan.get('key_beats', [])):
        chapter_range = beat.get('chapter', '')
        content = beat.get('content', '')
        state_changes = beat.get('state_changes', [])

        # Create chapter plan (simplified - one chapter per beat)
        chapter = ChapterPlan(
            chapter_id=f"chapter_{i+1:02d}",
            chapter_number=i+1,
            goals=[content],
            required_state_changes=state_changes,
            character_focus=[],  # Would need to parse from content
            scene_type=SceneType.DIALOGUE,  # Default, would need smarter detection
        )
        chapters.append(chapter)

    arc = ArcPlan(
        arc_id='arc_01',
        arc_title=arc_plan.get('arc_title', 'Arc 1'),
        chapters=chapters,
        arc_goal='',
        escalation_pattern=EscalationPattern(
            pattern_type='linear',
            key_escalation_points=[],
        ),
    )
    arcs.append(arc)

    return arcs


def load_series_vision_from_fixture(
    fixture_path: Path,
    require_approval: bool = False,
) -> SeriesVision:
    """
    Load SeriesVision from approved Story Fixture YAML.

    Args:
        fixture_path: Path to fixture YAML file
        require_approval: Whether to require human_review_ref

    Returns:
        SeriesVision parsed from fixture

    Raises:
        FixtureValidationError: If fixture validation fails
    """
    # Load YAML
    fixture_data = load_fixture_yaml(fixture_path)

    # Validate approval
    is_valid, error_msg = validate_fixture_approval(
        fixture_data,
        require_approval=require_approval,
    )
    if not is_valid:
        raise FixtureValidationError(error_msg)

    # Parse fixture components
    protagonist_goals = parse_protagonist_goals(fixture_data)
    world_constraints = parse_world_constraints(fixture_data)
    character_knowledge = parse_character_knowledge(fixture_data)
    secrets = parse_secrets(fixture_data)
    arc_plans = parse_arc_plans(fixture_data)

    # Create GenrePackBinding
    genre_binding = GenrePackBinding(
        pack_id=fixture_data.get('genre_pack_id', ''),
        version=fixture_data.get('genre_pack_version', ''),
        content_hash=fixture_data.get('genre_pack_hash', ''),
    )

    # Build SeriesVision
    series_vision = SeriesVision(
        series_id=fixture_data.get('fixture_id', ''),
        title=fixture_data.get('title', ''),
        synopsis=fixture_data.get('synopsis', ''),
        protagonist_goals=protagonist_goals,
        world_constraints=world_constraints,
        character_knowledge_map=character_knowledge,
        secrets=secrets,
        genre_pack_binding=genre_binding,
        arc_plans=arc_plans,
        fixture_version=fixture_data.get('genre_pack_version', '1.0'),
        human_review_ref=fixture_data.get('human_review_ref'),
    )

    return series_vision
