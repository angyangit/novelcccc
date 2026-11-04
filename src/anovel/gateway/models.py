"""Model Gateway data models for V2-019.

Defines request/response structures for LLM provider interaction per ADR-010.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ResultStatus(Enum):
    """Result status distinguishing success, known failure, and unknown."""

    SUCCESS = "success"
    KNOWN_FAILURE = "known_failure"
    UNKNOWN = "unknown"


class CostStatus(Enum):
    """Cost accounting status per ADR-010."""

    CONFIRMED = "confirmed"  # Verified from provider
    INFLIGHT = "inflight"  # Reserved but not yet confirmed
    UNKNOWN_LIABILITY = "unknown_liability"  # Unconfirmed due to timeout/error


@dataclass(frozen=True)
class ModelUsage:
    """Token usage and cost information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    cost_status: CostStatus
    pricing_version: str  # e.g., "gpt-4-2024-11"


@dataclass(frozen=True)
class ModelRequest:
    """Logical model request (reusable across attempts)."""

    request_id: str  # Stable identifier for this logical request
    model_id: str  # Logical model identifier
    prompt: str
    system_prompt: str | None
    temperature: float
    max_tokens: int
    input_hash: str  # SHA-256 of semantic input for cache lookup
    context_metadata: dict[str, Any]  # Source contracts, artifacts, etc.


@dataclass(frozen=True)
class ModelAttempt:
    """Single attempt to fulfill a ModelRequest."""

    attempt_id: str
    request_id: str  # Links back to logical request
    attempt_number: int  # 1, 2, 3... for retries
    provider_name: str  # e.g., "anthropic", "openai"
    provider_model_id: str  # Actual provider model used
    provider_request_id: str | None  # Provider's tracking ID if available
    started_at: datetime
    completed_at: datetime | None
    result_status: ResultStatus
    response_text: str | None
    usage: ModelUsage | None
    error_message: str | None
    template_version: str  # Prompt template version used


@dataclass(frozen=True)
class ModelResponse:
    """Final response from Model Gateway."""

    request_id: str
    result_status: ResultStatus
    response_text: str | None
    attempts: list[ModelAttempt]
    total_cost_usd: float
    cost_status: CostStatus
    cache_hit: bool
