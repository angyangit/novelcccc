"""Budget management for Model Gateway per ADR-010.

Tracks confirmed costs, inflight reservations, and unknown liabilities.
"""

from dataclasses import dataclass
from threading import Lock


@dataclass
class BudgetState:
    """Budget tracking state per ADR-010."""

    total_limit_usd: float
    confirmed_spent_usd: float
    inflight_reserved_usd: float
    unknown_liability_usd: float

    def available_usd(self) -> float:
        """Calculate available budget.

        ADR-010: Subtract confirmed, inflight, and unknown liability from total.
        """
        return (
            self.total_limit_usd
            - self.confirmed_spent_usd
            - self.inflight_reserved_usd
            - self.unknown_liability_usd
        )

    def can_reserve(self, estimated_cost_usd: float) -> bool:
        """Check if we can reserve budget for a new request."""
        return self.available_usd() >= estimated_cost_usd


class BudgetManager:
    """Thread-safe budget manager."""

    def __init__(self, total_limit_usd: float):
        """Initialize with total budget limit.

        Args:
            total_limit_usd: Maximum total spend allowed
        """
        self._state = BudgetState(
            total_limit_usd=total_limit_usd,
            confirmed_spent_usd=0.0,
            inflight_reserved_usd=0.0,
            unknown_liability_usd=0.0,
        )
        self._lock = Lock()

    def reserve(self, estimated_cost_usd: float) -> bool:
        """Reserve budget for a new request.

        Returns:
            True if reservation successful, False if insufficient budget
        """
        with self._lock:
            if not self._state.can_reserve(estimated_cost_usd):
                return False
            self._state = BudgetState(
                total_limit_usd=self._state.total_limit_usd,
                confirmed_spent_usd=self._state.confirmed_spent_usd,
                inflight_reserved_usd=self._state.inflight_reserved_usd
                + estimated_cost_usd,
                unknown_liability_usd=self._state.unknown_liability_usd,
            )
            return True

    def confirm_cost(self, reserved_amount_usd: float, actual_cost_usd: float) -> None:
        """Confirm actual cost and release reservation.

        Args:
            reserved_amount_usd: Amount that was reserved
            actual_cost_usd: Actual cost from provider
        """
        with self._lock:
            self._state = BudgetState(
                total_limit_usd=self._state.total_limit_usd,
                confirmed_spent_usd=self._state.confirmed_spent_usd + actual_cost_usd,
                inflight_reserved_usd=self._state.inflight_reserved_usd
                - reserved_amount_usd,
                unknown_liability_usd=self._state.unknown_liability_usd,
            )

    def mark_unknown(self, reserved_amount_usd: float) -> None:
        """Move reserved amount to unknown liability (timeout/error case).

        Args:
            reserved_amount_usd: Amount that was reserved but result is unknown
        """
        with self._lock:
            self._state = BudgetState(
                total_limit_usd=self._state.total_limit_usd,
                confirmed_spent_usd=self._state.confirmed_spent_usd,
                inflight_reserved_usd=self._state.inflight_reserved_usd
                - reserved_amount_usd,
                unknown_liability_usd=self._state.unknown_liability_usd
                + reserved_amount_usd,
            )

    def get_state(self) -> BudgetState:
        """Get current budget state snapshot."""
        with self._lock:
            return self._state
