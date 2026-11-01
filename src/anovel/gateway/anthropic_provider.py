"""Anthropic Provider Adapter for V2-019 Gateway.

Real Anthropic API integration with offline testing support.
"""

import json
import os
from typing import Any, Protocol

try:
    import requests
except ImportError:
    requests = None  # type: ignore


class HTTPClient(Protocol):
    """Protocol for HTTP client (real or fake)."""

    def post(self, url: str, headers: dict, json: dict) -> dict[str, Any]:
        """Post request and return JSON response."""
        ...


class AnthropicProvider:
    """Anthropic Claude API provider adapter.

    Supports real API calls and offline testing via injected HTTP client.
    """

    # Official Anthropic API pricing (as of 2024)
    # https://www.anthropic.com/api
    PRICING = {
        "claude-opus-4": {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
        "claude-sonnet-3-5": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
        "claude-haiku-3": {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000},
    }

    def __init__(
        self,
        model_id: str = "claude-sonnet-3-5-20241022",
        api_key: str | None = None,
        base_url: str | None = None,
        http_client: HTTPClient | None = None,
        allow_real_calls: bool = False,
    ):
        """Initialize Anthropic provider.

        Args:
            model_id: Claude model identifier
            api_key: Anthropic API key (or None to read from env)
            base_url: API base URL (default: https://api.anthropic.com)
            http_client: HTTP client for requests (None = use real requests)
            allow_real_calls: If False, raises error on real API attempts
        """
        self.model_id = model_id
        self.allow_real_calls = allow_real_calls
        self.call_count = 0

        # API key handling
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.api_key = api_key

        # Base URL handling
        if base_url is None:
            base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        self.base_url = base_url.rstrip("/")

        # HTTP client (real or fake)
        if http_client is not None:
            self.http_client = http_client
            self.use_fake_client = True
        else:
            self.use_fake_client = False
            # Real client would be initialized here

    def generate(self, prompt: str, max_tokens: int, **kwargs) -> dict[str, Any]:
        """Generate text using Claude API.

        Args:
            prompt: Input prompt
            max_tokens: Maximum output tokens
            **kwargs: Additional parameters (temperature, etc.)

        Returns:
            Response dict with: prose, input_tokens, output_tokens, model, finished

        Raises:
            RuntimeError: If real calls not allowed and no fake client
        """
        self.call_count += 1

        # Use fake client if provided
        if self.use_fake_client:
            return self._generate_with_fake_client(prompt, max_tokens, **kwargs)

        # Real API call
        if not self.allow_real_calls:
            raise RuntimeError(
                "Real Anthropic API calls disabled. "
                "Set allow_real_calls=True or provide http_client for testing."
            )

        if not self.api_key:
            raise RuntimeError(
                "API key not set. Cannot make real API calls."
            )

        if requests is None:
            raise RuntimeError(
                "requests library not available. Install with: pip install requests"
            )

        # Make real API call
        return self._generate_with_real_api(prompt, max_tokens, **kwargs)

    def _generate_with_real_api(
        self, prompt: str, max_tokens: int, **kwargs
    ) -> dict[str, Any]:
        """Generate using real HTTP API call."""
        temperature = kwargs.get("temperature", 0.7)

        # Build Anthropic API request format
        request_data = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        # Make HTTP POST request
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            response = requests.post(
                url, headers=headers, json=request_data, timeout=120
            )
            response.raise_for_status()
            response_data = response.json()
        except requests.exceptions.Timeout:
            raise TimeoutError(f"API request timed out after 120 seconds")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"API request failed: {e.response.status_code} {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"API request error: {e}")

        # Parse response
        content = response_data.get("content", [])
        if not content or content[0].get("type") != "text":
            raise ValueError(f"Invalid response format: {response_data}")

        prose = content[0].get("text", "")
        usage = response_data.get("usage", {})

        return {
            "prose": prose,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "model": response_data.get("model", self.model_id),
            "finished": response_data.get("stop_reason") == "end_turn",
        }

    def _generate_with_fake_client(
        self, prompt: str, max_tokens: int, **kwargs
    ) -> dict[str, Any]:
        """Generate using injected fake HTTP client."""
        temperature = kwargs.get("temperature", 0.7)

        # Build Anthropic API request format
        request = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        # Call fake client
        response = self.http_client.post(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key or "fake-key",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=request,
        )

        # Parse response
        content = response.get("content", [])
        if not content or content[0].get("type") != "text":
            raise ValueError("Invalid response format from fake client")

        prose = content[0].get("text", "")
        usage = response.get("usage", {})

        return {
            "prose": prose,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "model": response.get("model", self.model_id),
            "finished": response.get("stop_reason") == "end_turn",
        }

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate generation cost in USD.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        # Normalize model name for pricing lookup
        model_key = None
        if "opus" in self.model_id.lower():
            model_key = "claude-opus-4"
        elif "sonnet" in self.model_id.lower():
            model_key = "claude-sonnet-3-5"
        elif "haiku" in self.model_id.lower():
            model_key = "claude-haiku-3"

        if model_key and model_key in self.PRICING:
            pricing = self.PRICING[model_key]
            return input_tokens * pricing["input"] + output_tokens * pricing["output"]

        # Unknown model - conservative estimate (use Opus pricing)
        return input_tokens * 0.000015 + output_tokens * 0.000075
