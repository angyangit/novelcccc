"""Tests for P0-D: Plan version and freeze horizon enforcement.

Tests freeze horizon rules:
- Frozen chapters cannot be modified (compilation rejected)
- Adjustable chapters can be compiled
- Chapters not in freeze horizon are rejected
- FrozenInputs binding (canon_parent, genre_pack, fixture hashes)
- Superseded PlanVersion rejected
"""

import pytest
from datetime import datetime

from anovel.planning.models import (
    SeriesVision,
    ChapterPlan,
    ProtagonistGoal,
    WorldConstraints,
    GenrePackBinding,
    SceneType,
)
from anovel.planning.versions import PlanVersion, FreezeHorizon, FrozenInputs
from anovel.contracts.compiler import ContractCompiler, CompilationDiagnostic


def create_test_series() -> SeriesVision:
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
            pack_id="test.pack",
            version="1.0",
            content_hash="abc123",
        ),
        arc_plans=[],
        fixture_version="1.0",
        human_review_ref=None,
    )


class TestFreezeHorizonEnforcement:
    """Test freeze horizon enforcement (AT-V2-017-07)."""

    def test_frozen_chapter_modification_rejected(self):
        """Test that modifications to frozen chapters are rejected."""
        compiler = ContractCompiler()
        series_vision = create_test_series()

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=["Some change"],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        # Plan with chapter_01 frozen
        plan_version = PlanVersion(
            plan_id="test_plan",
            version="v2",
            created_at=datetime.now(),
            freeze_horizon=FreezeHorizon(
                frozen_chapters=["chapter_01"],  # Frozen!
                adjustable_chapters=["chapter_02", "chapter_03"],
                frozen_inputs=FrozenInputs(
                    canon_parent_hash="canon_abc",
                    genre_pack_hash="pack_def",
                    fixture_content_hash="fixture_ghi",
                )
            )
        )

        # Attempt to compile frozen chapter
        result = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent="canon_abc",
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Should return diagnostic rejecting modification
        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "frozen_chapter_modification"
        assert "frozen" in result.message.lower()
        assert "chapter_01" in result.message

    def test_adjustable_chapter_compiles_successfully(self):
        """Test that adjustable chapters can be compiled."""
        compiler = ContractCompiler()
        series_vision = create_test_series()

        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        # Plan with chapter_02 adjustable
        plan_version = PlanVersion(
            plan_id="test_plan",
            version="v2",
            created_at=datetime.now(),
            freeze_horizon=FreezeHorizon(
                frozen_chapters=["chapter_01"],
                adjustable_chapters=["chapter_02", "chapter_03"],  # Adjustable!
                frozen_inputs=FrozenInputs(
                    canon_parent_hash="canon_abc",
                    genre_pack_hash="pack_def",
                    fixture_content_hash="fixture_ghi",
                )
            )
        )

        # Compile adjustable chapter
        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent="canon_abc",
            previous_chapter_hash="prev_hash",
            previous_end_state={},
        )

        # Should compile successfully
        assert hasattr(contract, 'contract_id')
        assert contract.chapter_id == "chapter_02"

    def test_chapter_not_in_freeze_horizon_rejected(self):
        """Test that chapters not in freeze horizon are rejected."""
        compiler = ContractCompiler()
        series_vision = create_test_series()

        chapter_99 = ChapterPlan(
            chapter_id="chapter_99",
            chapter_number=99,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        # Plan doesn't include chapter_99
        plan_version = PlanVersion(
            plan_id="test_plan",
            version="v1",
            created_at=datetime.now(),
            freeze_horizon=FreezeHorizon(
                frozen_chapters=["chapter_01"],
                adjustable_chapters=["chapter_02", "chapter_03"],
                frozen_inputs=FrozenInputs(
                    canon_parent_hash="canon_abc",
                    genre_pack_hash="pack_def",
                    fixture_content_hash="fixture_ghi",
                )
            )
        )

        # Attempt to compile chapter not in plan
        result = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_99,
            plan_version=plan_version,
            canon_parent="canon_abc",
            previous_chapter_hash="prev_hash",
            previous_end_state={},
        )

        # Should return diagnostic
        assert isinstance(result, CompilationDiagnostic)
        assert "chapter_99" in result.message
        assert "not found" in result.message.lower()

    def test_reading_frozen_chapter_for_compilation_allowed(self):
        """Test that frozen chapters can be read for continuity purposes.

        Note: Compilation of chapter N+1 requires reading chapter N's end state,
        even if chapter N is frozen. This is allowed - freeze prevents modification,
        not reading.
        """
        compiler = ContractCompiler()
        series_vision = create_test_series()

        # Chapter 2 is adjustable, will read frozen chapter 1 state
        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = PlanVersion(
            plan_id="test_plan",
            version="v2",
            created_at=datetime.now(),
            freeze_horizon=FreezeHorizon(
                frozen_chapters=["chapter_01"],  # Frozen
                adjustable_chapters=["chapter_02"],  # Adjustable
                frozen_inputs=FrozenInputs(
                    canon_parent_hash="canon_abc",
                    genre_pack_hash="pack_def",
                    fixture_content_hash="fixture_ghi",
                )
            )
        )

        # Compile chapter 2, which reads frozen chapter 1's end state
        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent="canon_abc",
            previous_chapter_hash="chapter_1_hash",  # Reading frozen chapter
            previous_end_state={"frozen_chapter_fact": "value"},
        )

        # Should succeed - reading frozen chapters is allowed
        assert hasattr(contract, 'contract_id')
        assert contract.continuity_constraints.previous_chapter_hash == "chapter_1_hash"


class TestVersionSupersession:
    """Test plan version supersession enforcement."""

    def test_superseded_version_rejected(self):
        """Test that superseded plan versions are rejected."""
        compiler = ContractCompiler()
        series_vision = create_test_series()

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        # Plan version that has been superseded
        old_plan = PlanVersion(
            plan_id="test_plan",
            version="v1",
            created_at=datetime.now(),
            freeze_horizon=FreezeHorizon(
                frozen_chapters=[],
                adjustable_chapters=["chapter_01"],
                frozen_inputs=FrozenInputs(
                    canon_parent_hash="canon_abc",
                    genre_pack_hash="pack_def",
                    fixture_content_hash="fixture_ghi",
                )
            ),
            superseded_by="v2",  # Superseded!
            invalidation_reason="Canon parent advanced"
        )

        # Attempt to compile with superseded version
        result = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=old_plan,
            canon_parent="canon_abc",
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Should return diagnostic
        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "version_expired"
        assert "superseded" in result.message.lower()
        assert "v2" in result.suggested_resolution


class TestFrozenInputsBinding:
    """Test that FrozenInputs are bound to contracts."""

    def test_frozen_inputs_in_freeze_horizon(self):
        """Test that FrozenInputs capture compilation dependencies."""
        plan_version = PlanVersion(
            plan_id="test_plan",
            version="v1",
            created_at=datetime.now(),
            freeze_horizon=FreezeHorizon(
                frozen_chapters=[],
                adjustable_chapters=["chapter_01"],
                frozen_inputs=FrozenInputs(
                    canon_parent_hash="canon_abc123",
                    genre_pack_hash="pack_def456",
                    fixture_content_hash="fixture_ghi789",
                )
            )
        )

        # Verify frozen inputs are accessible
        assert plan_version.freeze_horizon.frozen_inputs.canon_parent_hash == "canon_abc123"
        assert plan_version.freeze_horizon.frozen_inputs.genre_pack_hash == "pack_def456"
        assert plan_version.freeze_horizon.frozen_inputs.fixture_content_hash == "fixture_ghi789"

        # In real implementation, compiler would verify these match actual inputs
        # and reject compilation if mismatch detected
