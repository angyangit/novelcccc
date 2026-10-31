"""Model Gateway core implementation for V2-019.

Unified interface for AI model generation with budget control and error handling.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Any

from ..context.models import ContextArtifact
from .models import (
    BudgetStatus,
    GenerationError,
    GenerationResult,
    ProviderAdapter,
    RequestStatus,
)


class ModelGateway:
    """Unified gateway for AI model generation."""

    def __init__(
        self,
        provider: ProviderAdapter,
        total_budget_usd: float | None = None,
    ):
        """Initialize gateway with provider and budget.

        Args:
            provider: Model provider adapter
            total_budget_usd: Total budget in USD (None = no budget check)
        """
        self.provider = provider
        self.total_budget_usd = total_budget_usd
        self.spent_usd = 0.0
        self.pending_usd = 0.0
        self.unknown_pending_usd = 0.0
        self._request_history: dict[str, Any] = {}

    def check_budget(self, estimated_cost: float) -> BudgetStatus:
        """Check if budget allows this request.

        Args:
            estimated_cost: Estimated cost in USD

        Returns:
            Budget status
        """
        if self.total_budget_usd is None:
            return BudgetStatus.NO_BUDGET  # No budget configured

        available = (
            self.total_budget_usd
            - self.spent_usd
            - self.pending_usd
            - self.unknown_pending_usd
        )

        if estimated_cost <= available:
            return BudgetStatus.AVAILABLE
        else:
            return BudgetStatus.INSUFFICIENT

    def prepare_writer_prompt(self, artifact: ContextArtifact) -> str:
        """Convert ContextArtifact to writer prompt.

        Args:
            artifact: Compiled context artifact

        Returns:
            Formatted prompt for model
        """
        sections = []

        # System instructions
        sections.append(
            "You are an expert novelist writing a compelling, natural chapter."
        )

        # Required context items
        if artifact.required_items:
            sections.append("\n# REQUIRED CONTEXT\n")
            for item in artifact.required_items:
                if isinstance(item.content, str):
                    sections.append(f"## {item.rationale}\n{item.content}\n")
                else:
                    sections.append(f"## {item.rationale}\n{str(item.content)}\n")

        # Optional context items
        if artifact.optional_items:
            sections.append("\n# ADDITIONAL CONTEXT\n")
            for item in artifact.optional_items:
                if isinstance(item.content, str):
                    sections.append(f"- {item.rationale}: {item.content}\n")
                else:
                    sections.append(f"- {item.rationale}: {str(item.content)}\n")

        # Generation instructions
        sections.append("\n# TASK\n")
        sections.append(
            f"Write Chapter {artifact.chapter_number} ({artifact.chapter_id}) as engaging, "
            "natural prose. Follow all required constraints and continuity from previous chapter."
        )

        return "\n".join(sections)

    def generate_chapter(
        self,
        artifact: ContextArtifact,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> GenerationResult | GenerationError:
        """Generate chapter prose from context artifact.

        Args:
            artifact: Context artifact
            max_tokens: Maximum output tokens
            temperature: Generation temperature

        Returns:
            GenerationResult on success, GenerationError on failure
        """
        # Create request IDs
        request_id = str(uuid.uuid4())
        attempt_id = f"{request_id}-001"

        # Prepare prompt
        prompt = self.prepare_writer_prompt(artifact)
        context_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        # Estimate cost
        input_tokens = len(prompt) // 4  # Rough estimate
        estimated_cost = self.provider.estimate_cost(input_tokens, max_tokens)

        # Budget check
        budget_status = self.check_budget(estimated_cost)
        if budget_status == BudgetStatus.NO_BUDGET:
            return GenerationError(
                request_id=request_id,
                attempt_id=attempt_id,
                error_type="no_budget",
                message="No budget configured for model generation",
                retryable=False,
                failed_at=datetime.now(),
            )
        elif budget_status == BudgetStatus.INSUFFICIENT:
            return GenerationError(
                request_id=request_id,
                attempt_id=attempt_id,
                error_type="budget_insufficient",
                message=f"Insufficient budget: need ${estimated_cost:.4f}, "
                f"available ${self.total_budget_usd - self.spent_usd - self.pending_usd:.4f}",
                retryable=False,
                failed_at=datetime.now(),
            )

        # Mark as pending
        self.pending_usd += estimated_cost

        try:
            # Call provider
            response = self.provider.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Parse response
            if not response.get("finished"):
                raise ValueError("Incomplete response from provider")

            prose = response["prose"]
            actual_input_tokens = response.get("input_tokens", input_tokens)
            actual_output_tokens = response.get("output_tokens", len(prose) // 4)
            actual_cost = self.provider.estimate_cost(
                actual_input_tokens, actual_output_tokens
            )

            # Update budget
            self.pending_usd -= estimated_cost
            self.spent_usd += actual_cost

            # Create result hash
            response_hash = hashlib.sha256(prose.encode()).hexdigest()[:16]

            result = GenerationResult(
                request_id=request_id,
                attempt_id=attempt_id,
                model_id=response.get("model", "unknown"),
                prose=prose,
                response_hash=response_hash,
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                cost_usd=actual_cost,
                completed_at=datetime.now(),
                metadata={
                    "context_artifact_id": artifact.artifact_id,
                    "chapter_id": artifact.chapter_id,
                },
            )

            # Store in history
            self._request_history[request_id] = {
                "status": RequestStatus.SUCCESS,
                "result": result,
            }

            return result

        except TimeoutError as e:
            # Timeout - status UNKNOWN
            self.pending_usd -= estimated_cost
            self.unknown_pending_usd += estimated_cost

            error = GenerationError(
                request_id=request_id,
                attempt_id=attempt_id,
                error_type="timeout",
                message=f"Provider timeout: {str(e)}",
                retryable=True,
                failed_at=datetime.now(),
            )

            self._request_history[request_id] = {
                "status": RequestStatus.UNKNOWN,
                "error": error,
            }

            return error

        except Exception as e:
            # Other errors
            self.pending_usd -= estimated_cost

            error = GenerationError(
                request_id=request_id,
                attempt_id=attempt_id,
                error_type="provider_error",
                message=str(e),
                retryable="rate_limit" in str(e).lower(),
                failed_at=datetime.now(),
            )

            self._request_history[request_id] = {
                "status": RequestStatus.FAILED,
                "error": error,
            }

            return error

    def get_budget_summary(self) -> dict[str, float]:
        """Get current budget status.

        Returns:
            Dict with budget breakdown
        """
        available = 0.0
        if self.total_budget_usd is not None:
            available = (
                self.total_budget_usd
                - self.spent_usd
                - self.pending_usd
                - self.unknown_pending_usd
            )

        return {
            "total": self.total_budget_usd or 0.0,
            "spent": self.spent_usd,
            "pending": self.pending_usd,
            "unknown_pending": self.unknown_pending_usd,
            "available": available,
        }
