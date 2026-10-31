"""Mock provider for testing without paid API calls."""

from typing import Any


class MockProvider:
    """Mock provider for integration tests."""

    def __init__(self, mode: str = "success"):
        """Initialize mock provider.

        Args:
            mode: "success", "timeout", "rate_limit", "invalid_response"
        """
        self.mode = mode
        self.call_count = 0

    def generate(self, prompt: str, max_tokens: int, **kwargs) -> dict[str, Any]:
        """Generate mock response."""
        self.call_count += 1

        if self.mode == "timeout":
            raise TimeoutError("Mock timeout")
        elif self.mode == "rate_limit":
            raise RuntimeError("Rate limit exceeded")
        elif self.mode == "invalid_response":
            return {"incomplete": "data"}

        # Success mode
        return {
            "prose": f"[MOCK CHAPTER PROSE]\n\nGenerated from prompt with {len(prompt)} chars.",
            "input_tokens": len(prompt) // 4,
            "output_tokens": max_tokens // 2,
            "model": "mock-model-v1",
            "finished": True,
        }

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate mock cost."""
        return (input_tokens * 0.01 + output_tokens * 0.03) / 1000
