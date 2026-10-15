"""
ANovelOS V2 Event Timeline Domain Model.

This module implements Event occurrence and Timeline semantics for narrative
story-time tracking. Supports non-linear narrative (flashback, disclosure order).

Public API:
    Types:
        EventId, Event, StoryTime (PreciseTime | IntervalTime | RelativeTime),
        Timeline, TemporalRelation

    Operations:
        compare_story_time

Invariants:
    - Event occurrence is immutable (retcon deferred)
    - story_time ≠ disclosure order (supports flashback)
    - Unknown occurrence ≠ occurred
    - IntervalTime partial order (OVERLAP/UNKNOWN allowed)
    - Timeline list position ≠ temporal truth for incomparable events

Contract: V2-007 Implementation per ADR-003
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, NewType

from .identity import EntityId, ProjectId

# --- Type Aliases ---

EventId = NewType("EventId", str)
"""Stable identifier for narrative events (UUID v4 format)."""


# --- Enums ---


class TemporalRelation(Enum):
    """Temporal ordering relationship between story-time values."""

    BEFORE = "BEFORE"
    AFTER = "AFTER"
    EQUAL = "EQUAL"
    OVERLAP = "OVERLAP"
    UNKNOWN = "UNKNOWN"


# --- StoryTime Models ---


@dataclass(frozen=True)
class PreciseTime:
    """
    Precise story-time point with known timestamp.

    Attributes:
        timestamp: ISO 8601 or story-world calendar string
        precision: Level of temporal precision
    """

    timestamp: str
    precision: Literal["year", "month", "day", "hour", "minute"]


@dataclass(frozen=True)
class IntervalTime:
    """
    Story-time interval (e.g., "spring", "within three months").

    Attributes:
        earliest: Start of interval (inclusive)
        latest: End of interval (inclusive)
        description: Human-readable interval description
    """

    earliest: str
    latest: str
    description: str


@dataclass(frozen=True)
class RelativeTime:
    """
    Story-time relative to another event or narrative point.

    Attributes:
        anchor_event_id: Reference event for relative positioning
        offset_description: Human description of offset
        relative_order: Ordering relationship to anchor
    """

    anchor_event_id: EventId | None
    offset_description: str
    relative_order: Literal["before", "after", "during", "concurrent"]


StoryTime = PreciseTime | IntervalTime | RelativeTime
"""Union type for story-time representations."""


# --- Event Model ---


@dataclass(frozen=True)
class Event:
    """
    Immutable narrative event representing story-world occurrence.

    BASE fields (all persisted):
        event_id: Unique stable identifier (UUID v4)
        project_id: Project isolation boundary
        event_type: Event classification
        story_time: When event occurred in story-world
        participants: Entities involved (immutable tuple)
        occurrence_chapter: Chapter where disclosed (may differ from story order)
        description: Human-readable description
        created_at: System timestamp
        authority: Authority source identifier
        provenance: Structured provenance metadata (immutable mapping)

    Invariants:
        - event_id must be UUID v4 format
        - Event is immutable (retcon not implemented in V2-007)
        - participants must belong to same project
        - story_time occurrence ≠ disclosure order

    Contract: ADR-003 Event semantics
    """

    event_id: EventId
    project_id: ProjectId
    event_type: str
    story_time: StoryTime
    participants: tuple[EntityId, ...]
    occurrence_chapter: str | None
    description: str
    created_at: datetime
    authority: str
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        """Validate Event invariants and enforce deep immutability."""
        _validate_uuid_v4(self.event_id, "event_id")

        if not self.event_type or not self.event_type.strip():
            raise ValueError("event_type cannot be empty")

        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

        # Enforce deep immutability: reject mutable provenance
        # Check if provenance is a plain mutable dict (not MappingProxyType)
        from types import MappingProxyType

        if isinstance(self.provenance, dict) and not isinstance(
            self.provenance, MappingProxyType
        ):
            raise TypeError(
                "Event provenance must be immutable (MappingProxyType), "
                "not mutable dict. Use create_event() or freeze manually."
            )


# --- Timeline Model ---


@dataclass(frozen=True)
class Timeline:
    """
    Ordered Event collection supporting non-linear narrative.

    BASE fields (all persisted):
        timeline_id: Unique identifier (UUID v4)
        project_id: Project isolation boundary
        name: Timeline name (e.g., "主线", "角色A回忆线")
        events: Event IDs in deterministic presentation order (immutable tuple)
        narrative_sequence: Optional disclosure order by chapter (immutable tuple)
        created_at: System timestamp
        authority: Authority source

    Invariants:
        - All events must belong to same project
        - events provides deterministic linearization, NOT temporal truth
        - List position between incomparable events is NOT temporal fact
        - narrative_sequence (if present) ordered by occurrence_chapter

    Contract: ADR-003 Timeline semantics with partial order support
    """

    timeline_id: str
    project_id: ProjectId
    name: str
    events: tuple[EventId, ...]
    narrative_sequence: tuple[EventId, ...] | None
    created_at: datetime
    authority: str

    def __post_init__(self) -> None:
        """Validate Timeline invariants."""
        _validate_uuid_v4(self.timeline_id, "timeline_id")

        if not self.name or not self.name.strip():
            raise ValueError("name cannot be empty")


# --- Temporal Comparison ---


def compare_story_time(a: StoryTime, b: StoryTime) -> TemporalRelation:
    """
    Compare two StoryTime values for temporal ordering.

    Returns BEFORE/AFTER/EQUAL only when reliably comparable.
    Returns OVERLAP for overlapping intervals.
    Returns UNKNOWN when comparison is not reliably determinable.

    Args:
        a: First story-time value
        b: Second story-time value

    Returns:
        TemporalRelation indicating ordering relationship

    Contract: ADR-003 partial order semantics
    """
    if isinstance(a, PreciseTime) and isinstance(b, PreciseTime):
        return _compare_precise_time(a, b)
    elif isinstance(a, IntervalTime) and isinstance(b, IntervalTime):
        return _compare_interval_time(a, b)
    elif isinstance(a, PreciseTime) and isinstance(b, IntervalTime):
        return _compare_precise_vs_interval(a, b)
    elif isinstance(a, IntervalTime) and isinstance(b, PreciseTime):
        rel = _compare_precise_vs_interval(b, a)
        return _invert_relation(rel)
    else:
        # RelativeTime or mixed types: cannot reliably compare without context
        return TemporalRelation.UNKNOWN


def _compare_precise_time(a: PreciseTime, b: PreciseTime) -> TemporalRelation:
    """
    Compare two PreciseTime values.

    Only compares timestamps when both can be safely parsed as ISO 8601.
    Returns UNKNOWN for arbitrary story-world strings that cannot be reliably ordered.
    """
    # Attempt to parse both as ISO 8601 timestamps
    from datetime import datetime as dt

    def try_parse_iso8601(timestamp: str) -> dt | None:
        """Try to parse timestamp as ISO 8601, return None if not parsable."""
        try:
            # Try ISO 8601 with various precisions
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%d",
                "%Y-%m",
                "%Y",
            ]:
                try:
                    return dt.strptime(timestamp, fmt)
                except ValueError:
                    continue
            return None
        except (ValueError, TypeError):
            return None

    parsed_a = try_parse_iso8601(a.timestamp)
    parsed_b = try_parse_iso8601(b.timestamp)

    # Only compare if both successfully parsed as ISO 8601
    if parsed_a is not None and parsed_b is not None:
        if parsed_a < parsed_b:
            return TemporalRelation.BEFORE
        elif parsed_a > parsed_b:
            return TemporalRelation.AFTER
        else:
            return TemporalRelation.EQUAL

    # Cannot reliably compare arbitrary story-world strings
    return TemporalRelation.UNKNOWN


def _compare_interval_time(a: IntervalTime, b: IntervalTime) -> TemporalRelation:
    """
    Compare two IntervalTime values using correct partial order semantics.

    A BEFORE B iff A.latest < B.earliest
    A AFTER B iff A.earliest > B.latest
    Otherwise OVERLAP or UNKNOWN

    Only compares when endpoints are safely comparable (ISO 8601).
    Returns UNKNOWN for uncomparable story-world interval endpoints.
    """
    from datetime import datetime as dt

    def try_parse_iso8601(timestamp: str) -> dt | None:
        """Try to parse timestamp as ISO 8601, return None if not parsable."""
        try:
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%d",
                "%Y-%m",
                "%Y",
            ]:
                try:
                    return dt.strptime(timestamp, fmt)
                except ValueError:
                    continue
            return None
        except (ValueError, TypeError):
            return None

    # Parse all four endpoints
    a_earliest = try_parse_iso8601(a.earliest)
    a_latest = try_parse_iso8601(a.latest)
    b_earliest = try_parse_iso8601(b.earliest)
    b_latest = try_parse_iso8601(b.latest)

    # All endpoints must be parsable for safe comparison
    if a_earliest is None or a_latest is None or b_earliest is None or b_latest is None:
        return TemporalRelation.UNKNOWN

    # A completely before B: A's end is before B's start
    if a_latest < b_earliest:
        return TemporalRelation.BEFORE
    # A completely after B: A's start is after B's end
    elif a_earliest > b_latest:
        return TemporalRelation.AFTER
    # Intervals overlap or are equal
    elif a_earliest == b_earliest and a_latest == b_latest:
        return TemporalRelation.EQUAL
    else:
        return TemporalRelation.OVERLAP


def _compare_precise_vs_interval(
    precise: PreciseTime,
    interval: IntervalTime,
) -> TemporalRelation:
    """
    Compare PreciseTime against IntervalTime.

    Only compares when all timestamps are safely parsable (ISO 8601).
    Returns UNKNOWN for uncomparable story-world strings.
    """
    from datetime import datetime as dt

    def try_parse_iso8601(timestamp: str) -> dt | None:
        """Try to parse timestamp as ISO 8601, return None if not parsable."""
        try:
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%d",
                "%Y-%m",
                "%Y",
            ]:
                try:
                    return dt.strptime(timestamp, fmt)
                except ValueError:
                    continue
            return None
        except (ValueError, TypeError):
            return None

    parsed_precise = try_parse_iso8601(precise.timestamp)
    parsed_earliest = try_parse_iso8601(interval.earliest)
    parsed_latest = try_parse_iso8601(interval.latest)

    # All must be parsable for safe comparison
    if parsed_precise is None or parsed_earliest is None or parsed_latest is None:
        return TemporalRelation.UNKNOWN

    if parsed_precise < parsed_earliest:
        return TemporalRelation.BEFORE
    elif parsed_precise > parsed_latest:
        return TemporalRelation.AFTER
    elif parsed_earliest <= parsed_precise <= parsed_latest:
        return TemporalRelation.OVERLAP
    else:
        return TemporalRelation.UNKNOWN


def _invert_relation(rel: TemporalRelation) -> TemporalRelation:
    """Invert temporal relation (swap A and B)."""
    if rel == TemporalRelation.BEFORE:
        return TemporalRelation.AFTER
    elif rel == TemporalRelation.AFTER:
        return TemporalRelation.BEFORE
    else:
        return rel


# --- Validation Helpers ---


def resolve_event_occurrence(
    event_ref: EventId | None,
    events: Sequence[Event],
) -> Event | None:
    """
    Resolve event occurrence from reference using explicit Event evidence.

    Critical semantics:
    - event_ref is None → UNKNOWN (no occurrence evidence)
    - event_ref not found in supplied events → UNKNOWN (unresolved reference)
    - event_ref resolves to Event → occurrence proven by that Event

    Important: UNKNOWN ≠ definitely NOT_OCCURRED. Unknown means cannot prove
    occurrence from available evidence, not that it definitely did not occur.

    Args:
        event_ref: Optional EventId reference to resolve
        events: Explicit collection of Event domain evidence

    Returns:
        Event if reference resolves to evidence, None if unresolved/unknown

    Contract: V2-007 pure domain occurrence resolution with explicit context
    """
    if event_ref is None:
        return None

    for event in events:
        if event.event_id == event_ref:
            return event

    return None


# --- Validation Helpers ---


def _validate_uuid_v4(value: str, field_name: str) -> None:
    """
    Validate UUID v4 format.

    Contract: Reuses validation pattern from knowledge.py
    """
    import re

    if len(value) != 36:
        raise ValueError(
            f"{field_name} must be 36 characters (UUID v4 format), got {len(value)}"
        )

    uuid_v4_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )

    if not uuid_v4_pattern.match(value):
        raise ValueError(f"{field_name} must be valid UUID v4 format. Got: {value}")


def validate_event_project_isolation(
    event: Event,
    entity_registry: object,  # EntityRegistry from identity module
) -> None:
    """
    Validate Event respects project isolation.

    Requires explicit EntityRegistry context - no database queries.

    Fail-closed semantics:
    - Referenced entity missing from supplied context → reject (unresolved)
    - Referenced entity found but wrong project → reject
    - Referenced entity found and same project → pass

    Args:
        event: Event to validate
        entity_registry: In-memory EntityRegistry for validation

    Raises:
        ValueError: If participants cross project boundary or are unresolved

    Contract: ADR-003 project isolation with explicit context and fail-closed
    """
    from .identity import EntityRegistry

    if not isinstance(entity_registry, EntityRegistry):
        raise TypeError("entity_registry must be EntityRegistry instance")

    for participant_id in event.participants:
        identity = entity_registry.get_entity(participant_id)

        # Fail closed: unknown entity in validation context is rejected
        if identity is None:
            raise ValueError(
                f"Event {event.event_id} participant {participant_id} "
                f"not found in supplied EntityRegistry. "
                f"Cannot validate project isolation without entity context."
            )

        if identity.project_id != event.project_id:
            raise ValueError(
                f"Event {event.event_id} participant {participant_id} "
                f"belongs to project {identity.project_id}, but event "
                f"belongs to {event.project_id}. Cross-project not allowed."
            )


def create_event(
    project_id: ProjectId,
    event_type: str,
    story_time: StoryTime,
    participants: tuple[EntityId, ...],
    description: str,
    authority: str,
    occurrence_chapter: str | None = None,
    provenance: Mapping[str, str] | None = None,
) -> Event:
    """
    Create a new Event with fresh UUID v4 event_id.

    Args:
        project_id: Project scope
        event_type: Event classification
        story_time: When event occurred in story-world
        participants: Involved entities (tuple for immutability)
        description: Human-readable description
        authority: Authority source
        occurrence_chapter: Optional disclosure chapter
        provenance: Optional provenance metadata

    Returns:
        Immutable Event instance

    Contract: V2-007 Event creation with deep immutability
    """
    from types import MappingProxyType

    event_id = EventId(str(uuid.uuid4()))
    now = datetime.utcnow()

    # Ensure deep immutability
    frozen_provenance: Mapping[str, str] = (
        MappingProxyType(dict(provenance)) if provenance else MappingProxyType({})
    )

    return Event(
        event_id=event_id,
        project_id=project_id,
        event_type=event_type,
        story_time=story_time,
        participants=participants,
        occurrence_chapter=occurrence_chapter,
        description=description,
        created_at=now,
        authority=authority,
        provenance=frozen_provenance,
    )
