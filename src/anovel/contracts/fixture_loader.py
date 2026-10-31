"""Story Fixture YAML parser for V2-017.

Loads approved Story Fixtures and converts to SeriesVision data structures.
Validates human_review_ref binding to approved content SHA-256.
"""

import hashlib
import re
from pathlib import Path

import yaml

from ..planning.models import (
    ArcPlan,
    ChapterPlan,
    CharacterKnowledge,
    EscalationPattern,
    GenrePackBinding,
    ProtagonistGoal,
    SceneType,
    Secret,
    SeriesVision,
    WorldConstraints,
)


class FixtureValidationError(Exception):
    """Raised when fixture validation fails."""

    pass


def compute_content_sha256(yaml_content: str) -> str:
    """Compute SHA-256 of YAML content for approval verification."""
    return hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()


def load_fixture_yaml(fixture_path: Path) -> dict:
    """Load and parse fixture YAML file."""
    with open(fixture_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_approval_record(approval_ref: str, fixture_base_path: Path) -> dict:
    """Load approval record YAML from reference path."""
    # approval_ref is a relative path from repo root (e.g., "specs/fixtures/reviews/...")
    # fixture_base_path is the fixture file path
    # We need to resolve relative to the repo root

    # Find repo root by looking for .git directory
    repo_root = fixture_base_path.resolve()
    while repo_root.parent != repo_root:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent
    else:
        # If no .git found, assume current working directory
        import os

        repo_root = Path(os.getcwd())

    approval_path = repo_root / approval_ref

    if not approval_path.exists():
        raise FixtureValidationError(f"Approval record not found: {approval_path}")

    with open(approval_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_fixture_approval(
    fixture_path: Path,
    fixture_data: dict,
    require_approval: bool = False,
) -> tuple[bool, str | None]:
    """
    Validate fixture approval status and content binding.

    Args:
        fixture_path: Path to fixture file (for computing hash)
        fixture_data: Parsed YAML fixture
        require_approval: Whether to require human_review_ref

    Returns:
        (is_valid, error_message)
    """
    status = fixture_data.get("status")
    human_review_ref = fixture_data.get("human_review_ref")
    fixture_id = fixture_data.get("fixture_id")

    # Check approval requirement
    if require_approval and human_review_ref is None:
        return (
            False,
            f"Fixture {fixture_id} requires human_review_ref for production use",
        )

    # If approved, verify binding exists
    if status == "APPROVED" and human_review_ref is None:
        return (
            False,
            f"Fixture {fixture_id} marked APPROVED but missing human_review_ref",
        )

    # If human_review_ref exists, verify SHA-256 binding
    if human_review_ref:
        try:
            approval_record = load_approval_record(human_review_ref, fixture_path)
        except Exception as e:
            return False, f"Failed to load approval record: {e}"

        # Find fixture in approval scope
        fixture_approval = None
        for item in approval_record.get("scope", []):
            if item.get("fixture_id") == fixture_id:
                fixture_approval = item
                break

        if not fixture_approval:
            return False, f"Fixture {fixture_id} not found in approval record scope"

        # Compute actual content hash
        with open(fixture_path, encoding="utf-8") as f:
            actual_content = f.read()
        actual_hash = compute_content_sha256(actual_content)

        # Verify against approved hash (with metadata)
        expected_hash = fixture_approval.get("with_approval_metadata_sha256")
        if actual_hash != expected_hash:
            return False, (
                f"Fixture {fixture_id} content hash mismatch: "
                f"expected {expected_hash}, got {actual_hash}"
            )

    return True, None


def parse_protagonist_goals(fixture_data: dict) -> list[ProtagonistGoal]:
    """Parse protagonist goals from fixture."""
    pg = fixture_data.get("protagonist_goal")
    if not pg:
        return []

    primary = pg.get("primary")
    if not primary:
        raise FixtureValidationError("protagonist_goal.primary is required but missing")

    goal = ProtagonistGoal(
        goal_id="primary_goal",
        description=primary,
        constraints=pg.get("constraints", []),
        success_criteria=pg.get("success_criteria", []),
    )
    return [goal]


def parse_world_constraints(fixture_data: dict) -> WorldConstraints:
    """Parse world constraints from fixture.

    Handles differences between urban (realistic_constraints) and
    fantasy (cultivation_constraints, progression_rules) fixtures.
    """
    wb = fixture_data.get("world_boundaries", {})

    return WorldConstraints(
        realistic_constraints=wb.get("realistic_constraints", []),
        cultivation_constraints=wb.get("cultivation_constraints", []),
        progression_rules=wb.get("progression_rules", []),
        prohibited_mechanisms=wb.get("prohibited_mechanisms", []),
    )


def parse_character_knowledge(fixture_data: dict) -> dict[str, CharacterKnowledge]:
    """Parse character knowledge map from fixture."""
    knowledge_map = {}
    for char_data in fixture_data.get("characters", []):
        char_id = char_data.get("character_id")
        initial_state = char_data.get("initial_state", {})

        knowledge = CharacterKnowledge(
            character_id=char_id,
            known_facts=initial_state.get("knowledge", []),
            goals=initial_state.get("goals", []),
            personality_traits=[char_data.get("personality", "")],
        )
        knowledge_map[char_id] = knowledge

    return knowledge_map


def parse_secrets(fixture_data: dict) -> list[Secret]:
    """Parse secrets from fixture."""
    secrets = []
    for secret_data in fixture_data.get("secrets_and_knowers", []):
        secret_id = secret_data.get("secret_id")
        if not secret_id:
            raise FixtureValidationError("secret_id is required for each secret")

        content = secret_data.get("content")
        if not content:
            raise FixtureValidationError(
                f"secret {secret_id} missing required 'content' field"
            )

        # Extract chapter number from potential_reveal string
        reveal_chapter = None
        reveal_str = secret_data.get("potential_reveal", "")
        if reveal_str:
            # Match "第N章" or "chapter N" patterns
            match = re.search(
                r"第(\d+)章|chapter[:\s]+(\d+)", reveal_str, re.IGNORECASE
            )
            if match:
                reveal_chapter = int(match.group(1) or match.group(2))

        knowers = secret_data.get("knowers", [])
        reader_knows = "reader" in knowers

        secret = Secret(
            secret_id=secret_id,
            content=content,
            knowers=knowers,
            potential_reveal_chapter=reveal_chapter,
            reader_knows=reader_knows,
        )
        secrets.append(secret)

    return secrets


def parse_arc_plans(fixture_data: dict) -> list[ArcPlan]:
    """Parse arc plans from fixture first_arc_plan.

    Extracts actual chapter ranges from key_beats instead of using list indices.

    Phase 3 limitation: Current fixture format only provides Beat-level state_changes,
    not chapter-specific assignments. To prevent resource over-consumption (e.g., cash
    dropping 3x instead of 1x), state_changes are assigned only to the last chapter
    of each beat range as a TEMPORARY PLACEHOLDER.

    This does NOT imply all changes happen in the last chapter - it's an artifact
    of the current fixture format lacking chapter-level allocation. Beat-level
    state_changes represent cumulative outcomes across the beat, not actions
    definitively occurring in the final chapter.

    Future fixture versions should support explicit chapter-level state change
    allocation or mark beat-level changes as "unallocated planning goals" rather
    than executable chapter requirements.
    """
    arcs: list[ArcPlan] = []
    arc_plan = fixture_data.get("first_arc_plan", {})

    if not arc_plan:
        return arcs

    # Parse chapters from key_beats
    chapters = []
    for beat in arc_plan.get("key_beats", []):
        chapter_range = beat.get("chapter", "")
        content = beat.get("content", "")
        state_changes = beat.get("state_changes", [])

        if not chapter_range:
            raise FixtureValidationError(f"key_beat missing 'chapter' field: {beat}")

        # Parse chapter range (e.g., "1-3", "4-7", "8-10")
        match = re.match(r"^(\d+)(?:-(\d+))?$", str(chapter_range))
        if not match:
            raise FixtureValidationError(
                f"Invalid chapter range format: '{chapter_range}'. Expected 'N' or 'N-M'"
            )

        start_chapter = int(match.group(1))
        end_chapter = int(match.group(2)) if match.group(2) else start_chapter

        # Create chapter plans for the range
        # TEMPORARY: Assign state_changes only to last chapter to prevent duplication.
        # This is a limitation of the current fixture format which doesn't support
        # chapter-level allocation. The last-chapter assignment is a placeholder to
        # avoid resource over-consumption, NOT a claim that changes occur there.
        for chapter_num in range(start_chapter, end_chapter + 1):
            is_last_in_beat = chapter_num == end_chapter

            chapter = ChapterPlan(
                chapter_id=f"chapter_{chapter_num:02d}",
                chapter_number=chapter_num,
                goals=[content],
                # Beat-level state_changes assigned to last chapter as temporary placeholder
                # to prevent duplication. Does NOT imply temporal semantics.
                required_state_changes=state_changes if is_last_in_beat else [],
                character_focus=[],  # Would need deeper parsing
                scene_type=SceneType.DIALOGUE,  # Default, would need smarter detection
            )
            chapters.append(chapter)

    arc = ArcPlan(
        arc_id="arc_01",
        arc_title=arc_plan.get("arc_title", "Arc 1"),
        chapters=chapters,
        arc_goal="",
        escalation_pattern=EscalationPattern(
            pattern_type="linear",
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

    # Validate required top-level fields
    fixture_id = fixture_data.get("fixture_id")
    if not fixture_id:
        raise FixtureValidationError("fixture_id is required but missing")

    title = fixture_data.get("title")
    if not title:
        raise FixtureValidationError(
            f"Fixture {fixture_id}: 'title' is required but missing"
        )

    # Validate approval
    is_valid, error_msg = validate_fixture_approval(
        fixture_path,
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
    genre_pack_id = fixture_data.get("genre_pack_id")
    genre_pack_version = fixture_data.get("genre_pack_version")
    genre_pack_hash = fixture_data.get("genre_pack_hash")

    if not genre_pack_id:
        raise FixtureValidationError(
            f"Fixture {fixture_id}: 'genre_pack_id' is required but missing"
        )
    if not genre_pack_hash:
        raise FixtureValidationError(
            f"Fixture {fixture_id}: 'genre_pack_hash' is required but missing"
        )

    genre_binding = GenrePackBinding(
        pack_id=genre_pack_id,
        version=genre_pack_version or "1.0.0",
        content_hash=genre_pack_hash,
    )

    # Build SeriesVision
    series_vision = SeriesVision(
        series_id=fixture_id,
        title=title,
        synopsis=fixture_data.get("synopsis", ""),
        protagonist_goals=protagonist_goals,
        world_constraints=world_constraints,
        character_knowledge_map=character_knowledge,
        secrets=secrets,
        genre_pack_binding=genre_binding,
        arc_plans=arc_plans,
        fixture_version=genre_pack_version or "1.0.0",
        human_review_ref=fixture_data.get("human_review_ref"),
    )

    return series_vision
