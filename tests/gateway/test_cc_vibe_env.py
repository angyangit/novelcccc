"""Offline tests: all runtime model configuration comes from one root .env."""

from unittest.mock import Mock, patch

import pytest

from anovel.gateway import ModelGateway
from anovel.gateway.config import load_model_settings


_ENV_CONTENT = (
    "CC_VIBE_ANTHROPIC_BASE_URL=https://cc-vibe.com\n"
    "CC_VIBE_ANTHROPIC_AUTH_TOKEN=test-fixture-token\n"
    "CC_VIBE_ANTHROPIC_MODEL=claude-fable-5-1\n"
    "CC_VIBE_ANTHROPIC_EFFORTLEVEL=max\n"
)


def test_single_root_env_overrides_conflicting_shell_settings(monkeypatch):
    """Never load the model or token from a second location or shell fallback."""
    monkeypatch.setenv("CC_VIBE_ANTHROPIC_MODEL", "wrong-shell-model")
    monkeypatch.setenv("CC_VIBE_ANTHROPIC_AUTH_TOKEN", "wrong-shell-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "wrong-legacy-token")
    with patch("anovel.gateway.config.ENV_FILE") as root_env:
        root_env.is_file.return_value = True
        root_env.read_text.return_value = _ENV_CONTENT
        settings = load_model_settings()
        root_env.read_text.assert_called_once_with(encoding="utf-8")

    assert settings.base_url == "https://cc-vibe.com"
    assert settings.model_id == "claude-fable-5-1"
    assert settings.effort_level == "max"
    assert settings.auth_token == "test-fixture-token"
    assert "test-fixture-token" not in repr(settings)


def test_missing_root_env_fails_instead_of_falling_back(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "legacy-token")
    with patch("anovel.gateway.config.ENV_FILE") as root_env:
        root_env.is_file.return_value = False
        with pytest.raises(FileNotFoundError, match="root .env"):
            load_model_settings()


def test_incomplete_root_env_fails_without_exposing_secret():
    with patch("anovel.gateway.config.ENV_FILE") as root_env:
        root_env.is_file.return_value = True
        root_env.read_text.return_value = (
            "CC_VIBE_ANTHROPIC_AUTH_TOKEN=test-fixture-token\n"
        )
        with pytest.raises(ValueError, match="CC_VIBE_ANTHROPIC_BASE_URL"):
            load_model_settings()


def test_invalid_root_env_assignment_fails():
    with patch("anovel.gateway.config.ENV_FILE") as root_env:
        root_env.is_file.return_value = True
        root_env.read_text.return_value = "MALFORMED_SETTING\n"
        with pytest.raises(ValueError, match="Invalid model .env assignment"):
            load_model_settings()


@patch("anovel.gateway.anthropic_provider.Anthropic")
def test_gateway_from_root_env_uses_model_and_effort(mock_client_class):
    client = mock_client_class.return_value
    client.messages.create.return_value = Mock(
        id="fixture-response-id",
        usage=Mock(input_tokens=20, output_tokens=30),
        content=[Mock(type="text", text="第一章：故事开始")],
    )
    with patch("anovel.gateway.config.ENV_FILE") as root_env:
        root_env.is_file.return_value = True
        root_env.read_text.return_value = _ENV_CONTENT
        gateway = ModelGateway.from_project_env(
            budget_limit_usd=5.0, max_retries=1
        )

    mock_client_class.assert_called_once_with(
        auth_token="test-fixture-token",
        base_url="https://cc-vibe.com",
        max_retries=0,
    )
    assert gateway.configured_model_id == "claude-fable-5-1"
    with pytest.raises(ValueError, match="root .env"):
        gateway.generate(model_id="other-model", prompt="test")

    result = gateway.generate(
        model_id=gateway.configured_model_id,
        prompt="写一段中文小说。",
        max_tokens=100,
    )
    assert result.result_status.value == "success"
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-fable-5-1"
    assert kwargs["extra_body"] == {"output_config": {"effort": "max"}}
    assert "temperature" not in kwargs
