"""Single source of truth for all model connection settings: repository-root .env.

Never copy credentials into other files or export them to process-wide variables.
Normal runtime fails closed when the local .env is missing or incomplete.
"""

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED = (
    "CC_VIBE_ANTHROPIC_BASE_URL",
    "CC_VIBE_ANTHROPIC_AUTH_TOKEN",
    "CC_VIBE_ANTHROPIC_MODEL",
    "CC_VIBE_ANTHROPIC_EFFORTLEVEL",
)


@dataclass(frozen=True)
class ModelSettings:
    """Model settings sourced exclusively from the existing root .env."""

    base_url: str
    auth_token: str = field(repr=False)
    model_id: str
    effort_level: str


def load_model_settings() -> ModelSettings:
    """Read root .env directly; no environment override, copies, or fallback."""
    if not ENV_FILE.is_file():
        raise FileNotFoundError(
            "Project-root .env is required for model calls. "
            "Use the existing local .env; do not copy model credentials elsewhere."
        )

    values: dict[str, str] = {}
    for number, raw in enumerate(ENV_FILE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key.isidentifier():
            raise ValueError(f"Invalid model .env assignment at line {number}")
        if key not in _REQUIRED:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value

    for key in _REQUIRED:
        if not values.get(key):
            raise ValueError(
                f"Missing required model setting in project-root .env: {key}"
            )

    base_url = values["CC_VIBE_ANTHROPIC_BASE_URL"]
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError("CC_VIBE_ANTHROPIC_BASE_URL must be a valid HTTPS URL")

    token = values["CC_VIBE_ANTHROPIC_AUTH_TOKEN"]
    if token == "sk-":
        raise ValueError("CC_VIBE_ANTHROPIC_AUTH_TOKEN contains a placeholder")

    effort = values["CC_VIBE_ANTHROPIC_EFFORTLEVEL"]
    if effort not in {"low", "medium", "high", "xhigh", "max"}:
        raise ValueError("Invalid CC_VIBE_ANTHROPIC_EFFORTLEVEL in project-root .env")

    return ModelSettings(
        base_url=base_url,
        auth_token=token,
        model_id=values["CC_VIBE_ANTHROPIC_MODEL"],
        effort_level=effort,
    )
