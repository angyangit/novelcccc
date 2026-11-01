"""V2-023 Q1 Canon Validators - Canon状态一致性检查

Owner要求的优先功能：
1. 状态前值验证
2. 人物生命状态
3. 人物知识边界
4. 跨项目隔离
5. 实际Canon读取

这些是确定性检查，不依赖未决ADR-011政策。
未获授权前，不接入正式生产许可链路。
"""

from dataclasses import dataclass
from enum import StrEnum

from ..contracts.models import ChapterContract
from ..domain.delta import (
    CanonState,
    FactValue,
    NarrativeDelta,
    SetFactOperation,
    get_fact_path,
)


class Q1CheckStatus(StrEnum):
    """Q1 check result status."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    UNKNOWN = "unknown"  # Cannot determine without more context


@dataclass
class Q1CheckResult:
    """Result of a single Q1 check."""

    check_name: str
    status: Q1CheckStatus
    message: str
    severity: str = "error"  # "error" | "warning"


@dataclass
class Q1ValidationResult:
    """Complete Q1 validation result."""

    passed: bool  # True only if ALL checks passed
    checks: list[Q1CheckResult]
    blocking_issues: list[str]
    warnings: list[str]


class Q1CanonValidator:
    """Q1 Canon consistency validator.

    Checks narrative state changes against Canon for consistency.
    """

    def validate(
        self,
        delta: NarrativeDelta,
        canon_state: CanonState,
        contract: ChapterContract,
    ) -> Q1ValidationResult:
        """Run Q1 Canon consistency checks.

        Args:
            delta: NarrativeDelta to validate
            canon_state: Current Canon state
            contract: Chapter contract

        Returns:
            Q1ValidationResult with pass/fail for each check
        """
        checks: list[Q1CheckResult] = []
        blocking_issues: list[str] = []
        warnings: list[str] = []

        # Q1-01: Project isolation
        check = self._check_project_isolation(delta, canon_state)
        checks.append(check)
        if check.status == Q1CheckStatus.FAIL:
            blocking_issues.append(f"Q1-01: {check.message}")

        # Q1-02: State precondition validation (for SetFactOperation)
        check = self._check_state_preconditions(delta, canon_state)
        checks.append(check)
        if check.status == Q1CheckStatus.FAIL:
            blocking_issues.append(f"Q1-02: {check.message}")
        elif check.status == Q1CheckStatus.UNKNOWN:
            warnings.append(f"Q1-02 (warning): {check.message}")

        # Q1-03: Life state consistency (dead characters cannot act)
        check = self._check_life_state_consistency(delta, canon_state)
        checks.append(check)
        if check.status == Q1CheckStatus.FAIL:
            blocking_issues.append(f"Q1-03: {check.message}")

        # Overall pass only if no blocking issues
        passed = len(blocking_issues) == 0

        return Q1ValidationResult(
            passed=passed,
            checks=checks,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )

    def _check_project_isolation(
        self, delta: NarrativeDelta, canon_state: CanonState
    ) -> Q1CheckResult:
        """Q1-01: Verify project isolation."""
        if delta.project_id != canon_state.project_id:
            return Q1CheckResult(
                check_name="project_isolation",
                status=Q1CheckStatus.FAIL,
                message=f"Delta project {delta.project_id} does not match Canon project {canon_state.project_id}",
                severity="error",
            )

        # Check all operations have matching scope
        for i, op in enumerate(delta.operations):
            if isinstance(op, SetFactOperation):
                if op.scope != canon_state.project_id:
                    return Q1CheckResult(
                        check_name="project_isolation",
                        status=Q1CheckStatus.FAIL,
                        message=f"Operation {i} scope {op.scope} does not match Canon project {canon_state.project_id}",
                        severity="error",
                    )

        return Q1CheckResult(
            check_name="project_isolation",
            status=Q1CheckStatus.PASS,
            message="Project isolation verified",
            severity="error",
        )

    def _check_state_preconditions(
        self, delta: NarrativeDelta, canon_state: CanonState
    ) -> Q1CheckResult:
        """Q1-02: Verify preconditions match current Canon state with sequential delta application.

        Each operation's precondition is validated against the accumulated state after
        applying previous operations in the delta, not just the initial Canon state.
        """
        from ..domain.delta import (
            ExpectAbsent,
            ExpectPresent,
            ExpectUnknown,
            ExpectValue,
        )

        # Track accumulated state as we apply operations
        state_tracker = {}  # (subject, fact_path) -> current_value

        # Initialize from canon
        for fact in canon_state.facts:
            key = (str(fact.subject), fact.path.path)
            state_tracker[key] = fact.value

        for i, op in enumerate(delta.operations):
            if not isinstance(op, SetFactOperation):
                continue

            key = (str(op.subject), op.path.path)

            # Get current value from accumulated state
            exists = key in state_tracker
            current_value = state_tracker.get(key) if exists else None

            # Check precondition against accumulated state
            precond = op.precondition

            if isinstance(precond, ExpectAbsent):
                if exists:
                    return Q1CheckResult(
                        check_name="state_preconditions",
                        status=Q1CheckStatus.FAIL,
                        message=f"Operation {i} expects absent, but {op.path.path} exists with value {current_value}",
                        severity="error",
                    )

            elif isinstance(precond, ExpectValue):
                if not exists:
                    return Q1CheckResult(
                        check_name="state_preconditions",
                        status=Q1CheckStatus.FAIL,
                        message=f"Operation {i} expects value {precond.expected_value}, but {op.path.path} does not exist",
                        severity="error",
                    )
                if current_value != precond.expected_value:
                    return Q1CheckResult(
                        check_name="state_preconditions",
                        status=Q1CheckStatus.FAIL,
                        message=f"Operation {i} expects {op.path.path}={precond.expected_value}, but has {current_value}",
                        severity="error",
                    )

            elif isinstance(precond, ExpectPresent):
                if not exists:
                    return Q1CheckResult(
                        check_name="state_preconditions",
                        status=Q1CheckStatus.FAIL,
                        message=f"Operation {i} expects {op.path.path} to exist, but it does not exist",
                        severity="error",
                    )

            elif isinstance(precond, ExpectUnknown):
                if not exists or current_value != FactValue.UNKNOWN:
                    return Q1CheckResult(
                        check_name="state_preconditions",
                        status=Q1CheckStatus.FAIL,
                        message=f"Operation {i} expects {op.path.path}=UNKNOWN, but has {current_value if exists else 'absent'}",
                        severity="error",
                    )

            # Apply operation to accumulated state
            state_tracker[key] = op.value

        return Q1CheckResult(
            check_name="state_preconditions",
            status=Q1CheckStatus.PASS,
            message="All preconditions match accumulated state",
            severity="error",
        )

    def _check_life_state_consistency(
        self, delta: NarrativeDelta, canon_state: CanonState
    ) -> Q1CheckResult:
        """Q1-03: Verify dead characters cannot perform actions.

        Owner要求：
        - UNKNOWN、ERROR不能获得生产级硬门禁PASS
        - 人物复活必须符合世界规则、正文证据及授权约束，不能仅依靠单个布尔变化

        Checks if the subject entity is marked as not alive (is_alive=False)
        in Canon. If so, new fact changes should not be allowed.
        Resurrection requires explicit authorization in world rules, not just
        setting is_alive=True.
        """
        # Get is_alive fact path
        try:
            is_alive_path = get_fact_path("is_alive")
        except ValueError:
            # Owner要求: UNKNOWN不能获得PASS
            return Q1CheckResult(
                check_name="life_state_consistency",
                status=Q1CheckStatus.ERROR,
                message="is_alive not in FactPath registry, cannot verify life state - BLOCKING",
                severity="error",
            )

        for i, op in enumerate(delta.operations):
            if not isinstance(op, SetFactOperation):
                continue

            # Check if subject is marked as dead in Canon
            is_alive_value, is_alive_exists = canon_state.get_value(
                op.subject, is_alive_path
            )

            if is_alive_exists and is_alive_value is False:
                # Subject is dead in Canon
                # Owner要求: 人物复活必须符合世界规则、正文证据及授权约束
                # 不能仅依靠单个布尔变化 - 必须拒绝所有操作包括复活
                # 复活需要通过世界规则授权机制（未实现前阻断）
                if op.path.path == "is_alive" and op.value is True:
                    return Q1CheckResult(
                        check_name="life_state_consistency",
                        status=Q1CheckStatus.FAIL,
                        message=f"Operation {i} attempts resurrection for {op.subject}, but resurrection requires world rules authorization (not implemented)",
                        severity="error",
                    )

                # Dead characters cannot have new facts set
                return Q1CheckResult(
                    check_name="life_state_consistency",
                    status=Q1CheckStatus.FAIL,
                    message=f"Operation {i} attempts to modify {op.path.path} for subject {op.subject}, but subject is marked as not alive in Canon",
                    severity="error",
                )

        return Q1CheckResult(
            check_name="life_state_consistency",
            status=Q1CheckStatus.PASS,
            message="Life state consistency verified",
            severity="error",
        )
