"""Tests for P0-C: Continuity constraint evidence binding.

Tests continuity binding requirements:
- Chapter 1 explicitly has no prior (previous_chapter_hash: None)
- Chapter 2+ requires previous_chapter_hash
- Prior chapter revision invalidates continuation (hash mismatch detection)
- Continuity binds previous end state evidence

Note: Actual prose hash verification requires Canon read access, which is
outside the scope of the pure-function compiler. The compiler accepts hash
strings and binds them to the contract; validation happens at execution time.
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


def create_minimal_series_vision(series_id: str = "test_series") -> SeriesVision:
    """Create minimal SeriesVision for testing."""
    return SeriesVision(
        series_id=series_id,
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
            pack_id="urban.business.realistic",  # Use real genre for fact mapping
            version="1.0",
            content_hash="abc123",
        ),
        arc_plans=[],
        fixture_version="1.0",
        human_review_ref=None,
    )


def create_plan_version(plan_id: str = "test_plan") -> PlanVersion:
    """Create minimal PlanVersion for testing."""
    return PlanVersion(
        plan_id=plan_id,
        version="v1",
        created_at=datetime.now(),
        freeze_horizon=FreezeHorizon(
            frozen_chapters=[],
            adjustable_chapters=["chapter_01", "chapter_02"],
            frozen_inputs=FrozenInputs(
                canon_parent_hash="initial",
                genre_pack_hash="abc123",
                fixture_content_hash="def456",
            ),
        ),
    )


class TestContinuityBinding:
    """Test continuity constraint binding (AT-V2-017-05)."""

    def test_chapter_1_explicitly_no_prior(self):
        """Test that chapter 1 explicitly has previous_chapter_hash: None."""
        compiler = ContractCompiler()
        series_vision = create_minimal_series_vision()

        chapter_1 = ChapterPlan(
            chapter_id="chapter_01",
            chapter_number=1,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version()

        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_1,
            plan_version=plan_version,
            canon_parent="initial",  # Match frozen_inputs
            previous_chapter_hash=None,  # Chapter 1 has no prior
            previous_end_state=None,
        )

        # Chapter 1 should have no continuity constraints
        assert contract.continuity_constraints is None

    def test_chapter_2_requires_previous_hash(self):
        """Test that chapter 2+ requires previous_chapter_hash."""
        compiler = ContractCompiler()
        series_vision = create_minimal_series_vision()

        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version()

        # Missing previous_chapter_hash should return diagnostic
        result = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent="initial",  # Match frozen_inputs
            previous_chapter_hash=None,  # Missing!
            previous_end_state=None,
        )

        assert isinstance(result, CompilationDiagnostic)
        assert "previous chapter hash" in result.message.lower()

    def test_chapter_2_binds_previous_hash_and_state(self):
        """Test that chapter 2 binds previous chapter hash and end state."""
        compiler = ContractCompiler()
        series_vision = create_minimal_series_vision()

        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version()

        previous_hash = "abc123def456"
        previous_state = {"equity.protagonist.percentage": "70%"}

        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent="initial",  # Match frozen_inputs
            previous_chapter_hash=previous_hash,
            previous_end_state=previous_state,
        )

        # Should have continuity constraint with bound evidence
        assert contract.continuity_constraints is not None
        assert contract.continuity_constraints.previous_chapter_hash == previous_hash
        assert contract.continuity_constraints.previous_end_state == previous_state
        assert contract.continuity_constraints.previous_chapter_id == "chapter_1"

    def test_prior_revision_detection_via_hash_change(self):
        """Test that changing previous_chapter_hash indicates prior revision.

        Note: The compiler accepts hash strings but doesn't verify them against
        Canon. Detection of actual revision happens when:
        1. Contract compiled with hash H1
        2. Chapter 1 revised, new hash H2
        3. Attempt to use old contract with H1 fails validation

        This test shows the contract binds the hash; external validation
        would detect the mismatch.
        """
        compiler = ContractCompiler()
        series_vision = create_minimal_series_vision()

        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Test goal"],
            required_state_changes=[],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version()

        # Compile with original hash
        original_hash = "original_chapter_1_hash"
        contract_v1 = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent="initial",  # Match frozen_inputs
            previous_chapter_hash=original_hash,
            previous_end_state={},
        )

        # Compile again with revised hash (simulating chapter 1 revision)
        revised_hash = "revised_chapter_1_hash"
        contract_v2 = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent="initial",  # Match frozen_inputs
            previous_chapter_hash=revised_hash,
            previous_end_state={},
        )

        # Contracts should bind different hashes
        assert contract_v1.continuity_constraints.previous_chapter_hash == original_hash
        assert contract_v2.continuity_constraints.previous_chapter_hash == revised_hash
        assert original_hash != revised_hash

        # This demonstrates that contracts are invalidated by prior revision:
        # - Old contract (v1) expects original_hash
        # - After revision, chapter 1 has revised_hash
        # - Validation would detect mismatch and reject contract_v1
        # - New contract (v2) must be compiled with correct revised_hash


class TestContinuityEvidence:
    """Test evidence binding in continuity constraints."""

    def test_continuity_binds_end_state_evidence(self):
        """Test that continuity binds specific end state facts."""
        compiler = ContractCompiler()
        series_vision = create_minimal_series_vision()

        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Test goal"],
            # Use mappable state change (Phase 2 requirement)
            required_state_changes=["公司账户余额从30万降至20万"],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version()

        # End state from chapter 1
        end_state = {
            "equity.protagonist.percentage": "70%",
            "resources.company.cash": "30万",
            "relationships.protagonist.cofounder.trust": "medium",
        }

        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent="initial",  # Match frozen_inputs
            previous_chapter_hash="chapter_1_hash",
            previous_end_state=end_state,
        )

        # Verify end state evidence is bound
        assert contract.continuity_constraints.previous_end_state == end_state
        assert len(contract.continuity_constraints.previous_end_state) == 3

    def test_start_requirements_can_reference_prior_state(self):
        """Test that start requirements can reference prior chapter state."""
        compiler = ContractCompiler()
        series_vision = create_minimal_series_vision()

        chapter_2 = ChapterPlan(
            chapter_id="chapter_02",
            chapter_number=2,
            goals=["Build on previous outcome"],
            # Use mappable state change (Phase 2 requirement)
            required_state_changes=["张明股权从70%降至65%"],
            character_focus=[],
            scene_type=SceneType.ACTION,
        )

        plan_version = create_plan_version()

        contract = compiler.compile_chapter(
            series_vision=series_vision,
            chapter_plan=chapter_2,
            plan_version=plan_version,
            canon_parent="initial",  # Match frozen_inputs
            previous_chapter_hash="chapter_1_hash",
            previous_end_state={"key_fact": "value"},
        )

        # Continuity constraints provide the binding
        assert contract.continuity_constraints is not None
        # current_start_requirements could reference previous_end_state facts
        # (in real implementation, compiler would analyze dependencies)
