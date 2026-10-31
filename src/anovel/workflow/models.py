"""Data models for V2-020 Chapter Workflow."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class WorkflowStatus(StrEnum):
    """Workflow execution status."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class WorkflowStage(StrEnum):
    """Pipeline stages."""

    CONTRACT_COMPILE = "contract_compile"
    CONTEXT_COMPILE = "context_compile"
    GENERATION = "generation"
    DELTA_EXTRACTION = "delta_extraction"
    QUALITY_VALIDATION = "quality_validation"
    CANON_COMMIT = "canon_commit"


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
class ChapterWorkflowResult:
    """Complete chapter workflow result."""

    workflow_id: str
    chapter_id: str
    chapter_number: int
    status: WorkflowStatus
    prose: str | None
    canon_commit_hash: str | None
    stages_completed: list[WorkflowStage]
    error: WorkflowError | None
    execution_time_seconds: float
    total_cost_usd: float
    metadata: dict[str, Any]
    completed_at: datetime
