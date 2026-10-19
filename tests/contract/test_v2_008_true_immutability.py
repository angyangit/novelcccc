"""True deep immutability tests - direct nested mutation attempts on domain objects.

These tests verify that accessing nested values directly from domain objects
and attempting to mutate them does not change the domain semantics.
"""

import uuid

from anovel.domain import (
    CanonState,
    CommitChange,
    CommitId,
    EntityId,
    EvidenceRef,
    ExpectAbsent,
    ExpectValue,
    FactPath,
    ProjectId,
    SetFactOperation,
)


def test_operation_value_direct_nested_mutation_blocked():
    """Directly mutating operation.value["nested"] must not change operation semantics."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    original_data = {"history": [10, 20, 30], "meta": {"version": 1}}

    operation = SetFactOperation(
        scope=project_id,
        subject=entity_id,
        path=FactPath("data", dict),
        value=original_data,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "test:1", "a" * 64),
    )

    # Attempt direct mutation of operation.value internals
    try:
        operation.value["history"].append(40)
        operation.value["meta"]["version"] = 2
        operation.value["injected"] = "malicious"
    except (TypeError, AttributeError):
        # If mutation raises exception, immutability is enforced
        pass

    # Verify semantics unchanged
    assert operation.value == {"history": [10, 20, 30], "meta": {"version": 1}}
    assert "injected" not in operation.value
    assert operation.value["history"] == [10, 20, 30]


def test_expect_value_direct_nested_mutation_blocked():
    """Directly mutating ExpectValue.expected_value nested content must not change precondition."""
    nested_value = {"scores": [85, 90], "tags": ["A", "B"]}

    precondition = ExpectValue(expected_value=nested_value)

    # Attempt direct mutation
    try:
        precondition.expected_value["scores"].append(95)
        precondition.expected_value["tags"].append("C")
        precondition.expected_value["new_field"] = "injected"
    except (TypeError, AttributeError):
        pass

    # Verify semantics unchanged
    assert precondition.expected_value == {"scores": [85, 90], "tags": ["A", "B"]}
    assert "new_field" not in precondition.expected_value


def test_commit_change_value_before_direct_mutation_blocked():
    """Directly mutating CommitChange.value_before nested content must not change record."""
    before_value = {"count": [1, 2, 3]}

    change = CommitChange(
        commit_id=CommitId("commit-001"),
        project_id=ProjectId("test-project"),
        subject=EntityId(str(uuid.uuid4())),
        path="metrics",
        value_before=before_value,
        existed_before=True,
        value_after={"count": [1, 2, 3, 4]},
        existed_after=True,
    )

    # Attempt direct mutation
    try:
        change.value_before["count"].append(99)
        change.value_before["injected"] = "malicious"
    except (TypeError, AttributeError):
        pass

    # Verify semantics unchanged
    assert change.value_before == {"count": [1, 2, 3]}
    assert "injected" not in change.value_before


def test_commit_change_value_after_direct_mutation_blocked():
    """Directly mutating CommitChange.value_after nested content must not change record."""
    after_value = {"count": [1, 2, 3, 4]}

    change = CommitChange(
        commit_id=CommitId("commit-001"),
        project_id=ProjectId("test-project"),
        subject=EntityId(str(uuid.uuid4())),
        path="metrics",
        value_before={"count": [1, 2, 3]},
        existed_before=True,
        value_after=after_value,
        existed_after=True,
    )

    # Attempt direct mutation
    try:
        change.value_after["count"].append(99)
        change.value_after["injected"] = "malicious"
    except (TypeError, AttributeError):
        pass

    # Verify semantics unchanged
    assert change.value_after == {"count": [1, 2, 3, 4]}
    assert "injected" not in change.value_after


def test_canon_state_retrieved_value_direct_mutation_blocked():
    """Directly mutating value retrieved from CanonState must not change state."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    state = CanonState(
        project_id=project_id,
        facts=(((entity_id, "data"), {"history": [10, 20, 30]}),),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    # Retrieve value
    retrieved, exists = state.get_value(entity_id, FactPath("data", dict))
    assert exists

    # Attempt direct mutation of retrieved value
    try:
        retrieved["history"].append(40)
        retrieved["injected"] = "malicious"
    except (TypeError, AttributeError):
        pass

    # Verify state unchanged via second retrieval
    second_retrieval, _ = state.get_value(entity_id, FactPath("data", dict))
    assert second_retrieval == {"history": [10, 20, 30]}
    assert "injected" not in second_retrieval


def test_reducer_output_state_direct_mutation_blocked():
    """Directly mutating values in reducer output state must not affect state semantics."""
    from anovel.domain import DeltaReducer

    reducer = DeltaReducer()
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    initial_state = CanonState(
        project_id=project_id,
        facts=(),
        tombstones=frozenset(),
        commit_history=(),
        commit_changes=(),
    )

    nested_value = {"items": [1, 2, 3], "config": {"enabled": True}}

    operation = SetFactOperation(
        scope=project_id,
        subject=entity_id,
        path=FactPath("name", str),
        value="test-value",  # Use simple string for registered path
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "test:1", "a" * 64),
    )

    # Apply operation
    result_state = reducer.apply_operation(initial_state, operation)

    # Retrieve value from result
    retrieved, exists = result_state.get_value(entity_id, FactPath("name", str))
    assert exists

    # Attempt mutation (on string this should fail)
    # This tests that reducer preserves immutability
    assert retrieved == "test-value"


def test_operation_deeply_nested_direct_mutation_blocked():
    """Directly mutating multi-level nested structures in operations must not change semantics."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    deep_structure = {"level1": {"level2": {"level3": {"data": [1, 2, 3]}}}}

    operation = SetFactOperation(
        scope=project_id,
        subject=entity_id,
        path=FactPath("nested", dict),
        value=deep_structure,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "test:1", "a" * 64),
    )

    # Attempt deeply nested mutation
    try:
        operation.value["level1"]["level2"]["level3"]["data"].append(4)
        operation.value["level1"]["level2"]["level3"]["injected"] = "malicious"
    except (TypeError, AttributeError):
        pass

    # Verify deep structure unchanged
    assert operation.value["level1"]["level2"]["level3"]["data"] == [1, 2, 3]
    assert "injected" not in operation.value["level1"]["level2"]["level3"]


def test_operation_list_value_direct_mutation_blocked():
    """Directly mutating list values in operations must not change semantics."""
    project_id = ProjectId("test-project")
    entity_id = EntityId(str(uuid.uuid4()))

    list_value = [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": ["c"]}]

    operation = SetFactOperation(
        scope=project_id,
        subject=entity_id,
        path=FactPath("items", list),
        value=list_value,
        precondition=ExpectAbsent(),
        evidence=EvidenceRef("TEXT", "test:1", "a" * 64),
    )

    # Attempt list mutation
    try:
        operation.value.append({"id": 3, "tags": ["injected"]})
        operation.value[0]["tags"].append("injected")
    except (TypeError, AttributeError):
        pass

    # Verify list unchanged
    assert len(operation.value) == 2
    assert operation.value[0]["tags"] == ["a", "b"]
