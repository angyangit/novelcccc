"""
ANovelOS V2 Domain Layer.

This package contains the core domain models and business logic for narrative
generation and management.

Public submodules:
    identity: Entity identity and alias resolution
    knowledge: Character knowledge and propositions
    character: Character aggregate with knowledge, goals, and intents
    events: Event occurrence and timeline semantics
    promises: Promise lifecycle and fulfillment
    delta: NarrativeDelta finite change language and reducer preconditions
"""

# V2-008 NarrativeDelta
from .delta import (
    CommitId,
    DeltaId,
    EndFactOperation,
    EvidenceRef,
    ExpectAbsent,
    ExpectPresent,
    ExpectUnknown,
    ExpectValue,
    FactPath,
    FactValue,
    NarrativeDelta,
    Operation,
    OperationType,
    Precondition,
    Reducer,
    ReducerError,
    SetFactOperation,
    UndoFactOperation,
    ValidationResult,
    evaluate_precondition,
    validate_operation,
)

# V2-005 Entity Identity
# V2-061 Character
from .character import (
    ActionStatus,
    Character,
    CharacterLifecycle,
    Goal,
    GoalId,
    GoalStatus,
    Intent,
    IntentId,
    PlannedAction,
    PlannedActionId,
    create_character,
)

# V2-007 Event Timeline
from .events import (
    Event,
    EventId,
    IntervalTime,
    PreciseTime,
    RelativeTime,
    StoryTime,
    TemporalRelation,
    Timeline,
    compare_story_time,
    create_event,
    resolve_event_occurrence,
    validate_event_project_isolation,
)
from .identity import (
    EntityId,
    EntityIdentity,
    EntityRegistry,
    ProjectId,
    ResolutionResult,
    ResolutionStatus,
    add_alias,
    create_identity,
    normalize_for_lookup,
    remove_alias,
    rename_identity,
    resolve_alias,
)

# V2-061 Character Knowledge
from .knowledge import (
    AcquisitionSource,
    CharacterKnowledge,
    KnowledgeLevel,
    Proposition,
    PropositionId,
    create_proposition,
    freeze_context,
)

# V2-007 Promise
from .promises import (
    ContributionRole,
    Promise,
    PromiseFulfillmentLink,
    PromiseId,
    PromiseStatus,
    create_fulfillment_link,
    create_promise,
    derive_promise_status,
    validate_fulfillment_link_project_isolation,
    validate_link_uniqueness,
    validate_promise_project_isolation,
    validate_terminal_exclusivity,
)

__all__ = [
    # V2-008 NarrativeDelta
    "DeltaId",
    "CommitId",
    "NarrativeDelta",
    "Operation",
    "OperationType",
    "SetFactOperation",
    "EndFactOperation",
    "UndoFactOperation",
    "Precondition",
    "ExpectValue",
    "ExpectAbsent",
    "ExpectPresent",
    "ExpectUnknown",
    "FactPath",
    "FactValue",
    "EvidenceRef",
    "ValidationResult",
    "Reducer",
    "ReducerError",
    "validate_operation",
    "evaluate_precondition",
    # V2-005
    "EntityId",
    "ProjectId",
    "EntityIdentity",
    "ResolutionResult",
    "ResolutionStatus",
    "create_identity",
    "rename_identity",
    "add_alias",
    "remove_alias",
    "resolve_alias",
    "normalize_for_lookup",
    "EntityRegistry",
    # V2-061 Knowledge
    "PropositionId",
    "Proposition",
    "CharacterKnowledge",
    "KnowledgeLevel",
    "AcquisitionSource",
    "create_proposition",
    "freeze_context",
    # V2-061 Character
    "Character",
    "Goal",
    "Intent",
    "PlannedAction",
    "CharacterLifecycle",
    "GoalStatus",
    "ActionStatus",
    "GoalId",
    "IntentId",
    "PlannedActionId",
    "create_character",
    # V2-007 Events
    "EventId",
    "Event",
    "PreciseTime",
    "IntervalTime",
    "RelativeTime",
    "StoryTime",
    "TemporalRelation",
    "Timeline",
    "compare_story_time",
    "create_event",
    "resolve_event_occurrence",
    "validate_event_project_isolation",
    # V2-007 Promises
    "PromiseId",
    "Promise",
    "PromiseStatus",
    "PromiseFulfillmentLink",
    "ContributionRole",
    "derive_promise_status",
    "create_promise",
    "create_fulfillment_link",
    "validate_promise_project_isolation",
    "validate_fulfillment_link_project_isolation",
    "validate_terminal_exclusivity",
    "validate_link_uniqueness",
]
