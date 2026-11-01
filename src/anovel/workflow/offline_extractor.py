"""Offline/Fake Extractor for deterministic testing."""

import hashlib
import uuid
from datetime import datetime

from ..contracts.models import ChapterContract
from ..domain.delta import (
    DeltaId,
    EvidenceRef,
    ExpectAbsent,
    NarrativeDelta,
    OperationType,
    SetFactOperation,
    get_fact_path,
)
from ..domain.identity import EntityId, ProjectId
from ..planning.models import SeriesVision
from .extractor import (
    EvidenceLocation,
    ExtractionDiagnostic,
    ExtractionStatus,
    NarrativeDeltaExtractionResult,
    OperationEvidence,
)


class OfflineExtractor:
    """Deterministic offline extractor for testing.

    Uses predefined extraction fixtures based on prose content patterns.
    Simulates evidence extraction without LLM calls.
    """

    def extract(
        self,
        prose: str,
        prose_hash: str,
        contract: ChapterContract,
        series_vision: SeriesVision,
        canon_parent: str,
    ) -> NarrativeDeltaExtractionResult:
        """Extract using deterministic pattern matching.

        For testing purposes only. Real extraction requires LLM.
        """
        issues = []
        operation_evidence = []

        # Verify prose hash
        actual_hash = hashlib.sha256(prose.encode()).hexdigest()
        if actual_hash != prose_hash:
            issues.append(
                f"Prose hash mismatch: expected {prose_hash[:16]}..., "
                f"got {actual_hash[:16]}..."
            )
            return self._create_failed_result(prose_hash, issues)

        # Check for mock prose marker
        if "[MOCK CHAPTER PROSE]" in prose or "[OFFLINE TEST PROSE]" in prose:
            issues.append("Mock/test prose marker detected - not real content")

        # Analyze required transitions and construct real Operations
        required_count = len(contract.required_transitions)
        found_count = 0
        operations = []

        # Simple pattern matching (offline simulation)
        for i, transition in enumerate(contract.required_transitions):
            # Check if fact_path or target_value mentioned in prose
            fact_mentioned = transition.fact_path in prose
            value_str = str(transition.target_value) if transition.target_value else ""
            value_mentioned = value_str in prose if value_str else False

            if fact_mentioned or value_mentioned:
                # Simulate evidence location
                if fact_mentioned:
                    start_pos = prose.index(transition.fact_path)
                    end_pos = start_pos + len(transition.fact_path)
                    snippet = prose[
                        max(0, start_pos - 20) : min(len(prose), end_pos + 20)
                    ]
                else:
                    start_pos = 0
                    end_pos = 50
                    snippet = prose[:50]

                evidence_loc = EvidenceLocation(
                    start_char=start_pos,
                    end_char=end_pos,
                    text_snippet=snippet,
                    verified=True,
                )

                operation_evidence.append(
                    OperationEvidence(
                        operation_index=i,
                        fact_path=transition.fact_path,
                        extracted_value=transition.target_value,
                        evidence_locations=[evidence_loc],
                        confidence="confirmed",
                        extraction_rationale=f"Offline pattern match for {transition.fact_path}",
                    )
                )
                found_count += 1

                # Construct real SetFactOperation from extracted evidence
                try:
                    # Get FactPath from registry
                    fact_path = get_fact_path(transition.fact_path)

                    # Create EvidenceRef
                    evidence_ref = EvidenceRef(
                        source_type="TEXT",
                        source_ref=f"{contract.chapter_id}:{start_pos}-{end_pos}",
                        content_hash=prose_hash,
                    )

                    # Create Operation with proper subject and scope
                    # For offline testing: use dummy entity ID (real extractor would resolve from prose)
                    subject = EntityId("protagonist")  # Simplified for offline
                    scope = ProjectId(series_vision.series_id)

                    operation = SetFactOperation(
                        operation_type=OperationType.SET_FACT,
                        operation_version="1.0.0",
                        subject=subject,
                        scope=scope,
                        path=fact_path,
                        value=transition.target_value,
                        precondition=ExpectAbsent(),  # Simplified: assume new fact
                        evidence=evidence_ref,
                    )

                    # Validate operation schema
                    operation.validate_schema()
                    operations.append(operation)

                except ValueError as e:
                    # Path not in registry - mark as issue but continue
                    issues.append(
                        f"Cannot construct operation for {transition.fact_path}: {e}"
                    )

        # Determine status
        # If we found evidence but couldn't construct operations, that's incomplete
        operations_constructed = len(operations)

        if required_count > 0 and found_count == 0:
            status = ExtractionStatus.FAILED
        elif found_count < required_count:
            status = ExtractionStatus.INCOMPLETE
            issues.append(
                f"Required transitions: {found_count}/{required_count} extracted"
            )
        elif operations_constructed < found_count:
            # Found evidence but couldn't construct all operations
            status = ExtractionStatus.INCOMPLETE
            issues.append(
                f"Operations constructed: {operations_constructed}/{found_count} "
                f"(some fact paths not in registry)"
            )
        elif required_count == 0:
            status = ExtractionStatus.NO_CHANGES
        else:
            status = ExtractionStatus.SUCCESS

        # Create delta with real operations
        delta_id = DeltaId(str(uuid.uuid4()))
        project_id = ProjectId(series_vision.series_id)

        delta = NarrativeDelta(
            delta_id=delta_id,
            project_id=project_id,
            operations=tuple(operations),  # Real Operations constructed from evidence
            source_chapter=contract.chapter_id,
            created_at=datetime.now(),
            authority="offline_extractor_v2021",
            provenance=(
                ("extraction_method", "offline_pattern_match"),
                ("prose_hash", prose_hash),
                ("canon_parent", canon_parent),
            ),
        )

        # Owner要求: 不能固定声称100% coverage
        # Offline extractor只验证显式标记的required_transitions
        # 无法保证覆盖全部正文语义
        if required_count > 0:
            coverage_percentage = (found_count / required_count) * 100.0
        else:
            # 无required transitions时，无法计算有意义的coverage
            coverage_percentage = 0.0

        diagnostics = ExtractionDiagnostic(
            coverage_percentage=coverage_percentage,
            required_transitions_found=found_count,
            required_transitions_missing=required_count - found_count,
            unexpected_changes_found=0,  # Offline不检测unexpected changes
            conflicting_evidence_count=0,
            uncertain_extractions=[],
            issues=issues.copy(),
        )

        return NarrativeDeltaExtractionResult(
            status=status,
            delta=delta,
            prose_hash=prose_hash,
            operation_evidence=operation_evidence,
            diagnostics=diagnostics,
            extraction_method="offline_deterministic",
            extracted_at=datetime.now(),
            issues=issues,
        )

    def _create_failed_result(
        self, prose_hash: str, issues: list[str]
    ) -> NarrativeDeltaExtractionResult:
        """Create a failed extraction result."""
        return NarrativeDeltaExtractionResult(
            status=ExtractionStatus.FAILED,
            delta=None,
            prose_hash=prose_hash,
            operation_evidence=[],
            diagnostics=ExtractionDiagnostic(
                coverage_percentage=0.0,
                required_transitions_found=0,
                required_transitions_missing=0,
                unexpected_changes_found=0,
                conflicting_evidence_count=0,
                uncertain_extractions=[],
                issues=issues,
            ),
            extraction_method="offline_deterministic",
            extracted_at=datetime.now(),
            issues=issues,
        )
