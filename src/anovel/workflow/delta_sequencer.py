"""Minimal Delta Sequencer

Orders operations by narrative evidence position and calculates correct preconditions.

Requirements:
- Use trusted frozen CanonState as input
- Order by actual narrative event sequence (evidence position)
- Track state per (subject, fact_path)
- First operation: precondition from Canon current value
- Subsequent operations: ExpectValue(previous_applied_value)
- Preserve operation-evidence correspondence
- All-or-nothing: any step fails, entire delta rejected
"""

from dataclasses import dataclass

from ..domain.delta import (
    CanonState,
    ExpectAbsent,
    ExpectValue,
    NarrativeDelta,
    SetFactOperation,
)


@dataclass
class SequencingResult:
    """Result of operation sequencing."""

    success: bool
    sequenced_operations: list[SetFactOperation]
    issues: list[str]


class DeltaSequencer:
    """Sequences operations with correct preconditions based on narrative order."""

    def sequence_operations(
        self, operations: list[SetFactOperation], canon_state: CanonState
    ) -> SequencingResult:
        """
        Order operations by evidence position and set correct preconditions.

        Args:
            operations: Candidate operations from extractor
            canon_state: Trusted frozen canon state

        Returns:
            SequencingResult with sequenced operations or issues
        """
        issues = []

        if not operations:
            return SequencingResult(
                success=True, sequenced_operations=[], issues=[]
            )

        # Step 1: Sort operations by evidence position (temporal order)
        sorted_ops = self._sort_by_evidence_position(operations)

        # Step 2: Group by (subject, fact_path) and calculate preconditions
        sequenced_ops = []
        state_tracker = {}  # (subject, fact_path) -> current_value

        # Initialize state tracker from canon
        for fact in canon_state.facts:
            key = (str(fact.subject), fact.path.path)
            state_tracker[key] = fact.value

        for op in sorted_ops:
            key = (str(op.subject), op.path.path)

            # Determine correct precondition
            if key in state_tracker:
                # Fact exists - expect current value
                expected_value = state_tracker[key]
                correct_precondition = ExpectValue(expected_value)
            else:
                # Fact doesn't exist - expect absent
                correct_precondition = ExpectAbsent()

            # Create new operation with correct precondition
            sequenced_op = SetFactOperation(
                operation_type=op.operation_type,
                operation_version=op.operation_version,
                subject=op.subject,
                scope=op.scope,
                path=op.path,
                value=op.value,
                precondition=correct_precondition,
                evidence=op.evidence,
            )

            sequenced_ops.append(sequenced_op)

            # Update state tracker with new value
            state_tracker[key] = op.value

        return SequencingResult(
            success=True, sequenced_operations=sequenced_ops, issues=issues
        )

    def _sort_by_evidence_position(
        self, operations: list[SetFactOperation]
    ) -> list[SetFactOperation]:
        """
        Sort operations by evidence position (start character).

        Evidence format: "chapter:START-END"
        Extract START and use for sorting.
        """
        def get_evidence_start(op: SetFactOperation) -> int:
            """Extract start position from evidence source_ref."""
            try:
                # Parse "chapter:123-456" -> 123
                ref = op.evidence.source_ref
                if ":" in ref:
                    positions = ref.split(":")[1]
                    start = positions.split("-")[0]
                    return int(start)
            except (ValueError, IndexError, AttributeError):
                pass
            return 0  # Default to start if can't parse

        return sorted(operations, key=get_evidence_start)
