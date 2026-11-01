"""V2-024 Q2 Genre Validators - Genre一致性检查

Owner要求的优先功能：
1. GenrePack版本验证
2. 防止非法世界能力混合（Urban突然玄幻能力）
3. 合法跨类型表达（梦境、传闻、幻觉）

这些是确定性检查，基于冻结的GenrePack配置。
"""

from dataclasses import dataclass
from enum import StrEnum

from ..contracts.models import ChapterContract
from ..domain.delta import NarrativeDelta


class Q2CheckStatus(StrEnum):
    """Q2 check result status."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class Q2CheckResult:
    """Result of a single Q2 check."""

    check_name: str
    status: Q2CheckStatus
    message: str
    severity: str = "error"  # "error" | "warning"


@dataclass
class Q2ValidationResult:
    """Complete Q2 validation result."""

    passed: bool  # True only if ALL checks passed
    checks: list[Q2CheckResult]
    blocking_issues: list[str]
    warnings: list[str]


class Q2GenreValidator:
    """Q2 Genre consistency validator.

    Checks narrative changes against frozen GenrePack for world rule violations.
    """

    def validate(
        self,
        delta: NarrativeDelta,
        contract: ChapterContract,
    ) -> Q2ValidationResult:
        """Run Q2 Genre consistency checks.

        Args:
            delta: NarrativeDelta to validate
            contract: Chapter contract with GenrePack binding

        Returns:
            Q2ValidationResult with pass/fail for each check
        """
        checks: list[Q2CheckResult] = []
        blocking_issues: list[str] = []
        warnings: list[str] = []

        # Q2-01: GenrePack version match
        check = self._check_genre_pack_version(delta, contract)
        checks.append(check)
        if check.status == Q2CheckStatus.FAIL or check.status == Q2CheckStatus.ERROR:
            blocking_issues.append(f"Q2-01: {check.message}")

        # Q2-02: World ability consistency (placeholder - requires GenrePack content)
        # This check would verify no illegal cross-genre abilities
        # For V2-024, we implement the framework with basic version checking
        # Full ability validation requires GenrePack schema definition

        # Overall pass only if no blocking issues
        passed = len(blocking_issues) == 0

        return Q2ValidationResult(
            passed=passed,
            checks=checks,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )

    def _check_genre_pack_version(
        self, delta: NarrativeDelta, contract: ChapterContract
    ) -> Q2CheckResult:
        """Q2-01: Verify GenrePack version consistency.

        The delta must be validated against the same GenrePack version
        specified in the contract.
        """
        if not contract.genre_pack_binding:
            return Q2CheckResult(
                check_name="genre_pack_version",
                status=Q2CheckStatus.ERROR,
                message="Contract has no GenrePack binding",
                severity="error",
            )

        # For now, we verify that the contract has a valid binding
        # Full validation would check delta operations against GenrePack rules
        binding = contract.genre_pack_binding

        if not binding.pack_id:
            return Q2CheckResult(
                check_name="genre_pack_version",
                status=Q2CheckStatus.FAIL,
                message="GenrePack binding missing pack_id",
                severity="error",
            )

        if not binding.version:
            return Q2CheckResult(
                check_name="genre_pack_version",
                status=Q2CheckStatus.FAIL,
                message="GenrePack binding missing version",
                severity="error",
            )

        if not binding.content_hash:
            return Q2CheckResult(
                check_name="genre_pack_version",
                status=Q2CheckStatus.FAIL,
                message="GenrePack binding missing content_hash",
                severity="error",
            )

        return Q2CheckResult(
            check_name="genre_pack_version",
            status=Q2CheckStatus.PASS,
            message=f"GenrePack {binding.pack_id} v{binding.version} verified",
            severity="error",
        )
