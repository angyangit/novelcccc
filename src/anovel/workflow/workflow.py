"""Core Chapter Workflow orchestration for V2-020/V2-021/V2-022."""

import hashlib
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..context.compiler import ContextCompiler
from ..context.models import ContextCompilationError
from ..contracts.compiler import ContractCompiler
from ..contracts.models import ChapterContract
from ..domain.delta import NarrativeDelta
from ..gateway.gateway import ModelGateway
from ..gateway.models import GenerationError
from ..planning.models import SeriesVision
from .extractor import NarrativeDeltaExtractionResult, NarrativeDeltaExtractor
from .models import (
    ChapterWorkflowResult,
    DeltaExtractionResult,
    QualityCheckResult,
    WorkflowError,
    WorkflowStage,
    WorkflowStatus,
)

if TYPE_CHECKING:
    from ..quality.q0 import Q0Validator


class ChapterWorkflow:
    """Orchestrates single chapter generation workflow."""

    def __init__(
        self,
        contract_compiler: ContractCompiler,
        context_compiler: ContextCompiler,
        model_gateway: ModelGateway,
        extractor: NarrativeDeltaExtractor
        | None = None,  # V2-021: injectable extractor
        q0_validator: "Q0Validator | None" = None,  # V2-022: Q0 deterministic validator
        q1_validator: Any | None = None,  # V2-023: Q1 Canon validator
        q2_validator: Any | None = None,  # V2-024: Q2 Genre validator
        q3_validator: Any | None = None,  # V2-025: Q3 Transition validator
        mock_mode: bool = True,  # True = mock canon commits, False = real commits
    ):
        """Initialize workflow with required components.

        Args:
            contract_compiler: Contract compiler (V2-017)
            context_compiler: Context compiler (V2-018)
            model_gateway: Model gateway (V2-019)
            extractor: Narrative delta extractor (V2-021), None = use legacy stub
            q0_validator: Q0 deterministic validator (V2-022), None = create default
            q1_validator: Q1 Canon validator (V2-023), None = create default
            q2_validator: Q2 Genre validator (V2-024), None = create default
            q3_validator: Q3 Transition validator (V2-025), None = create default
            mock_mode: If True, use mock canon commits (NOT production)
        """
        self.contract_compiler = contract_compiler
        self.context_compiler = context_compiler
        self.model_gateway = model_gateway
        self.extractor = extractor  # V2-021: new injected extractor

        # V2-022: Q0 validator (lazy import to avoid circular dependency)
        if q0_validator is None:
            from ..quality.q0 import Q0Validator

            q0_validator = Q0Validator()
        self.q0_validator = q0_validator

        # V2-023: Q1 Canon validator
        if q1_validator is None:
            from ..quality.q1 import Q1CanonValidator

            q1_validator = Q1CanonValidator()
        self.q1_validator = q1_validator

        # V2-024: Q2 Genre validator
        if q2_validator is None:
            from ..quality.q2 import Q2GenreValidator

            q2_validator = Q2GenreValidator()
        self.q2_validator = q2_validator

        # V2-025: Q3 Transition validator
        if q3_validator is None:
            from ..quality.q3 import Q3TransitionValidator

            q3_validator = Q3TransitionValidator()
        self.q3_validator = q3_validator

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

            # Store full extraction result for Q0 validation (V2-022)
            full_extraction_result = getattr(delta_result, "_full_result", None)

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
                extraction_result=full_extraction_result,  # V2-022: Pass to Q0
                canon_snapshot=canon_snapshot,  # V2-023: Pass to Q1/Q3
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
            last_stage = (
                stages_completed[-1]
                if stages_completed
                else WorkflowStage.CONTRACT_COMPILE
            )

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
            delta_result = DeltaExtractionResult(
                success=(extraction_result.status == "success"),
                delta=extraction_result.delta,
                prose_hash=extraction_result.prose_hash,
                extraction_method=extraction_result.extraction_method,
                issues=extraction_result.issues,
            )
            # Attach full result for Q0 validation (V2-022)
            delta_result._full_result = extraction_result  # type: ignore
            return delta_result

        # Legacy V2-020 stub (for backward compatibility)
        return self._legacy_extraction_stub(prose, prose_hash, contract, series_vision)

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
        extraction_result: NarrativeDeltaExtractionResult | None = None,
        canon_snapshot: dict | None = None,
    ) -> QualityCheckResult:
        """Validate chapter quality with fail-closed gates.

        FAIL-CLOSED: Any blocking issue prevents canon commit.

        Args:
            prose: Generated prose
            prose_hash: SHA-256 of prose
            delta: Narrative delta (may be None if extraction failed)
            contract: Chapter contract
            extraction_result: Full extraction result for Q0 validation (V2-022)
            canon_snapshot: Canon state for Q1/Q3 validation (V2-023/V2-025)

        Returns:
            Quality check result with passed=True only if all checks pass
        """
        from .models import CheckDetail, CheckStatus

        blocking_issues = []
        warnings = []
        checks_run = []
        check_details = []
        q0_passed = None
        q1_passed = None
        q2_passed = None
        q3_passed = None

        # Q0 VALIDATION (V2-022): Deterministic checks FIRST
        if extraction_result:
            checks_run.append("q0_validation")
            try:
                q0_result = self.q0_validator.validate(
                    extraction_result, contract, prose, prose_hash
                )
                q0_passed = q0_result.passed

                # Record detailed check results
                for check in q0_result.checks:
                    check_details.append(
                        CheckDetail(
                            check_name=f"Q0-{check.check_name}",
                            status=CheckStatus.PASS
                            if check.status == "pass"
                            else CheckStatus.FAIL
                            if check.status == "fail"
                            else CheckStatus.UNKNOWN,
                            message=check.message,
                            severity="error",  # Q0 checks are always blocking
                        )
                    )

                if not q0_result.passed:
                    blocking_issues.extend(q0_result.blocking_issues)
            except Exception as e:
                q0_passed = False
                blocking_issues.append(f"Q0 validation error: {e}")
                check_details.append(
                    CheckDetail(
                        check_name="Q0-execution",
                        status=CheckStatus.ERROR,
                        message=str(e),
                        severity="error",
                    )
                )
        else:
            check_details.append(
                CheckDetail(
                    check_name="Q0-validation",
                    status=CheckStatus.NOT_RUN,
                    message="No extraction result available",
                    severity="error",
                )
            )
            blocking_issues.append("Q0 validation not run: no extraction result")

        # Q1 VALIDATION (V2-023): Canon consistency checks
        if delta and canon_snapshot:
            checks_run.append("q1_canon_validation")
            try:
                from ..domain.delta import CanonState
                from ..domain.identity import ProjectId

                # Convert canon_snapshot to proper CanonState
                if isinstance(canon_snapshot, dict):
                    # Extract project_id from canon_snapshot or delta
                    if "project_id" in canon_snapshot:
                        project_id = ProjectId(canon_snapshot["project_id"])
                    elif delta and delta.operations:
                        # Extract from first operation's subject
                        project_id = delta.operations[0].subject.project_id
                    else:
                        # Fallback: use generic identifier
                        project_id = ProjectId("unknown")

                    # Create CanonState with proper structure
                    canon_state = CanonState(
                        project_id=project_id,
                        facts=canon_snapshot.get("facts", ()),
                        tombstones=canon_snapshot.get("tombstones", frozenset()),
                        commit_history=canon_snapshot.get("commit_history", ()),
                    )
                else:
                    canon_state = canon_snapshot

                q1_result = self.q1_validator.validate(delta, canon_state, contract)
                q1_passed = q1_result.passed

                # Record Q1 check details
                for check in q1_result.checks:
                    check_details.append(
                        CheckDetail(
                            check_name=f"Q1-{check.check_name}",
                            status=CheckStatus.PASS
                            if check.status == "pass"
                            else CheckStatus.FAIL
                            if check.status == "fail"
                            else CheckStatus.UNKNOWN,
                            message=check.message,
                            severity=check.severity,
                        )
                    )

                if not q1_result.passed:
                    blocking_issues.extend(q1_result.blocking_issues)
                warnings.extend(q1_result.warnings)
            except Exception as e:
                q1_passed = False
                blocking_issues.append(f"Q1 validation error: {e}")
                check_details.append(
                    CheckDetail(
                        check_name="Q1-execution",
                        status=CheckStatus.ERROR,
                        message=str(e),
                        severity="error",
                    )
                )
        elif delta:
            check_details.append(
                CheckDetail(
                    check_name="Q1-validation",
                    status=CheckStatus.NOT_RUN,
                    message="No canon snapshot available",
                    severity="error",
                )
            )
            blocking_issues.append("Q1 validation not run: no canon snapshot")

        # Q2 VALIDATION (V2-024): Genre consistency checks
        if delta:
            checks_run.append("q2_genre_validation")
            try:
                q2_result = self.q2_validator.validate(delta, contract)
                q2_passed = q2_result.passed

                # Record Q2 check details
                for check in q2_result.checks:
                    check_details.append(
                        CheckDetail(
                            check_name=f"Q2-{check.check_name}",
                            status=CheckStatus.PASS
                            if check.status == "pass"
                            else CheckStatus.FAIL
                            if check.status == "fail"
                            else CheckStatus.UNKNOWN,
                            message=check.message,
                            severity=check.severity,
                        )
                    )

                if not q2_result.passed:
                    blocking_issues.extend(q2_result.blocking_issues)
                warnings.extend(q2_result.warnings)
            except Exception as e:
                q2_passed = False
                warnings.append(f"Q2 validation error: {e}")
                check_details.append(
                    CheckDetail(
                        check_name="Q2-execution",
                        status=CheckStatus.ERROR,
                        message=str(e),
                        severity="warning",  # Q2 not fully implemented yet
                    )
                )

        # Q3 VALIDATION (V2-025): Transition checks
        if delta and canon_snapshot:
            checks_run.append("q3_transition_validation")
            try:
                from ..domain.delta import CanonState
                from ..domain.identity import ProjectId

                if isinstance(canon_snapshot, dict):
                    # Extract project_id from canon_snapshot or delta
                    if "project_id" in canon_snapshot:
                        project_id = ProjectId(canon_snapshot["project_id"])
                    elif delta and delta.operations:
                        # Extract from first operation's subject
                        project_id = delta.operations[0].subject.project_id
                    else:
                        # Fallback: use generic identifier
                        project_id = ProjectId("unknown")

                    canon_state = CanonState(
                        project_id=project_id,
                        facts=canon_snapshot.get("facts", ()),
                        tombstones=canon_snapshot.get("tombstones", frozenset()),
                        commit_history=canon_snapshot.get("commit_history", ()),
                    )
                else:
                    canon_state = canon_snapshot

                q3_result = self.q3_validator.validate(delta, canon_state, contract)
                q3_passed = q3_result.passed

                # Record Q3 check details
                for check in q3_result.checks:
                    check_details.append(
                        CheckDetail(
                            check_name=f"Q3-{check.check_name}",
                            status=CheckStatus.PASS
                            if check.status == "pass"
                            else CheckStatus.FAIL
                            if check.status == "fail"
                            else CheckStatus.UNKNOWN,
                            message=check.message,
                            severity=check.severity,
                        )
                    )

                if not q3_result.passed:
                    blocking_issues.extend(q3_result.blocking_issues)
                warnings.extend(q3_result.warnings)
            except Exception as e:
                q3_passed = False
                blocking_issues.append(f"Q3 validation error: {e}")
                check_details.append(
                    CheckDetail(
                        check_name="Q3-execution",
                        status=CheckStatus.ERROR,
                        message=str(e),
                        severity="error",
                    )
                )
        elif delta:
            check_details.append(
                CheckDetail(
                    check_name="Q3-validation",
                    status=CheckStatus.NOT_RUN,
                    message="No canon snapshot available",
                    severity="error",
                )
            )
            blocking_issues.append("Q3 validation not run: no canon snapshot")

        # Check 1: Prose minimum length (BLOCKING)
        checks_run.append("prose_minimum_length")
        prose_length = len(prose.strip()) if prose else 0
        if prose_length < 100:
            blocking_issues.append("Prose too short (< 100 chars)")
            check_details.append(
                CheckDetail(
                    check_name="basic-prose_length",
                    status=CheckStatus.FAIL,
                    message=f"Prose length {prose_length} < 100 chars",
                    severity="error",
                    metadata={"actual_length": prose_length, "min_required": 100},
                )
            )
        else:
            check_details.append(
                CheckDetail(
                    check_name="basic-prose_length",
                    status=CheckStatus.PASS,
                    message=f"Prose length {prose_length} chars",
                    severity="error",
                    metadata={"actual_length": prose_length},
                )
            )

        # Check 2: No error markers in prose (BLOCKING)
        checks_run.append("no_error_markers")
        error_markers = ["[ERROR]", "[FAILED]", "[MOCK CHAPTER PROSE]"]
        found_markers = [m for m in error_markers if m in prose]
        if found_markers:
            for marker in found_markers:
                blocking_issues.append(f"Error marker found in prose: {marker}")
            check_details.append(
                CheckDetail(
                    check_name="basic-no_error_markers",
                    status=CheckStatus.FAIL,
                    message=f"Found error markers: {', '.join(found_markers)}",
                    severity="error",
                    metadata={"markers_found": found_markers},
                )
            )
        else:
            check_details.append(
                CheckDetail(
                    check_name="basic-no_error_markers",
                    status=CheckStatus.PASS,
                    message="No error markers found",
                    severity="error",
                )
            )

        # Check 3: Delta operations present if contract requires transitions (BLOCKING)
        checks_run.append("delta_operations_present")
        if delta and contract.required_transitions:
            op_count = len(delta.operations)
            required_count = len(contract.required_transitions)
            if op_count == 0:
                blocking_issues.append(
                    f"Contract requires {required_count} transitions "
                    "but delta has 0 operations (extraction failed or not implemented)"
                )
                check_details.append(
                    CheckDetail(
                        check_name="basic-delta_operations",
                        status=CheckStatus.FAIL,
                        message=f"No operations extracted (required: {required_count})",
                        severity="error",
                        metadata={"operations": 0, "required": required_count},
                    )
                )
            elif op_count != required_count:
                warnings.append(
                    f"Delta operations count ({op_count}) "
                    f"!= contract transitions ({required_count})"
                )
                check_details.append(
                    CheckDetail(
                        check_name="basic-delta_operations",
                        status=CheckStatus.PASS,
                        message=f"Operations extracted: {op_count} (required: {required_count})",
                        severity="warning",
                        metadata={"operations": op_count, "required": required_count},
                    )
                )
            else:
                check_details.append(
                    CheckDetail(
                        check_name="basic-delta_operations",
                        status=CheckStatus.PASS,
                        message=f"Operations match required: {op_count}",
                        severity="error",
                        metadata={"operations": op_count, "required": required_count},
                    )
                )
        elif contract.required_transitions:
            check_details.append(
                CheckDetail(
                    check_name="basic-delta_operations",
                    status=CheckStatus.NOT_RUN,
                    message="No delta available for validation",
                    severity="error",
                )
            )

        # Check 4: Prose hash bound to delta (WARNING)
        checks_run.append("prose_hash_binding")
        if delta:
            provenance_dict = dict(delta.provenance)
            delta_prose_hash = provenance_dict.get("prose_hash")
            if delta_prose_hash != prose_hash:
                warnings.append("Delta not bound to current prose hash")
                check_details.append(
                    CheckDetail(
                        check_name="basic-prose_hash_binding",
                        status=CheckStatus.FAIL,
                        message=f"Hash mismatch: delta={delta_prose_hash[:16]}... vs current={prose_hash[:16]}...",
                        severity="warning",
                        metadata={
                            "delta_hash": delta_prose_hash,
                            "current_hash": prose_hash,
                        },
                    )
                )
            else:
                check_details.append(
                    CheckDetail(
                        check_name="basic-prose_hash_binding",
                        status=CheckStatus.PASS,
                        message="Delta bound to current prose",
                        severity="warning",
                    )
                )

        # FAIL-CLOSED: passed only if NO blocking issues
        passed = len(blocking_issues) == 0

        return QualityCheckResult(
            passed=passed,
            blocking_issues=blocking_issues,
            warnings=warnings,
            checks_run=checks_run,
            check_details=check_details,
            q0_passed=q0_passed,
            q1_passed=q1_passed,
            q2_passed=q2_passed,
            q3_passed=q3_passed,
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
            content = (
                f"{chapter_id}:{prose_hash}:{delta.delta_id if delta else 'no-delta'}"
            )
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
