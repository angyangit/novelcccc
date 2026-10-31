"""Acceptance tests for V2-020 Single Chapter Workflow.

Tests the complete pipeline: Contract → Context → Gateway → Delta → Quality → Canon
"""

from datetime import datetime

import pytest

from anovel.context.compiler import ContextCompiler
from anovel.contracts.compiler import ContractCompiler
from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import OperationType
from anovel.gateway.gateway import ModelGateway
from anovel.gateway.mock_provider import MockProvider
from anovel.planning.models import (
    GenrePackBinding,
    ProtagonistGoal,
    SeriesVision,
    WorldConstraints,
)
from anovel.workflow.models import WorkflowStage, WorkflowStatus
from anovel.workflow.workflow import ChapterWorkflow


@pytest.fixture
def base_vision():
    """Base series vision for tests."""
    return SeriesVision(
        series_id="test-001",
        title="Test Novel",
        synopsis="A test novel",
        protagonist_goals=[
            ProtagonistGoal(
                goal_id="test-goal",
                description="Complete test",
                constraints=[],
                success_criteria=["test_pass"],
            )
        ],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="test",
            version="1.0",
            content_hash="test",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )


@pytest.fixture
def workflow():
    """Workflow instance with mock provider."""
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    return ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
    )


def test_at_v2_020_01_single_chapter_success(workflow, base_vision):
    """AT-V2-020-01: Single chapter successful generation.

    Pipeline stages: all 6 stages complete
    Result: SUCCESS with prose and canon commit
    """
    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="init",
                operation_type=OperationType.SET_FACT,
                fact_path="test.initialized",
                target_value=True,
                rationale="Initialize test",
            )
        ],
    )

    result = workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
        token_budget=8000,
        max_output_tokens=2000,
    )

    # All stages completed
    assert len(result.stages_completed) == 6
    assert WorkflowStage.CONTRACT_COMPILE in result.stages_completed
    assert WorkflowStage.CONTEXT_COMPILE in result.stages_completed
    assert WorkflowStage.GENERATION in result.stages_completed
    assert WorkflowStage.DELTA_EXTRACTION in result.stages_completed
    assert WorkflowStage.QUALITY_VALIDATION in result.stages_completed
    assert WorkflowStage.CANON_COMMIT in result.stages_completed

    # Success status
    assert result.status == WorkflowStatus.SUCCESS
    assert result.error is None

    # Generated content
    assert result.prose is not None
    assert len(result.prose) > 0
    assert result.canon_commit_hash is not None

    # Cost tracking
    assert result.total_cost_usd > 0
    assert result.execution_time_seconds >= 0

    # Chapter metadata
    assert result.chapter_id == "ch-1"
    assert result.chapter_number == 1


def test_at_v2_020_02_budget_admission_control(base_vision):
    """AT-V2-020-02: Budget admission control blocks generation.

    Setup: insufficient budget ($0.001)
    Expected: FAILED at GENERATION stage with budget_insufficient error
    """
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=0.001)  # Too low

    workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # Failed at generation stage
    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None
    assert result.error.stage == WorkflowStage.GENERATION
    assert "budget" in result.error.error_type.lower()
    assert not result.error.retryable

    # No prose generated
    assert result.prose is None
    assert result.canon_commit_hash is None


def test_at_v2_020_03_three_chapter_sequence(workflow, base_vision):
    """AT-V2-020-03: Three-chapter continuous generation.

    Generate 3 chapters sequentially with canon progression.
    Each chapter's canon_commit becomes next chapter's canon_parent.
    """
    chapters = []
    canon_snapshot = {"commit_hash": "canon-0"}
    previous_ending = None

    for i in range(1, 4):
        contract = ChapterContract(
            contract_id=f"test-ch{i}",
            chapter_id=f"ch-{i}",
            chapter_number=i,
            plan_version="v1",
            created_at=datetime.now(),
            canon_parent=canon_snapshot["commit_hash"],
            genre_pack_binding=base_vision.genre_pack_binding,
            required_transitions=[
                RequiredTransition(
                    transition_id=f"step-{i}",
                    operation_type=OperationType.SET_FACT,
                    fact_path=f"test.step_{i}",
                    target_value=True,
                    rationale=f"Step {i}",
                )
            ],
        )

        result = workflow.execute_chapter(
            contract=contract,
            series_vision=base_vision,
            canon_snapshot=canon_snapshot,
            previous_chapter_ending=previous_ending,
        )

        chapters.append(result)

        if result.status == WorkflowStatus.SUCCESS:
            # Update canon for next chapter
            canon_snapshot = {"commit_hash": result.canon_commit_hash}
            # Extract ending for continuity
            if result.prose:
                previous_ending = result.prose[-100:]

    # All chapters succeeded
    assert len(chapters) == 3
    assert all(ch.status == WorkflowStatus.SUCCESS for ch in chapters)

    # Sequential chapter numbers
    assert [ch.chapter_number for ch in chapters] == [1, 2, 3]

    # Each has unique canon commit
    canon_commits = [ch.canon_commit_hash for ch in chapters]
    assert len(set(canon_commits)) == 3  # All unique

    # Total cost accumulated
    total_cost = sum(ch.total_cost_usd for ch in chapters)
    assert total_cost > 0


def test_at_v2_020_04_provider_timeout_handling(base_vision):
    """AT-V2-020-04: Provider timeout results in retryable error.

    Setup: MockProvider with timeout mode
    Expected: FAILED with retryable=True, unknown_pending budget
    """
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="timeout")  # Timeout mode
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
    )

    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # Failed with timeout
    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None
    assert result.error.error_type == "timeout"
    assert result.error.retryable is True

    # Budget has unknown_pending
    budget = gateway.get_budget_summary()
    assert budget["unknown_pending"] > 0


def test_at_v2_020_05_quality_validation_executed(workflow, base_vision):
    """AT-V2-020-05: Quality validation stage executes.

    Verify quality checks run and report issues in metadata.
    """
    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # Quality validation stage completed
    assert WorkflowStage.QUALITY_VALIDATION in result.stages_completed

    # Quality issues reported in metadata
    assert "quality_issues" in result.metadata
    quality_issues = result.metadata["quality_issues"]
    assert isinstance(quality_issues, list)


def test_at_v2_020_06_delta_extraction_executed(workflow, base_vision):
    """AT-V2-020-06: Delta extraction stage executes.

    Verify NarrativeDelta is created from prose.
    """
    contract = ChapterContract(
        contract_id="test-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="test-transition",
                operation_type=OperationType.SET_FACT,
                fact_path="test.fact",
                target_value="value",
                rationale="Test",
            )
        ],
    )

    result = workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # Delta extraction stage completed
    assert WorkflowStage.DELTA_EXTRACTION in result.stages_completed
    assert result.status == WorkflowStatus.SUCCESS
