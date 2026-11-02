"""Tests for compiler rejection of unmappable state changes.

Phase 2 requirement: Compiler must reject unmappable changes with
CompilationDiagnostic, not silently create untyped placeholder transitions.
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


def create_test_series(genre_pack_id: str = "urban.business.realistic") -> SeriesVision:
    """Create minimal SeriesVision for testing."""
    return SeriesVision(
        series_id="test_series",
        title="Test",
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
            pack_id=genre_pack_id,
            version="1.0",
            content_hash="abc123",
        ),
        arc_plans=[],
        fixture_version="1.0",
        human_review_ref=None,
    )


def create_test_plan(chapter_id: str = "chapter_01") -> PlanVersion:
    """Create minimal PlanVersion for testing."""
    return PlanVersion(
        plan_id="test_plan",
        version="v1",
        created_at=datetime.now(),
        freeze_horizon=FreezeHorizon(
            frozen_chapters=[],
            adjustable_chapters=[chapter_id],
            frozen_inputs=FrozenInputs(
                canon_parent_hash="test",
                genre_pack_hash="abc123",
                fixture_content_hash="test",
            ),
        ),
    )


class TestUnmappableStateChangeRejection:
    """Test that compiler rejects unmappable state changes."""

    def test_unmappable_change_returns_diagnostic(self):
        """Test that compiler rejects chapters with unmappable state changes."""
        compiler = ContractCompiler()
        series = create_test_series()

        chapter = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test"],
            required_state_changes=["完全无法识别的奇怪变化XYZ123"],  # Unmappable
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan = create_test_plan()

        result = compiler.compile_chapter(
            series_vision=series,
            chapter_plan=chapter,
            plan_version=plan,
            canon_parent="test",  # Match frozen_inputs
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Should return diagnostic, not contract
        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "unmappable_state_changes"
        assert "cannot be reliably mapped" in result.message
        assert len(result.conflicts) == 1
        assert "完全无法识别的奇怪变化XYZ123" in result.conflicts[0]

    def test_multiple_unmappable_changes(self):
        """Test that compiler reports all unmappable changes."""
        compiler = ContractCompiler()
        series = create_test_series()

        chapter = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test"],
            required_state_changes=[
                "奇怪变化A",
                "奇怪变化B",
                "奇怪变化C",
            ],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan = create_test_plan()

        result = compiler.compile_chapter(
            series_vision=series,
            chapter_plan=chapter,
            plan_version=plan,
            canon_parent="test",  # Match frozen_inputs
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "unmappable_state_changes"
        assert "3 state changes" in result.message
        assert len(result.conflicts) == 3

    def test_mappable_and_unmappable_mix(self):
        """Test that compiler rejects if ANY state change is unmappable."""
        compiler = ContractCompiler()
        series = create_test_series()

        chapter = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test"],
            required_state_changes=[
                "公司账户余额从50万降至30万",  # Mappable
                "完全无法识别的变化",  # Unmappable
            ],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan = create_test_plan()

        result = compiler.compile_chapter(
            series_vision=series,
            chapter_plan=chapter,
            plan_version=plan,
            canon_parent="test",  # Match frozen_inputs
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Should reject entire chapter if any change is unmappable
        assert isinstance(result, CompilationDiagnostic)
        assert result.error_type == "unmappable_state_changes"
        assert len(result.conflicts) == 1
        assert "完全无法识别" in result.conflicts[0]

    def test_all_mappable_changes_succeed(self):
        """Test that chapters with all mappable changes compile successfully."""
        compiler = ContractCompiler()
        series = create_test_series()

        chapter = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test"],
            required_state_changes=[
                "公司账户余额从50万降至30万",
                "张明股权从70%降至49%",
            ],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan = create_test_plan()

        result = compiler.compile_chapter(
            series_vision=series,
            chapter_plan=chapter,
            plan_version=plan,
            canon_parent="test",  # Match frozen_inputs
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        # Should compile successfully
        assert hasattr(result, "contract_id")
        assert len(result.required_transitions) == 2
        # Verify no untyped paths
        for trans in result.required_transitions:
            assert "untyped_change" not in trans.fact_path

    def test_diagnostic_suggests_resolution(self):
        """Test that diagnostic includes helpful resolution suggestion."""
        compiler = ContractCompiler()
        series = create_test_series()

        chapter = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test"],
            required_state_changes=["无法识别的变化"],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan = create_test_plan()

        result = compiler.compile_chapter(
            series_vision=series,
            chapter_plan=chapter,
            plan_version=plan,
            canon_parent="test",  # Match frozen_inputs
            previous_chapter_hash=None,
            previous_end_state=None,
        )

        assert isinstance(result, CompilationDiagnostic)
        assert result.suggested_resolution is not None
        assert (
            "structured" in result.suggested_resolution
            or "extend" in result.suggested_resolution
        )
