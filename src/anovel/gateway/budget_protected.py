"""Budget-protected Model Gateway for real API calls.

Implements $5 hard cap for Stage 9 testing.
"""

from anovel.gateway.anthropic_provider import AnthropicProvider
from anovel.gateway.gateway import ModelGateway


class BudgetProtectedGateway:
    """Gateway with hard budget cap for real model testing.

    Owner authorization: $5 total budget for Stage 9 testing.
    """

    def __init__(
        self,
        provider: AnthropicProvider,
        total_budget_usd: float = 5.0,
    ):
        """Initialize budget-protected gateway.

        Args:
            provider: Real Anthropic provider
            total_budget_usd: Hard budget cap (default: $5)
        """
        self.gateway = ModelGateway(provider, total_budget_usd)
        self.provider = provider
        self.total_budget_usd = total_budget_usd
        self.request_log: list[dict] = []

    def generate(
        self, prompt: str, max_tokens: int, **kwargs
    ) -> tuple[dict, float]:
        """Generate with budget check.

        Args:
            prompt: Input prompt
            max_tokens: Max output tokens
            **kwargs: Additional parameters

        Returns:
            Tuple of (result dict, actual cost)

        Raises:
            RuntimeError: If budget exceeded
        """
        # Estimate cost
        # Conservative estimate: assume full max_tokens usage
        input_tokens = len(prompt) // 4  # Rough estimate
        estimated_cost = self.provider.estimate_cost(input_tokens, max_tokens)

        # Check budget
        budget_status = self.gateway.check_budget(estimated_cost)
        if budget_status != "available":
            raise RuntimeError(
                f"Budget exceeded. Status: {budget_status}. "
                f"Spent: ${self.gateway.spent_usd:.4f} / ${self.total_budget_usd:.4f}"
            )

        # Reserve budget
        self.gateway.pending_usd += estimated_cost

        try:
            # Make real call
            result = self.provider.generate(prompt, max_tokens, **kwargs)

            # Calculate actual cost
            actual_cost = self.provider.estimate_cost(
                result["input_tokens"], result["output_tokens"]
            )

            # Update budget
            self.gateway.pending_usd -= estimated_cost
            self.gateway.spent_usd += actual_cost

            # Log request
            self.request_log.append(
                {
                    "prompt_length": len(prompt),
                    "max_tokens": max_tokens,
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                    "model": result["model"],
                    "estimated_cost": estimated_cost,
                    "actual_cost": actual_cost,
                }
            )

            return result, actual_cost

        except Exception as e:
            # Release reserved budget on error
            self.gateway.pending_usd -= estimated_cost
            raise e

    def get_budget_status(self) -> dict:
        """Get current budget status.

        Returns:
            Dict with spent, pending, remaining, total
        """
        return {
            "spent_usd": self.gateway.spent_usd,
            "pending_usd": self.gateway.pending_usd,
            "remaining_usd": self.total_budget_usd
            - self.gateway.spent_usd
            - self.gateway.pending_usd,
            "total_budget_usd": self.total_budget_usd,
            "requests_made": len(self.request_log),
        }

    def print_budget_report(self):
        """Print budget usage report."""
        status = self.get_budget_status()
        print()
        print("=" * 80)
        print("Budget Report")
        print("=" * 80)
        print(f"Total Budget: ${status['total_budget_usd']:.4f}")
        print(f"Spent: ${status['spent_usd']:.4f}")
        print(f"Pending: ${status['pending_usd']:.4f}")
        print(f"Remaining: ${status['remaining_usd']:.4f}")
        print(f"Requests Made: {status['requests_made']}")
        print()

        if self.request_log:
            print("Request Log:")
            print("-" * 80)
            for i, req in enumerate(self.request_log, 1):
                print(
                    f"{i}. Model: {req['model']}, "
                    f"Tokens: {req['input_tokens']}→{req['output_tokens']}, "
                    f"Cost: ${req['actual_cost']:.6f}"
                )
            print("-" * 80)
        print()
