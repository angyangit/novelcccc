"""Gateway data models for V2-019."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class RequestStatus(StrEnum):
    """Generation request status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"  # Timeout or unconfirmed state
    TIMEOUT = "timeout"


class BudgetStatus(StrEnum):
    """Budget check status."""
    AVAILABLE = "available"
    INSUFFICIENT = "insufficient"
    NO_BUDGET = "no_budget"
    UNKNOWN_PENDING = "unknown_pending"  # Awaiting confirmation


@dataclass(frozen=True)
class GenerationRequest:
    """Request to generate chapter prose."""
    request_id: str
    attempt_id: str  # For retry tracking
    context_artifact_id: str
    context_hash: str
    model_id: str
    max_tokens: int
    temperature: float = 0.7
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResult:
    """Successful generation result."""
    request_id: str
    attempt_id: str
    model_id: str
    prose: str
    response_hash: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    completed_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationError:
    """Generation error diagnostic."""
    request_id: str
    attempt_id: str
    error_type: str  # "timeout", "rate_limit", "auth", "budget", "invalid_response"
    message: str
    retryable: bool
    failed_at: datetime


class ProviderAdapter(Protocol):
    """Protocol for model provider adapters."""

    def generate(self, prompt: str, max_tokens: int, **kwargs) -> dict[str, Any]:
        """Generate text from prompt."""
        ...

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate generation cost in USD."""
        ...
