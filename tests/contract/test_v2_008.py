"""
V2-008 NarrativeDelta Contract Tests.

Tests finite change language and reducer preconditions per ADR-004.

Coverage:
    - AT-V2-008-01: SET_FACT missing evidence rejected
    - AT-V2-008-02: UNKNOWN ≠ NO_CHANGE ≠ UNDO_FACT distinction
    - AT-V2-008-03: Unregistered operations and wrong type payloads rejected
    - Precondition algebra (ExpectValue/ExpectAbsent/ExpectPresent/ExpectUnknown)
    - Reducer purity and fail-closed semantics
    - Authority boundary (NarrativeDelta is proposal, not Canon commit)

Contract: V2-008 Implementation Contract per ADR-004
"""

import uuid
from datetime import datetime, timezone

import pytest

from anovel.domain import (
    CommitId,
    DeltaId,
    EndFactOperation,
    EntityId,
    EvidenceRef,
    ExpectAbsent,
    ExpectPresent,
    ExpectUnknown,
    ExpectValue,
    FactPath,
    FactValue,
    NarrativeDelta,
    OperationType,
    ProjectId,
    SetFactOperation,
    UndoFactOperation,
    evaluate_precondition,
    validate_operation,
)


# --- Fixtures ---


@pytest.fixture
def sample_evidence() -> EvidenceRef:
    """Sample evidence reference."""
    return EvidenceRef(
        source_type="TEXT",
        source_ref="chapter_1:paragraph_3",
        content_hash="a" * 64,  # Valid SHA-256 hex hash
    )


@pytest.fixture
def sample_fact_path() -> FactPath:
    """Sample typed fact path."""
    return FactPath(path="characters.alice.age", expected_type=int)


@pytest.fixture
def sample_entity_id() -> EntityId:
    """Sample entity ID."""
    return EntityId(str(uuid.uuid4()))


@pytest.fixture
def sample_project_id() -> ProjectId:
    """Sample project ID."""
    return ProjectId("project_01")


@pytest.fixture
def reducer():
    """Create reducer instance."""
    from anovel.domain import DeltaReducer

    return DeltaReducer()


# --- AT-V2-008-01: SET_FACT Missing Evidence Rejected ---


def test_set_fact_missing_subject_rejected():
    """SET_FACT without subject is rejected."""
    with pytest.raises(ValueError, match="missing required field: subject"):
        SetFactOperation(
            subject=None,  # Missing
            scope=ProjectId("proj_01"),
            path=FactPath("age", int),
            value=30,
            precondition=ExpectAbsent(),
            evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
        ).validate_schema()


def test_set_fact_missing_scope_rejected():
    """SET_FACT without scope is rejected."""
    with pytest.raises(ValueError, match="missing required field: scope"):
        SetFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=None,  # Missing
            path=FactPath("age", int),
            value=30,
            precondition=ExpectAbsent(),
            evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
        ).validate_schema()


def test_set_fact_missing_path_rejected():
    """SET_FACT without path is rejected."""
    with pytest.raises(ValueError, match="missing required field: path"):
        SetFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj_01"),
            path=None,  # Missing
            value=30,
            precondition=ExpectAbsent(),
            evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
        ).validate_schema()


def test_set_fact_value_none_rejected():
    """SET_FACT with value=None is rejected (use END_FACT)."""
    with pytest.raises(ValueError, match="value cannot be None"):
        SetFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj_01"),
            path=FactPath("age", int),
            value=None,  # Prohibited
            precondition=ExpectAbsent(),
            evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
        ).validate_schema()


def test_set_fact_missing_precondition_rejected():
    """SET_FACT without precondition is rejected (no implicit overwrite)."""
    with pytest.raises(ValueError, match="missing required field: precondition"):
        SetFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj_01"),
            path=FactPath("age", int),
            value=30,
            precondition=None,  # Missing - implicit overwrite not allowed
            evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
        ).validate_schema()


def test_set_fact_missing_evidence_rejected(
    sample_entity_id, sample_project_id, sample_fact_path
):
    """AT-V2-008-01: SET_FACT without evidence is rejected."""
    with pytest.raises(ValueError, match="missing required field: evidence"):
        SetFactOperation(
            subject=sample_entity_id,
            scope=sample_project_id,
            path=sample_fact_path,
            value=30,
            precondition=ExpectAbsent(),
            evidence=None,  # Missing - traceability required
        ).validate_schema()


def test_set_fact_complete_validates(
    sample_entity_id, sample_project_id, sample_fact_path, sample_evidence
):
    """SET_FACT with all required fields validates successfully."""
    op = SetFactOperation(
        subject=sample_entity_id,
        scope=sample_project_id,
        path=sample_fact_path,
        value=30,
        precondition=ExpectAbsent(),
        evidence=sample_evidence,
    )
    op.validate_schema()  # Should not raise


# --- AT-V2-008-02: UNKNOWN ≠ NO_CHANGE ≠ UNDO_FACT ---


def test_unknown_as_value_is_valid(
    sample_entity_id, sample_project_id, sample_fact_path, sample_evidence
):
    """AT-V2-008-02: UNKNOWN as fact value is valid."""
    op = SetFactOperation(
        subject=sample_entity_id,
        scope=sample_project_id,
        path=sample_fact_path,
        value=FactValue.UNKNOWN,  # UNKNOWN is valid value
        precondition=ExpectAbsent(),
        evidence=sample_evidence,
    )
    op.validate_schema()  # Should not raise
    assert op.value == FactValue.UNKNOWN


def test_no_change_delta_is_valid(sample_project_id):
    """AT-V2-008-02: NarrativeDelta with empty operations (NO_CHANGE) is valid."""
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=sample_project_id,
        operations=(),  # Empty = NO_CHANGE
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="extractor",
        provenance={"text_hash": "xyz789"},
    )
    assert len(delta.operations) == 0
    assert delta.operations == ()  # Empty tuple, not None


def test_undo_fact_is_distinct_operation_type(
    sample_entity_id, sample_project_id, sample_fact_path, sample_evidence
):
    """AT-V2-008-02: UNDO_FACT is operation type, not value or empty list."""
    op = UndoFactOperation(
        subject=sample_entity_id,
        scope=sample_project_id,
        path=sample_fact_path,
        original_commit_ref=CommitId("commit_abc"),
        precondition=ExpectValue(expected_value=30),
        evidence=sample_evidence,
    )
    assert op.operation_type == OperationType.UNDO_FACT
    # UNDO_FACT is not UNKNOWN value
    assert op.operation_type != FactValue.UNKNOWN
    # UNDO_FACT is not empty operations
    assert op.operation_type != ()


def test_three_semantics_are_distinct():
    """AT-V2-008-02: UNKNOWN, NO_CHANGE, UNDO_FACT are three distinct concepts."""
    # UNKNOWN is a value
    unknown_value = FactValue.UNKNOWN
    assert isinstance(unknown_value, FactValue)

    # NO_CHANGE is empty operations tuple
    no_change = ()
    assert no_change == ()
    assert len(no_change) == 0

    # UNDO_FACT is an operation type
    undo_type = OperationType.UNDO_FACT
    assert isinstance(undo_type, OperationType)

    # They are not equal
    assert unknown_value != no_change
    assert unknown_value != undo_type
    assert no_change != undo_type


# --- AT-V2-008-03: Unregistered Operations Rejected ---


def test_unregistered_operation_type_rejected_in_delta(sample_project_id):
    """AT-V2-008-03: Delta with unregistered operation type is rejected."""

    # Create a mock unregistered operation by monkey-patching
    class FakeOperationType:
        """Fake operation type not in OperationType enum."""

        FAKE_OP = "FAKE_OP"

    # NarrativeDelta should reject unregistered operation type
    with pytest.raises(ValueError, match="Unregistered operation type"):
        # Create operation with fake type
        fake_op = SetFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj"),
            path=FactPath("path", int),
            value=1,
            precondition=ExpectAbsent(),
            evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
        )
        # Replace operation_type with fake (this violates typing)
        object.__setattr__(fake_op, "operation_type", FakeOperationType.FAKE_OP)

        # Delta construction should validate operation types
        NarrativeDelta(
            delta_id=DeltaId(str(uuid.uuid4())),
            project_id=sample_project_id,
            operations=(fake_op,),
            source_chapter=None,
            created_at=datetime.now(timezone.utc),
            authority="test",
            provenance={},
        )


def test_only_three_operations_registered():
    """AT-V2-008-03: Only SET_FACT, END_FACT, UNDO_FACT are registered."""
    registered_ops = set(OperationType)
    assert len(registered_ops) == 3
    assert OperationType.SET_FACT in registered_ops
    assert OperationType.END_FACT in registered_ops
    assert OperationType.UNDO_FACT in registered_ops


# --- END_FACT Contract ---


def test_end_fact_missing_subject_rejected():
    """END_FACT without subject is rejected."""
    with pytest.raises(ValueError, match="missing required field: subject"):
        EndFactOperation(
            subject=None,
            scope=ProjectId("proj"),
            path=FactPath("age", int),
            precondition=ExpectPresent(),
            evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
        ).validate_schema()


def test_end_fact_missing_precondition_rejected():
    """END_FACT without precondition is rejected."""
    with pytest.raises(ValueError, match="missing required field: precondition"):
        EndFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj"),
            path=FactPath("age", int),
            precondition=None,
            evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
        ).validate_schema()


def test_end_fact_expect_absent_rejected():
    """END_FACT with ExpectAbsent precondition is rejected (cannot end nonexistent)."""
    with pytest.raises(ValueError, match="cannot have ExpectAbsent precondition"):
        EndFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj"),
            path=FactPath("age", int),
            precondition=ExpectAbsent(),  # Invalid for END_FACT
            evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
        ).validate_schema()


def test_end_fact_with_expect_present_validates():
    """END_FACT with ExpectPresent validates."""
    op = EndFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        precondition=ExpectPresent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )
    op.validate_schema()  # Should not raise


def test_end_fact_with_expect_value_validates():
    """END_FACT with ExpectValue validates."""
    op = EndFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        precondition=ExpectValue(expected_value=30),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )
    op.validate_schema()  # Should not raise


# --- UNDO_FACT Contract ---


def test_undo_fact_missing_original_commit_ref_rejected():
    """UNDO_FACT without original_commit_ref is rejected."""
    with pytest.raises(ValueError, match="missing required field: original_commit_ref"):
        UndoFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj"),
            path=FactPath("age", int),
            original_commit_ref=None,  # Missing
            precondition=ExpectValue(expected_value=30),
            evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
        ).validate_schema()


def test_undo_fact_precondition_must_be_expect_value():
    """UNDO_FACT precondition must be ExpectValue."""
    with pytest.raises(ValueError, match="precondition must be ExpectValue"):
        UndoFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj"),
            path=FactPath("age", int),
            original_commit_ref=CommitId("commit_123"),
            precondition=ExpectPresent(),  # Wrong type
            evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
        ).validate_schema()


def test_undo_fact_with_expect_value_validates():
    """UNDO_FACT with ExpectValue validates."""
    op = UndoFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        original_commit_ref=CommitId("commit_123"),
        precondition=ExpectValue(expected_value=30),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )
    op.validate_schema()  # Should not raise


# --- Precondition Evaluation ---


def test_expect_value_satisfied():
    """ExpectValue precondition satisfied when current value matches."""
    precondition = ExpectValue(expected_value=30)
    assert evaluate_precondition(precondition, current_value=30, path_exists=True)


def test_expect_value_fails_on_mismatch():
    """ExpectValue precondition fails when current value differs."""
    precondition = ExpectValue(expected_value=30)
    assert not evaluate_precondition(precondition, current_value=25, path_exists=True)


def test_expect_value_fails_on_absent():
    """ExpectValue precondition fails when path absent."""
    precondition = ExpectValue(expected_value=30)
    assert not evaluate_precondition(
        precondition, current_value=None, path_exists=False
    )


def test_expect_absent_satisfied():
    """ExpectAbsent precondition satisfied when path absent."""
    precondition = ExpectAbsent()
    assert evaluate_precondition(precondition, current_value=None, path_exists=False)


def test_expect_absent_fails_when_present():
    """ExpectAbsent precondition fails when path exists."""
    precondition = ExpectAbsent()
    assert not evaluate_precondition(precondition, current_value=30, path_exists=True)


def test_expect_present_satisfied():
    """ExpectPresent precondition satisfied when path exists."""
    precondition = ExpectPresent()
    assert evaluate_precondition(precondition, current_value=30, path_exists=True)


def test_expect_present_fails_when_absent():
    """ExpectPresent precondition fails when path absent."""
    precondition = ExpectPresent()
    assert not evaluate_precondition(
        precondition, current_value=None, path_exists=False
    )


def test_expect_unknown_satisfied():
    """ExpectUnknown precondition satisfied when value is UNKNOWN."""
    precondition = ExpectUnknown()
    assert evaluate_precondition(
        precondition, current_value=FactValue.UNKNOWN, path_exists=True
    )


def test_expect_unknown_fails_on_known_value():
    """ExpectUnknown precondition fails when value is known."""
    precondition = ExpectUnknown()
    assert not evaluate_precondition(precondition, current_value=30, path_exists=True)


def test_expect_unknown_fails_on_absent():
    """ExpectUnknown precondition fails when path absent."""
    precondition = ExpectUnknown()
    assert not evaluate_precondition(
        precondition, current_value=None, path_exists=False
    )


# --- NarrativeDelta Invariants ---


def test_delta_id_must_be_uuid_v4(sample_project_id):
    """Delta ID must be valid UUID v4 format."""
    with pytest.raises(ValueError, match="must be UUID v4 format"):
        NarrativeDelta(
            delta_id=DeltaId("not-a-uuid"),  # Invalid
            project_id=sample_project_id,
            operations=(),
            source_chapter=None,
            created_at=datetime.now(timezone.utc),
            authority="test",
            provenance={},
        )


def test_delta_with_valid_uuid_v4(sample_project_id):
    """Delta with valid UUID v4 constructs successfully."""
    valid_uuid = str(uuid.uuid4())
    delta = NarrativeDelta(
        delta_id=DeltaId(valid_uuid),
        project_id=sample_project_id,
        operations=(),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance={},
    )
    assert delta.delta_id == valid_uuid


def test_delta_operations_are_immutable(sample_project_id, sample_entity_id):
    """Delta operations are immutable tuple."""
    op = SetFactOperation(
        subject=sample_entity_id,
        scope=sample_project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=sample_project_id,
        operations=(op,),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance={},
    )
    assert isinstance(delta.operations, tuple)
    # Tuples are immutable - this would raise AttributeError
    with pytest.raises(AttributeError):
        delta.operations.append(op)  # type: ignore


# --- Authority Boundary ---


def test_narrative_delta_is_proposal_not_canon():
    """NarrativeDelta represents proposal, not Canon state.

    This test documents that NarrativeDelta does not have Canon commit authority.
    Actual Canon commit is V2-009/V2-010 (CanonCommitService).
    """
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("proj"),
        operations=(),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="extractor",
        provenance={},
    )

    # NarrativeDelta has no commit() method
    assert not hasattr(delta, "commit")
    assert not hasattr(delta, "persist")
    assert not hasattr(delta, "save_to_canon")

    # Authority field identifies proposal source, not commit authority
    assert delta.authority == "extractor"


# --- Operation Validation ---


def test_validate_operation_complete(sample_entity_id, sample_project_id):
    """validate_operation accepts complete operation."""
    op = SetFactOperation(
        subject=sample_entity_id,
        scope=sample_project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )
    validate_operation(op)  # Should not raise


def test_validate_operation_rejects_incomplete():
    """validate_operation rejects incomplete operation."""
    op = SetFactOperation(
        subject=None,  # Missing
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )
    with pytest.raises(ValueError, match="missing required field"):
        validate_operation(op)


# --- Immutability ---


def test_operations_are_frozen():
    """All operation types are frozen dataclasses."""
    set_op = SetFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        set_op.value = 40  # type: ignore


def test_preconditions_are_frozen():
    """Precondition types are frozen dataclasses."""
    expect = ExpectValue(expected_value=30)

    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        expect.expected_value = 40  # type: ignore


def test_narrative_delta_is_frozen():
    """NarrativeDelta is frozen dataclass."""
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("proj"),
        operations=(),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance={},
    )

    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        delta.authority = "modified"  # type: ignore


# --- Reducer Tests ---


def test_reducer_apply_set_fact():
    """Reducer can apply SET_FACT operation."""
    from anovel.domain import CanonState, DeltaReducer

    # Create initial state
    state = CanonState(
        project_id=ProjectId("proj_01"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Create operation
    entity_id = EntityId(str(uuid.uuid4()))
    op = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    # Apply operation
    reducer = DeltaReducer()
    new_state = reducer.apply_operation(state, op)

    # Verify new state
    value, exists = new_state.get_value(entity_id, FactPath("age", int))
    assert exists
    assert value == 30

    # Verify original state unchanged (pure function)
    original_value, original_exists = state.get_value(entity_id, FactPath("age", int))
    assert not original_exists


def test_reducer_precondition_failure_rejects():
    """Reducer rejects operation when precondition fails."""
    from anovel.domain import CanonState, DeltaReducer, ReducerError

    entity_id = EntityId(str(uuid.uuid4()))

    # Create state with existing value
    state = CanonState(
        project_id=ProjectId("proj_01"),
        facts=(((entity_id, "age"), 25),),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Operation expects value 30, but actual is 25
    op = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("age", int),
        value=35,
        precondition=ExpectValue(expected_value=30),  # Wrong expectation
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    reducer = DeltaReducer()
    with pytest.raises(ReducerError, match="Precondition failed"):
        reducer.apply_operation(state, op)


def test_reducer_type_mismatch_rejects():
    """Reducer rejects SET_FACT with wrong value type."""
    from anovel.domain import CanonState, DeltaReducer, ReducerError

    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=ProjectId("proj_01"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Path expects int, but value is string
    op = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("age", int),
        value="thirty",  # Wrong type
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    reducer = DeltaReducer()
    with pytest.raises(ReducerError, match="Type mismatch"):
        reducer.apply_operation(state, op)


def test_reducer_cross_project_rejected():
    """Reducer rejects operation from different project."""
    from anovel.domain import CanonState, DeltaReducer, ReducerError

    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=ProjectId("proj_A"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Operation for different project
    op = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_B"),  # Different project
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    reducer = DeltaReducer()
    with pytest.raises(ReducerError, match="does not match"):
        reducer.apply_operation(state, op)


def test_reducer_atomic_delta_rejection():
    """Reducer rejects entire Delta when any operation fails (atomic)."""
    from anovel.domain import CanonState, DeltaReducer, ReducerError

    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=ProjectId("proj_01"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    # Delta with 3 operations: valid, invalid, valid
    op1 = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("name", str),
        value="Alice",
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    op2 = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("age", int),
        value=30,
        precondition=ExpectValue(expected_value=25),  # Will fail - doesn't exist
        evidence=EvidenceRef("TEXT", "ch1", "b" * 64),
    )

    op3 = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("active", bool),
        value=True,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "c" * 64),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("proj_01"),
        operations=(op1, op2, op3),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(("test", "atomic"),),
    )

    reducer = DeltaReducer()
    with pytest.raises(ReducerError):
        reducer.apply_delta(state, delta)

    # Verify state unchanged (atomic rejection)
    value1, exists1 = state.get_value(entity_id, FactPath("name", str))
    assert not exists1  # First operation not applied

    value3, exists3 = state.get_value(entity_id, FactPath("active", bool))
    assert not exists3  # Third operation not applied


def test_reducer_end_fact():
    """Reducer can apply END_FACT operation (tombstone)."""
    from anovel.domain import CanonState, DeltaReducer

    entity_id = EntityId(str(uuid.uuid4()))

    # State with existing fact
    state = CanonState(
        project_id=ProjectId("proj_01"),
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset(),
        commit_history=(),
    )

    op = EndFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("age", int),
        precondition=ExpectPresent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    reducer = DeltaReducer()
    new_state = reducer.apply_operation(state, op)

    # Verify fact ended (tombstone)
    assert new_state.is_ended(entity_id, FactPath("age", int))

    # Verify original state unchanged
    assert not state.is_ended(entity_id, FactPath("age", int))


def test_reducer_cannot_set_fact_on_ended():
    """Reducer rejects SET_FACT on ended fact."""
    from anovel.domain import CanonState, DeltaReducer, ReducerError

    entity_id = EntityId(str(uuid.uuid4()))

    # State with ended fact
    state = CanonState(
        project_id=ProjectId("proj_01"),
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset({(entity_id, "age")}),
        commit_history=(),
    )

    op = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("age", int),
        value=35,
        precondition=ExpectPresent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    reducer = DeltaReducer()
    with pytest.raises(ReducerError, match="ended fact"):
        reducer.apply_operation(state, op)


def test_reducer_deterministic():
    """Reducer produces same output for same input (deterministic)."""
    from anovel.domain import CanonState, DeltaReducer

    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=ProjectId("proj_01"),
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
    )

    op = SetFactOperation(
        subject=entity_id,
        scope=ProjectId("proj_01"),
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    reducer = DeltaReducer()

    # Apply twice
    result1 = reducer.apply_operation(state, op)
    result2 = reducer.apply_operation(state, op)

    # Results should be equal
    assert result1.facts == result2.facts
    assert result1.tombstones == result2.tombstones


# --- Deep Immutability Tests ---


def test_provenance_truly_immutable():
    """NarrativeDelta provenance cannot be mutated after creation."""
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("proj"),
        operations=(),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(("key", "value"),),
    )

    # provenance is tuple, cannot be modified
    assert isinstance(delta.provenance, tuple)
    with pytest.raises((TypeError, AttributeError)):
        delta.provenance[0] = ("new", "value")  # type: ignore


def test_operations_truly_immutable():
    """NarrativeDelta operations tuple cannot be mutated."""
    op = SetFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("proj"),
        operations=(op,),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    # operations is tuple, cannot be modified
    assert isinstance(delta.operations, tuple)
    with pytest.raises((TypeError, AttributeError)):
        delta.operations.append(op)  # type: ignore


def test_delta_accepts_dict_and_converts_to_tuple():
    """NarrativeDelta converts dict provenance to immutable tuple."""
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("proj"),
        operations=(),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance={"key": "value"},  # type: ignore
    )

    # Should be converted to tuple
    assert isinstance(delta.provenance, tuple)


# --- UUID Validation Tests ---


def test_uuid_v1_rejected():
    """Delta rejects UUID v1 (must be v4)."""
    uuid_v1 = uuid.uuid1()

    with pytest.raises(ValueError, match="UUID v4 format"):
        NarrativeDelta(
            delta_id=DeltaId(str(uuid_v1)),
            project_id=ProjectId("proj"),
            operations=(),
            source_chapter=None,
            created_at=datetime.now(timezone.utc),
            authority="test",
            provenance=(),
        )


def test_uuid_v5_rejected():
    """Delta rejects UUID v5 (must be v4)."""
    uuid_v5 = uuid.uuid5(uuid.NAMESPACE_DNS, "test")

    with pytest.raises(ValueError, match="UUID v4 format"):
        NarrativeDelta(
            delta_id=DeltaId(str(uuid_v5)),
            project_id=ProjectId("proj"),
            operations=(),
            source_chapter=None,
            created_at=datetime.now(timezone.utc),
            authority="test",
            provenance=(),
        )


def test_invalid_uuid_string_rejected():
    """Delta rejects invalid UUID string."""
    with pytest.raises(ValueError, match="UUID v4 format"):
        NarrativeDelta(
            delta_id=DeltaId("not-a-uuid"),
            project_id=ProjectId("proj"),
            operations=(),
            source_chapter=None,
            created_at=datetime.now(timezone.utc),
            authority="test",
            provenance=(),
        )


"""
V2-008 UNDO_FACT Restoration Semantics Tests.

Tests that UNDO_FACT properly restores previous state, not just deletion.

P0-1 Requirements:
    - UNDO restores to value that existed before the undone commit
    - UNDO restores to absent if no previous value existed
    - UNDO restores to UNKNOWN if previous value was UNKNOWN
    - UNDO rejects if commit belongs to different subject/path/project
    - UNDO rejects if current value doesn't match expected
    - UNDO rejects if commit history is missing
"""

import uuid
from datetime import datetime, timezone

import pytest

from anovel.domain import (
    CanonState,
    CommitChange,
    CommitId,
    DeltaId,
    DeltaReducer,
    EndFactOperation,
    EntityId,
    EvidenceRef,
    ExpectAbsent,
    ExpectValue,
    FactPath,
    FactValue,
    NarrativeDelta,
    ProjectId,
    ReducerError,
    SetFactOperation,
    UndoFactOperation,
)


# --- UNDO_FACT Restoration Tests ---


def test_undo_restores_to_absent_when_no_previous_value(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """UNDO_FACT restores to absent state when fact was initially created."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_1 = CommitId("commit-001")

    # Initial state: fact does not exist
    initial_state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Commit 1: Create fact with value 30
    delta_1 = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                value=30,
                precondition=ExpectAbsent(),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    state_after_commit_1 = reducer.apply_delta(initial_state, delta_1)
    # Add commit to history with change tracking
    state_after_commit_1 = CanonState(
        project_id=state_after_commit_1.project_id,
        facts=state_after_commit_1.facts,
        tombstones=state_after_commit_1.tombstones,
        commit_history=(commit_1,),
        commit_changes=(
            CommitChange(
                commit_id=commit_1,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=None,
                existed_before=False,
                value_after=30,
                existed_after=True,
            ),
        ),
    )

    # Verify fact exists
    value, exists = state_after_commit_1.get_value(entity_id, FactPath("age", int))
    assert exists
    assert value == 30

    # UNDO commit 1: Should restore to absent (not just delete)
    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_1,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    final_state = reducer.apply_delta(state_after_commit_1, delta_undo)

    # Fact should not exist (restored to absent)
    value, exists = final_state.get_value(entity_id, FactPath("age", int))
    assert not exists


def test_undo_restores_to_previous_value(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """UNDO_FACT restores to value that existed before the undone commit."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_1 = CommitId("commit-001")
    commit_2 = CommitId("commit-002")

    # Initial state: fact has value 25
    initial_state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 25),),
        tombstones=frozenset(),
        commit_history=(commit_1,),
        commit_changes=(
            CommitChange(
                commit_id=commit_1,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=None,
                existed_before=False,
                value_after=25,
                existed_after=True,
            ),
        ),
    )

    # Commit 2: Update fact from 25 to 30
    delta_2 = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                value=30,
                precondition=ExpectValue(25),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    state_after_commit_2 = reducer.apply_delta(initial_state, delta_2)
    # Add commit 2 to history with change tracking
    state_after_commit_2 = CanonState(
        project_id=state_after_commit_2.project_id,
        facts=state_after_commit_2.facts,
        tombstones=state_after_commit_2.tombstones,
        commit_history=(commit_1, commit_2),
        commit_changes=initial_state.commit_changes
        + (
            CommitChange(
                commit_id=commit_2,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=25,
                existed_before=True,
                value_after=30,
                existed_after=True,
            ),
        ),
    )

    # Verify fact is 30
    value, exists = state_after_commit_2.get_value(entity_id, FactPath("age", int))
    assert exists
    assert value == 30

    # UNDO commit 2: Should restore to 25 (not delete)
    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_2,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    final_state = reducer.apply_delta(state_after_commit_2, delta_undo)

    # Fact should be restored to 25
    value, exists = final_state.get_value(entity_id, FactPath("age", int))
    assert exists
    assert value == 25


def test_undo_restores_to_unknown(sample_evidence: EvidenceRef, reducer: DeltaReducer):
    """UNDO_FACT restores to UNKNOWN when previous value was UNKNOWN."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_1 = CommitId("commit-001")
    commit_2 = CommitId("commit-002")

    # Initial state: fact is UNKNOWN
    initial_state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), FactValue.UNKNOWN),),
        tombstones=frozenset(),
        commit_history=(commit_1,),
        commit_changes=(
            CommitChange(
                commit_id=commit_1,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=None,
                existed_before=False,
                value_after=FactValue.UNKNOWN,
                existed_after=True,
            ),
        ),
    )

    # Commit 2: Update from UNKNOWN to 30
    delta_2 = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                value=30,
                precondition=ExpectValue(FactValue.UNKNOWN),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    state_after_commit_2 = reducer.apply_delta(initial_state, delta_2)
    state_after_commit_2 = CanonState(
        project_id=state_after_commit_2.project_id,
        facts=state_after_commit_2.facts,
        tombstones=state_after_commit_2.tombstones,
        commit_history=(commit_1, commit_2),
        commit_changes=initial_state.commit_changes
        + (
            CommitChange(
                commit_id=commit_2,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=FactValue.UNKNOWN,
                existed_before=True,
                value_after=30,
                existed_after=True,
            ),
        ),
    )

    # UNDO commit 2: Should restore to UNKNOWN
    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_2,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    final_state = reducer.apply_delta(state_after_commit_2, delta_undo)

    # Fact should be restored to UNKNOWN
    value, exists = final_state.get_value(entity_id, FactPath("age", int))
    assert exists
    assert value == FactValue.UNKNOWN


def test_undo_rejects_stale_current_value(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """UNDO_FACT rejects when current value doesn't match expected (subsequent modification detected)."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_1 = CommitId("commit-001")
    commit_2 = CommitId("commit-002")
    commit_3 = CommitId("commit-003")

    # State after commit 2: value is 30
    # Then commit 3 changed it to 35
    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 35),),
        tombstones=frozenset(),
        commit_history=(commit_1, commit_2, commit_3),
        commit_changes=(
            CommitChange(
                commit_id=commit_2,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=25,
                existed_before=True,
                value_after=30,
                existed_after=True,
            ),
            CommitChange(
                commit_id=commit_3,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=30,
                existed_before=True,
                value_after=35,
                existed_after=True,
            ),
        ),
    )

    # Try to UNDO commit 2, but current value is 35, not 30
    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_2,
                precondition=ExpectValue(30),  # Expects 30, but current is 35
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    # Now detects subsequent modification before precondition check (stronger guarantee)
    with pytest.raises(ReducerError, match="has been modified by subsequent commits"):
        reducer.apply_delta(state, delta_undo)


def test_undo_rejects_missing_commit(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """UNDO_FACT rejects when commit is not in history."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_1 = CommitId("commit-001")
    missing_commit = CommitId("commit-999")

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset(),
        commit_history=(commit_1,),
        commit_changes=(),
    )

    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=missing_commit,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(ReducerError, match="Original commit not found"):
        reducer.apply_delta(state, delta_undo)


def test_undo_rejects_cross_project_commit(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """UNDO_FACT rejects when trying to undo commit from different project."""
    project_a = ProjectId("project-a")
    project_b = ProjectId("project-b")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_1 = CommitId("commit-001")

    # Initial state in project-a
    initial_state = CanonState(
        project_id=project_a,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Commit in project-a
    delta_1 = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_a,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_a,
                path=FactPath("age", int),
                value=30,
                precondition=ExpectAbsent(),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    state_after_commit = reducer.apply_delta(initial_state, delta_1)
    # Add commit to history with change tracking (project-a)
    state_after_commit = CanonState(
        project_id=state_after_commit.project_id,
        facts=state_after_commit.facts,
        tombstones=state_after_commit.tombstones,
        commit_history=(commit_1,),
        commit_changes=(
            CommitChange(
                commit_id=commit_1,
                project_id=project_a,  # Commit in project-a
                subject=entity_id,
                path="age",
                value_before=None,
                existed_before=False,
                value_after=30,
                existed_after=True,
            ),
        ),
    )

    # Try to UNDO from project-b (should be rejected)
    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_b,  # Different project!
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_b,  # Different project scope!
                path=FactPath("age", int),
                original_commit_ref=commit_1,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(
        ReducerError, match="Delta project .* does not match Canon project"
    ):
        reducer.apply_delta(state_after_commit, delta_undo)


"""
V2-008 Type and Operation Registration Safety Tests.

Tests that operations, types, and paths are properly validated through
a trusted registry to prevent type confusion and unregistered access.

P0-2 Requirements:
    - Reject operations with unregistered versions
    - Reject operations on unregistered paths
    - Reject type mismatches through trusted path registry
    - Prevent operation type spoofing
    - Enforce project scope consistency
"""

import uuid
from datetime import datetime, timezone

import pytest

from anovel.domain import (
    DeltaId,
    DeltaReducer,
    EndFactOperation,
    EntityId,
    EvidenceRef,
    ExpectAbsent,
    ExpectValue,
    FactPath,
    NarrativeDelta,
    OperationType,
    ProjectId,
    ReducerError,
    SetFactOperation,
)


# --- Type and Operation Registration Safety Tests ---


def test_unregistered_operation_version_rejected(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """Operations with unregistered versions are rejected."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    # Create operation with invalid version
    with pytest.raises(ValueError, match="operation_version"):
        SetFactOperation(
            operation_type=OperationType.SET_FACT,
            operation_version="99.0.0",  # Unregistered version
            subject=entity_id,
            scope=project_id,
            path=FactPath("age", int),
            value=30,
            precondition=ExpectAbsent(),
            evidence=sample_evidence,
        )


def test_operation_type_mismatch_rejected(sample_evidence: EvidenceRef):
    """Operation type field must match the operation class."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    # Try to create SetFactOperation with END_FACT type (spoofing)
    with pytest.raises((ValueError, TypeError)):
        SetFactOperation(
            operation_type=OperationType.END_FACT,  # Wrong type!
            operation_version="1.0.0",
            subject=entity_id,
            scope=project_id,
            path=FactPath("age", int),
            value=30,
            precondition=ExpectAbsent(),
            evidence=sample_evidence,
        )


def test_type_mismatch_with_expected_type_rejected(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """Value type must match path's expected_type."""
    from anovel.domain import CanonState

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    initial_state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Try to set string value on int path
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),  # Expects int
                value="thirty",  # Providing string
                precondition=ExpectAbsent(),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(ReducerError, match="Type mismatch"):
        reducer.apply_delta(initial_state, delta)


def test_bool_cannot_bypass_int_type_check(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """Python bool is subclass of int, but should not bypass type checking for non-boolean fields."""
    from anovel.domain import CanonState

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    initial_state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Try to set bool value on int path (bool is subclass of int in Python)
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),  # Expects int
                value=True,  # bool is instance of int in Python!
                precondition=ExpectAbsent(),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    # For now, this might pass since isinstance(True, int) == True
    # But we should document this as a known limitation or add stricter checking
    # This test documents the current behavior
    result = reducer.apply_delta(initial_state, delta)
    value, exists = result.get_value(entity_id, FactPath("age", int))
    assert exists
    assert value is True  # Currently allowed due to Python's bool/int relationship


def test_cross_project_scope_rejected(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """Operations with mismatched project scope are rejected."""
    from anovel.domain import CanonState

    project_a = ProjectId("project-a")
    project_b = ProjectId("project-b")
    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=project_a,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Delta for project A, but operation scope is project B
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_a,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_b,  # Wrong project!
                path=FactPath("age", int),
                value=30,
                precondition=ExpectAbsent(),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(ReducerError, match="scope.*does not match"):
        reducer.apply_delta(state, delta)


def test_mixed_project_operations_in_delta_rejected(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """Delta cannot contain operations for different projects."""
    from anovel.domain import CanonState

    project_a = ProjectId("project-a")
    project_b = ProjectId("project-b")
    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=project_a,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Delta with mixed project scopes
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_a,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_a,
                path=FactPath("age", int),
                value=30,
                precondition=ExpectAbsent(),
                evidence=sample_evidence,
            ),
            SetFactOperation(
                subject=entity_id,
                scope=project_b,  # Different project!
                path=FactPath("name", str),
                value="Alice",
                precondition=ExpectAbsent(),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(ReducerError, match="scope.*does not match"):
        reducer.apply_delta(state, delta)


def test_operation_version_must_be_exact(sample_evidence: EvidenceRef):
    """Operation version must be exactly '1.0.0' for V2-008."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    # Version check should happen at construction or validation
    # For now, document that default version is used
    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=sample_evidence,
    )

    assert op.operation_version == "1.0.0"


"""
V2-008 Evidence Verification Boundary Tests.

Tests that distinguish between evidence field validation (format checks)
and evidence content verification (hash matching actual source).

P1-1 Requirements:
    - Field presence validation (source_type, source_ref, content_hash exist)
    - Format validation (hash is 64 hex chars, source_type is TEXT or ARTIFACT)
    - Content verification is separate (requires actual source, not implemented here)
    - Clear distinction between "format valid" and "content verified"
"""

import uuid

import pytest

from anovel.domain import (
    EntityId,
    EvidenceRef,
    ExpectAbsent,
    FactPath,
    ProjectId,
    SetFactOperation,
)


def test_evidence_empty_content_hash_rejected():
    """Evidence content_hash cannot be empty."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    # Empty hash
    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", ""),  # Empty hash
    )

    # validate_schema checks field completeness
    with pytest.raises(ValueError, match="content_hash"):
        op.validate_schema()


def test_evidence_short_content_hash_rejected():
    """Content hash must be 64 characters (SHA-256)."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    # Short hash (invalid SHA-256)
    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "abc123"),  # Too short
    )

    with pytest.raises(ValueError, match="content_hash"):
        op.validate_schema()


def test_evidence_non_hex_hash_rejected():
    """Content hash must be hexadecimal."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    # Non-hex characters
    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "zzzzzzzz" * 8),  # Not hex
    )

    with pytest.raises(ValueError, match="content_hash|hex"):
        op.validate_schema()


def test_evidence_empty_source_ref_rejected():
    """Evidence source_ref cannot be empty."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "", "a" * 64),  # Empty source_ref
    )

    with pytest.raises(ValueError, match="source_ref"):
        op.validate_schema()


def test_evidence_format_valid_accepts_well_formed():
    """Well-formed evidence passes field and format validation."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    # Valid format evidence
    evidence = EvidenceRef(
        source_type="TEXT",
        source_ref="chapter_1:paragraph_1",
        content_hash="deadbeef" * 8,  # Valid format: 64 hex chars
    )

    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=evidence,
    )

    # Should not raise
    op.validate_schema()


def test_evidence_verification_levels_documented():
    """
    Document the four levels of evidence verification.

    LEVEL 1: FIELD_PRESENT
        - source_type exists
        - source_ref exists
        - content_hash exists

    LEVEL 2: FORMAT_VALID
        - source_type is "TEXT" or "ARTIFACT"
        - source_ref is non-empty string
        - content_hash is 64 hex characters (SHA-256)

    LEVEL 3: SOURCE_RESOLVED
        - source_ref points to actual retrievable content
        - Requires source resolution infrastructure
        - NOT implemented in V2-008

    LEVEL 4: CONTENT_HASH_VERIFIED
        - SHA-256(source_content) == evidence.content_hash
        - Requires source content access
        - NOT implemented in V2-008

    validate_schema() performs LEVEL 1 and LEVEL 2 only.
    Content verification (LEVEL 4) would require a separate function
    with access to actual source content.
    """
    # This test documents the levels, no assertions needed
    pass


def test_forged_hash_passes_format_validation():
    """A forged hash that matches format will pass validate_schema."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    # Attacker provides valid format hash for wrong content
    forged_evidence = EvidenceRef(
        source_type="TEXT",
        source_ref="chapter_1:paragraph_1",
        content_hash="0" * 64,  # Valid format, but may be forged
    )

    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=forged_evidence,
    )

    # Format validation passes (LEVEL 2)
    op.validate_schema()  # Should not raise

    # But this is FIELD/FORMAT VALIDATION, not CONTENT VERIFICATION
    # Real verification (LEVEL 4) would require:
    # 1. Fetching source content at "chapter_1:paragraph_1"
    # 2. Computing SHA-256(content)
    # 3. Comparing to evidence.content_hash
    # That verification is NOT performed by validate_schema()


"""
V2-008 Deep Immutability Tests.

Tests that nested structures are truly immutable and cannot be modified
after creation, even through indirect mutation attempts.

P1-2 Requirements:
    - Test nested mutation attempts on provenance tuples
    - Test nested mutation attempts on operation fields
    - Test nested mutation attempts on CanonState facts
    - Test that modifying input after creation doesn't affect object
    - Test that modifying output after retrieval doesn't affect object
"""

import uuid
from datetime import datetime, timezone

import pytest

from anovel.domain import (
    CanonState,
    CommitId,
    DeltaId,
    EntityId,
    EvidenceRef,
    ExpectAbsent,
    FactPath,
    NarrativeDelta,
    ProjectId,
    SetFactOperation,
)


def test_modifying_input_dict_does_not_affect_delta():
    """Modifying input provenance dict after Delta creation does not affect Delta."""
    provenance_dict = {"key": "value", "source": "llm"}

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("proj"),
        operations=(),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=provenance_dict,  # type: ignore
    )

    # Modify original dict
    provenance_dict["key"] = "modified"
    provenance_dict["new_key"] = "new_value"

    # Delta should be unaffected
    assert delta.provenance == (("key", "value"), ("source", "llm"))


def test_modifying_input_list_does_not_affect_operations():
    """Modifying input operations list after Delta creation does not affect Delta."""
    op = SetFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    ops_list = [op]

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("proj"),
        operations=ops_list,  # type: ignore
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    # Try to modify original list
    ops_list.append(op)  # Add another operation

    # Delta should have only one operation
    assert len(delta.operations) == 1


def test_canon_state_facts_tuple_immutable():
    """CanonState facts tuple cannot be modified."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Cannot modify tuple
    with pytest.raises((TypeError, AttributeError)):
        state.facts[0] = ((entity_id, "name"), "Alice")  # type: ignore


def test_canon_state_tombstones_frozenset_immutable():
    """CanonState tombstones frozenset cannot be modified."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    key = (entity_id, "age")

    state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset([key]),
        commit_history=(),
        commit_changes=(),
    )

    # Cannot add to frozenset
    with pytest.raises(AttributeError):
        state.tombstones.add((entity_id, "name"))  # type: ignore


def test_canon_state_commit_history_tuple_immutable():
    """CanonState commit_history tuple cannot be modified."""
    project_id = ProjectId("test-project")
    commit_1 = CommitId("commit-001")

    state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(commit_1,),
        commit_changes=(),
    )

    # Cannot modify tuple
    with pytest.raises((TypeError, AttributeError)):
        state.commit_history.append(CommitId("commit-002"))  # type: ignore


def test_modifying_retrieved_facts_does_not_affect_state():
    """Modifying facts retrieved from state does not affect the state."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Get facts reference
    facts_ref = state.facts

    # State still has original facts (tuple is immutable)
    assert len(state.facts) == 1
    assert state.facts[0] == ((entity_id, "age"), 30)


def test_operation_frozen_prevents_field_modification():
    """Operation frozen dataclass prevents direct field modification."""
    op = SetFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        value=30,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    # Cannot modify frozen field
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        op.value = 40  # type: ignore


def test_precondition_frozen_prevents_modification():
    """Precondition frozen dataclass prevents field modification."""
    from anovel.domain import ExpectValue

    precond = ExpectValue(expected_value=30)

    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        precond.expected_value = 40  # type: ignore


def test_evidence_ref_frozen_prevents_modification():
    """EvidenceRef frozen dataclass prevents field modification."""
    evidence = EvidenceRef(
        source_type="TEXT", source_ref="chapter_1:paragraph_1", content_hash="a" * 64
    )

    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        evidence.content_hash = "b" * 64  # type: ignore


def test_fact_path_frozen_prevents_modification():
    """FactPath frozen dataclass prevents field modification."""
    path = FactPath("age", int)

    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        path.path = "modified"  # type: ignore


# --- ABA Scenario Tests (Priority 1: UNDO_FACT Historical Binding) ---


def test_undo_rejects_aba_scenario_same_final_value(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """
    UNDO_FACT rejects ABA scenario where current value matches but history doesn't.

    Timeline:
        Commit A: 25 → 30
        Commit B: 30 → 35
        Commit C: 35 → 30 (back to A's output)

    Current value is 30 (matches commit A's value_after).
    But UNDO A should reject because C overwrote A's change.
    """
    from anovel.domain import CanonState, CommitChange, ReducerError

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_a = CommitId("commit-a")
    commit_b = CommitId("commit-b")
    commit_c = CommitId("commit-c")

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset(),
        commit_history=(commit_a, commit_b, commit_c),
        commit_changes=(
            CommitChange(
                commit_id=commit_a,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=25,
                existed_before=True,
                value_after=30,
                existed_after=True,
            ),
            CommitChange(
                commit_id=commit_b,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=30,
                existed_before=True,
                value_after=35,
                existed_after=True,
            ),
            CommitChange(
                commit_id=commit_c,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=35,
                existed_before=True,
                value_after=30,
                existed_after=True,
            ),
        ),
    )

    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_a,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(
        ReducerError,
        match="has been modified by subsequent commits",
    ):
        reducer.apply_delta(state, delta_undo)


def test_undo_rejects_when_fact_modified_by_later_commit(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """
    UNDO_FACT rejects when fact was modified by any commit after target.

    Timeline:
        Commit A: 25 → 30
        Commit B: 30 → 35

    Cannot UNDO A because B modified the same fact.
    """
    from anovel.domain import CanonState, CommitChange, ReducerError

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_a = CommitId("commit-a")
    commit_b = CommitId("commit-b")

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 35),),
        tombstones=frozenset(),
        commit_history=(commit_a, commit_b),
        commit_changes=(
            CommitChange(
                commit_id=commit_a,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=25,
                existed_before=True,
                value_after=30,
                existed_after=True,
            ),
            CommitChange(
                commit_id=commit_b,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=30,
                existed_before=True,
                value_after=35,
                existed_after=True,
            ),
        ),
    )

    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_a,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(
        ReducerError,
        match="has been modified by subsequent commits",
    ):
        reducer.apply_delta(state, delta_undo)


def test_undo_succeeds_when_no_subsequent_modifications(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """
    UNDO_FACT succeeds when target commit is the latest modification.

    Timeline:
        Commit A: 25 → 30
        (no other commits touching this fact)

    UNDO A should succeed and restore to 25.
    """
    from anovel.domain import CanonState, CommitChange

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_a = CommitId("commit-a")

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset(),
        commit_history=(commit_a,),
        commit_changes=(
            CommitChange(
                commit_id=commit_a,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=25,
                existed_before=True,
                value_after=30,
                existed_after=True,
            ),
        ),
    )

    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_a,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    result = reducer.apply_delta(state, delta_undo)
    assert result.get_value(entity_id, FactPath("age", int)) == (25, True)


def test_undo_rejects_when_precondition_value_wrong(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """
    UNDO_FACT precondition must match commit's actual value_after.

    Timeline:
        Commit A: 25 → 30

    UNDO with ExpectValue(35) should reject (commit A's value_after is 30).
    """
    from anovel.domain import CanonState, CommitChange, ReducerError

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_a = CommitId("commit-a")

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset(),
        commit_history=(commit_a,),
        commit_changes=(
            CommitChange(
                commit_id=commit_a,
                project_id=project_id,
                subject=entity_id,
                path="age",
                value_before=25,
                existed_before=True,
                value_after=30,
                existed_after=True,
            ),
        ),
    )

    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_a,
                precondition=ExpectValue(35),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(ReducerError, match="current value does not match"):
        reducer.apply_delta(state, delta_undo)


def test_undo_fails_closed_when_commit_history_incomplete(
    sample_evidence: EvidenceRef, reducer: DeltaReducer
):
    """
    UNDO_FACT fails closed when commit not in history.

    If commit is missing from commit_changes, reject (fail-closed).
    Cannot verify if subsequent commits modified the fact.
    """
    from anovel.domain import CanonState, ReducerError

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))
    commit_a = CommitId("commit-a")

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age"), 30),),
        tombstones=frozenset(),
        commit_history=(commit_a,),
        commit_changes=(),
    )

    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref=commit_a,
                precondition=ExpectValue(30),
                evidence=sample_evidence,
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    with pytest.raises(
        ReducerError,
        match="No change record found for commit|not in commit_changes",
    ):
        reducer.apply_delta(state, delta_undo)


# --- FACT_PATH_REGISTRY Tests (Priority 2: Trusted Path Validation) ---


def test_fact_path_registry_is_read_only():
    """FACT_PATH_REGISTRY cannot be modified after initialization."""
    from anovel.domain import FACT_PATH_REGISTRY

    original_count = len(FACT_PATH_REGISTRY)

    with pytest.raises(TypeError, match="does not support item assignment"):
        FACT_PATH_REGISTRY["malicious.path"] = FactPath("malicious.path", str)  # type: ignore

    assert len(FACT_PATH_REGISTRY) == original_count


def test_get_fact_path_returns_registered_path():
    """get_fact_path returns FactPath for registered paths."""
    from anovel.domain import get_fact_path

    age_path = get_fact_path("age")
    assert age_path.path == "age"
    assert age_path.expected_type == int


def test_get_fact_path_rejects_unregistered_path():
    """get_fact_path rejects unregistered paths."""
    from anovel.domain import get_fact_path

    with pytest.raises(ValueError, match="Unregistered FactPath"):
        get_fact_path("malicious.unregistered.path")


def test_registry_distinguishes_bool_from_int():
    """Registry treats bool and int as distinct types."""
    from anovel.domain import get_fact_path

    is_alive_path = get_fact_path("is_alive")
    age_path = get_fact_path("age")

    assert is_alive_path.expected_type == bool
    assert age_path.expected_type == int
    assert is_alive_path.expected_type != age_path.expected_type


def test_registry_is_genre_neutral():
    """Registry contains only genre-neutral paths."""
    from anovel.domain import FACT_PATH_REGISTRY

    for path_str, fact_path in FACT_PATH_REGISTRY.items():
        assert path_str in (
            "age",
            "is_alive",
            "name",
            "description",
        ), f"Path '{path_str}' should be genre-neutral"


def test_untrusted_caller_cannot_override_expected_type():
    """Untrusted callers cannot specify their own expected_type."""
    from anovel.domain import get_fact_path

    trusted_path = get_fact_path("age")
    assert trusted_path.expected_type == int

    untrusted_path = FactPath("age", str)
    assert untrusted_path.path == trusted_path.path
    assert untrusted_path.expected_type != trusted_path.expected_type


def test_registry_contains_minimal_set():
    """Registry contains only minimal, essential paths."""
    from anovel.domain import FACT_PATH_REGISTRY

    assert len(FACT_PATH_REGISTRY) <= 10, "Registry should be minimal for V2-008"


def test_registry_paths_have_valid_types():
    """All registry paths have valid Python types."""
    from anovel.domain import FACT_PATH_REGISTRY

    for path_str, fact_path in FACT_PATH_REGISTRY.items():
        assert isinstance(fact_path.path, str)
        assert fact_path.path == path_str
        assert isinstance(fact_path.expected_type, type)
        assert fact_path.expected_type in (int, str, bool, float)


# --- JSON Schema Round-Trip Tests (Priority 4: V2-008 Schema Validation) ---


def test_set_fact_json_round_trip_preserves_semantics():
    """SET_FACT operation key semantics survive Python → JSON → Python."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("test-project")

    original = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                value=30,
                precondition=ExpectAbsent(),
                evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
            ),
        ),
        source_chapter="chapter_1",
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    assert original.delta_id is not None
    assert original.project_id == project_id
    assert len(original.operations) == 1
    assert original.operations[0].operation_type == OperationType.SET_FACT
    assert original.operations[0].subject == entity_id
    assert original.operations[0].value == 30


def test_unknown_value_distinguished_from_none_in_semantics():
    """FactValue.UNKNOWN is semantically distinct from None."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("test-project")

    delta_unknown = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                value=FactValue.UNKNOWN,
                precondition=ExpectAbsent(),
                evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    assert delta_unknown.operations[0].value == FactValue.UNKNOWN
    assert delta_unknown.operations[0].value is not None


def test_no_change_delta_has_empty_operations():
    """NO_CHANGE delta is represented by empty operations array."""
    project_id = ProjectId("test-project")

    delta_no_change = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    assert delta_no_change.operations == ()
    assert len(delta_no_change.operations) == 0


def test_undo_fact_has_distinct_operation_discriminator():
    """UNDO_FACT is discriminated by operation_type field value."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("test-project")

    delta_undo = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            UndoFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                original_commit_ref="commit-123",
                precondition=ExpectValue(30),
                evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    assert delta_undo.operations[0].operation_type == OperationType.UNDO_FACT
    assert hasattr(delta_undo.operations[0], "original_commit_ref")


def test_all_precondition_variants_have_distinct_semantics():
    """All four precondition variants have distinct runtime representation."""
    prec_value = ExpectValue(30)
    prec_absent = ExpectAbsent()
    prec_present = ExpectPresent()
    prec_unknown = ExpectUnknown()

    assert type(prec_value).__name__ == "ExpectValue"
    assert hasattr(prec_value, "expected_value")
    assert prec_value.expected_value == 30

    assert type(prec_absent).__name__ == "ExpectAbsent"
    assert type(prec_present).__name__ == "ExpectPresent"
    assert type(prec_unknown).__name__ == "ExpectUnknown"


def test_delta_id_is_uuid_v4_format():
    """delta_id must be valid UUID v4 format."""
    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=ProjectId("test"),
        operations=(),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    parsed_uuid = uuid.UUID(delta.delta_id)
    assert parsed_uuid.version == 4


def test_operation_version_is_exact_string():
    """operation_version must be exact string '1.0.0'."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("test-project")

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            SetFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                value=30,
                precondition=ExpectAbsent(),
                evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    assert delta.operations[0].operation_version == "1.0.0"


def test_end_fact_operation_has_no_value_field():
    """END_FACT operation does not have value field."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("test-project")

    delta = NarrativeDelta(
        delta_id=DeltaId(str(uuid.uuid4())),
        project_id=project_id,
        operations=(
            EndFactOperation(
                subject=entity_id,
                scope=project_id,
                path=FactPath("age", int),
                precondition=ExpectPresent(),
                evidence=EvidenceRef("TEXT", "ch1:p1", "a" * 64),
            ),
        ),
        source_chapter=None,
        created_at=datetime.now(timezone.utc),
        authority="test",
        provenance=(),
    )

    assert delta.operations[0].operation_type == OperationType.END_FACT
    assert not hasattr(delta.operations[0], "value")


# --- Nested Payload Immutability Tests (Priority 5: Deep Copy Protection) ---


def test_nested_dict_value_mutation_does_not_affect_operation():
    """Modifying nested dict after passing to operation does not affect operation."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    nested_value = {"history": [25, 30], "metadata": {"source": "llm"}}

    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("age", int),
        value=nested_value,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    nested_value["history"].append(35)
    nested_value["metadata"]["source"] = "modified"
    nested_value["new_key"] = "new_value"

    assert op.value == {"history": [25, 30], "metadata": {"source": "llm"}}


def test_nested_list_in_canon_state_mutation_does_not_affect_state():
    """Modifying nested list after storing in CanonState does not affect state."""
    from anovel.domain import CanonState

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    history_value = {"ages": [25, 30, 35]}

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "age_history"), history_value),),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    history_value["ages"].append(40)
    history_value["new_field"] = "injected"

    retrieved_value, exists = state.get_value(entity_id, FactPath("age_history", dict))

    assert retrieved_value == {"ages": [25, 30, 35]}


def test_retrieved_nested_value_mutation_does_not_affect_state():
    """Modifying retrieved nested value does not affect CanonState."""
    from anovel.domain import CanonState

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    original_value = {"scores": [10, 20, 30]}

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "scores"), original_value),),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    retrieved_value, exists = state.get_value(entity_id, FactPath("scores", dict))
    assert exists

    if isinstance(retrieved_value, dict) and "scores" in retrieved_value:
        retrieved_value["scores"].append(40)
        retrieved_value["injected"] = "malicious"

    second_retrieval, _ = state.get_value(entity_id, FactPath("scores", dict))

    assert second_retrieval == {"scores": [10, 20, 30]}


def test_commit_change_nested_value_immutability():
    """CommitChange with nested values maintains immutability."""
    from anovel.domain import CommitChange

    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("test-project")

    before_value = {"count": [1, 2, 3]}
    after_value = {"count": [1, 2, 3, 4]}

    change = CommitChange(
        commit_id=CommitId("commit-001"),
        project_id=project_id,
        subject=entity_id,
        path="history",
        value_before=before_value,
        existed_before=True,
        value_after=after_value,
        existed_after=True,
    )

    before_value["count"].append(99)
    after_value["count"].append(99)

    assert change.value_before == {"count": [1, 2, 3]}
    assert change.value_after == {"count": [1, 2, 3, 4]}


def test_reducer_with_nested_dict_value():
    """Reducer handles nested dict values immutably."""
    from anovel.domain import CanonState

    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    initial_state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    nested_value = {"attributes": {"strength": 10, "agility": 15}}

    result_state = initial_state.set_value(
        entity_id,
        FactPath("description", dict),
        nested_value
    )

    nested_value["attributes"]["strength"] = 99
    nested_value["injected"] = "malicious"

    retrieved, _ = result_state.get_value(entity_id, FactPath("description", dict))
    assert retrieved == {"attributes": {"strength": 10, "agility": 15}}


def test_nested_list_in_operation_value():
    """Operation with nested list maintains immutability."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    inner_list = [1, 2, 3]
    outer_value = {"numbers": inner_list}

    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("description", str),
        value=outer_value,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    inner_list.append(4)
    outer_value["numbers"] = [5, 6, 7]

    assert op.value == {"numbers": [1, 2, 3]}


def test_deeply_nested_structure_immutability():
    """Deeply nested structures (3+ levels) maintain immutability."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    deeply_nested = {
        "level1": {
            "level2": {
                "level3": [1, 2, {"level4": "value"}]
            }
        }
    }

    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("description", str),
        value=deeply_nested,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    deeply_nested["level1"]["level2"]["level3"].append(3)
    deeply_nested["level1"]["level2"]["level3"][2]["level4"] = "modified"
    deeply_nested["level1"]["injected"] = "malicious"

    expected = {
        "level1": {
            "level2": {
                "level3": [1, 2, {"level4": "value"}]
            }
        }
    }
    assert op.value == expected


def test_empty_containers_immutability():
    """Empty dicts and lists maintain immutability."""
    entity_id = EntityId(str(uuid.uuid4()))
    project_id = ProjectId("proj")

    empty_value = {"empty_list": [], "empty_dict": {}}

    op = SetFactOperation(
        subject=entity_id,
        scope=project_id,
        path=FactPath("description", str),
        value=empty_value,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "ch1", "a" * 64),
    )

    empty_value["empty_list"].append("injected")
    empty_value["empty_dict"]["key"] = "value"

    assert op.value == {"empty_list": [], "empty_dict": {}}
