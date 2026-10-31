"""Planning version tracking and supersession management.

Implements PlanVersion, FreezeHorizon, and version validation logic.
Plans evolve over time; this module tracks which versions are current vs superseded.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FrozenInputs:
    """Inputs that cannot change without invalidating the plan."""

    canon_parent_hash: str
    genre_pack_hash: str
    fixture_content_hash: str


@dataclass(frozen=True)
class FreezeHorizon:
    """Separates frozen (committed/in-progress) from adjustable (future) chapters."""

    frozen_chapters: list[str]  # Chapter IDs that cannot be modified
    adjustable_chapters: list[str]  # Chapter IDs that can still be revised
    frozen_inputs: FrozenInputs


@dataclass(frozen=True)
class PlanVersion:
    """Version tracking for SeriesVision plans with supersession."""

    plan_id: str
    version: str  # "v1", "v2", "v3", etc.
    created_at: datetime
    freeze_horizon: FreezeHorizon

    # Supersession tracking
    superseded_by: str | None = None  # Version string that replaced this
    supersedes: str | None = None  # Version string this replaces
    invalidation_reason: str | None = None  # Why superseded


@dataclass(frozen=True)
class VersionError:
    """Error from version validation."""

    message: str
    expired_version: str
    current_version: str | None = None


def validate_plan_version(plan_version: PlanVersion) -> VersionError | None:
    """
    Validate that plan version is current and usable.

    Returns:
        None if valid
        VersionError if superseded or expired
    """
    if plan_version.superseded_by is not None:
        return VersionError(
            message=f"Plan version {plan_version.version} has been superseded",
            expired_version=plan_version.version,
            current_version=plan_version.superseded_by,
        )

    return None


def can_modify_chapter(
    plan_version: PlanVersion,
    chapter_id: str,
) -> tuple[bool, str | None]:
    """
    Check if chapter can be modified in this plan version.

    Returns:
        (can_modify: bool, reason: Optional[str])
    """
    if chapter_id in plan_version.freeze_horizon.frozen_chapters:
        return (
            False,
            f"Chapter {chapter_id} is frozen in version {plan_version.version}",
        )

    if chapter_id not in plan_version.freeze_horizon.adjustable_chapters:
        return (
            False,
            f"Chapter {chapter_id} not found in plan version {plan_version.version}",
        )

    return True, None
