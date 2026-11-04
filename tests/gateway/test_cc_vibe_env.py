"""Offline tests for local CC_VIBE .env model configuration."""

import os
from unittest.mock import Mock, patch

import pytest

from anovel.gateway import ModelGateway
from scripts.generate_first_chapter import load_local_env


def test_local_env_loads_model_configuration_without_overwriting_shell(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        "CC_VIBE_ANTHROPIC_BASE_URL=https://cc-vibe.com\n"
        "CC_VIBE_ANTHROPIC_AUTH_TOKEN=test-fixture-token\n"
        "CC_VIBE_ANTHROPIC_MODEL=claude-fable-5-1\n"
        "CC_VIBE_ANTHROPIC_EFFORTLEVEL=max\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CC_VIBE_ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("CC_VIBE_ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("CC_VIBE_ANTHROPIC_MODEL", "shell-model")
    monkeypatch.delenv("CC_VIBE_ANTHROPIC_EFFORTLEVEL", raising=False)
    load_local_env(path)
    assert os.environ["CC_VIBE_ANTHROPIC_BASE_URL"] == "https://cc-vibe.com"
    assert os.environ["CC_VIBE_ANTHROPIC_AUTH_TOKEN"] == "test-fixture-token"
    assert os.environ["CC_VIBE_ANTHROPIC_MODEL"] == "shell-model"
    assert os.environ["CC_VIBE_ANTHROPIC_EFFORTLEVEL"] == "max"


def test_local_env_rejects_malformed_assignment(tmp_path):
    path = tmp_path / ".env"
    path.write_text("NOT_AN_ASSIGNMENT\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid .env assignment"):
        load_local_env(path)


@patch("anovel.gateway.anthropic_provider.Anthropic")
def test_custom_gateway_uses_token_base_url_and_max_effort_without_sampling(mock_client_class):
    client = mock_client_class.return_value
    client.messages.create.return_value = Mock(
        id="fixture-response-id",
        usage=Mock(input_tokens=20, output_tokens=30),
        content=[Mock(type="text", text="第一章：故事开始")],
    )
    gateway = ModelGateway(
        anthropic_key="test-fixture-token",
        anthropic_base_url="https://cc-vibe.com",
        effort_level="max",
        budget_limit_usd=5.0,
        max_retries=1,
    )
    mock_client_class.assert_called_once_with(
        auth_token="test-fixture-token",
        base_url="https://cc-vibe.com",
        max_retries=0,
    )
    result = gateway.generate(
        model_id="claude-fable-5-1",
        prompt="写一段中文小说。",
        max_tokens=100,
    )
    assert result.result_status.value == "success"
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-fable-5-1"
    assert kwargs["extra_body"] == {"output_config": {"effort": "max"}}
    assert "temperature" not in kwargs
