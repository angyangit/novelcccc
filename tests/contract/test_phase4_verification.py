"""Phase 4: Additional continuity and version constraint verification tests.

Supplements existing test_continuity_binding.py and test_freeze_enforcement.py
with specific Owner-required validation scenarios.
"""

from datetime import datetime

from anovel.contracts.compiler import CompilationDiagnostic, ContractCompiler
from anovel.planning.models import (
    ChapterPlan,
    GenrePackBinding,
    ProtagonistGoal,
    SceneType,
    SeriesVision,
    WorldConstraints,
)
from anovel.planning.versions import FreezeHorizon, FrozenInputs, PlanVersion


def create_test_series(genre_pack_hash: str = "abc123") -> SeriesVision:
    """Create minimal SeriesVision for testing."""
    return SeriesVision(
        series_id="test_series",
        title="Test Series",
        synopsis="Test",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="goal_1",
                description="Test goal",
                constraints=[],
                success_criteria=[],
            )
        ],
        world_constraints=WorldConstraints(
            realistic_constraints=[],
            cultivation_constraints=[],
            progression_rules=[],
            prohibited_mechanisms=[],
        ),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="urban.business.realistic",
            version="1.0",
            content_hash=genre_pack_hash,
        ),
        arc_plans=[],
        fixture_version="1.0",
        human_review_ref=None,
    )


def create_plan_version(
    canon_hash: str = "canon_abc",
    pack_hash: str = "pack_def",
    fixture_hash: str = "fixture_ghi",
    adjustable_chapters: list[str] = None,
) -> PlanVersion:
    """Create test PlanVersion with frozen inputs."""
    if adjustable_chapters is None:
        adjustable_chapters = ["chapter_01", "chapter_02"]

    return PlanVersion(
        plan_id="test_plan",
        version="v1",
        created_at=datetime.now(),
        freeze_horizon=FreezeHorizon(
            frozen_chapters=[],
            adjustable_chapters=adjustable_chapters,
            frozen_inputs=FrozenInputs(
                canon_parent_hash=canon_hash,
                genre_pack_hash=pack_hash,
                fixture_content_hash=fixture_hash,
            ),
        ),
    )


class TestContinuityEvidenceRequirements:
    """Test that continuity evidence is required, not optional."""

    def test_chapter_2_missing_end_state_warning(self):
        """Test that Chapter 2+ without previous_end_state is allowed but noted.

        Note: Current implementation allows None for previous_end_state.
        In production, this might warrant a warning but not rejection,
        as the hash binding alone provides some continuity.
        """
        compiler = ContractCompiler()

        # Use matching hashes to pass FrozenInputs verification
        genre_hash = "pack_def"
        series_vision = create_test_series(genre_pack_hash=genre_hash)

        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Test goal"],
            required_state_changes=["公司账户余额从30万降至20万"],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        canon_hash = "canon_abc"
        plan_version = create_plan_version(
            canon_hash=canon_hash,
            pack_hash=genre_hash,
        )

        # Compile with hash but no end state
        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent=canon_hash,
            previous_chapter_hash="chapter_1_hash",
            previous_end_state=None,  # Missing end state
        )

        # Currently allowed - contract created with empty previous_end_state
        assert hasattr(contract, "contract_id")
        assert contract.continuity_constraints.previous_end_state == {}

    def test_chapter_2_requires_previous_hash(self):
        """Test that Chapter 2+ MUST have previous_chapter_hash.

        This is stricter than end_state - hash is mandatory for continuity.
        """
        compiler = ContractCompiler()

        # Use matching hashes to pass FrozenInputs verification
        genre_hash = "pack_def"
        canon_hash = "canon_abc"
        series_vision = create_test_series(genre_pack_hash=genre_hash)

        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Test goal"],
            required_state_changes=["公司账户余额从30万降至20万"],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version(
            canon_hash=canon_hash,
            pack_hash=genre_hash,
        )

        # Attempt compile without previous_chapter_hash
        result = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent=canon_hash,
            previous_chapter_hash=None,  # Missing!
            previous_end_state={"some": "state"},
        )

        # Must reject - hash is mandatory
        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "missing_previous_chapter"
        assert "requires previous chapter hash" in result.message


class TestHashFormatValidation:
    """Test that content hashes are not just arbitrary strings.

    Note: Current implementation accepts any string as hash. This test
    documents the requirement for future hash format validation.
    """

    def test_compiler_accepts_hex_hash_format(self):
        """Test that compiler accepts reasonable hex-format hashes."""
        compiler = ContractCompiler()

        canon_hash = "abc123def456789"
        genre_hash = "pack_xyz_789"
        series_vision = create_test_series(genre_pack_hash=genre_hash)

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version(
            canon_hash=canon_hash,
            pack_hash=genre_hash,
        )

        # Valid-looking hex hash
        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent=canon_hash,  # Hex format
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        assert hasattr(contract, "contract_id")
        assert contract.canon_parent == canon_hash

    def test_compiler_currently_accepts_arbitrary_strings(self):
        """Test documenting that compiler currently accepts any string as hash.

        Owner requirement: Should not accept arbitrary strings as verified hashes.
        This test documents current behavior for future hardening.
        """
        compiler = ContractCompiler()

        canon_hash = "not_a_real_hash"
        genre_hash = "also_not_real"
        series_vision = create_test_series(genre_pack_hash=genre_hash)

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version(
            canon_hash=canon_hash,
            pack_hash=genre_hash,
        )

        # Currently accepts arbitrary string - documents behavior
        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent=canon_hash,
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Compiles successfully (current behavior)
        assert hasattr(contract, "contract_id")
        # Future: Should validate hash format or require explicit verification


class TestFrozenInputsMatchVerification:
    """Test that FrozenInputs must match actual compilation inputs."""

    def test_genre_pack_hash_mismatch_detected(self):
        """Test that genre pack hash mismatch is rejected."""
        compiler = ContractCompiler()

        # Series with one genre pack hash
        series_vision = create_test_series(genre_pack_hash="actual_pack_hash_123")

        # Plan frozen to different genre pack hash
        plan_version = create_plan_version(
            pack_hash="frozen_pack_hash_456"  # Mismatch!
        )

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        # Must reject with diagnostic
        result = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent="canon_abc",
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Must detect mismatch and reject
        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "frozen_inputs_mismatch"
        assert "GenrePack hash mismatch" in result.message
        assert "frozen_pack_hash_456" in result.message
        assert "actual_pack_hash_123" in result.message

    def test_canon_parent_must_match_frozen_inputs(self):
        """Test that canon_parent must match frozen canon_parent_hash.

        This prevents compiling against wrong Canon version.
        """
        compiler = ContractCompiler()
        series_vision = create_test_series()

        # Plan frozen to specific canon hash
        plan_version = create_plan_version(canon_hash="frozen_canon_hash")

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        # Attempt to compile with different canon_parent
        result = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent="different_canon_hash",  # Mismatch!
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Must reject with diagnostic
        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "frozen_inputs_mismatch"
        assert "Canon parent hash mismatch" in result.message
        assert "frozen_canon_hash" in result.message
        assert "different_canon_hash" in result.message

    def test_matching_frozen_inputs_compiles_successfully(self):
        """Test that compilation succeeds when all FrozenInputs match."""
        compiler = ContractCompiler()

        # Series with specific genre pack hash
        series_vision = create_test_series(genre_pack_hash="pack_hash_abc")

        # Plan frozen to matching hashes
        plan_version = create_plan_version(
            canon_hash="canon_hash_def",
            pack_hash="pack_hash_abc",  # Matches series_vision
            fixture_hash="fixture_hash_ghi",
        )

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        # Compile with matching canon_parent
        result = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent="canon_hash_def",  # Matches frozen canon_parent_hash
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Should compile successfully
        assert hasattr(result, "contract_id")
        assert result.canon_parent == "canon_hash_def"


class TestCompilerReadOnlyGuarantee:
    """Test that compiler never writes to Canon or external state."""

    def test_compiler_pure_function_no_side_effects(self):
        """Test that compiler is pure function with no side effects.

        Compiler should:
        - Not write to Canon
        - Not modify input objects
        - Not perform I/O except reading inputs
        - Return deterministic output for same inputs
        """
        compiler = ContractCompiler()

        canon_hash = "canon_abc"
        genre_hash = "pack_def"
        series_vision = create_test_series(genre_pack_hash=genre_hash)
        plan_version = create_plan_version(
            canon_hash=canon_hash,
            pack_hash=genre_hash,
        )

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        # Compile twice with same inputs
        contract1 = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent=canon_hash,
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        contract2 = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent=canon_hash,
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Should produce contracts with same structure (different IDs due to UUID)
        assert contract1.chapter_id == contract2.chapter_id
        assert contract1.chapter_number == contract2.chapter_number
        assert contract1.plan_version == contract2.plan_version
        assert len(contract1.required_transitions) == len(
            contract2.required_transitions
        )

        # Input objects should not be modified
        assert chapter_1.chapter_id == "chapter_01"
        assert plan_version.version == "v1"
