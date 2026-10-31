"""Core Chapter Workflow orchestration for V2-020."""

import time
import uuid
from datetime import datetime

from ..context.compiler import ContextCompiler
from ..context.models import ContextCompilationError
from ..contracts.compiler import ContractCompiler
from ..contracts.models import ChapterContract
from ..domain.delta import NarrativeDelta, Operation
from ..gateway.gateway import ModelGateway
from ..gateway.models import GenerationError
from ..planning.models import SeriesVision
from .models import (
    ChapterWorkflowResult,
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
    ):
        """Initialize workflow with required components.

        Args:
            contract_compiler: Contract compiler (V2-017)
            context_compiler: Context compiler (V2-018)
            model_gateway: Model gateway (V2-019)
        """
        self.contract_compiler = contract_compiler
        self.context_compiler = context_compiler
        self.model_gateway = model_gateway

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
                    canon_commit_hash=None,
                    stages_completed=stages_completed,
                    error=WorkflowError(
                        stage=WorkflowStage.CONTEXT_COMPILE,
                        error_type="context_compilation_error",
                        message=str(compilation_result),
                        retryable=False,
                        failed_at=datetime.now(),
                    ),
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
                    canon_commit_hash=None,
                    stages_completed=stages_completed,
                    error=WorkflowError(
                        stage=WorkflowStage.GENERATION,
                        error_type=generation_result.error_type,
                        message=generation_result.message,
                        retryable=generation_result.retryable,
                        failed_at=generation_result.failed_at,
                        context={"request_id": generation_result.request_id},
                    ),
                    execution_time_seconds=execution_time,
                    total_cost_usd=total_cost,
                    metadata={
                        "artifact_id": artifact.artifact_id,
                        "budget_summary": self.model_gateway.get_budget_summary(),
                    },
                    completed_at=datetime.now(),
                )

            prose = generation_result.prose
            total_cost = total_cost + (generation_result.cost_usd or 0.0)
            stages_completed.append(WorkflowStage.GENERATION)

            # Stage 4: Delta extraction
            delta = self._extract_narrative_delta(
                prose=prose,
                contract=contract,
            )
            stages_completed.append(WorkflowStage.DELTA_EXTRACTION)

            # Stage 5: Quality validation
            quality_issues = self._validate_quality(
                prose=prose,
                delta=delta,
                contract=contract,
            )
            stages_completed.append(WorkflowStage.QUALITY_VALIDATION)

            # Stage 6: Canon commit (mock for now)
            canon_hash = self._commit_to_canon(
                chapter_id=contract.chapter_id,
                prose=prose,
                delta=delta,
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
                canon_commit_hash=canon_hash,
                stages_completed=stages_completed,
                error=None,
                execution_time_seconds=execution_time,
                total_cost_usd=total_cost,
                metadata={
                    "artifact_id": artifact.artifact_id,
                    "generation_request_id": generation_result.request_id,
                    "input_tokens": generation_result.input_tokens,
                    "output_tokens": generation_result.output_tokens,
                    "quality_issues": quality_issues,
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
                canon_commit_hash=None,
                stages_completed=stages_completed,
                error=WorkflowError(
                    stage=last_stage,
                    error_type="workflow_error",
                    message=str(e),
                    retryable=False,
                    failed_at=datetime.now(),
                ),
                execution_time_seconds=execution_time,
                total_cost_usd=total_cost,
                metadata={"budget_summary": self.model_gateway.get_budget_summary()},
                completed_at=datetime.now(),
            )

    def _extract_narrative_delta(
        self,
        prose: str,
        contract: ChapterContract,
    ) -> NarrativeDelta:
        """Extract NarrativeDelta from generated prose.

        For V2-020 MVP: create minimal delta with empty operations.
        RequiredTransition != Operation, so we return empty operations for now.
        Future: use LLM to extract actual SetFactOperation from prose.

        Args:
            prose: Generated prose
            contract: Chapter contract

        Returns:
            Extracted narrative delta
        """
        from ..domain.delta import DeltaId
        from ..domain.identity import ProjectId

        delta_uuid = str(uuid.uuid4())

        # V2-020 MVP: empty operations
        # Future: convert transitions to proper Operation instances
        operations: tuple[Operation, ...] = ()

        return NarrativeDelta(
            delta_id=DeltaId(delta_uuid),
            project_id=ProjectId("default-project"),
            operations=operations,
            source_chapter=contract.chapter_id,
            created_at=datetime.now(),
            authority="chapter_workflow_v2020",
            provenance=(("extraction_method", "contract_passthrough"),),
        )

    def _validate_quality(
        self,
        prose: str,
        delta: NarrativeDelta,
        contract: ChapterContract,
    ) -> list[str]:
        """Validate chapter quality.

        For V2-020 MVP: basic checks.
        Future: comprehensive quality gates.

        Args:
            prose: Generated prose
            delta: Narrative delta
            contract: Chapter contract

        Returns:
            List of quality issues (empty if all pass)
        """
        issues = []

        # Check 1: Prose not empty
        if not prose or len(prose.strip()) < 100:
            issues.append("Prose too short or empty")

        # Check 2: Delta operations match contract
        if len(delta.operations) != len(contract.required_transitions):
            issues.append("Delta operations count mismatch")

        # Check 3: No obvious errors in prose
        if "[ERROR]" in prose or "[FAILED]" in prose:
            issues.append("Error markers in prose")

        return issues

    def _commit_to_canon(
        self,
        chapter_id: str,
        prose: str,
        delta: NarrativeDelta,
        canon_snapshot: dict,
    ) -> str:
        """Commit chapter to canonical state.

        For V2-020 MVP: return mock hash.
        Future: actual canon repository commit.

        Args:
            chapter_id: Chapter ID
            prose: Generated prose
            delta: Narrative delta
            canon_snapshot: Current canon state

        Returns:
            Canon commit hash
        """
        import hashlib

        content = f"{chapter_id}:{prose[:100]}:{delta.delta_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
