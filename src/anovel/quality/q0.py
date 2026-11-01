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
            check = self._check_operations_evidence(extraction_result, prose_hash)
            checks.append(check)
            if check.status != Q0CheckStatus.PASS:
                blocking_issues.append(f"Q0-04: {check.message}")

        # Q0-05: Evidence locations verified against actual prose
        check = self._check_evidence_locations_verified(extraction_result, prose)
        checks.append(check)
        if check.status != Q0CheckStatus.PASS:
            blocking_issues.append(f"Q0-05: {check.message}")

        # Q0-06: Operation与OperationEvidence对应关系
        check = self._check_operation_evidence_correspondence(extraction_result)
        checks.append(check)
        if check.status != Q0CheckStatus.PASS:
            blocking_issues.append(f"Q0-06: {check.message}")

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
        prose_hash: str,
    ) -> Q0CheckResult:
        """Q0-04: Verify all operations have valid evidence matching prose_hash."""
        if not extraction_result.delta:
            # Owner要求：空Delta也不能跳过检查
            # 如果extraction_result存在但delta为None，这是异常状态
            if extraction_result.status != "failed":
                return Q0CheckResult(
                    check_name="operations_evidence",
                    status=Q0CheckStatus.FAIL,
                    message="Delta is None but extraction status is not failed",
                )
            # 如果extraction failed，delta为None是合理的
            return Q0CheckResult(
                check_name="operations_evidence",
                status=Q0CheckStatus.PASS,
                message="Extraction failed, no operations to validate",
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

            # Owner要求：验证每个Operation的evidence hash与prose_hash匹配
            if op.evidence.content_hash != prose_hash:
                return Q0CheckResult(
                    check_name="operations_evidence",
                    status=Q0CheckStatus.FAIL,
                    message=f"Operation {i} evidence content_hash {op.evidence.content_hash[:16]}... does not match prose_hash {prose_hash[:16]}...",
                )

        return Q0CheckResult(
            check_name="operations_evidence",
            status=Q0CheckStatus.PASS,
            message=f"All {len(extraction_result.delta.operations)} operations have valid evidence matching prose_hash",
        )

    def _check_evidence_locations_verified(
        self,
        extraction_result: NarrativeDeltaExtractionResult,
        prose: str,
    ) -> Q0CheckResult:
        """Q0-05: Verify evidence locations against actual prose.

        Owner要求：不信任未验证的verified标记，实际验证位置和片段。
        """
        for evidence in extraction_result.operation_evidence:
            for loc in evidence.evidence_locations:
                # Check 1: verified标记
                if not loc.verified:
                    return Q0CheckResult(
                        check_name="evidence_locations_verified",
                        status=Q0CheckStatus.FAIL,
                        message=f"Evidence location for {evidence.fact_path} not verified",
                    )

                # Check 2: Owner要求实际验证位置范围
                if loc.start_char < 0:
                    return Q0CheckResult(
                        check_name="evidence_locations_verified",
                        status=Q0CheckStatus.FAIL,
                        message=f"Evidence location for {evidence.fact_path} has negative start_char {loc.start_char}",
                    )

                if loc.end_char > len(prose):
                    return Q0CheckResult(
                        check_name="evidence_locations_verified",
                        status=Q0CheckStatus.FAIL,
                        message=f"Evidence location for {evidence.fact_path} end_char {loc.end_char} exceeds prose length {len(prose)}",
                    )

                if loc.start_char >= loc.end_char:
                    return Q0CheckResult(
                        check_name="evidence_locations_verified",
                        status=Q0CheckStatus.FAIL,
                        message=f"Evidence location for {evidence.fact_path} has invalid range [{loc.start_char}:{loc.end_char}]",
                    )

                # Check 3: Owner要求验证实际片段与正文一致
                actual_snippet = prose[loc.start_char:loc.end_char]
                # text_snippet应该包含或等于actual_snippet
                # （允许text_snippet包含更多上下文）
                if actual_snippet not in loc.text_snippet and loc.text_snippet not in actual_snippet:
                    return Q0CheckResult(
                        check_name="evidence_locations_verified",
                        status=Q0CheckStatus.FAIL,
                        message=f"Evidence location for {evidence.fact_path} text_snippet does not match actual prose at [{loc.start_char}:{loc.end_char}]",
                    )

        return Q0CheckResult(
            check_name="evidence_locations_verified",
            status=Q0CheckStatus.PASS,
            message="All evidence locations verified against actual prose",
        )

    def _check_operation_evidence_correspondence(
        self,
        extraction_result: NarrativeDeltaExtractionResult,
    ) -> Q0CheckResult:
        """Q0-06: Verify Operation与OperationEvidence对应关系.

        Owner要求：检查数量、索引和事实路径对应。
        """
        if not extraction_result.delta:
            # 如果extraction failed，允许delta为None
            if extraction_result.status == "failed":
                return Q0CheckResult(
                    check_name="operation_evidence_correspondence",
                    status=Q0CheckStatus.PASS,
                    message="Extraction failed, no correspondence to check",
                )
            return Q0CheckResult(
                check_name="operation_evidence_correspondence",
                status=Q0CheckStatus.FAIL,
                message="Delta is None but extraction status is not failed",
            )

        operations = extraction_result.delta.operations
        evidences = extraction_result.operation_evidence

        # Check count correspondence
        if len(operations) != len(evidences):
            return Q0CheckResult(
                check_name="operation_evidence_correspondence",
                status=Q0CheckStatus.FAIL,
                message=f"Operation count ({len(operations)}) does not match OperationEvidence count ({len(evidences)})",
            )

        # Check index and fact_path correspondence
        for i, (op, evidence) in enumerate(zip(operations, evidences)):
            # Check index
            if evidence.operation_index != i:
                return Q0CheckResult(
                    check_name="operation_evidence_correspondence",
                    status=Q0CheckStatus.FAIL,
                    message=f"OperationEvidence {i} has operation_index {evidence.operation_index}, expected {i}",
                )

            # Check fact_path correspondence
            # Operations have 'path' attribute, evidence has 'fact_path'
            if hasattr(op, "path"):
                op_fact_path = op.path.path if hasattr(op.path, "path") else str(op.path)
                if op_fact_path != evidence.fact_path:
                    return Q0CheckResult(
                        check_name="operation_evidence_correspondence",
                        status=Q0CheckStatus.FAIL,
                        message=f"Operation {i} fact_path '{op_fact_path}' does not match OperationEvidence fact_path '{evidence.fact_path}'",
                    )

        return Q0CheckResult(
            check_name="operation_evidence_correspondence",
            status=Q0CheckStatus.PASS,
            message=f"All {len(operations)} operations have corresponding evidence with correct indices and fact_paths",
        )
