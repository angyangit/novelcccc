"""Tests for AnthropicProvider with fake HTTP client.

Proves provider adapter works without real API calls.
"""

from typing import Any

import pytest

from anovel.gateway.anthropic_provider import AnthropicProvider


class FakeHTTPClient:
    """Fake HTTP client for offline testing."""

    def __init__(self, response_mode: str = "success"):
        """Initialize fake client.

        Args:
            response_mode: "success", "error", "invalid_format"
        """
        self.response_mode = response_mode
        self.requests: list[dict[str, Any]] = []

    def post(self, url: str, headers: dict, json: dict) -> dict[str, Any]:
        """Record request and return fake response."""
        self.requests.append({"url": url, "headers": headers, "json": json})

        if self.response_mode == "error":
            raise RuntimeError("Fake HTTP error")

        if self.response_mode == "invalid_format":
            return {"invalid": "response"}

        # Success mode - return valid Anthropic API response format
        return {
            "id": "msg_fake123",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "第1章：测试章节\n\n这是一个测试生成的章节正文。",
                }
            ],
            "model": json.get("model", "claude-sonnet-3-5-20241022"),
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }


def test_anthropic_provider_with_fake_client_success():
    """Test AnthropicProvider with successful fake response."""
    fake_client = FakeHTTPClient(response_mode="success")
    provider = AnthropicProvider(
        model_id="claude-sonnet-3-5-20241022",
        api_key="fake-key-for-testing",
        http_client=fake_client,
    )

    prompt = "Write chapter 1 of a novel."
    result = provider.generate(prompt, max_tokens=2000, temperature=0.7)

    # Verify request was made
    assert len(fake_client.requests) == 1
    request = fake_client.requests[0]
    assert request["url"] == "https://api.anthropic.com/v1/messages"
    assert request["headers"]["x-api-key"] == "fake-key-for-testing"
    assert request["json"]["model"] == "claude-sonnet-3-5-20241022"
    assert request["json"]["max_tokens"] == 2000
    assert request["json"]["temperature"] == 0.7

    # Verify response parsing
    assert result["prose"] == "第1章：测试章节\n\n这是一个测试生成的章节正文。"
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50
    assert result["model"] == "claude-sonnet-3-5-20241022"
    assert result["finished"] is True


def test_anthropic_provider_blocks_real_calls():
    """Test that provider blocks real API calls by default."""
    provider = AnthropicProvider(
        model_id="claude-sonnet-3-5-20241022",
        api_key="fake-key",
        allow_real_calls=False,  # Default
    )

    with pytest.raises(RuntimeError, match="Real Anthropic API calls disabled"):
        provider.generate("test prompt", max_tokens=100)


def test_anthropic_provider_cost_estimation():
    """Test cost estimation for different models."""
    # Sonnet
    provider_sonnet = AnthropicProvider(model_id="claude-sonnet-3-5-20241022")
    cost_sonnet = provider_sonnet.estimate_cost(input_tokens=1000, output_tokens=500)
    expected_sonnet = (1000 * 3.00 + 500 * 15.00) / 1_000_000
    assert abs(cost_sonnet - expected_sonnet) < 0.0001

    # Opus
    provider_opus = AnthropicProvider(model_id="claude-opus-4-20250514")
    cost_opus = provider_opus.estimate_cost(input_tokens=1000, output_tokens=500)
    expected_opus = (1000 * 15.00 + 500 * 75.00) / 1_000_000
    assert abs(cost_opus - expected_opus) < 0.0001

    # Haiku
    provider_haiku = AnthropicProvider(model_id="claude-haiku-3-20240307")
    cost_haiku = provider_haiku.estimate_cost(input_tokens=1000, output_tokens=500)
    expected_haiku = (1000 * 0.25 + 500 * 1.25) / 1_000_000
    assert abs(cost_haiku - expected_haiku) < 0.0001


def test_anthropic_provider_handles_http_errors():
    """Test provider handles HTTP errors from fake client."""
    fake_client = FakeHTTPClient(response_mode="error")
    provider = AnthropicProvider(
        model_id="claude-sonnet-3-5-20241022",
        http_client=fake_client,
    )

    with pytest.raises(RuntimeError, match="Fake HTTP error"):
        provider.generate("test", max_tokens=100)


def test_anthropic_provider_handles_invalid_response():
    """Test provider handles invalid response format."""
    fake_client = FakeHTTPClient(response_mode="invalid_format")
    provider = AnthropicProvider(
        model_id="claude-sonnet-3-5-20241022",
        http_client=fake_client,
    )

    with pytest.raises(ValueError, match="Invalid response format"):
        provider.generate("test", max_tokens=100)


def test_anthropic_provider_call_counting():
    """Test provider tracks call count."""
    fake_client = FakeHTTPClient()
    provider = AnthropicProvider(http_client=fake_client)

    assert provider.call_count == 0

    provider.generate("prompt 1", max_tokens=100)
    assert provider.call_count == 1

    provider.generate("prompt 2", max_tokens=100)
    assert provider.call_count == 2
