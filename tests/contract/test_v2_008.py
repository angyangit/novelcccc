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
        content_hash="abc123",
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
            evidence=EvidenceRef("TEXT", "ch1:p1", "hash"),
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
            evidence=EvidenceRef("TEXT", "ch1:p1", "hash"),
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
            evidence=EvidenceRef("TEXT", "ch1:p1", "hash"),
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
            evidence=EvidenceRef("TEXT", "ch1:p1", "hash"),
        ).validate_schema()


def test_set_fact_missing_precondition_rejected():
    """SET_FACT without precondition is rejected (no implicit overwrite)."""
    with pytest.raises(
        ValueError, match="missing required field: precondition"
    ):
        SetFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj_01"),
            path=FactPath("age", int),
            value=30,
            precondition=None,  # Missing - implicit overwrite not allowed
            evidence=EvidenceRef("TEXT", "ch1:p1", "hash"),
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
            evidence=EvidenceRef("TEXT", "ch1", "hash"),
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
            evidence=EvidenceRef("TEXT", "ch1", "hash"),
        ).validate_schema()


def test_end_fact_missing_precondition_rejected():
    """END_FACT without precondition is rejected."""
    with pytest.raises(ValueError, match="missing required field: precondition"):
        EndFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj"),
            path=FactPath("age", int),
            precondition=None,
            evidence=EvidenceRef("TEXT", "ch1", "hash"),
        ).validate_schema()


def test_end_fact_expect_absent_rejected():
    """END_FACT with ExpectAbsent precondition is rejected (cannot end nonexistent)."""
    with pytest.raises(ValueError, match="cannot have ExpectAbsent precondition"):
        EndFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj"),
            path=FactPath("age", int),
            precondition=ExpectAbsent(),  # Invalid for END_FACT
            evidence=EvidenceRef("TEXT", "ch1", "hash"),
        ).validate_schema()


def test_end_fact_with_expect_present_validates():
    """END_FACT with ExpectPresent validates."""
    op = EndFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        precondition=ExpectPresent(),
        evidence=EvidenceRef("TEXT", "ch1", "hash"),
    )
    op.validate_schema()  # Should not raise


def test_end_fact_with_expect_value_validates():
    """END_FACT with ExpectValue validates."""
    op = EndFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        precondition=ExpectValue(expected_value=30),
        evidence=EvidenceRef("TEXT", "ch1", "hash"),
    )
    op.validate_schema()  # Should not raise


# --- UNDO_FACT Contract ---


def test_undo_fact_missing_original_commit_ref_rejected():
    """UNDO_FACT without original_commit_ref is rejected."""
    with pytest.raises(
        ValueError, match="missing required field: original_commit_ref"
    ):
        UndoFactOperation(
            subject=EntityId(str(uuid.uuid4())),
            scope=ProjectId("proj"),
            path=FactPath("age", int),
            original_commit_ref=None,  # Missing
            precondition=ExpectValue(expected_value=30),
            evidence=EvidenceRef("TEXT", "ch1", "hash"),
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
            evidence=EvidenceRef("TEXT", "ch1", "hash"),
        ).validate_schema()


def test_undo_fact_with_expect_value_validates():
    """UNDO_FACT with ExpectValue validates."""
    op = UndoFactOperation(
        subject=EntityId(str(uuid.uuid4())),
        scope=ProjectId("proj"),
        path=FactPath("age", int),
        original_commit_ref=CommitId("commit_123"),
        precondition=ExpectValue(expected_value=30),
        evidence=EvidenceRef("TEXT", "ch1", "hash"),
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
    assert not evaluate_precondition(precondition, current_value=None, path_exists=False)


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
    assert not evaluate_precondition(precondition, current_value=None, path_exists=False)


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
    assert not evaluate_precondition(precondition, current_value=None, path_exists=False)


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
        evidence=EvidenceRef("TEXT", "ch1", "hash"),
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
        evidence=EvidenceRef("TEXT", "ch1", "hash"),
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
        evidence=EvidenceRef("TEXT", "ch1", "hash"),
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
        evidence=EvidenceRef("TEXT", "ch1", "hash"),
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
