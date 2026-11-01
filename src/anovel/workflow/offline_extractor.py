"""Offline/Fake Extractor for deterministic testing."""

import hashlib
import uuid
from datetime import datetime

from ..contracts.models import ChapterContract
from ..domain.delta import DeltaId, NarrativeDelta
from ..domain.identity import ProjectId
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

        # Analyze required transitions
        required_count = len(contract.required_transitions)
        found_count = 0

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
                    snippet = prose[max(0, start_pos - 20) : min(len(prose), end_pos + 20)]
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

        # Determine status
        if required_count > 0 and found_count == 0:
            status = ExtractionStatus.FAILED
        elif found_count < required_count:
            status = ExtractionStatus.INCOMPLETE
            issues.append(
                f"Required transitions: {found_count}/{required_count} extracted"
            )
        elif required_count == 0:
            status = ExtractionStatus.NO_CHANGES
        else:
            status = ExtractionStatus.SUCCESS

        # Create delta
        delta_id = DeltaId(str(uuid.uuid4()))
        project_id = ProjectId(series_vision.series_id)

        # For offline: use empty operations (real extractor would create actual Operations)
        delta = NarrativeDelta(
            delta_id=delta_id,
            project_id=project_id,
            operations=(),  # Offline stub
            source_chapter=contract.chapter_id,
            created_at=datetime.now(),
            authority="offline_extractor_v2021",
            provenance=(
                ("extraction_method", "offline_pattern_match"),
                ("prose_hash", prose_hash),
                ("canon_parent", canon_parent),
            ),
        )

        diagnostics = ExtractionDiagnostic(
            coverage_percentage=100.0,  # Offline assumes full coverage
            required_transitions_found=found_count,
            required_transitions_missing=required_count - found_count,
            unexpected_changes_found=0,
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
