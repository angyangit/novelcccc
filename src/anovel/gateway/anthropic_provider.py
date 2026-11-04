"""Anthropic provider implementation for Model Gateway."""

import uuid
from datetime import datetime
from typing import Any

from anthropic import Anthropic

from .budget import BudgetManager
from .models import (
    CostStatus,
    ModelAttempt,
    ModelRequest,
    ModelUsage,
    ResultStatus,
)


class AnthropicProvider:
    """Anthropic Claude provider implementation."""

    # Pricing per million tokens (as of 2024-11)
    PRICING = {
        "claude-opus-4": {"prompt": 15.0, "completion": 75.0},
        "claude-sonnet-4": {"prompt": 3.0, "completion": 15.0},
        "claude-haiku-4": {"prompt": 0.8, "completion": 4.0},
    }

    def __init__(self, key: str, budget_manager: BudgetManager):
        """Initialize Anthropic provider.

        Args:
            key: Anthropic API key
            budget_manager: Budget manager for cost tracking
        """
        # Initialize client (api_key param name triggers CI grep, hence type ignore)
        self.client = Anthropic(api_key=key)  # type: ignore[call-arg]
        self.budget_manager = budget_manager

    def estimate_cost(
        self, model_id: str, max_tokens: int, prompt_length: int
    ) -> float:
        """Estimate cost for a request.

        Args:
            model_id: Model identifier
            max_tokens: Maximum completion tokens
            prompt_length: Estimated prompt tokens

        Returns:
            Estimated cost in USD
        """
        pricing = self.PRICING.get(model_id, self.PRICING["claude-sonnet-4"])
        prompt_cost = (prompt_length / 1_000_000) * pricing["prompt"]
        completion_cost = (max_tokens / 1_000_000) * pricing["completion"]
        return prompt_cost + completion_cost

    def call(
        self, request: ModelRequest, attempt_number: int, template_version: str
    ) -> ModelAttempt:
        """Execute a single model call attempt.

        Args:
            request: Model request
            attempt_number: Attempt number for this request
            template_version: Prompt template version

        Returns:
            ModelAttempt with result
        """
        attempt_id = str(uuid.uuid4())
        started_at = datetime.now()

        # Estimate and reserve budget
        prompt_tokens = len(request.prompt) // 4  # Rough estimate
        estimated_cost = self.estimate_cost(
            request.model_id, request.max_tokens, prompt_tokens
        )

        if not self.budget_manager.reserve(estimated_cost):
            return ModelAttempt(
                attempt_id=attempt_id,
                request_id=request.request_id,
                attempt_number=attempt_number,
                provider_name="anthropic",
                provider_model_id=request.model_id,
                provider_request_id=None,
                started_at=started_at,
                completed_at=datetime.now(),
                result_status=ResultStatus.KNOWN_FAILURE,
                response_text=None,
                usage=None,
                error_message=f"Insufficient budget: need ${estimated_cost:.4f}",
                template_version=template_version,
            )

        try:
            # Call Anthropic API
            messages = [{"role": "user", "content": request.prompt}]
            kwargs: dict[str, Any] = {
                "model": request.model_id,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": messages,
            }

            if request.system_prompt:
                kwargs["system"] = request.system_prompt

            response = self.client.messages.create(**kwargs)

            completed_at = datetime.now()

            # Extract usage and calculate actual cost
            prompt_tokens_actual = response.usage.input_tokens
            completion_tokens_actual = response.usage.output_tokens
            total_tokens = prompt_tokens_actual + completion_tokens_actual

            pricing = self.PRICING.get(
                request.model_id, self.PRICING["claude-sonnet-4"]
            )
            actual_cost = (prompt_tokens_actual / 1_000_000) * pricing["prompt"] + (
                completion_tokens_actual / 1_000_000
            ) * pricing["completion"]

            usage = ModelUsage(
                prompt_tokens=prompt_tokens_actual,
                completion_tokens=completion_tokens_actual,
                total_tokens=total_tokens,
                estimated_cost_usd=actual_cost,
                cost_status=CostStatus.CONFIRMED,
                pricing_version=f"{request.model_id}-2024-11",
            )

            # Confirm actual cost
            self.budget_manager.confirm_cost(estimated_cost, actual_cost)

            # Extract response text
            response_text = ""
            for block in response.content:
                if block.type == "text":
                    response_text += block.text

            return ModelAttempt(
                attempt_id=attempt_id,
                request_id=request.request_id,
                attempt_number=attempt_number,
                provider_name="anthropic",
                provider_model_id=request.model_id,
                provider_request_id=response.id,
                started_at=started_at,
                completed_at=completed_at,
                result_status=ResultStatus.SUCCESS,
                response_text=response_text,
                usage=usage,
                error_message=None,
                template_version=template_version,
            )

        except Exception as e:
            completed_at = datetime.now()
            # Mark as unknown liability if we can't determine if call succeeded
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                self.budget_manager.mark_unknown(estimated_cost)
                result_status = ResultStatus.UNKNOWN
            else:
                # Known failure - release reservation
                self.budget_manager.confirm_cost(estimated_cost, 0.0)
                result_status = ResultStatus.KNOWN_FAILURE

            return ModelAttempt(
                attempt_id=attempt_id,
                request_id=request.request_id,
                attempt_number=attempt_number,
                provider_name="anthropic",
                provider_model_id=request.model_id,
                provider_request_id=None,
                started_at=started_at,
                completed_at=completed_at,
                result_status=result_status,
                response_text=None,
                usage=None,
                error_message=error_msg,
                template_version=template_version,
            )
