"""Core Chapter Workflow orchestration for V2-020/V2-021."""

import hashlib
import time
import uuid
from datetime import datetime
from typing import Any

from ..context.compiler import ContextCompiler
from ..context.models import ContextCompilationError
from ..contracts.compiler import ContractCompiler
from ..contracts.models import ChapterContract
from ..domain.delta import NarrativeDelta
from ..gateway.gateway import ModelGateway
from ..gateway.models import GenerationError
from ..planning.models import SeriesVision
from .extractor import NarrativeDeltaExtractor
from .models import (
    ChapterWorkflowResult,
    DeltaExtractionResult,
    QualityCheckResult,
    WorkflowError,
    WorkflowStage,
    WorkflowStatus,
)


class ChapterWorkflow:
    """Orchestrates single chapter generation workflow."""

    def __init__(
        self,
        contract_compiler: ContractCompiler,
        context_compiler: ContextCompiler,
        model_gateway: ModelGateway,
        extractor: NarrativeDeltaExtractor | None = None,  # V2-021: injectable extractor
        mock_mode: bool = True,  # True = mock canon commits, False = real commits
    ):
        """Initialize workflow with required components.

        Args:
            contract_compiler: Contract compiler (V2-017)
            context_compiler: Context compiler (V2-018)
            model_gateway: Model gateway (V2-019)
            extractor: Narrative delta extractor (V2-021), None = use legacy stub
            mock_mode: If True, use mock canon commits (NOT production)
        """
        self.contract_compiler = contract_compiler
        self.context_compiler = context_compiler
        self.model_gateway = model_gateway
        self.extractor = extractor  # V2-021: new injected extractor
        self.mock_mode = mock_mode

    def execute_chapter(
        self,
        contract: ChapterContract,
        series_vision: SeriesVision,
        canon_snapshot: dict,
        previous_chapter_ending: str | None,
        token_budget: int = 8000,
        max_output_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> ChapterWorkflowResult:
        """Execute complete chapter generation workflow.

        Pipeline:
        1. Contract validation (already compiled)
        2. Context compilation (V2-018)
        3. Model generation (V2-019)
        4. Delta extraction (from prose)
        5. Quality validation
        6. Canon commit

        Args:
            contract: Chapter contract
            series_vision: Series vision
            canon_snapshot: Current canon state
            previous_chapter_ending: Previous chapter ending
            token_budget: Context token budget
            max_output_tokens: Max generation tokens
            temperature: Generation temperature

        Returns:
            Complete workflow result
        """
        workflow_id = str(uuid.uuid4())
        start_time = time.time()
        stages_completed: list[WorkflowStage] = []
        total_cost = 0.0

        try:
            # Stage 1: Contract already validated
            stages_completed.append(WorkflowStage.CONTRACT_COMPILE)

            # Stage 2: Context compilation
            compilation_result = self.context_compiler.compile_context(
                contract=contract,
                series_vision=series_vision,
                canon_snapshot=canon_snapshot,
                previous_chapter_ending=previous_chapter_ending,
                token_budget=token_budget,
            )

            if isinstance(compilation_result, ContextCompilationError):
                execution_time = time.time() - start_time
                return ChapterWorkflowResult(
                    workflow_id=workflow_id,
                    chapter_id=contract.chapter_id,
                    chapter_number=contract.chapter_number,
                    status=WorkflowStatus.FAILED,
                    prose=None,
                    prose_hash=None,
                    canon_commit_hash=None,
                    is_mock_commit=False,
                    stages_completed=stages_completed,
                    error=WorkflowError(
                        stage=WorkflowStage.CONTEXT_COMPILE,
                        error_type="context_compilation_error",
                        message=str(compilation_result),
                        retryable=False,
                        failed_at=datetime.now(),
                    ),
                    quality_result=None,
                    delta_result=None,
                    execution_time_seconds=execution_time,
                    total_cost_usd=total_cost,
                    metadata={},
                    completed_at=datetime.now(),
                )

            artifact = compilation_result
            stages_completed.append(WorkflowStage.CONTEXT_COMPILE)

            # Stage 3: Model generation
            generation_result = self.model_gateway.generate_chapter(
                artifact=artifact,
                max_tokens=max_output_tokens,
                temperature=temperature,
            )

            if isinstance(generation_result, GenerationError):
                execution_time = time.time() - start_time
                return ChapterWorkflowResult(
                    workflow_id=workflow_id,
                    chapter_id=contract.chapter_id,
                    chapter_number=contract.chapter_number,
                    status=WorkflowStatus.FAILED,
                    prose=None,
                    prose_hash=None,
                    canon_commit_hash=None,
                    is_mock_commit=False,
                    stages_completed=stages_completed,
                    error=WorkflowError(
                        stage=WorkflowStage.GENERATION,
                        error_type=generation_result.error_type,
                        message=generation_result.message,
                        retryable=generation_result.retryable,
                        failed_at=generation_result.failed_at,
                        context={"request_id": generation_result.request_id},
                    ),
                    quality_result=None,
                    delta_result=None,
                    execution_time_seconds=execution_time,
                    total_cost_usd=total_cost,
                    metadata={
                        "artifact_id": artifact.artifact_id,
                        "budget_summary": self.model_gateway.get_budget_summary(),
                    },
                    completed_at=datetime.now(),
                )

            prose = generation_result.prose
            prose_hash = hashlib.sha256(prose.encode()).hexdigest()
            total_cost = total_cost + (generation_result.cost_usd or 0.0)
            stages_completed.append(WorkflowStage.GENERATION)

            # Stage 4: Delta extraction
            delta_result = self._extract_narrative_delta(
                prose=prose,
                prose_hash=prose_hash,
                contract=contract,
                series_vision=series_vision,
                canon_parent=canon_snapshot.get("commit_hash", "unknown"),
            )
            stages_completed.append(WorkflowStage.DELTA_EXTRACTION)

            # Check extraction success
            if not delta_result.success:
                execution_time = time.time() - start_time
                return ChapterWorkflowResult(
                    workflow_id=workflow_id,
                    chapter_id=contract.chapter_id,
                    chapter_number=contract.chapter_number,
                    status=WorkflowStatus.EXTRACTION_FAILED,
                    prose=prose,
                    prose_hash=prose_hash,
                    canon_commit_hash=None,
                    is_mock_commit=False,
                    stages_completed=stages_completed,
                    error=WorkflowError(
                        stage=WorkflowStage.DELTA_EXTRACTION,
                        error_type="extraction_failed",
                        message="; ".join(delta_result.issues),
                        retryable=True,
                        failed_at=datetime.now(),
                    ),
                    quality_result=None,
                    delta_result=delta_result,
                    execution_time_seconds=execution_time,
                    total_cost_usd=total_cost,
                    metadata={
                        "artifact_id": artifact.artifact_id,
                        "generation_request_id": generation_result.request_id,
                        "input_tokens": generation_result.input_tokens,
                        "output_tokens": generation_result.output_tokens,
                        "budget_summary": self.model_gateway.get_budget_summary(),
                    },
                    completed_at=datetime.now(),
                )

            # Stage 5: Quality validation
            quality_result = self._validate_quality(
                prose=prose,
                prose_hash=prose_hash,
                delta=delta_result.delta,
                contract=contract,
            )
            stages_completed.append(WorkflowStage.QUALITY_VALIDATION)

            # FAIL-CLOSED: Quality check must pass to proceed
            if not quality_result.passed:
                execution_time = time.time() - start_time
                return ChapterWorkflowResult(
                    workflow_id=workflow_id,
                    chapter_id=contract.chapter_id,
                    chapter_number=contract.chapter_number,
                    status=WorkflowStatus.QUALITY_FAILED,
                    prose=prose,
                    prose_hash=prose_hash,
                    canon_commit_hash=None,
                    is_mock_commit=False,
                    stages_completed=stages_completed,
                    error=WorkflowError(
                        stage=WorkflowStage.QUALITY_VALIDATION,
                        error_type="quality_failed",
                        message=f"Quality checks failed: {', '.join(quality_result.blocking_issues)}",
                        retryable=True,
                        failed_at=datetime.now(),
                    ),
                    quality_result=quality_result,
                    delta_result=delta_result,
                    execution_time_seconds=execution_time,
                    total_cost_usd=total_cost,
                    metadata={
                        "artifact_id": artifact.artifact_id,
                        "generation_request_id": generation_result.request_id,
                        "input_tokens": generation_result.input_tokens,
                        "output_tokens": generation_result.output_tokens,
                        "budget_summary": self.model_gateway.get_budget_summary(),
                    },
                    completed_at=datetime.now(),
                )

            # Stage 6: Canon commit (mock or real based on mode)
            canon_result = self._commit_to_canon(
                chapter_id=contract.chapter_id,
                prose=prose,
                prose_hash=prose_hash,
                delta=delta_result.delta,
                canon_snapshot=canon_snapshot,
            )
            stages_completed.append(WorkflowStage.CANON_COMMIT)

            execution_time = time.time() - start_time

            return ChapterWorkflowResult(
                workflow_id=workflow_id,
                chapter_id=contract.chapter_id,
                chapter_number=contract.chapter_number,
                status=WorkflowStatus.SUCCESS,
                prose=prose,
                prose_hash=prose_hash,
                canon_commit_hash=canon_result["commit_hash"],
                is_mock_commit=canon_result["is_mock"],
                stages_completed=stages_completed,
                error=None,
                quality_result=quality_result,
                delta_result=delta_result,
                execution_time_seconds=execution_time,
                total_cost_usd=total_cost,
                metadata={
                    "artifact_id": artifact.artifact_id,
                    "generation_request_id": generation_result.request_id,
                    "input_tokens": generation_result.input_tokens,
                    "output_tokens": generation_result.output_tokens,
                    "budget_summary": self.model_gateway.get_budget_summary(),
                },
                completed_at=datetime.now(),
            )

        except Exception as e:
            execution_time = time.time() - start_time
            last_stage = stages_completed[-1] if stages_completed else WorkflowStage.CONTRACT_COMPILE

            return ChapterWorkflowResult(
                workflow_id=workflow_id,
                chapter_id=contract.chapter_id,
                chapter_number=contract.chapter_number,
                status=WorkflowStatus.FAILED,
                prose=None,
                prose_hash=None,
                canon_commit_hash=None,
                is_mock_commit=False,
                stages_completed=stages_completed,
                error=WorkflowError(
                    stage=last_stage,
                    error_type="workflow_error",
                    message=str(e),
                    retryable=False,
                    failed_at=datetime.now(),
                ),
                quality_result=None,
                delta_result=None,
                execution_time_seconds=execution_time,
                total_cost_usd=total_cost,
                metadata={"budget_summary": self.model_gateway.get_budget_summary()},
                completed_at=datetime.now(),
            )

    def _extract_narrative_delta(
        self,
        prose: str,
        prose_hash: str,
        contract: ChapterContract,
        series_vision: SeriesVision,
        canon_parent: str,
    ) -> DeltaExtractionResult:
        """Extract NarrativeDelta from generated prose.

        V2-021: Uses injected extractor if available, otherwise legacy stub.

        Args:
            prose: Generated prose
            prose_hash: SHA-256 hash of prose
            contract: Chapter contract
            series_vision: Series vision (for project_id)
            canon_parent: Canon parent hash

        Returns:
            Extraction result with success based on contract requirements
        """
        # V2-021: Use injected extractor if available
        if self.extractor is not None:
            extraction_result = self.extractor.extract(
                prose=prose,
                prose_hash=prose_hash,
                contract=contract,
                series_vision=series_vision,
                canon_parent=canon_parent,
            )

            # Convert V2-021 result to V2-020 DeltaExtractionResult
            return DeltaExtractionResult(
                success=(extraction_result.status == "success"),
                delta=extraction_result.delta,
                prose_hash=extraction_result.prose_hash,
                extraction_method=extraction_result.extraction_method,
                issues=extraction_result.issues,
            )

        # Legacy V2-020 stub (for backward compatibility)
        return self._legacy_extraction_stub(
            prose, prose_hash, contract, series_vision
        )

    def _legacy_extraction_stub(
        self,
        prose: str,
        prose_hash: str,
        contract: ChapterContract,
        series_vision: SeriesVision,
    ) -> DeltaExtractionResult:
        """Legacy extraction stub from V2-020."""
        from ..domain.delta import DeltaId
        from ..domain.identity import ProjectId

        issues = []
        success = True

        # FAIL-CLOSED: If contract requires transitions, extraction must implement them
        if contract.required_transitions:
            issues.append(
                f"Extraction not implemented: {len(contract.required_transitions)} "
                "required transitions cannot be verified from prose"
            )
            success = False

        # Create delta with empty operations
        delta_uuid = str(uuid.uuid4())
        project_id = ProjectId(series_vision.series_id)

        delta = NarrativeDelta(
            delta_id=DeltaId(delta_uuid),
            project_id=project_id,
            operations=(),  # Empty - extraction not implemented
            source_chapter=contract.chapter_id,
            created_at=datetime.now(),
            authority="chapter_workflow_v2020_legacy",
            provenance=(
                ("extraction_method", "not_implemented_legacy"),
                ("prose_hash", prose_hash),
            ),
        )

        return DeltaExtractionResult(
            success=success,  # Success if no transitions required
            delta=delta,
            prose_hash=prose_hash,
            extraction_method="not_implemented_mvp",
            issues=issues,
        )

    def _validate_quality(
        self,
        prose: str,
        prose_hash: str,
        delta: NarrativeDelta | None,
        contract: ChapterContract,
    ) -> QualityCheckResult:
        """Validate chapter quality with fail-closed gates.

        FAIL-CLOSED: Any blocking issue prevents canon commit.

        Args:
            prose: Generated prose
            prose_hash: SHA-256 of prose
            delta: Narrative delta (may be None if extraction failed)
            contract: Chapter contract

        Returns:
            Quality check result with passed=True only if all checks pass
        """
        blocking_issues = []
        warnings = []
        checks_run = []

        # Check 1: Prose minimum length (BLOCKING)
        checks_run.append("prose_minimum_length")
        if not prose or len(prose.strip()) < 100:
            blocking_issues.append("Prose too short (< 100 chars)")

        # Check 2: No error markers in prose (BLOCKING)
        checks_run.append("no_error_markers")
        error_markers = ["[ERROR]", "[FAILED]", "[MOCK CHAPTER PROSE]"]
        for marker in error_markers:
            if marker in prose:
                blocking_issues.append(f"Error marker found in prose: {marker}")

        # Check 3: Delta operations present if contract requires transitions (BLOCKING)
        checks_run.append("delta_operations_present")
        if delta and contract.required_transitions:
            if len(delta.operations) == 0:
                blocking_issues.append(
                    f"Contract requires {len(contract.required_transitions)} transitions "
                    "but delta has 0 operations (extraction failed or not implemented)"
                )
            elif len(delta.operations) != len(contract.required_transitions):
                warnings.append(
                    f"Delta operations count ({len(delta.operations)}) "
                    f"!= contract transitions ({len(contract.required_transitions)})"
                )

        # Check 4: Prose hash bound to delta (WARNING)
        checks_run.append("prose_hash_binding")
        if delta:
            provenance_dict = dict(delta.provenance)
            if provenance_dict.get("prose_hash") != prose_hash:
                warnings.append("Delta not bound to current prose hash")

        # FAIL-CLOSED: passed only if NO blocking issues
        passed = len(blocking_issues) == 0

        return QualityCheckResult(
            passed=passed,
            blocking_issues=blocking_issues,
            warnings=warnings,
            checks_run=checks_run,
        )

    def _commit_to_canon(
        self,
        chapter_id: str,
        prose: str,
        prose_hash: str,
        delta: NarrativeDelta | None,
        canon_snapshot: dict,
    ) -> dict[str, Any]:
        """Commit chapter to canonical state.

        V2-020 MVP: Mock mode only.
        Future: Real canon commit via CanonRepository.

        Args:
            chapter_id: Chapter ID
            prose: Generated prose
            prose_hash: SHA-256 of prose
            delta: Narrative delta
            canon_snapshot: Current canon state

        Returns:
            Dict with commit_hash and is_mock flag
        """
        if self.mock_mode:
            # Mock mode: generate mock hash with MOCK prefix
            content = f"{chapter_id}:{prose_hash}:{delta.delta_id if delta else 'no-delta'}"
            mock_hash = "MOCK-" + hashlib.sha256(content.encode()).hexdigest()[:16]

            return {
                "commit_hash": mock_hash,
                "is_mock": True,
            }
        else:
            # Real mode: Use CanonRepository (not implemented in V2-020)
            # Future: Real canon commit with:
            # - Permit verification
            # - Parent validation
            # - Transaction atomicity
            # - Idempotency check
            # - CommitReceipt generation
            raise NotImplementedError(
                "Real canon commit not implemented in V2-020. "
                "Use mock_mode=True or implement real canon integration."
            )
