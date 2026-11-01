"""V2-021 NarrativeDelta Extractor - Core Interface and Models.

Extracts narrative state changes from chapter prose with evidence binding.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from ..domain.delta import NarrativeDelta


class ExtractionStatus(StrEnum):
    """Extraction result status."""

    SUCCESS = "success"  # All required transitions extracted with evidence
    INCOMPLETE = "incomplete"  # Some transitions missing or uncertain
    FAILED = "failed"  # Extraction failed
    NO_CHANGES = "no_changes"  # Confirmed no state changes (not just no extraction)
    CONFLICTED = "conflicted"  # Conflicting evidence found


@dataclass
class EvidenceLocation:
    """Location of evidence in prose."""

    start_char: int  # Character offset in prose
    end_char: int  # End character offset
    text_snippet: str  # Actual text from prose
    verified: bool  # True if location verified against prose


@dataclass
class OperationEvidence:
    """Evidence for a single operation."""

    operation_index: int  # Index in NarrativeDelta.operations
    fact_path: str
    extracted_value: Any
    evidence_locations: list[EvidenceLocation]
    confidence: str  # "confirmed" | "probable" | "uncertain"
    extraction_rationale: str


@dataclass
class ExtractionDiagnostic:
    """Diagnostic information about extraction."""

    coverage_percentage: float  # Percentage of prose analyzed
    required_transitions_found: int
    required_transitions_missing: int
    unexpected_changes_found: int
    conflicting_evidence_count: int
    uncertain_extractions: list[str]  # Fact paths with uncertain evidence
    issues: list[str]  # Human-readable issues


@dataclass
class NarrativeDeltaExtractionResult:
    """Complete extraction result with evidence and diagnostics."""

    status: ExtractionStatus
    delta: NarrativeDelta | None
    prose_hash: str  # SHA-256 of prose
    operation_evidence: list[OperationEvidence]
    diagnostics: ExtractionDiagnostic
    extraction_method: str
    extracted_at: datetime
    issues: list[str]  # Critical issues blocking commit


class NarrativeDeltaExtractor(Protocol):
    """Protocol for narrative delta extraction.

    Implementations must extract state changes from prose with verifiable evidence.
    """

    def extract(
        self,
        prose: str,
        prose_hash: str,
        contract: Any,  # ChapterContract
        series_vision: Any,  # SeriesVision
        canon_parent: str,
    ) -> NarrativeDeltaExtractionResult:
        """Extract NarrativeDelta from chapter prose.

        Args:
            prose: Complete chapter prose
            prose_hash: SHA-256 hash of prose
            contract: ChapterContract with required_transitions
            series_vision: SeriesVision for project context
            canon_parent: Current canon parent hash

        Returns:
            NarrativeDeltaExtractionResult with:
            - status: SUCCESS only if all required transitions extracted
            - delta: NarrativeDelta with operations
            - operation_evidence: Evidence for each operation
            - diagnostics: Coverage and conflict analysis

        Fail-Closed Semantics:
        - Missing required transitions → status=INCOMPLETE
        - Conflicting evidence → status=CONFLICTED
        - Unverifiable locations → operation excluded
        - Uncertain belief vs fact → marked in confidence
        """
        ...
