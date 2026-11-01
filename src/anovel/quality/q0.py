"""V2-022 Q0 Deterministic Quality Validators.

Zero-cost deterministic checks per ADR-011:
- Verify required artifacts present
- Verify prose hash matches
- Verify delta evidence hash matches
- Fail-closed: ERROR/UNKNOWN/unauthorized SKIP cannot pass

These are deterministic validators that run before any LLM-based quality checks.
"""

from dataclasses import dataclass
from enum import StrEnum

from ..contracts.models import ChapterContract
from ..workflow.extractor import NarrativeDeltaExtractionResult


class Q0CheckStatus(StrEnum):
    """Q0 check result status."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass
class Q0CheckResult:
    """Result of a single Q0 check."""

    check_name: str
    status: Q0CheckStatus
    message: str


@dataclass
class Q0ValidationResult:
    """Complete Q0 validation result."""

    passed: bool  # True only if ALL checks passed
    checks: list[Q0CheckResult]
    blocking_issues: list[str]


class Q0Validator:
    """Deterministic Q0 quality validator.

    Performs zero-cost checks that must pass before any LLM-based validation.
    """

    def validate(
        self,
        extraction_result: NarrativeDeltaExtractionResult,
        contract: ChapterContract,
        prose: str,
        prose_hash: str,
    ) -> Q0ValidationResult:
        """Run all Q0 deterministic checks.

        Args:
            extraction_result: Extraction result to validate
            contract: Chapter contract
            prose: Original chapter prose
            prose_hash: Expected prose hash

        Returns:
            Q0ValidationResult with pass/fail for each check
        """
        checks: list[Q0CheckResult] = []
        blocking_issues: list[str] = []

        # Q0-01: Required artifacts present
        check = self._check_required_artifacts(extraction_result, contract, prose)
        checks.append(check)
        if check.status != Q0CheckStatus.PASS:
            blocking_issues.append(f"Q0-01: {check.message}")

        # Q0-02: Prose hash matches
        check = self._check_prose_hash(extraction_result, prose, prose_hash)
        checks.append(check)
        if check.status != Q0CheckStatus.PASS:
            blocking_issues.append(f"Q0-02: {check.message}")

        # Q0-03: Delta evidence hash matches
        if extraction_result.delta:
            check = self._check_delta_evidence_hash(extraction_result, prose_hash)
            checks.append(check)
            if check.status != Q0CheckStatus.PASS:
                blocking_issues.append(f"Q0-03: {check.message}")

        # Q0-04: Operations have valid evidence
        if extraction_result.delta and len(extraction_result.delta.operations) > 0:
            check = self._check_operations_evidence(extraction_result)
            checks.append(check)
            if check.status != Q0CheckStatus.PASS:
                blocking_issues.append(f"Q0-04: {check.message}")

        # Q0-05: Evidence locations verified
        check = self._check_evidence_locations_verified(extraction_result)
        checks.append(check)
        if check.status != Q0CheckStatus.PASS:
            blocking_issues.append(f"Q0-05: {check.message}")

        # Overall pass only if all checks passed
        passed = len(blocking_issues) == 0

        return Q0ValidationResult(
            passed=passed,
            checks=checks,
            blocking_issues=blocking_issues,
        )

    def _check_required_artifacts(
        self,
        extraction_result: NarrativeDeltaExtractionResult,
        contract: ChapterContract,
        prose: str,
    ) -> Q0CheckResult:
        """Q0-01: Verify required artifacts are present."""
        if not prose or len(prose.strip()) == 0:
            return Q0CheckResult(
                check_name="required_artifacts",
                status=Q0CheckStatus.FAIL,
                message="Prose is empty or whitespace-only",
            )

        if not contract:
            return Q0CheckResult(
                check_name="required_artifacts",
                status=Q0CheckStatus.FAIL,
                message="Contract is missing",
            )

        if not extraction_result:
            return Q0CheckResult(
                check_name="required_artifacts",
                status=Q0CheckStatus.FAIL,
                message="Extraction result is missing",
            )

        return Q0CheckResult(
            check_name="required_artifacts",
            status=Q0CheckStatus.PASS,
            message="All required artifacts present",
        )

    def _check_prose_hash(
        self,
        extraction_result: NarrativeDeltaExtractionResult,
        prose: str,
        expected_hash: str,
    ) -> Q0CheckResult:
        """Q0-02: Verify prose hash matches."""
        import hashlib

        actual_hash = hashlib.sha256(prose.encode()).hexdigest()

        if actual_hash != expected_hash:
            return Q0CheckResult(
                check_name="prose_hash_match",
                status=Q0CheckStatus.FAIL,
                message=f"Prose hash mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}...",
            )

        if extraction_result.prose_hash != expected_hash:
            return Q0CheckResult(
                check_name="prose_hash_match",
                status=Q0CheckStatus.FAIL,
                message=f"Extraction result prose_hash mismatch: expected {expected_hash[:16]}..., got {extraction_result.prose_hash[:16]}...",
            )

        return Q0CheckResult(
            check_name="prose_hash_match",
            status=Q0CheckStatus.PASS,
            message="Prose hash verified",
        )

    def _check_delta_evidence_hash(
        self,
        extraction_result: NarrativeDeltaExtractionResult,
        prose_hash: str,
    ) -> Q0CheckResult:
        """Q0-03: Verify delta provenance contains prose hash."""
        if not extraction_result.delta:
            return Q0CheckResult(
                check_name="delta_evidence_hash",
                status=Q0CheckStatus.FAIL,
                message="Delta is None",
            )

        provenance_dict = dict(extraction_result.delta.provenance)

        if "prose_hash" not in provenance_dict:
            return Q0CheckResult(
                check_name="delta_evidence_hash",
                status=Q0CheckStatus.FAIL,
                message="prose_hash not in delta provenance",
            )

        if provenance_dict["prose_hash"] != prose_hash:
            return Q0CheckResult(
                check_name="delta_evidence_hash",
                status=Q0CheckStatus.FAIL,
                message=f"Delta provenance prose_hash mismatch: expected {prose_hash[:16]}..., got {provenance_dict['prose_hash'][:16]}...",
            )

        return Q0CheckResult(
            check_name="delta_evidence_hash",
            status=Q0CheckStatus.PASS,
            message="Delta evidence hash verified",
        )

    def _check_operations_evidence(
        self,
        extraction_result: NarrativeDeltaExtractionResult,
    ) -> Q0CheckResult:
        """Q0-04: Verify all operations have valid evidence."""
        if not extraction_result.delta:
            return Q0CheckResult(
                check_name="operations_evidence",
                status=Q0CheckStatus.FAIL,
                message="Delta is None",
            )

        for i, op in enumerate(extraction_result.delta.operations):
            if not hasattr(op, "evidence") or op.evidence is None:
                return Q0CheckResult(
                    check_name="operations_evidence",
                    status=Q0CheckStatus.FAIL,
                    message=f"Operation {i} missing evidence",
                )

            if not op.evidence.content_hash:
                return Q0CheckResult(
                    check_name="operations_evidence",
                    status=Q0CheckStatus.FAIL,
                    message=f"Operation {i} evidence missing content_hash",
                )

            if len(op.evidence.content_hash) != 64:
                return Q0CheckResult(
                    check_name="operations_evidence",
                    status=Q0CheckStatus.FAIL,
                    message=f"Operation {i} evidence content_hash invalid length: {len(op.evidence.content_hash)}",
                )

        return Q0CheckResult(
            check_name="operations_evidence",
            status=Q0CheckStatus.PASS,
            message=f"All {len(extraction_result.delta.operations)} operations have valid evidence",
        )

    def _check_evidence_locations_verified(
        self,
        extraction_result: NarrativeDeltaExtractionResult,
    ) -> Q0CheckResult:
        """Q0-05: Verify evidence locations are marked as verified."""
        for evidence in extraction_result.operation_evidence:
            for loc in evidence.evidence_locations:
                if not loc.verified:
                    return Q0CheckResult(
                        check_name="evidence_locations_verified",
                        status=Q0CheckStatus.FAIL,
                        message=f"Evidence location for {evidence.fact_path} not verified",
                    )

        return Q0CheckResult(
            check_name="evidence_locations_verified",
            status=Q0CheckStatus.PASS,
            message="All evidence locations verified",
        )
