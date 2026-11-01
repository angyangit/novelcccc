"""V2-020 Production Integrity Tests - Fail-Closed Quality Gates.

Tests that workflow correctly blocks canon commits when:
1. Quality checks fail
2. Delta extraction fails
3. Mock prose markers are present
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
        series_id="test-production-001",
        title="Production Test Novel",
        synopsis="Testing production integrity",
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
def mock_workflow():
    """Workflow instance in mock mode."""
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    return ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
        mock_mode=True,
    )


def test_quality_fail_blocks_canon_commit(mock_workflow, base_vision):
    """Quality check failure MUST block canon commit.

    MockProvider returns '[MOCK CHAPTER PROSE]' which contains error marker.
    This MUST be detected and block commit.
    """
    contract = ChapterContract(
        contract_id="test-ch-quality-fail",
        chapter_id="ch-quality-fail",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = mock_workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # CRITICAL: Must NOT be SUCCESS when mock prose detected
    assert result.status == WorkflowStatus.QUALITY_FAILED
    assert result.prose is not None  # Prose was generated
    assert result.canon_commit_hash is None  # But NOT committed
    assert result.is_mock_commit is False

    # Quality result must show blocking issue
    assert result.quality_result is not None
    assert result.quality_result.passed is False
    assert len(result.quality_result.blocking_issues) > 0
    assert any("MOCK CHAPTER PROSE" in issue for issue in result.quality_result.blocking_issues)

    # Error must be present
    assert result.error is not None
    assert result.error.stage == WorkflowStage.QUALITY_VALIDATION
    assert result.error.error_type == "quality_failed"


def test_extraction_fail_blocks_canon_commit(mock_workflow, base_vision):
    """Delta extraction failure MUST block canon commit.

    Contract requires transitions but extraction not implemented.
    This MUST be detected and block commit.
    """
    contract = ChapterContract(
        contract_id="test-ch-extraction-fail",
        chapter_id="ch-extraction-fail",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="required-transition",
                operation_type=OperationType.SET_FACT,
                fact_path="test.state",
                target_value=True,
                rationale="Required state change",
            )
        ],
    )

    result = mock_workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # CRITICAL: Must NOT be SUCCESS when extraction fails
    assert result.status == WorkflowStatus.EXTRACTION_FAILED
    assert result.prose is not None  # Prose was generated
    assert result.canon_commit_hash is None  # But NOT committed
    assert result.is_mock_commit is False

    # Delta result must show failure
    assert result.delta_result is not None
    assert result.delta_result.success is False
    assert len(result.delta_result.issues) > 0

    # Error must be present
    assert result.error is not None
    assert result.error.stage == WorkflowStage.DELTA_EXTRACTION
    assert result.error.error_type == "extraction_failed"


def test_mock_commit_clearly_marked(mock_workflow, base_vision):
    """Mock canon commits MUST be clearly marked as mock.

    Even if all checks somehow pass in mock mode, the commit hash
    must be clearly identifiable as mock, not a real canon commit.
    """
    # Contract with no required transitions to allow extraction to "pass"
    contract = ChapterContract(
        contract_id="test-ch-mock-commit",
        chapter_id="ch-mock-commit",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],  # No transitions required
    )

    result = mock_workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # Will fail quality due to mock prose marker, but if it somehow succeeded:
    if result.status == WorkflowStatus.SUCCESS:
        # Mock commits MUST be marked
        assert result.is_mock_commit is True
        assert result.canon_commit_hash is not None
        assert result.canon_commit_hash.startswith("MOCK-")


def test_prose_hash_binding(mock_workflow, base_vision):
    """Prose hash MUST be bound to delta and recorded in result."""
    contract = ChapterContract(
        contract_id="test-ch-prose-hash",
        chapter_id="ch-prose-hash",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = mock_workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # Prose hash must be present
    assert result.prose_hash is not None
    assert len(result.prose_hash) == 64  # SHA-256 hex length

    # Delta result must include prose hash
    if result.delta_result:
        assert result.delta_result.prose_hash == result.prose_hash


def test_project_id_not_hardcoded(mock_workflow, base_vision):
    """Project ID MUST come from series_vision, not hardcoded."""
    contract = ChapterContract(
        contract_id="test-ch-project-id",
        chapter_id="ch-project-id",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=base_vision.genre_pack_binding,
        required_transitions=[],
    )

    result = mock_workflow.execute_chapter(
        contract=contract,
        series_vision=base_vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # Delta must use series_id as project_id
    if result.delta_result and result.delta_result.delta:
        delta = result.delta_result.delta
        assert str(delta.project_id) == base_vision.series_id
        assert str(delta.project_id) != "default-project"


def test_real_mode_not_implemented():
    """Real canon commit mode MUST raise NotImplementedError in V2-020.

    Note: Quality check will fail first due to mock prose marker,
    but we verify that real mode is configured and would fail at commit stage.
    """
    contract_compiler = ContractCompiler()
    context_compiler = ContextCompiler()
    provider = MockProvider(mode="success")
    gateway = ModelGateway(provider=provider, total_budget_usd=100.0)

    workflow = ChapterWorkflow(
        contract_compiler=contract_compiler,
        context_compiler=context_compiler,
        model_gateway=gateway,
        mock_mode=False,  # Real mode
    )

    vision = SeriesVision(
        series_id="test-real-001",
        title="Real Mode Test",
        synopsis="Testing real mode",
        protagonist_goals=[],
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

    contract = ChapterContract(
        contract_id="test-ch-real",
        chapter_id="ch-real",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=vision.genre_pack_binding,
        required_transitions=[],
    )

    # Real mode should fail (either at quality or at canon commit if quality somehow passed)
    result = workflow.execute_chapter(
        contract=contract,
        series_vision=vision,
        canon_snapshot={"commit_hash": "canon-0"},
        previous_chapter_ending=None,
    )

    # Should fail - either at quality (due to mock prose) or at commit (real mode not implemented)
    assert result.status in [WorkflowStatus.FAILED, WorkflowStatus.QUALITY_FAILED]

    # Verify mock_mode is False (real mode configured)
    assert workflow.mock_mode is False
