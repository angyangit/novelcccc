"""Model Gateway for V2-019 per ADR-010.

Provides unified interface to LLM providers with budget management,
attempt tracking, and proper UNKNOWN handling.
"""

import hashlib
import uuid
from typing import Any

from .anthropic_provider import AnthropicProvider
from .budget import BudgetManager
from .config import load_model_settings
from .models import (
    CostStatus,
    ModelRequest,
    ModelResponse,
    ResultStatus,
)


class ModelGateway:
    """Main Model Gateway managing provider calls and budget."""

    def __init__(
        self,
        anthropic_key: str | None = None,
        budget_limit_usd: float = 100.0,
        max_retries: int = 3,
        anthropic_base_url: str | None = None,
        effort_level: str | None = None,
    ):
        """Initialize Model Gateway.

        Args:
            anthropic_key: Anthropic API key (None for testing)
            budget_limit_usd: Total budget limit in USD
            max_retries: Maximum retry attempts per request
        """
        self.budget_manager = BudgetManager(budget_limit_usd)
        self.max_retries = max_retries
        self.template_version = "v1.0"
        self.configured_model_id: str | None = None

        # Initialize providers
        self.anthropic_provider = (
            AnthropicProvider(
                anthropic_key,
                self.budget_manager,
                base_url=anthropic_base_url,
                effort_level=effort_level,
            )
            if anthropic_key
            else None
        )

        # Simple in-memory cache (production would use persistent cache)
        self._cache: dict[str, ModelResponse] = {}

    @classmethod
    def from_project_env(
        cls, budget_limit_usd: float = 5.0, max_retries: int = 1
    ) -> "ModelGateway":
        """Build a real model gateway from the one existing root .env only."""
        settings = load_model_settings()
        gateway = cls(
            anthropic_key=settings.auth_token,
            budget_limit_usd=budget_limit_usd,
            max_retries=max_retries,
            anthropic_base_url=settings.base_url,
            effort_level=settings.effort_level,
        )
        gateway.configured_model_id = settings.model_id
        return gateway

    def _compute_input_hash(self, request: ModelRequest) -> str:
        """Compute hash of semantic input for cache lookup."""
        content = f"{request.model_id}:{request.temperature}:{request.max_tokens}:"
        content += f"{request.prompt}:{request.system_prompt or ''}"
        return hashlib.sha256(content.encode()).hexdigest()

    def generate(
        self,
        model_id: str,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 1.0,
        max_tokens: int = 4000,
        context_metadata: dict[str, Any] | None = None,
    ) -> ModelResponse:
        """Generate text from LLM with budget management and retry logic.

        Args:
            model_id: Model identifier (e.g., "claude-sonnet-4")
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum completion tokens
            context_metadata: Metadata about request source

        Returns:
            ModelResponse with result and attempt history

        Raises:
            RuntimeError: If no provider available or budget exhausted
        """
        if self.configured_model_id is not None and model_id != self.configured_model_id:
            raise ValueError("Model ID must match CC_VIBE_ANTHROPIC_MODEL in root .env")

        # Create logical request
        request_id = str(uuid.uuid4())
        request = ModelRequest(
            request_id=request_id,
            model_id=model_id,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            input_hash=self._compute_input_hash(
                ModelRequest(
                    request_id="",
                    model_id=model_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    input_hash="",
                    context_metadata={},
                )
            ),
            context_metadata=context_metadata or {},
        )

        # Check cache
        if request.input_hash in self._cache:
            cached = self._cache[request.input_hash]
            # Return cached response with new request_id but same content
            return ModelResponse(
                request_id=request_id,
                result_status=cached.result_status,
                response_text=cached.response_text,
                attempts=[],  # Don't duplicate attempt history
                total_cost_usd=0.0,  # No new cost for cache hit
                cost_status=CostStatus.CONFIRMED,
                cache_hit=True,
            )

        # Execute attempts
        if not self.anthropic_provider:
            raise RuntimeError("No provider configured - set anthropic_key")

        attempts = []
        for attempt_num in range(1, self.max_retries + 1):
            attempt = self.anthropic_provider.call(
                request, attempt_num, self.template_version
            )
            attempts.append(attempt)

            if attempt.result_status == ResultStatus.SUCCESS:
                # Success - cache and return
                total_cost = sum(
                    a.usage.estimated_cost_usd for a in attempts if a.usage
                )
                response = ModelResponse(
                    request_id=request_id,
                    result_status=ResultStatus.SUCCESS,
                    response_text=attempt.response_text,
                    attempts=attempts,
                    total_cost_usd=total_cost,
                    cost_status=CostStatus.CONFIRMED,
                    cache_hit=False,
                )
                self._cache[request.input_hash] = response
                return response

            if attempt.result_status == ResultStatus.UNKNOWN:
                # Unknown result - don't retry (may have succeeded on server)
                total_cost = sum(
                    a.usage.estimated_cost_usd if a.usage else 0.0 for a in attempts
                )
                return ModelResponse(
                    request_id=request_id,
                    result_status=ResultStatus.UNKNOWN,
                    response_text=None,
                    attempts=attempts,
                    total_cost_usd=total_cost,
                    cost_status=CostStatus.UNKNOWN_LIABILITY,
                    cache_hit=False,
                )

            # Known failure - continue to retry if attempts remaining

        # All retries exhausted
        total_cost = sum(
            a.usage.estimated_cost_usd if a.usage else 0.0 for a in attempts
        )
        return ModelResponse(
            request_id=request_id,
            result_status=ResultStatus.KNOWN_FAILURE,
            response_text=None,
            attempts=attempts,
            total_cost_usd=total_cost,
            cost_status=CostStatus.CONFIRMED,
            cache_hit=False,
        )
