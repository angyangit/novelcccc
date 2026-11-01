"""LLM-based Narrative Delta Extractor.

Uses LLM to extract state changes from prose with evidence.
NO PAID CALLS in this implementation - uses mock responses for testing.
"""

import hashlib
import uuid
from datetime import datetime

from ..contracts.models import ChapterContract
from ..domain.delta import DeltaId, NarrativeDelta
from ..domain.identity import ProjectId
from ..gateway.gateway import ModelGateway
from ..planning.models import SeriesVision
from .extractor import (
    ExtractionDiagnostic,
    ExtractionStatus,
    NarrativeDeltaExtractionResult,
)


class LLMExtractor:
    """LLM-based extractor using ModelGateway.

    V2-021 Implementation: Structure defined, NO PAID CALLS.
    Real extraction requires actual LLM provider integration.
    """

    def __init__(self, model_gateway: ModelGateway, enable_llm_calls: bool = False):
        """Initialize LLM extractor.

        Args:
            model_gateway: Model gateway for LLM access
            enable_llm_calls: If False, returns mock extraction (NO PAID CALLS)
        """
        self.model_gateway = model_gateway
        self.enable_llm_calls = enable_llm_calls

        if enable_llm_calls:
            raise NotImplementedError(
                "Real LLM extraction not implemented in V2-021. "
                "Set enable_llm_calls=False to use mock extraction for testing."
            )

    def extract(
        self,
        prose: str,
        prose_hash: str,
        contract: ChapterContract,
        series_vision: SeriesVision,
        canon_parent: str,
    ) -> NarrativeDeltaExtractionResult:
        """Extract narrative delta using LLM.

        V2-021: Returns mock extraction. Real LLM calls not implemented.
        """
        issues = []

        # Verify prose hash
        actual_hash = hashlib.sha256(prose.encode()).hexdigest()
        if actual_hash != prose_hash:
            issues.append(
                f"CRITICAL: Prose hash mismatch. "
                f"Expected {prose_hash[:16]}..., got {actual_hash[:16]}..."
            )
            return self._create_failed_result(prose_hash, issues)

        # V2-021: Mock extraction (no real LLM call)
        if not self.enable_llm_calls:
            return self._mock_extraction(
                prose, prose_hash, contract, series_vision, canon_parent
            )

        # Real LLM extraction (not implemented)
        raise NotImplementedError("Real LLM extraction requires V2-021+ implementation")

    def _mock_extraction(
        self,
        prose: str,
        prose_hash: str,
        contract: ChapterContract,
        series_vision: SeriesVision,
        canon_parent: str,
    ) -> NarrativeDeltaExtractionResult:
        """Mock extraction for testing without LLM calls."""
        issues = []

        # Check for test markers
        if "[MOCK CHAPTER PROSE]" in prose:
            issues.append("Mock prose marker detected")

        # Mock: Assume no transitions extracted (extraction not implemented)
        required_count = len(contract.required_transitions)

        if required_count > 0:
            status = ExtractionStatus.INCOMPLETE
            issues.append(
                f"LLM extraction not implemented: "
                f"{required_count} required transitions cannot be extracted"
            )
        else:
            status = ExtractionStatus.NO_CHANGES

        # Create empty delta
        delta_id = DeltaId(str(uuid.uuid4()))
        project_id = ProjectId(series_vision.series_id)

        delta = NarrativeDelta(
            delta_id=delta_id,
            project_id=project_id,
            operations=(),  # Empty - extraction not implemented
            source_chapter=contract.chapter_id,
            created_at=datetime.now(),
            authority="llm_extractor_v2021_mock",
            provenance=(
                ("extraction_method", "llm_mock_no_calls"),
                ("prose_hash", prose_hash),
                ("canon_parent", canon_parent),
            ),
        )

        diagnostics = ExtractionDiagnostic(
            coverage_percentage=0.0,  # Mock: no actual analysis
            required_transitions_found=0,
            required_transitions_missing=required_count,
            unexpected_changes_found=0,
            conflicting_evidence_count=0,
            uncertain_extractions=[],
            issues=issues.copy(),
        )

        return NarrativeDeltaExtractionResult(
            status=status,
            delta=delta,
            prose_hash=prose_hash,
            operation_evidence=[],
            diagnostics=diagnostics,
            extraction_method="llm_mock",
            extracted_at=datetime.now(),
            issues=issues,
        )

    def _create_failed_result(
        self, prose_hash: str, issues: list[str]
    ) -> NarrativeDeltaExtractionResult:
        """Create failed extraction result."""
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
            extraction_method="llm_extraction",
            extracted_at=datetime.now(),
            issues=issues,
        )

    def _prepare_extraction_prompt(
        self, prose: str, contract: ChapterContract, series_vision: SeriesVision
    ) -> str:
        """Prepare extraction prompt for LLM.

        Structure for future real LLM extraction.
        """
        prompt_parts = []

        prompt_parts.append("# Task: Extract Narrative State Changes")
        prompt_parts.append("\nAnalyze the following chapter prose and extract:")
        prompt_parts.append("1. Factual state changes that actually occurred")
        prompt_parts.append("2. Evidence locations in the prose")
        prompt_parts.append("3. Distinguish facts from beliefs, plans, and rumors")

        prompt_parts.append("\n## Required Transitions")
        if contract.required_transitions:
            for trans in contract.required_transitions:
                prompt_parts.append(
                    f"- {trans.fact_path}: {trans.target_value} ({trans.rationale})"
                )
        else:
            prompt_parts.append("(No required transitions)")

        prompt_parts.append("\n## Chapter Prose")
        prompt_parts.append(prose)

        prompt_parts.append("\n## Output Format")
        prompt_parts.append("Return JSON with:")
        prompt_parts.append("- operations: list of state changes")
        prompt_parts.append("- evidence: locations for each operation")
        prompt_parts.append("- coverage: percentage of prose analyzed")

        return "\n".join(prompt_parts)
