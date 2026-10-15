"""
ANovelOS V2 Promise Domain Model.

This module implements Promise lifecycle and fulfillment semantics for narrative
commitment tracking. Promise represents reader-facing narrative commitments,
distinct from Character Goals.

Public API:
    Types:
        PromiseId, Promise, PromiseStatus, PromiseFulfillmentLink, ContributionRole

    Operations:
        derive_promise_status

Invariants:
    - Promise.status is DERIVED (pure function from terminal_disposition + Links)
    - Terminal states (FULFILLED/FAILED/ABANDONED) are mutually exclusive
    - FAILED/ABANDONED + PRIMARY/COMPLETE Link is INVALID
    - (promise_id, event_id) uniqueness enforced
    - Promise ≠ Character Goal

Contract: V2-007 Implementation per ADR-003
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, NewType

from .events import EventId, StoryTime
from .identity import EntityId, ProjectId

# --- Type Aliases ---

PromiseId = NewType("PromiseId", str)
"""Stable identifier for narrative promises (UUID v4 format)."""


# --- Enums ---


class PromiseStatus(Enum):
    """
    Promise lifecycle status (DERIVED from terminal_disposition + Links).

    OPEN: Promise established, not yet fulfilled, actively tracked
    FULFILLED: Promise completed via PRIMARY/COMPLETE fulfillment
    FAILED: Promise determined impossible in story-world
    ABANDONED: Promise no longer tracked due to narrative direction change
    """

    OPEN = "OPEN"
    FULFILLED = "FULFILLED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class ContributionRole(Enum):
    """Event contribution role in promise fulfillment."""

    PRIMARY = "PRIMARY"
    COMPLETE = "COMPLETE"
    SUPPORTING = "SUPPORTING"


# --- Promise Model ---


@dataclass(frozen=True)
class Promise:
    """
    Narrative promise representing reader-facing commitment.

    BASE fields (all persisted):
        promise_id: Unique stable identifier (UUID v4)
        project_id: Project isolation boundary
        promise_type: Promise classification
        opened_at_chapter: Chapter where promise established
        target_entities: Related entities (immutable tuple)
        target_window: Expected fulfillment time window (optional)
        terminal_disposition: Explicit terminal state marker (FAILED | ABANDONED | None)
        description: Human-readable promise description
        created_at: System timestamp
        authority: Authority source
        provenance: Structured provenance metadata (immutable mapping)

    Status Authority:
        - terminal_disposition: BASE field (persisted)
        - status: DERIVED via derive_promise_status() (NOT a field on Promise)

    Invariants:
        - promise_id must be UUID v4 format
        - terminal_disposition cannot revert from FAILED/ABANDONED to None
        - FAILED/ABANDONED + PRIMARY/COMPLETE Link is INVALID domain state
        - target_entities must belong to same project

    Contract: ADR-003 Promise semantics with status derivation
    """

    promise_id: PromiseId
    project_id: ProjectId
    promise_type: str
    opened_at_chapter: str
    target_entities: tuple[EntityId, ...]
    target_window: StoryTime | None
    terminal_disposition: Literal["FAILED", "ABANDONED"] | None
    description: str
    created_at: datetime
    authority: str
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        """Validate Promise invariants and enforce deep immutability."""
        _validate_uuid_v4(self.promise_id, "promise_id")

        if not self.promise_type or not self.promise_type.strip():
            raise ValueError("promise_type cannot be empty")

        if not self.opened_at_chapter or not self.opened_at_chapter.strip():
            raise ValueError("opened_at_chapter cannot be empty")

        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

        # Enforce deep immutability via defensive copying
        from types import MappingProxyType

        # Convert target_entities to tuple if not already (defensive copy)
        if not isinstance(self.target_entities, tuple):
            object.__setattr__(self, "target_entities", tuple(self.target_entities))

        # Convert provenance to MappingProxyType with defensive dict copy
        if not isinstance(self.provenance, MappingProxyType):
            # Defensive copy: create new dict to avoid aliasing caller's mutable dict
            object.__setattr__(
                self, "provenance", MappingProxyType(dict(self.provenance))
            )


# --- Fulfillment Link Model ---


@dataclass(frozen=True)
class PromiseFulfillmentLink:
    """
    Link between Promise and fulfilling Event.

    BASE fields (all persisted):
        link_id: Unique link identifier (UUID v4)
        promise_id: Promise being fulfilled
        event_id: Event contributing to fulfillment
        contribution_role: How event contributes (PRIMARY/COMPLETE/SUPPORTING)
        created_at: System timestamp
        authority: Authority source

    Invariants:
        - link_id must be UUID v4 format
        - (promise_id, event_id) must be unique (domain uniqueness)
        - PRIMARY/COMPLETE incompatible with terminal FAILED/ABANDONED Promise

    Contract: ADR-003 Fulfillment Link semantics with uniqueness
    """

    link_id: str
    promise_id: PromiseId
    event_id: EventId
    contribution_role: ContributionRole
    created_at: datetime
    authority: str

    def __post_init__(self) -> None:
        """Validate PromiseFulfillmentLink invariants."""
        _validate_uuid_v4(self.link_id, "link_id")


# --- Status Derivation ---


def derive_promise_status(
    promise: Promise,
    fulfillment_links: Sequence[PromiseFulfillmentLink],
) -> PromiseStatus:
    """
    Pure function deriving Promise status from terminal_disposition + Links.

    V2-007 pure-domain requirement:
    - No external store/repository/database queries
    - Caller provides all relevant Links explicitly
    - Deterministic derivation, no side effects
    - Rejects invalid state (terminal + completion evidence)

    Derivation rules:
    1. Validate terminal exclusivity (FAILED/ABANDONED ⊕ PRIMARY/COMPLETE)
    2. terminal_disposition = FAILED → PromiseStatus.FAILED
    3. terminal_disposition = ABANDONED → PromiseStatus.ABANDONED
    4. terminal_disposition = None:
       - Has PRIMARY or COMPLETE Link → PromiseStatus.FULFILLED
       - Otherwise → PromiseStatus.OPEN

    Args:
        promise: Promise domain object
        fulfillment_links: All PromiseFulfillmentLinks for this Promise

    Returns:
        PromiseStatus (OPEN/FULFILLED/FAILED/ABANDONED)

    Raises:
        ValueError: If terminal disposition conflicts with completion Links

    Contract: ADR-003 M1 - Promise.status pure derivation with exclusivity
    """
    # Enforce terminal exclusivity - reject invalid states
    validate_terminal_exclusivity(promise, fulfillment_links)

    # Terminal disposition takes precedence
    if promise.terminal_disposition == "FAILED":
        return PromiseStatus.FAILED
    if promise.terminal_disposition == "ABANDONED":
        return PromiseStatus.ABANDONED

    # Active state: derive from Link collection
    has_completion = any(
        link.contribution_role in [ContributionRole.PRIMARY, ContributionRole.COMPLETE]
        for link in fulfillment_links
        if link.promise_id == promise.promise_id
    )

    return PromiseStatus.FULFILLED if has_completion else PromiseStatus.OPEN


# --- Validation ---


def validate_terminal_exclusivity(
    promise: Promise,
    fulfillment_links: Sequence[PromiseFulfillmentLink],
) -> None:
    """
    Validate terminal exclusivity invariant.

    FAILED/ABANDONED + PRIMARY/COMPLETE Link is INVALID domain state.

    This validation prevents silent normalization of data integrity violations.
    Such combinations represent impossible canonical states that must be rejected.

    Args:
        promise: Promise to validate
        fulfillment_links: All PromiseFulfillmentLinks for this Promise

    Raises:
        ValueError: If terminal disposition conflicts with completion Links

    Contract: ADR-003 M2 - Terminal exclusivity enforcement
    """
    if promise.terminal_disposition in ["FAILED", "ABANDONED"]:
        completion_links = [
            link
            for link in fulfillment_links
            if link.promise_id == promise.promise_id
            and link.contribution_role
            in [ContributionRole.PRIMARY, ContributionRole.COMPLETE]
        ]

        if completion_links:
            raise ValueError(
                f"Promise {promise.promise_id} has terminal_disposition={promise.terminal_disposition} "
                f"but also has PRIMARY/COMPLETE Links: {[link.link_id for link in completion_links]}. "
                f"Terminal FAILED/ABANDONED cannot coexist with completion evidence."
            )


def validate_link_uniqueness(
    links: Sequence[PromiseFulfillmentLink],
) -> None:
    """
    Validate (promise_id, event_id) uniqueness across Links.

    This enforces domain uniqueness invariant (idempotency semantics).
    Actual persistence retry mechanism deferred to V2-009.

    Args:
        links: Collection of PromiseFulfillmentLinks to validate

    Raises:
        ValueError: If duplicate (promise_id, event_id) pairs found

    Contract: ADR-003 FulfillmentLink uniqueness invariant
    """
    seen_pairs: set[tuple[PromiseId, EventId]] = set()

    for link in links:
        pair = (link.promise_id, link.event_id)
        if pair in seen_pairs:
            raise ValueError(
                f"Duplicate (promise_id, event_id) pair: {pair}. "
                f"Link uniqueness invariant violated."
            )
        seen_pairs.add(pair)


def validate_promise_project_isolation(
    promise: Promise,
    entity_registry: object,  # EntityRegistry from identity module
) -> None:
    """
    Validate Promise respects project isolation.

    Requires explicit EntityRegistry context - no database queries.

    Fail-closed semantics:
    - Referenced entity missing from supplied context → reject (unresolved)
    - Referenced entity found but wrong project → reject
    - Referenced entity found and same project → pass

    Args:
        promise: Promise to validate
        entity_registry: In-memory EntityRegistry for validation

    Raises:
        ValueError: If target_entities cross project boundary or are unresolved

    Contract: ADR-003 project isolation with explicit context and fail-closed
    """
    from .identity import EntityRegistry

    if not isinstance(entity_registry, EntityRegistry):
        raise TypeError("entity_registry must be EntityRegistry instance")

    for target_id in promise.target_entities:
        identity = entity_registry.get_entity(target_id)

        # Fail closed: unknown entity in validation context is rejected
        if identity is None:
            raise ValueError(
                f"Promise {promise.promise_id} target {target_id} "
                f"not found in supplied EntityRegistry. "
                f"Cannot validate project isolation without entity context."
            )

        if identity.project_id != promise.project_id:
            raise ValueError(
                f"Promise {promise.promise_id} target {target_id} "
                f"belongs to project {identity.project_id}, but promise "
                f"belongs to {promise.project_id}. Cross-project not allowed."
            )


def validate_fulfillment_link_project_isolation(
    link: PromiseFulfillmentLink,
    promise: Promise,
    event: object,  # Event from events module
) -> None:
    """
    Validate PromiseFulfillmentLink respects project isolation and identity binding.

    Link connects Promise and Event - both must belong to same project.
    Link IDs must match the provided Promise and Event objects.

    Args:
        link: PromiseFulfillmentLink to validate
        promise: Promise being fulfilled
        event: Event fulfilling the Promise

    Raises:
        ValueError: If Promise and Event have different project_id, or if
                   link IDs don't match the provided objects

    Contract: ADR-003 cross-domain project isolation with identity binding
    """
    from .events import Event

    if not isinstance(event, Event):
        raise TypeError("event must be Event instance")

    # Validate identity binding: link must reference the provided objects
    if link.promise_id != promise.promise_id:
        raise ValueError(
            f"PromiseFulfillmentLink {link.link_id} references promise_id={link.promise_id} "
            f"but was validated against Promise {promise.promise_id}. "
            f"Link identity binding violated."
        )

    if link.event_id != event.event_id:
        raise ValueError(
            f"PromiseFulfillmentLink {link.link_id} references event_id={link.event_id} "
            f"but was validated against Event {event.event_id}. "
            f"Link identity binding violated."
        )

    # Validate project isolation
    if promise.project_id != event.project_id:
        raise ValueError(
            f"PromiseFulfillmentLink {link.link_id} connects Promise {promise.promise_id} "
            f"(project {promise.project_id}) with Event {event.event_id} "
            f"(project {event.project_id}). Cross-project links not allowed."
        )


# --- Creation Helpers ---


def create_promise(
    project_id: ProjectId,
    promise_type: str,
    opened_at_chapter: str,
    description: str,
    authority: str,
    target_entities: tuple[EntityId, ...] = (),
    target_window: StoryTime | None = None,
    terminal_disposition: Literal["FAILED", "ABANDONED"] | None = None,
    provenance: Mapping[str, str] | None = None,
) -> Promise:
    """
    Create a new Promise with fresh UUID v4 promise_id.

    Args:
        project_id: Project scope
        promise_type: Promise classification
        opened_at_chapter: Chapter where promise established
        description: Human-readable description
        authority: Authority source
        target_entities: Optional related entities (tuple for immutability)
        target_window: Optional fulfillment time window
        terminal_disposition: Optional explicit terminal state
        provenance: Optional provenance metadata

    Returns:
        Immutable Promise instance

    Contract: V2-007 Promise creation with deep immutability
    """
    from types import MappingProxyType

    promise_id = PromiseId(str(uuid.uuid4()))
    now = datetime.utcnow()

    # Ensure deep immutability
    frozen_provenance: Mapping[str, str] = (
        MappingProxyType(dict(provenance)) if provenance else MappingProxyType({})
    )

    return Promise(
        promise_id=promise_id,
        project_id=project_id,
        promise_type=promise_type,
        opened_at_chapter=opened_at_chapter,
        target_entities=target_entities,
        target_window=target_window,
        terminal_disposition=terminal_disposition,
        description=description,
        created_at=now,
        authority=authority,
        provenance=frozen_provenance,
    )


def create_fulfillment_link(
    promise_id: PromiseId,
    event_id: EventId,
    contribution_role: ContributionRole,
    authority: str,
) -> PromiseFulfillmentLink:
    """
    Create a new PromiseFulfillmentLink with fresh UUID v4 link_id.

    Args:
        promise_id: Promise being fulfilled
        event_id: Event contributing to fulfillment
        contribution_role: How event contributes
        authority: Authority source

    Returns:
        Immutable PromiseFulfillmentLink instance

    Contract: V2-007 FulfillmentLink creation
    """
    link_id = str(uuid.uuid4())
    now = datetime.utcnow()

    return PromiseFulfillmentLink(
        link_id=link_id,
        promise_id=promise_id,
        event_id=event_id,
        contribution_role=contribution_role,
        created_at=now,
        authority=authority,
    )


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
