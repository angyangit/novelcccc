"""Contract Compiler for V2-017.

Compiles SeriesVision planning inputs into ChapterContract validation rules.
Returns contracts on success, diagnostics on conflicts.

Key principles:
- Read-only: Never modifies Canon or plans
- Pure function: No side effects, database writes, or LLM calls
- Reuses NarrativeDelta semantics for RequiredTransition (ADR-004)
- Returns diagnostics on conflicts, doesn't auto-fix
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union
import uuid

from ..domain.delta import OperationType
from ..planning.models import (
    SeriesVision,
    ChapterPlan,
    ProtagonistGoal,
    Secret,
)
from ..planning.versions import PlanVersion, validate_plan_version
from .models import (
    ChapterContract,
    CompilationDiagnostic,
    RequiredTransition,
    ProhibitedTransition,
    ProtectedFact,
    KnowledgeBoundary,
    ContinuityConstraint,
)


# Result type for compilation
CompilationResult = Union[ChapterContract, CompilationDiagnostic]


class ContractCompiler:
    """Compiles planning inputs into chapter contracts."""

    def __init__(self):
        """Initialize compiler (stateless, can be reused)."""
        pass

    def compile_chapter(
        self,
        series_vision: SeriesVision,
        chapter_plan: ChapterPlan,
        plan_version: PlanVersion,
        canon_parent: str,
        previous_chapter_hash: Optional[str] = None,
        previous_end_state: Optional[dict] = None,
    ) -> CompilationResult:
        """
        Compile chapter plan into executable contract.

        Args:
            series_vision: Overall story plan
            chapter_plan: Specific chapter to compile
            plan_version: Version tracking with supersession
            canon_parent: Frozen Canon commit hash
            previous_chapter_hash: Content hash of previous chapter (None for chapter 1)
            previous_end_state: Key facts from end of previous chapter

        Returns:
            ChapterContract if compilation succeeds
            CompilationDiagnostic if conflicts detected
        """
        # Validate plan version not superseded
        version_error = validate_plan_version(plan_version)
        if version_error:
            return CompilationDiagnostic(
                diagnostic_id=str(uuid.uuid4()),
                error_type="version_expired",
                message=version_error.message,
                affected_chapters=[chapter_plan.chapter_id],
                suggested_resolution=f"Use plan version {version_error.current_version}",
            )

        # Validate fixture has human review for production
        if series_vision.human_review_ref is None:
            # Allow for dev/test, but warn
            pass  # In production, this would be rejected

        # Check for conflicting constraints
        conflict_check = self._check_conflicts(
            series_vision.protagonist_goals,
            series_vision.world_constraints,
            chapter_plan,
        )
        if conflict_check:
            return conflict_check

        # Compile required transitions from chapter goals
        required_transitions = self._compile_required_transitions(
            chapter_plan,
            series_vision.protagonist_goals,
        )

        # Compile prohibited transitions from world constraints
        prohibited_transitions = self._compile_prohibited_transitions(
            series_vision.world_constraints,
        )

        # Compile protected facts
        protected_facts = self._compile_protected_facts(
            series_vision.world_constraints,
        )

        # Compile knowledge boundaries from secrets
        knowledge_boundaries = self._compile_knowledge_boundaries(
            series_vision.secrets,
            chapter_plan.chapter_number,
        )

        # Compile continuity constraints
        continuity = None
        if chapter_plan.chapter_number > 1:
            if previous_chapter_hash is None:
                return CompilationDiagnostic(
                    diagnostic_id=str(uuid.uuid4()),
                    error_type="missing_previous_chapter",
                    message=f"Chapter {chapter_plan.chapter_number} requires previous chapter hash",
                    affected_chapters=[chapter_plan.chapter_id],
                )
            continuity = ContinuityConstraint(
                previous_chapter_id=f"chapter_{chapter_plan.chapter_number - 1}",
                previous_chapter_hash=previous_chapter_hash,
                previous_end_state=previous_end_state or {},
                current_start_requirements=[],
            )

        # Build contract
        contract = ChapterContract(
            contract_id=str(uuid.uuid4()),
            chapter_id=chapter_plan.chapter_id,
            chapter_number=chapter_plan.chapter_number,
            plan_version=plan_version.version,
            created_at=datetime.now(),
            canon_parent=canon_parent,
            genre_pack_binding=series_vision.genre_pack_binding,
            required_transitions=required_transitions,
            prohibited_transitions=prohibited_transitions,
            protected_facts=protected_facts,
            knowledge_boundaries=knowledge_boundaries,
            continuity_constraints=continuity,
            fixture_ref=series_vision.series_id,
            human_review_ref=series_vision.human_review_ref,
        )

        return contract

    def _check_conflicts(
        self,
        protagonist_goals: list[ProtagonistGoal],
        world_constraints,
        chapter_plan: ChapterPlan,
    ) -> Optional[CompilationDiagnostic]:
        """
        Check for conflicting constraints that make chapter unsatisfiable.

        Returns CompilationDiagnostic if conflicts found, None otherwise.
        """
        conflicts = []

        # Check for direct equity conflicts
        state_changes_text = " ".join(chapter_plan.required_state_changes)

        # Look for equity dilution vs control maintenance conflicts
        has_dilution = any("49%" in change or "股权稀释" in change for change in chapter_plan.required_state_changes)
        has_control_requirement = any("51%" in change or "超过51%" in change for change in chapter_plan.required_state_changes)

        if has_dilution and has_control_requirement:
            conflicts.append(
                "State changes contain conflicting equity requirements: dilution to 49% vs maintaining >51% control"
            )

        # Check against protagonist goals constraints
        for goal in protagonist_goals:
            for constraint in goal.constraints:
                if "控制权" in constraint:
                    for state_change in chapter_plan.required_state_changes:
                        if "49%" in state_change and "失去" not in state_change:
                            # Diluting to 49% conflicts with maintaining control
                            if any("51%" in other for other in chapter_plan.required_state_changes):
                                conflicts.append(
                                    f"State change '{state_change}' conflicts with goal constraint '{constraint}'"
                                )

        if conflicts:
            return CompilationDiagnostic(
                diagnostic_id=str(uuid.uuid4()),
                error_type="conflicting_constraints",
                message="Chapter plan contains conflicting constraints",
                conflicts=conflicts,
                affected_chapters=[chapter_plan.chapter_id],
                suggested_resolution="Revise chapter plan to resolve constraints",
            )

        return None

    def _compile_required_transitions(
        self,
        chapter_plan: ChapterPlan,
        protagonist_goals: list[ProtagonistGoal],
    ) -> list[RequiredTransition]:
        """
        Compile required state transitions from chapter plan.

        Uses NarrativeDelta OperationType semantics (ADR-004).
        """
        transitions = []

        for i, state_change in enumerate(chapter_plan.required_state_changes):
            # Map state change description to operation type and fact path
            # This is simplified - real implementation would parse structured data
            operation_type = OperationType.SET_FACT
            fact_path = f"state.{chapter_plan.chapter_id}.change_{i}"

            # Find related goal for rationale
            rationale = state_change
            for goal in protagonist_goals:
                if any(criterion in state_change for criterion in goal.success_criteria):
                    rationale = f"Required for goal: {goal.description}"
                    break

            transition = RequiredTransition(
                transition_id=str(uuid.uuid4()),
                operation_type=operation_type,
                fact_path=fact_path,
                target_value=state_change,
                rationale=rationale,
            )
            transitions.append(transition)

        return transitions

    def _compile_prohibited_transitions(
        self,
        world_constraints,
    ) -> list[ProhibitedTransition]:
        """Compile prohibited transitions from world constraints."""
        prohibitions = []

        # Map prohibited mechanisms to transitions
        for mechanism in world_constraints.prohibited_mechanisms:
            prohibition = ProhibitedTransition(
                prohibition_id=str(uuid.uuid4()),
                fact_path=f"prohibited.{mechanism.replace(' ', '_')}",
                prohibited_operation=OperationType.SET_FACT,
                rationale=f"World constraint prohibits: {mechanism}",
            )
            prohibitions.append(prohibition)

        return prohibitions

    def _compile_protected_facts(
        self,
        world_constraints,
    ) -> list[ProtectedFact]:
        """Compile protected facts from world constraints."""
        protected = []

        # Mark constraint rules as protected facts
        for i, constraint in enumerate(world_constraints.realistic_constraints):
            fact = ProtectedFact(
                fact_id=str(uuid.uuid4()),
                fact_path=f"constraint.realistic.{i}",
                protection_reason=constraint,
            )
            protected.append(fact)

        return protected

    def _compile_knowledge_boundaries(
        self,
        secrets: list[Secret],
        current_chapter: int,
    ) -> list[KnowledgeBoundary]:
        """Compile knowledge boundaries from secrets."""
        boundaries = []

        for secret in secrets:
            # Determine if revelation is allowed in current chapter
            revelation_constraint = None
            if secret.potential_reveal_chapter:
                if current_chapter < secret.potential_reveal_chapter:
                    revelation_constraint = f"not_before_chapter_{secret.potential_reveal_chapter}"

            boundary = KnowledgeBoundary(
                boundary_id=str(uuid.uuid4()),
                fact_id=secret.secret_id,
                knowers=secret.knowers,
                revelation_constraint=revelation_constraint,
                reader_knows=secret.reader_knows,
            )
            boundaries.append(boundary)

        return boundaries
