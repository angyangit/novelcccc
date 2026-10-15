"""
ANovelOS V2-007 Event Timeline Promise Core Contract Tests.

Authoritative acceptance tests for V2-007 implementation per ADR-003.
These tests verify narrative semantics, not just field existence.

Acceptance Criteria:
    AC-1: Same chapter multiple events with distinguishable story-time
    AC-2: Flashback (story order ≠ disclosure order)
    AC-3: Promise lifecycle (OPEN → FULFILLED/FAILED/ABANDONED)
    AC-4: Promise ≠ Character Goal distinction

Additional Requirements:
    - Unknown occurrence ≠ occurred
    - Terminal exclusivity (FULFILLED ⊕ FAILED ⊕ ABANDONED)
    - IntervalTime partial order (OVERLAP/UNKNOWN)
    - Project isolation
    - Deep immutability
    - Link uniqueness

Contract: V2-007 Machine Acceptance
"""

import pytest
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType

from anovel.domain.events import (
    Event,
    EventId,
    PreciseTime,
    IntervalTime,
    RelativeTime,
    TemporalRelation,
    Timeline,
    compare_story_time,
    create_event,
    validate_event_project_isolation,
)
from anovel.domain.promises import (
    Promise,
    PromiseId,
    PromiseStatus,
    PromiseFulfillmentLink,
    ContributionRole,
    derive_promise_status,
    create_promise,
    create_fulfillment_link,
    validate_terminal_exclusivity,
    validate_link_uniqueness,
    validate_promise_project_isolation,
    validate_fulfillment_link_project_isolation,
)
from anovel.domain.identity import (
    ProjectId,
    EntityId,
    EntityRegistry,
    create_identity,
)


# --- AC-1: Same Chapter Multiple Events ---


def test_same_chapter_multiple_events_distinguishable_story_time():
    """
    AC-1: Verify multiple events in same chapter have distinguishable story-time.

    Same narrative chapter can contain multiple events with different story-time.
    Temporal ordering must be determinable when time information is sufficient.
    """
    project_id = ProjectId("test_project_01")

    # Event A: earlier precise time
    event_a = create_event(
        project_id=project_id,
        event_type="confrontation",
        story_time=PreciseTime(timestamp="2023-06-15T10:00:00", precision="minute"),
        participants=(),
        description="Morning confrontation",
        authority="test",
        occurrence_chapter="chapter_05",
    )

    # Event B: later precise time, same chapter
    event_b = create_event(
        project_id=project_id,
        event_type="resolution",
        story_time=PreciseTime(timestamp="2023-06-15T14:30:00", precision="minute"),
        participants=(),
        description="Afternoon resolution",
        authority="test",
        occurrence_chapter="chapter_05",
    )

    # Verify both events disclosed in same chapter
    assert event_a.occurrence_chapter == "chapter_05"
    assert event_b.occurrence_chapter == "chapter_05"

    # Verify story-time ordering is distinguishable
    relation = compare_story_time(event_a.story_time, event_b.story_time)
    assert relation == TemporalRelation.BEFORE

    # Verify reverse comparison
    relation_reverse = compare_story_time(event_b.story_time, event_a.story_time)
    assert relation_reverse == TemporalRelation.AFTER


# --- AC-2: Flashback (Story Order ≠ Disclosure Order) ---


def test_flashback_story_order_differs_from_disclosure_order():
    """
    AC-2: Verify flashback support (story-time ≠ disclosure order).

    Event occurring earlier in story-world can be disclosed later in narrative.
    System must distinguish story order from narrative disclosure order.
    """
    project_id = ProjectId("test_project_02")

    # Flashback event: story-time is 10 years ago, disclosed in chapter 80
    flashback = create_event(
        project_id=project_id,
        event_type="past_trauma",
        story_time=PreciseTime(timestamp="2010-01-15", precision="day"),
        participants=(),
        description="Traumatic event from character's past",
        authority="test",
        occurrence_chapter="chapter_80",
    )

    # Mainline event: story-time is present, disclosed in chapter 5
    mainline = create_event(
        project_id=project_id,
        event_type="present_action",
        story_time=PreciseTime(timestamp="2020-06-20", precision="day"),
        participants=(),
        description="Current timeline action",
        authority="test",
        occurrence_chapter="chapter_05",
    )

    # Verify disclosure order: mainline disclosed before flashback
    assert mainline.occurrence_chapter == "chapter_05"
    assert flashback.occurrence_chapter == "chapter_80"

    # Verify story order: flashback occurred before mainline in story-world
    story_relation = compare_story_time(flashback.story_time, mainline.story_time)
    assert story_relation == TemporalRelation.BEFORE

    # Timeline can maintain presentation order while preserving story semantics
    timeline = Timeline(
        timeline_id="123e4567-e89b-42d3-a456-426614174000",
        project_id=project_id,
        name="主线",
        events=(flashback.event_id, mainline.event_id),  # Story order
        narrative_sequence=(mainline.event_id, flashback.event_id),  # Disclosure order
        created_at=datetime.utcnow(),
        authority="test",
    )

    assert timeline.events[0] == flashback.event_id  # Story order first
    assert timeline.narrative_sequence[0] == mainline.event_id  # Disclosed first


# --- AC-3: Promise Lifecycle ---


def test_promise_lifecycle_open_to_fulfilled():
    """
    AC-3: Verify Promise lifecycle OPEN → FULFILLED via PRIMARY Link.

    New Promise starts OPEN. Adding PRIMARY/COMPLETE Link transitions to FULFILLED.
    Status is derived, not directly set.
    """
    project_id = ProjectId("test_project_03")

    # Create Promise with no terminal disposition (active)
    promise = create_promise(
        project_id=project_id,
        promise_type="revenge",
        opened_at_chapter="chapter_01",
        description="Protagonist will avenge their family",
        authority="test",
        terminal_disposition=None,
    )

    # No fulfillment links → OPEN
    status_open = derive_promise_status(promise, [])
    assert status_open == PromiseStatus.OPEN

    # Create fulfilling Event
    event = create_event(
        project_id=project_id,
        event_type="revenge_completed",
        story_time=PreciseTime(timestamp="2023-12-25", precision="day"),
        participants=(),
        description="Final confrontation",
        authority="test",
    )

    # Add PRIMARY fulfillment Link
    link = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.PRIMARY,
        authority="test",
    )

    # With PRIMARY Link → FULFILLED
    status_fulfilled = derive_promise_status(promise, [link])
    assert status_fulfilled == PromiseStatus.FULFILLED


def test_promise_lifecycle_supporting_remains_open():
    """
    AC-3: Verify SUPPORTING Links alone do not fulfill Promise.

    Promise requires PRIMARY or COMPLETE Link for fulfillment.
    SUPPORTING Links contribute but don't complete.
    """
    project_id = ProjectId("test_project_04")

    promise = create_promise(
        project_id=project_id,
        promise_type="mystery",
        opened_at_chapter="chapter_02",
        description="Reveal the true culprit",
        authority="test",
    )

    event = create_event(
        project_id=project_id,
        event_type="clue_discovery",
        story_time=PreciseTime(timestamp="2023-10-10", precision="day"),
        participants=(),
        description="Important clue found",
        authority="test",
    )

    # SUPPORTING Link alone
    link_supporting = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.SUPPORTING,
        authority="test",
    )

    # SUPPORTING alone → still OPEN
    status = derive_promise_status(promise, [link_supporting])
    assert status == PromiseStatus.OPEN


def test_promise_lifecycle_terminal_failed():
    """
    AC-3: Verify terminal FAILED disposition.

    terminal_disposition=FAILED results in FAILED status regardless of Links.
    Terminal states are irreversible.
    """
    project_id = ProjectId("test_project_05")

    promise_failed = create_promise(
        project_id=project_id,
        promise_type="rescue",
        opened_at_chapter="chapter_03",
        description="Save the character before deadline",
        authority="test",
        terminal_disposition="FAILED",
    )

    # Terminal FAILED → FAILED status
    status = derive_promise_status(promise_failed, [])
    assert status == PromiseStatus.FAILED

    # Even with SUPPORTING Links, terminal disposition takes precedence
    event = create_event(
        project_id=project_id,
        event_type="attempt",
        story_time=PreciseTime(timestamp="2023-11-11", precision="day"),
        participants=(),
        description="Failed rescue attempt",
        authority="test",
    )

    link_supporting = create_fulfillment_link(
        promise_id=promise_failed.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.SUPPORTING,
        authority="test",
    )

    status_with_link = derive_promise_status(promise_failed, [link_supporting])
    assert status_with_link == PromiseStatus.FAILED


def test_promise_lifecycle_terminal_abandoned():
    """
    AC-3: Verify terminal ABANDONED disposition.

    terminal_disposition=ABANDONED results in ABANDONED status.
    Represents narrative direction change, not story-world impossibility.
    """
    project_id = ProjectId("test_project_06")

    promise_abandoned = create_promise(
        project_id=project_id,
        promise_type="side_quest",
        opened_at_chapter="chapter_04",
        description="Explore the abandoned temple",
        authority="test",
        terminal_disposition="ABANDONED",
    )

    # Terminal ABANDONED → ABANDONED status
    status = derive_promise_status(promise_abandoned, [])
    assert status == PromiseStatus.ABANDONED


# --- AC-4: Promise ≠ Character Goal ---


def test_promise_distinct_from_character_goal():
    """
    AC-4: Verify Promise and Character Goal are distinct concepts.

    Character can have Goal while narrative has separate Promise.
    They don't automatically synchronize.
    """
    from anovel.domain.character import (
        Goal,
        GoalId,
        GoalStatus,
        create_character,
    )

    project_id = ProjectId("test_project_07")
    registry = EntityRegistry()

    # Create Character with Goal
    character = create_character(
        project_id=project_id,
        canonical_name="Protagonist",
        authority="test",
    )
    registry.add_entity(create_identity(
        project_id=project_id,
        canonical_name="Protagonist",
        entity_type="CHARACTER",
    ))

    # Character Goal: revenge (character planning state)
    goal = Goal(
        goal_id=GoalId("123e4567-e89b-42d3-a456-426614174001"),
        character=character.entity_id,
        description="Avenge family",
        target_state=None,
        status=GoalStatus.ACTIVE,
        priority=10,
        formed_at=datetime.utcnow(),
        resolved_at=None,
    )

    # Narrative Promise: revenge (reader-facing commitment)
    promise = create_promise(
        project_id=project_id,
        promise_type="revenge",
        opened_at_chapter="chapter_01",
        description="Protagonist will succeed in revenge",
        authority="test",
    )

    # Verify distinct types
    assert isinstance(goal, Goal)
    assert isinstance(promise, Promise)

    # Verify Goal has GoalStatus, Promise has PromiseStatus
    assert goal.status == GoalStatus.ACTIVE
    promise_status = derive_promise_status(promise, [])
    assert promise_status == PromiseStatus.OPEN

    # Goal and Promise can have different states
    # Goal might FAIL while Promise is still OPEN (protagonist keeps trying)
    # Or Promise might be ABANDONED while Goal remains ACTIVE (narrative pivot)


# --- Unknown Occurrence ≠ Occurred ---


def test_unknown_occurrence_not_equal_to_occurred():
    """
    Verify unknown/missing Event does not imply occurrence.

    Critical acceptance criterion: absence of evidence ≠ evidence of occurrence.
    PlannedAction.occurred_event_ref alone is not occurrence authority.
    """
    from anovel.domain.character import PlannedAction, PlannedActionId, ActionStatus

    project_id = ProjectId("test_project_08")

    # PlannedAction with event reference
    planned_action = PlannedAction(
        action_id=PlannedActionId("123e4567-e89b-42d3-a456-426614174002"),
        character=EntityId("223e4567-e89b-42d3-a456-426614174003"),
        action_description="Confront the antagonist",
        intent_ref=None,
        planned_for="chapter_20",
        status=ActionStatus.PLANNED,
        occurred_event_ref="event_unknown_or_missing",
        created_at=datetime.utcnow(),
        cancelled_at=None,
    )

    # Having occurred_event_ref is NOT occurrence authority
    # V2-007 defines: only explicit Event domain evidence proves occurrence
    assert planned_action.occurred_event_ref is not None

    # To prove occurrence, must have actual Event
    # Missing/unresolved EventId → occurrence remains UNKNOWN, not occurred
    # This test documents the semantic boundary, not implementation


def test_missing_event_ref_does_not_imply_occurred():
    """
    Verify None event_ref explicitly means unknown/not-occurred.
    """
    from anovel.domain.character import PlannedAction, PlannedActionId, ActionStatus

    planned_action = PlannedAction(
        action_id=PlannedActionId("323e4567-e89b-42d3-a456-426614174004"),
        character=EntityId("423e4567-e89b-42d3-a456-426614174005"),
        action_description="Escape the fortress",
        intent_ref=None,
        planned_for=None,
        status=ActionStatus.PLANNED,
        occurred_event_ref=None,  # Explicitly None
        created_at=datetime.utcnow(),
        cancelled_at=None,
    )

    # None occurred_event_ref → unknown/not-occurred, not occurred
    assert planned_action.occurred_event_ref is None


# --- Terminal Exclusivity ---


def test_terminal_exclusivity_rejects_failed_plus_primary():
    """
    Verify FAILED + PRIMARY Link is rejected as invalid domain state.

    Terminal FAILED/ABANDONED cannot coexist with PRIMARY/COMPLETE Links.
    This is data integrity violation, not precedence.
    """
    project_id = ProjectId("test_project_09")

    promise = create_promise(
        project_id=project_id,
        promise_type="rescue",
        opened_at_chapter="chapter_10",
        description="Save the prisoner",
        authority="test",
        terminal_disposition="FAILED",
    )

    event = create_event(
        project_id=project_id,
        event_type="rescue",
        story_time=PreciseTime(timestamp="2023-12-01", precision="day"),
        participants=(),
        description="Rescue event",
        authority="test",
    )

    link_primary = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.PRIMARY,
        authority="test",
    )

    # FAILED + PRIMARY is invalid
    with pytest.raises(ValueError, match="terminal_disposition=FAILED.*PRIMARY/COMPLETE"):
        validate_terminal_exclusivity(promise, [link_primary])


def test_terminal_exclusivity_rejects_abandoned_plus_complete():
    """
    Verify ABANDONED + COMPLETE Link is rejected.
    """
    project_id = ProjectId("test_project_10")

    promise = create_promise(
        project_id=project_id,
        promise_type="exploration",
        opened_at_chapter="chapter_11",
        description="Explore the ruins",
        authority="test",
        terminal_disposition="ABANDONED",
    )

    event = create_event(
        project_id=project_id,
        event_type="exploration_complete",
        story_time=PreciseTime(timestamp="2023-12-05", precision="day"),
        participants=(),
        description="Ruins explored",
        authority="test",
    )

    link_complete = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.COMPLETE,
        authority="test",
    )

    # ABANDONED + COMPLETE is invalid
    with pytest.raises(ValueError, match="terminal_disposition=ABANDONED.*PRIMARY/COMPLETE"):
        validate_terminal_exclusivity(promise, [link_complete])


def test_terminal_exclusivity_allows_terminal_plus_supporting():
    """
    Verify terminal disposition + SUPPORTING Link is valid.

    SUPPORTING Links don't complete Promise, so they can coexist with terminal states.
    """
    project_id = ProjectId("test_project_11")

    promise = create_promise(
        project_id=project_id,
        promise_type="quest",
        opened_at_chapter="chapter_12",
        description="Find the artifact",
        authority="test",
        terminal_disposition="FAILED",
    )

    event = create_event(
        project_id=project_id,
        event_type="search_attempt",
        story_time=PreciseTime(timestamp="2023-12-10", precision="day"),
        participants=(),
        description="Search attempt",
        authority="test",
    )

    link_supporting = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.SUPPORTING,
        authority="test",
    )

    # FAILED + SUPPORTING is valid (no exception)
    validate_terminal_exclusivity(promise, [link_supporting])


# --- IntervalTime Partial Order ---


def test_interval_time_overlap_not_forced_total_order():
    """
    Verify IntervalTime supports partial order (OVERLAP allowed).

    Overlapping intervals return OVERLAP, not forced BEFORE/AFTER.
    """
    # Interval A: January to December
    interval_a = IntervalTime(
        earliest="2023-01-01",
        latest="2023-12-31",
        description="全年",
    )

    # Interval B: June to June (contained within A)
    interval_b = IntervalTime(
        earliest="2023-06-01",
        latest="2023-06-02",
        description="两天",
    )

    # A and B overlap (B is fully contained in A)
    relation = compare_story_time(interval_a, interval_b)
    assert relation == TemporalRelation.OVERLAP

    # Reverse also overlap
    relation_reverse = compare_story_time(interval_b, interval_a)
    assert relation_reverse == TemporalRelation.OVERLAP


def test_interval_time_unknown_for_uncomparable():
    """
    Verify UNKNOWN returned for uncomparable time systems.
    """
    # Incompatible time representations
    relative = RelativeTime(
        anchor_event_id=EventId("event_anchor"),
        offset_description="three days after",
        relative_order="after",
    )

    interval = IntervalTime(
        earliest="2023-05-01",
        latest="2023-05-10",
        description="spring",
    )

    # Cannot reliably compare without resolving anchor
    relation = compare_story_time(relative, interval)
    assert relation == TemporalRelation.UNKNOWN


def test_interval_time_correct_before_semantics():
    """
    Verify correct IntervalTime BEFORE semantics.

    A BEFORE B iff A.latest < B.earliest (not A.earliest < B.earliest).
    """
    interval_a = IntervalTime(
        earliest="2023-01-01",
        latest="2023-01-31",
        description="January",
    )

    interval_b = IntervalTime(
        earliest="2023-02-01",
        latest="2023-02-28",
        description="February",
    )

    # A completely before B: A.latest < B.earliest
    relation = compare_story_time(interval_a, interval_b)
    assert relation == TemporalRelation.BEFORE


# --- Link Uniqueness ---


def test_link_uniqueness_rejects_duplicate_pair():
    """
    Verify (promise_id, event_id) uniqueness enforced.

    Domain uniqueness invariant prevents duplicate Links.
    Persistence retry mechanism deferred to V2-009.
    """
    link1 = create_fulfillment_link(
        promise_id=PromiseId("promise_123e4567-e89b-42d3-a456-426614174006"),
        event_id=EventId("event_123e4567-e89b-42d3-a456-426614174007"),
        contribution_role=ContributionRole.PRIMARY,
        authority="test",
    )

    link2 = create_fulfillment_link(
        promise_id=PromiseId("promise_123e4567-e89b-42d3-a456-426614174006"),
        event_id=EventId("event_123e4567-e89b-42d3-a456-426614174007"),
        contribution_role=ContributionRole.SUPPORTING,
        authority="test",
    )

    # Duplicate (promise_id, event_id) pair
    with pytest.raises(ValueError, match="Duplicate.*promise_id.*event_id"):
        validate_link_uniqueness([link1, link2])


# --- Project Isolation ---


def test_event_project_isolation_rejects_cross_project_participant():
    """
    Verify Event project isolation with explicit EntityRegistry context.
    """
    registry = EntityRegistry()

    # Entity in project A
    identity_a = create_identity(
        project_id=ProjectId("project_a"),
        canonical_name="Character A",
        entity_type="CHARACTER",
    )
    registry.add_entity(identity_a)

    # Event in project B referencing entity from project A
    event = create_event(
        project_id=ProjectId("project_b"),
        event_type="meeting",
        story_time=PreciseTime(timestamp="2023-11-20", precision="day"),
        participants=(identity_a.entity_id,),
        description="Cross-project meeting",
        authority="test",
    )

    # Cross-project participant rejected
    with pytest.raises(ValueError, match="Cross-project not allowed"):
        validate_event_project_isolation(event, registry)


def test_promise_project_isolation_rejects_cross_project_target():
    """
    Verify Promise project isolation.
    """
    registry = EntityRegistry()

    identity = create_identity(
        project_id=ProjectId("project_x"),
        canonical_name="Target",
        entity_type="CHARACTER",
    )
    registry.add_entity(identity)

    promise = create_promise(
        project_id=ProjectId("project_y"),
        promise_type="protection",
        opened_at_chapter="chapter_01",
        description="Protect the target",
        authority="test",
        target_entities=(identity.entity_id,),
    )

    with pytest.raises(ValueError, match="Cross-project not allowed"):
        validate_promise_project_isolation(promise, registry)


def test_fulfillment_link_project_isolation():
    """
    Verify PromiseFulfillmentLink connects same-project Promise and Event.
    """
    promise = create_promise(
        project_id=ProjectId("project_alpha"),
        promise_type="quest",
        opened_at_chapter="chapter_02",
        description="Complete the quest",
        authority="test",
    )

    event = create_event(
        project_id=ProjectId("project_beta"),
        event_type="quest_complete",
        story_time=PreciseTime(timestamp="2023-12-15", precision="day"),
        participants=(),
        description="Quest completed",
        authority="test",
    )

    link = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.COMPLETE,
        authority="test",
    )

    with pytest.raises(ValueError, match="Cross-project links not allowed"):
        validate_fulfillment_link_project_isolation(link, promise, event)


# --- Deep Immutability ---


def test_event_participants_immutable():
    """
    Verify Event participants tuple is immutable.
    """
    event = create_event(
        project_id=ProjectId("test_immutable"),
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(EntityId("entity_1"), EntityId("entity_2")),
        description="Test event",
        authority="test",
    )

    # Tuple is immutable
    assert isinstance(event.participants, tuple)

    # Cannot modify
    with pytest.raises((TypeError, AttributeError)):
        event.participants[0] = EntityId("entity_3")


def test_promise_target_entities_immutable():
    """
    Verify Promise target_entities tuple is immutable.
    """
    promise = create_promise(
        project_id=ProjectId("test_immutable"),
        promise_type="test",
        opened_at_chapter="chapter_01",
        description="Test promise",
        authority="test",
        target_entities=(EntityId("target_1"),),
    )

    assert isinstance(promise.target_entities, tuple)

    with pytest.raises((TypeError, AttributeError)):
        promise.target_entities[0] = EntityId("target_2")


def test_event_provenance_immutable():
    """
    Verify Event provenance mapping is immutable.
    """
    event = create_event(
        project_id=ProjectId("test_immutable"),
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(),
        description="Test event",
        authority="test",
        provenance={"source": "test_suite"},
    )

    assert isinstance(event.provenance, Mapping)

    # Cannot modify
    with pytest.raises((TypeError, AttributeError)):
        event.provenance["new_key"] = "new_value"


def test_timeline_events_immutable():
    """
    Verify Timeline events tuple is immutable.
    """
    timeline = Timeline(
        timeline_id="523e4567-e89b-42d3-a456-426614174099",
        project_id=ProjectId("test_project"),
        name="Test Timeline",
        events=(EventId("event_1"), EventId("event_2")),
        narrative_sequence=None,
        created_at=datetime.utcnow(),
        authority="test",
    )

    assert isinstance(timeline.events, tuple)

    with pytest.raises((TypeError, AttributeError)):
        timeline.events[0] = EventId("event_3")


# --- Composition: Character + PlannedAction + Event + Promise ---


def test_domain_composition_character_to_promise():
    """
    Verify natural composition across V2-005/V2-061/V2-007 domains.

    Character → PlannedAction → Event → Promise
    """
    from anovel.domain.character import (
        create_character,
        PlannedAction,
        PlannedActionId,
        ActionStatus,
    )

    project_id = ProjectId("composition_test")
    registry = EntityRegistry()

    # V2-061: Create Character
    character = create_character(
        project_id=project_id,
        canonical_name="Hero",
        authority="test",
    )

    # Register Character's actual entity_id for validation
    # Must use character.entity_id, not a separate random identity
    character_identity = create_identity(
        project_id=project_id,
        canonical_name="Hero",
        entity_type="CHARACTER",
    )
    # Replace the auto-generated entity_id with character's actual entity_id
    from anovel.domain.identity import EntityIdentity
    character_identity = EntityIdentity(
        entity_id=character.entity_id,
        project_id=project_id,
        canonical_name="Hero",
        aliases=frozenset(),
        entity_type="CHARACTER",
    )
    registry.add_entity(character_identity)

    # V2-061: PlannedAction
    planned_action = PlannedAction(
        action_id=PlannedActionId("623e4567-e89b-42d3-a456-426614174008"),
        character=character.entity_id,
        action_description="Confront villain",
        intent_ref=None,
        planned_for="chapter_50",
        status=ActionStatus.PLANNED,
        occurred_event_ref=None,  # Not yet occurred
        created_at=datetime.utcnow(),
        cancelled_at=None,
    )

    # V2-007: Event (occurrence)
    event = create_event(
        project_id=project_id,
        event_type="confrontation",
        story_time=PreciseTime(timestamp="2023-12-20", precision="day"),
        participants=(character.entity_id,),
        description="Hero confronts villain",
        authority="test",
        occurrence_chapter="chapter_50",
    )

    # PlannedAction can reference Event
    # (In real system, would update PlannedAction.occurred_event_ref)
    assert event.event_id is not None

    # V2-007: Promise (narrative commitment)
    promise = create_promise(
        project_id=project_id,
        promise_type="confrontation",
        opened_at_chapter="chapter_01",
        description="Hero will face the villain",
        authority="test",
        target_entities=(character.entity_id,),
    )

    # V2-007: Promise fulfilled by Event
    link = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.PRIMARY,
        authority="test",
    )

    # Verify composition
    assert promise.project_id == project_id
    assert event.project_id == project_id
    assert character.project_id == project_id

    # Verify Promise fulfilled
    status = derive_promise_status(promise, [link])
    assert status == PromiseStatus.FULFILLED

    # Verify project isolation
    validate_event_project_isolation(event, registry)
    validate_promise_project_isolation(promise, registry)
    validate_fulfillment_link_project_isolation(link, promise, event)


# --- R1: derive_promise_status rejects terminal + completion evidence ---


def test_derive_promise_status_rejects_failed_plus_primary():
    """
    R1: derive_promise_status must reject FAILED + PRIMARY Link.

    Terminal exclusivity enforcement in status derivation path.
    """
    project_id = ProjectId("test_project_r1a")

    promise = create_promise(
        project_id=project_id,
        promise_type="test",
        opened_at_chapter="chapter_01",
        description="Test promise",
        authority="test",
        terminal_disposition="FAILED",
    )

    event = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(),
        description="Test event",
        authority="test",
    )

    link = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.PRIMARY,
        authority="test",
    )

    # derive_promise_status must reject this invalid state
    with pytest.raises(ValueError, match="terminal_disposition=FAILED.*PRIMARY"):
        derive_promise_status(promise, [link])


def test_derive_promise_status_rejects_abandoned_plus_complete():
    """
    R1: derive_promise_status must reject ABANDONED + COMPLETE Link.

    Terminal exclusivity enforcement in status derivation path.
    """
    project_id = ProjectId("test_project_r1b")

    promise = create_promise(
        project_id=project_id,
        promise_type="test",
        opened_at_chapter="chapter_01",
        description="Test promise",
        authority="test",
        terminal_disposition="ABANDONED",
    )

    event = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(),
        description="Test event",
        authority="test",
    )

    link = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.COMPLETE,
        authority="test",
    )

    # derive_promise_status must reject this invalid state
    with pytest.raises(ValueError, match="terminal_disposition=ABANDONED.*COMPLETE"):
        derive_promise_status(promise, [link])


# --- R2: Temporal comparison must not guess arbitrary strings ---


def test_arbitrary_story_world_strings_return_unknown():
    """
    R2: Arbitrary story-world strings must return UNKNOWN, not guessed order.

    V2-007 does not implement full calendar engine for all story-world systems.
    """
    time_a = PreciseTime(timestamp="天启三年春", precision="year")
    time_b = PreciseTime(timestamp="赤曜二年冬", precision="year")

    # Cannot reliably order arbitrary story-world calendar strings
    relation = compare_story_time(time_a, time_b)
    assert relation == TemporalRelation.UNKNOWN


def test_uncomparable_interval_endpoints_return_unknown():
    """
    R2: IntervalTime with uncomparable endpoints must return UNKNOWN.

    Only safely comparable (ISO 8601) endpoints allow partial order comparison.
    """
    interval_a = IntervalTime(
        earliest="故事开始前",
        latest="第一次相遇",
        description="背景时期",
    )
    interval_b = IntervalTime(
        earliest="第二次相遇",
        latest="故事结束",
        description="后续时期",
    )

    # Cannot reliably order intervals with uncomparable endpoints
    relation = compare_story_time(interval_a, interval_b)
    assert relation == TemporalRelation.UNKNOWN


# --- R3: Unknown occurrence resolution ---


def test_resolve_event_occurrence_none_ref_returns_none():
    """
    R3: resolve_event_occurrence with None ref returns None (UNKNOWN).
    """
    from anovel.domain.events import resolve_event_occurrence

    project_id = ProjectId("test_project_r3a")

    event = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(),
        description="Test event",
        authority="test",
    )

    # None reference → UNKNOWN occurrence
    result = resolve_event_occurrence(None, [event])
    assert result is None


def test_resolve_event_occurrence_unresolved_ref_returns_none():
    """
    R3: resolve_event_occurrence with unresolved ref returns None (UNKNOWN).
    """
    from anovel.domain.events import resolve_event_occurrence

    project_id = ProjectId("test_project_r3b")

    event = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(),
        description="Test event",
        authority="test",
    )

    # Reference to non-existent event → UNKNOWN occurrence
    missing_ref = EventId("123e4567-e89b-42d3-a456-426614174099")
    result = resolve_event_occurrence(missing_ref, [event])
    assert result is None


def test_resolve_event_occurrence_found_returns_event():
    """
    R3: resolve_event_occurrence with valid ref returns Event (occurrence proven).
    """
    from anovel.domain.events import resolve_event_occurrence

    project_id = ProjectId("test_project_r3c")

    event = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(),
        description="Test event",
        authority="test",
    )

    # Valid reference → occurrence proven by Event evidence
    result = resolve_event_occurrence(event.event_id, [event])
    assert result is not None
    assert result.event_id == event.event_id


# --- R4: Project isolation fail-closed ---


def test_event_project_isolation_rejects_unknown_participant():
    """
    R4: validate_event_project_isolation must reject unknown participants.

    Fail-closed: unknown entity in validation context is rejected.
    """
    project_id = ProjectId("test_project_r4a")
    registry = EntityRegistry()

    unknown_entity = EntityId("123e4567-e89b-42d3-a456-426614174001")

    event = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(unknown_entity,),
        description="Test event",
        authority="test",
    )

    # Unknown participant must be rejected (fail-closed)
    with pytest.raises(ValueError, match="not found in supplied EntityRegistry"):
        validate_event_project_isolation(event, registry)


def test_promise_project_isolation_rejects_unknown_target():
    """
    R4: validate_promise_project_isolation must reject unknown targets.

    Fail-closed: unknown entity in validation context is rejected.
    """
    project_id = ProjectId("test_project_r4b")
    registry = EntityRegistry()

    unknown_entity = EntityId("123e4567-e89b-42d3-a456-426614174002")

    promise = create_promise(
        project_id=project_id,
        promise_type="test",
        opened_at_chapter="chapter_01",
        description="Test promise",
        authority="test",
        target_entities=(unknown_entity,),
    )

    # Unknown target must be rejected (fail-closed)
    with pytest.raises(ValueError, match="not found in supplied EntityRegistry"):
        validate_promise_project_isolation(promise, registry)


# --- R5: Fulfillment link identity binding ---


def test_link_validation_rejects_wrong_promise():
    """
    R5: validate_fulfillment_link_project_isolation must reject wrong Promise.

    Link identity binding: link.promise_id must match promise.promise_id.
    """
    project_id = ProjectId("test_project_r5a")

    promise_a = create_promise(
        project_id=project_id,
        promise_type="test",
        opened_at_chapter="chapter_01",
        description="Promise A",
        authority="test",
    )

    promise_b = create_promise(
        project_id=project_id,
        promise_type="test",
        opened_at_chapter="chapter_01",
        description="Promise B",
        authority="test",
    )

    event = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(),
        description="Test event",
        authority="test",
    )

    # Link references promise_a
    link = create_fulfillment_link(
        promise_id=promise_a.promise_id,
        event_id=event.event_id,
        contribution_role=ContributionRole.PRIMARY,
        authority="test",
    )

    # Validating with wrong promise_b must be rejected
    with pytest.raises(ValueError, match="Link identity binding violated"):
        validate_fulfillment_link_project_isolation(link, promise_b, event)


def test_link_validation_rejects_wrong_event():
    """
    R5: validate_fulfillment_link_project_isolation must reject wrong Event.

    Link identity binding: link.event_id must match event.event_id.
    """
    project_id = ProjectId("test_project_r5b")

    promise = create_promise(
        project_id=project_id,
        promise_type="test",
        opened_at_chapter="chapter_01",
        description="Test promise",
        authority="test",
    )

    event_a = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
        participants=(),
        description="Event A",
        authority="test",
    )

    event_b = create_event(
        project_id=project_id,
        event_type="test",
        story_time=PreciseTime(timestamp="2023-01-02", precision="day"),
        participants=(),
        description="Event B",
        authority="test",
    )

    # Link references event_a
    link = create_fulfillment_link(
        promise_id=promise.promise_id,
        event_id=event_a.event_id,
        contribution_role=ContributionRole.PRIMARY,
        authority="test",
    )

    # Validating with wrong event_b must be rejected
    with pytest.raises(ValueError, match="Link identity binding violated"):
        validate_fulfillment_link_project_isolation(link, promise, event_b)


# --- R6: Deep immutability ---


def test_event_rejects_mutable_provenance():
    """
    R6: Event construction must reject mutable dict provenance.

    Deep immutability: public constructor must enforce frozen provenance.
    """
    project_id = ProjectId("test_project_r6a")

    mutable_provenance = {"source": "test"}

    # Direct construction with mutable dict must be rejected
    with pytest.raises(TypeError, match="provenance must be immutable"):
        Event(
            event_id=EventId("123e4567-e89b-42d3-a456-426614174003"),
            project_id=project_id,
            event_type="test",
            story_time=PreciseTime(timestamp="2023-01-01", precision="day"),
            participants=(),
            occurrence_chapter=None,
            description="Test event",
            created_at=datetime.utcnow(),
            authority="test",
            provenance=mutable_provenance,
        )


def test_promise_rejects_mutable_provenance():
    """
    R6: Promise construction must reject mutable dict provenance.

    Deep immutability: public constructor must enforce frozen provenance.
    """
    project_id = ProjectId("test_project_r6b")

    mutable_provenance = {"source": "test"}

    # Direct construction with mutable dict must be rejected
    with pytest.raises(TypeError, match="provenance must be immutable"):
        Promise(
            promise_id=PromiseId("123e4567-e89b-42d3-a456-426614174004"),
            project_id=project_id,
            promise_type="test",
            opened_at_chapter="chapter_01",
            target_entities=(),
            target_window=None,
            terminal_disposition=None,
            description="Test promise",
            created_at=datetime.utcnow(),
            authority="test",
            provenance=mutable_provenance,
        )
