"""
Urban Business Realistic Extension (V2-015).

Implements world state tracking for urban.business.realistic GenrePack.
Tracks companies, equity, resources, and business state transitions.

Core capabilities:
- Company and organization identity
- Equity ownership and transfers
- Capital and resource tracking
- Business state transitions with preconditions
- Reject supernatural mechanisms in realistic anchor

State types:
    Company: Business entity with type, ownership, capital
    EquityPosition: Ownership stake with holder and percentage
    ResourcePool: Capital, assets, or resources with units
    BusinessTransaction: State change with preconditions

Contract: V2-015 Implementation per ADR-007
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from anovel.domain import EntityId, ProjectId


class CompanyType(StrEnum):
    """Business entity type per Pack schema."""

    STARTUP = "startup"
    CORPORATION = "corporation"
    SMALL_BUSINESS = "small_business"
    ENTERPRISE = "enterprise"


class RevenueScale(StrEnum):
    """Business revenue scale per Pack schema."""

    SEED = "seed"
    GROWING = "growing"
    ESTABLISHED = "established"
    MATURE = "mature"


class ResourceType(StrEnum):
    """Business resource types."""

    CAPITAL = "capital"
    EQUITY = "equity"
    TIME = "time"
    ASSETS = "assets"


class TransactionType(StrEnum):
    """Business transaction categories."""

    EQUITY_TRANSFER = "equity_transfer"
    CAPITAL_INJECTION = "capital_injection"
    CAPITAL_EXPENDITURE = "capital_expenditure"
    REVENUE_RECOGNITION = "revenue_recognition"


# --- State Types ---


@dataclass(frozen=True)
class Company:
    """
    Business entity in urban.business.realistic world.

    Attributes:
        company_id: Unique entity identifier
        project_id: Story project scope
        name: Company name
        company_type: Business entity type
        revenue_scale: Current revenue scale
        created_at: Story time of establishment
    """

    company_id: EntityId
    project_id: ProjectId
    name: str
    company_type: CompanyType
    revenue_scale: RevenueScale
    created_at: str  # StoryTime reference


@dataclass(frozen=True)
class EquityPosition:
    """
    Ownership stake in a company.

    Attributes:
        position_id: Unique position identifier
        company_id: Company being owned
        holder_id: Entity holding this equity
        percentage: Ownership percentage (0.0-100.0)
        acquired_at: Story time of acquisition
    """

    position_id: str
    company_id: EntityId
    holder_id: EntityId
    percentage: Decimal
    acquired_at: str

    def __post_init__(self):
        if not (Decimal("0.0") <= self.percentage <= Decimal("100.0")):
            raise ValueError(
                f"Equity percentage must be 0-100, got {self.percentage}"
            )


@dataclass(frozen=True)
class ResourcePool:
    """
    Capital, assets, or resources with explicit units.

    Attributes:
        pool_id: Unique resource pool identifier
        owner_id: Entity owning this resource
        resource_type: Type of resource
        amount: Quantity (Decimal for precise financial calculations)
        unit: Unit of measurement (USD, shares, months, etc.)
        last_updated: Story time of last change
    """

    pool_id: str
    owner_id: EntityId
    resource_type: ResourceType
    amount: Decimal
    unit: str
    last_updated: str

    def __post_init__(self):
        if self.amount < Decimal("0"):
            raise ValueError(f"Resource amount cannot be negative: {self.amount}")


@dataclass(frozen=True)
class TransactionPrecondition:
    """
    Precondition for business transaction.

    Attributes:
        condition_type: Type of precondition check
        required_value: Value that must be satisfied
        actual_value: Current value (None if not yet evaluated)
        satisfied: Whether condition is met
    """

    condition_type: str
    required_value: str
    actual_value: str | None = None
    satisfied: bool = False


@dataclass(frozen=True)
class BusinessTransaction:
    """
    Proposed business state change with preconditions.

    Attributes:
        transaction_id: Unique transaction identifier
        transaction_type: Category of transaction
        source_entity: Entity initiating transaction
        target_entity: Entity receiving transaction effects
        resource_changes: Resources being transferred or changed
        preconditions: Required conditions for validity
        story_time: When transaction occurs
        evidence_ref: Source evidence in narrative
    """

    transaction_id: str
    transaction_type: TransactionType
    source_entity: EntityId
    target_entity: EntityId | None
    resource_changes: dict[str, Decimal]
    preconditions: list[TransactionPrecondition]
    story_time: str
    evidence_ref: str


# --- Validation Logic ---


class BusinessStateValidator:
    """
    Validates business state transitions and world rules.

    Enforces urban.business.realistic anchor boundaries:
    - No supernatural abilities or cultivation
    - No rebirth systems (not in frozen Pack)
    - Explicit capital and equity tracking
    - Preconditions for state changes
    """

    @staticmethod
    def validate_company_preconditions(company: Company) -> list[str]:
        """
        Validate company state preconditions.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not company.name:
            errors.append("Company name cannot be empty")

        if not company.company_id:
            errors.append("Company must have valid entity ID")

        return errors

    @staticmethod
    def validate_equity_transfer(
        positions: list[EquityPosition], company_id: EntityId
    ) -> list[str]:
        """
        Validate equity positions for a company.

        Checks:
        - Total equity does not exceed 100%
        - No negative positions
        - All positions reference same company

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        company_positions = [p for p in positions if p.company_id == company_id]

        total_equity = sum(p.percentage for p in company_positions)
        if total_equity > Decimal("100.0"):
            errors.append(
                f"Total equity {total_equity}% exceeds 100% for company {company_id}"
            )

        for pos in company_positions:
            if pos.percentage < Decimal("0"):
                errors.append(f"Negative equity position: {pos.position_id}")

        return errors

    @staticmethod
    def validate_resource_sufficiency(
        pool: ResourcePool, required_amount: Decimal
    ) -> bool:
        """
        Check if resource pool has sufficient amount.

        Args:
            pool: Resource pool to check
            required_amount: Amount required

        Returns:
            True if sufficient, False otherwise
        """
        return pool.amount >= required_amount

    @staticmethod
    def validate_transaction_preconditions(
        transaction: BusinessTransaction,
    ) -> tuple[bool, list[str]]:
        """
        Validate all preconditions for a transaction.

        Args:
            transaction: Transaction to validate

        Returns:
            Tuple of (all_satisfied, unsatisfied_conditions)
        """
        unsatisfied = []

        for precond in transaction.preconditions:
            if not precond.satisfied:
                unsatisfied.append(
                    f"{precond.condition_type}: requires {precond.required_value}"
                )

        return len(unsatisfied) == 0, unsatisfied

    @staticmethod
    def reject_supernatural_in_realistic_anchor(
        fact_description: str,
    ) -> tuple[bool, str | None]:
        """
        Detect supernatural mechanisms in realistic anchor.

        This is minimal heuristic detection, not claimed as general semantic understanding.
        Actual world facts (not dialogue/dreams) with cultivation/supernatural should be rejected.

        Args:
            fact_description: Fact description to check

        Returns:
            Tuple of (is_supernatural, rejection_reason)
        """
        supernatural_keywords = [
            "修炼",
            "cultivation",
            "炼气",
            "筑基",
            "金丹",
            "元婴",
            "法术",
            "magic spell",
            "灵力",
            "spiritual energy",
            "重生系统",
            "rebirth system",
            "系统奖励",
            "system reward",
        ]

        fact_lower = fact_description.lower()

        for keyword in supernatural_keywords:
            if keyword in fact_lower:
                return True, f"Realistic anchor rejects supernatural mechanism: {keyword}"

        return False, None


# --- Public API ---

__all__ = [
    "CompanyType",
    "RevenueScale",
    "ResourceType",
    "TransactionType",
    "Company",
    "EquityPosition",
    "ResourcePool",
    "TransactionPrecondition",
    "BusinessTransaction",
    "BusinessStateValidator",
]
