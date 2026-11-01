"""Environment configuration loader for real model testing.

Loads .env configuration for CC_VIBE Anthropic proxy.
"""

import os
from pathlib import Path
from typing import Optional, Union


def load_env_file(env_path: Optional[Union[str, Path]] = None) -> dict[str, str]:
    """Load environment variables from .env file.

    Args:
        env_path: Path to .env file (default: project root/.env)

    Returns:
        Dict of environment variables
    """
    if env_path is None:
        # Find project root .env
        current = Path(__file__).resolve()
        for parent in [current.parent] + list(current.parents):
            env_file = parent / ".env"
            if env_file.exists():
                env_path = env_file
                break

    if env_path is None:
        return {}

    env_path = Path(env_path)
    if not env_path.exists():
        return {}

    env_vars = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def get_real_provider_config() -> dict[str, str]:
    """Get real provider configuration from .env.

    Returns:
        Dict with: base_url, api_key, model_id

    Raises:
        RuntimeError: If configuration not found
    """
    # Load .env file
    env_vars = load_env_file()

    # Check for CC_VIBE configuration
    if "CC_VIBE_ANTHROPIC_BASE_URL" in env_vars:
        return {
            "base_url": env_vars["CC_VIBE_ANTHROPIC_BASE_URL"],
            "api_key": env_vars.get("CC_VIBE_ANTHROPIC_AUTH_TOKEN", ""),
            "model_id": env_vars.get("CC_VIBE_ANTHROPIC_MODEL", "claude-fable-5-1"),
        }

    # Check for standard Anthropic configuration
    if "ANTHROPIC_API_KEY" in env_vars:
        return {
            "base_url": env_vars.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            "api_key": env_vars["ANTHROPIC_API_KEY"],
            "model_id": env_vars.get("ANTHROPIC_MODEL", "claude-sonnet-3-5-20241022"),
        }

    # Check environment variables
    if os.getenv("CC_VIBE_ANTHROPIC_BASE_URL"):
        return {
            "base_url": os.getenv("CC_VIBE_ANTHROPIC_BASE_URL", ""),
            "api_key": os.getenv("CC_VIBE_ANTHROPIC_AUTH_TOKEN", ""),
            "model_id": os.getenv("CC_VIBE_ANTHROPIC_MODEL", "claude-fable-5-1"),
        }

    if os.getenv("ANTHROPIC_API_KEY"):
        return {
            "base_url": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
            "model_id": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-3-5-20241022"),
        }

    raise RuntimeError(
        "No provider configuration found. "
        "Set CC_VIBE_ANTHROPIC_* or ANTHROPIC_API_KEY in .env or environment."
    )


def mask_api_key(api_key: str) -> str:
    """Mask API key for safe logging.

    Args:
        api_key: Full API key

    Returns:
        Masked key showing only first/last 4 chars
    """
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}...{api_key[-4:]}"
