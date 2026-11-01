"""Data models for V2-020 Chapter Workflow."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class WorkflowStatus(StrEnum):
    """Workflow execution status."""

    SUCCESS = "success"  # All stages passed, canon committed
    FAILED = "failed"  # Hard failure, cannot proceed
    DRAFT_GENERATED = "draft_generated"  # Prose generated but not committed
    QUALITY_FAILED = "quality_failed"  # Quality checks failed
    EXTRACTION_FAILED = "extraction_failed"  # Delta extraction failed


class WorkflowStage(StrEnum):
    """Pipeline stages."""

    CONTRACT_COMPILE = "contract_compile"
    CONTEXT_COMPILE = "context_compile"
    GENERATION = "generation"
    DELTA_EXTRACTION = "delta_extraction"
    QUALITY_VALIDATION = "quality_validation"
    CANON_COMMIT = "canon_commit"


class CheckStatus(StrEnum):
    """Individual quality check status."""

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    ERROR = "error"
    NOT_RUN = "not_run"


@dataclass
class CheckDetail:
    """Detailed check execution result."""

    check_name: str
    status: CheckStatus
    message: str
    severity: str = "error"  # "error" | "warning"
    metadata: dict[str, Any] | None = None


@dataclass
class WorkflowError:
    """Workflow execution error."""

    stage: WorkflowStage
    error_type: str
    message: str
    retryable: bool
    failed_at: datetime
    context: dict[str, Any] | None = None


@dataclass
class QualityCheckResult:
    """Quality validation result with detailed check tracking."""

    passed: bool
    blocking_issues: list[str]  # Issues that block canon commit
    warnings: list[str]  # Non-blocking issues
    checks_run: list[str]  # Names of checks executed
    check_details: list[CheckDetail] | None = None  # Detailed results per check
    q0_passed: bool | None = None  # Q0 deterministic validation
    q1_passed: bool | None = None  # Q1 Canon consistency
    q2_passed: bool | None = None  # Q2 Genre rules
    q3_passed: bool | None = None  # Q3 Required transitions


@dataclass
class DeltaExtractionResult:
    """Delta extraction result."""

    success: bool
    delta: Any | None  # NarrativeDelta if successful
    prose_hash: str  # SHA-256 of prose content
    extraction_method: str
    issues: list[str]  # Extraction problems


@dataclass
class ChapterWorkflowResult:
    """Complete chapter workflow result.

    Status semantics:
    - SUCCESS: prose generated, quality passed, canon committed
    - DRAFT_GENERATED: prose generated but not committed (quality pending or failed)
    - QUALITY_FAILED: prose generated but quality checks blocked commit
    - EXTRACTION_FAILED: prose generated but delta extraction failed
    - FAILED: hard failure before prose generation
    """

    workflow_id: str
    chapter_id: str
    chapter_number: int
    status: WorkflowStatus
    prose: str | None
    prose_hash: str | None  # SHA-256 of prose if generated
    canon_commit_hash: str | None  # None unless actually committed
    is_mock_commit: bool  # True if canon_commit_hash is mock, not real
    stages_completed: list[WorkflowStage]
    error: WorkflowError | None
    quality_result: QualityCheckResult | None
    delta_result: DeltaExtractionResult | None
    execution_time_seconds: float
    total_cost_usd: float
    metadata: dict[str, Any]
    completed_at: datetime
