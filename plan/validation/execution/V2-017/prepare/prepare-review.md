# V2-017 Contract Compiler — PREPARE Review

**Task:** V2-017 Contract Compiler  
**Action:** PREPARE  
**Canonical Baseline:** `99b59810cc9e4d5c0164e13add8dbc465dbd84dc`  
**Date:** 2026-10-27  
**Status:** Design complete, ready for IMPLEMENT authorization

---

## Executive Summary

V2-017 Contract Compiler transforms human-provided story goals, character objectives, world constraints, and knowledge boundaries into verifiable chapter planning contracts. This PREPARE phase defines minimal viable architecture, clarifies interface contracts, maps 8 AT scenarios to concrete tests, identifies ADR-008 decisions, and documents Story Fixture requirements.

**Key Finding:** All dependencies satisfied. V2-015/016 world state extensions provide necessary type definitions. NarrativeDelta provides change language. Story fixtures provide planning inputs. Ready for IMPLEMENT.

---

## 1. Minimal Viable Architecture

### 1.1 Core Modules (Recommended Structure)

```
src/anovel/planning/
├── models.py          # Plan data structures (SeriesVision, Arc, Chapter, Scene)
├── versions.py        # Version tracking, supersession, freeze horizon
└── replanning.py      # Replan proposals, invalidation logic

src/anovel/contracts/
├── models.py          # Contract data (RequiredTransition, ProtectedFact, KnowledgeBoundary)
└── compiler.py        # Compile planning inputs → Contract or Diagnostic
```

**Design Principle:** Start minimal. Don't create files until real responsibilities require separation. Avoid premature abstraction.

### 1.2 Data Flow

```
Input: Story Fixture (YAML)
  ↓
Parse → SeriesVision
  ↓
  + Frozen Canon parent
  + GenrePack (ID/version/hash)
  + Planning version
  ↓
Compiler.compile()
  ↓
Output: ChapterContract | CompilationDiagnostic
```

**Key Constraint:** Compiler reads Canon, never writes. Contract expresses intent, doesn't execute state changes.

### 1.3 Core Types

#### Planning Models (`planning/models.py`)

```python
@dataclass(frozen=True)
class SeriesVision:
    """Top-level story plan from human input."""
    series_id: str
    title: str
    protagonist_goals: list[ProtagonistGoal]
    world_constraints: WorldConstraints
    character_knowledge_map: dict[str, CharacterKnowledge]
    genre_pack_binding: GenrePackBinding
    arc_plans: list[ArcPlan]
    
@dataclass(frozen=True)
class ArcPlan:
    """Multi-chapter story arc."""
    arc_id: str
    chapters: list[ChapterPlan]
    arc_goal: str
    escalation_pattern: EscalationPattern
    
@dataclass(frozen=True)
class ChapterPlan:
    """Single chapter intent."""
    chapter_id: str
    chapter_number: int
    goals: list[str]  # What should happen
    required_state_changes: list[str]  # Expected outcomes
    character_focus: list[str]  # Character IDs
    scene_type: SceneType  # action, dialogue, revelation, quiet
```

#### Versioning (`planning/versions.py`)

```python
@dataclass(frozen=True)
class PlanVersion:
    """Plan version with supersession tracking."""
    plan_id: str
    version: str
    created_at: str
    superseded_by: str | None
    supersedes: str | None
    freeze_horizon: FreezeHorizon
    invalidation_reason: str | None
    
@dataclass(frozen=True)
class FreezeHorizon:
    """Which parts of plan are frozen vs adjustable."""
    frozen_chapters: list[str]  # Already compiled/in-progress
    adjustable_chapters: list[str]  # Future, can modify
    frozen_inputs: FrozenInputs  # Canon parent, Pack hash, etc.
```

#### Contract Models (`contracts/models.py`)

```python
@dataclass(frozen=True)
class ChapterContract:
    """Compiled contract for one chapter."""
    contract_id: str
    chapter_id: str
    plan_version: str
    canon_parent: str  # Frozen Canon commit hash
    genre_pack_binding: GenrePackBinding
    
    required_transitions: list[RequiredTransition]
    prohibited_transitions: list[ProhibitedTransition]
    protected_facts: list[ProtectedFact]
    knowledge_boundaries: list[KnowledgeBoundary]
    continuity_constraints: list[ContinuityConstraint]
    
@dataclass(frozen=True)
class RequiredTransition:
    """State change that MUST occur in this chapter."""
    transition_id: str
    operation: Operation  # Uses NarrativeDelta operation types
    preconditions: list[Precondition]
    rationale: str  # Why required (from protagonist goal, etc.)
    
@dataclass(frozen=True)
class KnowledgeBoundary:
    """Who knows what, when revealed."""
    fact_id: str
    knowers: list[str]  # Character IDs
    revelation_constraint: str | None  # "not_before_chapter_5"
    reader_knows: bool
```

#### Compiler (`contracts/compiler.py`)

```python
class ContractCompiler:
    """Compiles planning inputs into chapter contracts."""
    
    def compile_chapter(
        self,
        series_vision: SeriesVision,
        chapter_plan: ChapterPlan,
        canon_parent: str,
        plan_version: str,
    ) -> Result[ChapterContract, CompilationDiagnostic]:
        """
        Compile chapter plan into executable contract.
        
        Returns:
            Success(ChapterContract) if valid
            Failure(CompilationDiagnostic) if conflict/unsatisfiable
        """
        
    def validate_continuity(
        self,
        previous_chapter_hash: str | None,
        previous_chapter_end_state: dict,
        current_chapter_start: ChapterPlan,
    ) -> Result[ContinuityConstraint, DiagnosticError]:
        """Validate chapter N follows from chapter N-1."""
```

---

## 2. AT Scenario Test Mapping

### AT-V2-017-01: Compile from SeriesVision, not P10 Genesis

**Requirement:** Contract Compiler consumes human-provided Story Fixture, doesn't depend on automated Genesis.

**Test Strategy:**
- **Positive:** Load `urban_business_startup_v1.yaml` → parse SeriesVision → compile chapter 1 contract → verify RequiredTransitions exist
- **Negative:** Missing protagonist_goal → compilation fails with diagnostic
- **Assertion:** `contract.plan_version` references fixture input, not Genesis artifact

**Dependencies:** Story Fixture YAML parser, SeriesVision model

**Open Question:** Fixture format stable? Need migration if schema changes?

---

### AT-V2-017-02: RequiredTransition uses NarrativeDelta semantics

**Requirement:** RequiredTransition.operation must use same operation types as NarrativeDelta (SET_FACT, END_FACT, UNDO_FACT).

**Test Strategy:**
- **Positive:** Chapter requires "Zhang Ming accepts funding" → RequiredTransition with `operation=SET_FACT`, `fact_path="equity.zhang_ming"`, `target_value=49.0`
- **Negative:** RequiredTransition with unknown operation type → rejected at contract creation
- **Assertion:** `isinstance(transition.operation, OperationType)` from `anovel.domain.delta`

**Dependencies:** 
- `anovel.domain.delta.OperationType`
- `anovel.domain.delta.FactPath` registry

**Implementation Note:** Don't create parallel state transition language. Reuse existing Delta types.

---

### AT-V2-017-03: Conflicts return diagnostic, don't modify Canon

**Requirement:** Unsatisfiable contracts (e.g., "maintain 51% equity AND accept 30% dilution") return CompilationDiagnostic, never auto-rewrite Canon.

**Test Strategy:**
- **Positive:** Conflicting goals → `Failure(CompilationDiagnostic(reason="conflicting_constraints", conflicts=[...]))`
- **Negative:** Compiler attempts `CanonCommitService.commit()` → fails (compiler has no write permission)
- **Assertion:** Compilation returns diagnostic, Canon HEAD unchanged

**Dependencies:** CanonCommitService remains sole write authority

**Critical:** Compiler is pure function. No side effects. No database writes.

---

### AT-V2-017-04: Story Fixtures human-reviewed with knowledge boundaries

**Requirement:** Both fixtures must have `human_review_ref` populated, contain `secrets_and_knowers` with revelation timing.

**Test Strategy:**
- **Positive:** Fixture with `human_review_ref: "review-2026-10-27-001"` → accepted
- **Negative:** Fixture with `human_review_ref: null` → rejected for production compile (allowed for dev/test)
- **Assertion:** All secrets have `knowers` list and `potential_reveal` timing

**Dependencies:** Fixture validation logic

**Current Blocker:** Both fixtures are DRAFT (`human_review_ref: null`). Need Owner review before IMPLEMENT.

---

### AT-V2-017-05: Continuity binds to previous chapter hash

**Requirement:** 
- Chapter N contract binds to chapter N-1 content_hash + end state
- If chapter N-1 revised, chapter N contract invalidated
- Chapter 1 explicitly marks `previous_chapter: null`

**Test Strategy:**
- **Positive:** Compile chapter 2 with `previous_chapter_hash="abc123..."` → contract.continuity_constraints references hash
- **Negative:** Chapter 2 compiled with wrong/missing previous hash → rejected
- **Assertion:** Chapter 1 has `previous_chapter: null`, Chapter 2+ have valid hash

**Dependencies:** 
- Canon commit receipts with content_hash
- Chapter boundary markers

**Implementation:** ContinuityConstraint must store:
```python
@dataclass(frozen=True)
class ContinuityConstraint:
    previous_chapter_hash: str | None  # None only for chapter 1
    previous_end_state: dict  # Key facts from chapter N-1
    current_start_requirements: list[Precondition]
```

---

### AT-V2-017-06: Support quiet/cognitive chapters, not just combat

**Requirement:** Compiler must support chapters focused on relationships, revelations, internal conflict—not force "combat" or "power升级" into every chapter.

**Test Strategy:**
- **Positive:** Chapter plan `scene_type: "quiet_relationship"` → contract with relationship state changes, no combat required
- **Negative:** Compiler rejects chapter without "action" field → FAIL (over-constrained)
- **Assertion:** ChapterContract can have zero combat-related RequiredTransitions

**Dependencies:** SceneType enum includes:
```python
class SceneType(StrEnum):
    ACTION = "action"
    DIALOGUE = "dialogue"
    REVELATION = "revelation"
    QUIET_RELATIONSHIP = "quiet_relationship"
    INTERNAL_CONFLICT = "internal_conflict"
    INVESTIGATION = "investigation"
```

**Critical for Quality:** Don't mechanize storytelling. Allow narrative variety.

---

### AT-V2-017-07: Planning versions with freeze horizon

**Requirement:** 
- Plans have versions (v1, v2, v3)
- Supersession tracking (v2 supersedes v1)
- Frozen inputs (Canon parent, Pack hash) vs adjustable future
- Expired inputs cannot silently recompile

**Test Strategy:**
- **Positive:** PlanVersion v1 frozen on chapters 1-3, adjustable 4-10 → v2 can modify chapter 5, cannot modify chapter 2
- **Negative:** Compile with `plan_version="v1"` when v2 exists and v1 superseded → rejected
- **Assertion:** `plan.superseded_by` checked before compilation

**Dependencies:** Version tracking in planning database/files

**Implementation:**
```python
def validate_plan_version(plan: SeriesVision) -> Result[None, VersionError]:
    if plan.version.superseded_by is not None:
        return Failure(VersionError(
            f"Plan version {plan.version} superseded by {plan.version.superseded_by}"
        ))
    return Success(None)
```

---

### AT-V2-017-08: Canon/Pack changes trigger invalidation + replan proposal

**Requirement:**
- Canon parent changes → invalidate contracts bound to old parent
- Pack upgrade → invalidate contracts using old Pack hash  
- Generate ReplanProposal (don't auto-rewrite Canon)
- After approval, recompile with new inputs

**Test Strategy:**
- **Positive:** Canon advances (chapter 1 committed) → chapter 2 contract with old parent marked invalid → new ReplanProposal generated
- **Negative:** Contract with invalid parent used anyway → detected and rejected
- **Assertion:** Invalidation creates audit trail (reason, affected chapters, proposal ID)

**Dependencies:** 
- Invalidation tracking system
- ReplanProposal workflow (approval required)

**Implementation:**
```python
@dataclass(frozen=True)
class InvalidationRecord:
    contract_id: str
    invalidation_reason: str  # "canon_parent_changed", "pack_upgraded"
    invalidated_at: str
    affected_inputs: dict[str, str]  # old_parent, new_parent
    replan_proposal_id: str | None
    
@dataclass(frozen=True)
class ReplanProposal:
    proposal_id: str
    reason: str
    affected_chapters: list[str]
    proposed_changes: dict
    approval_status: str  # "pending", "approved", "rejected"
```

---

## 3. ADR-008 Decision Recommendation

**Decision Title:** Contract-Overlay Binding, Planning Versioning, and Replanning Semantics

### 3.1 Contract and Candidate Overlay Binding

**Recommendation:** 
- ChapterContract compiled against specific Canon parent
- Candidate overlay = `parent + proposed_delta`
- Contract validates overlay satisfies requirements
- Overlay never written to Canon until CanonCommitService approves

**Rationale:** Maintains single write authority (CanonCommitService), enables validation before commit.

### 3.2 Planning Version and Freeze Horizon

**Recommendation:**
- PlanVersion has ID + version string (e.g., "urban_v1", "urban_v2")
- FreezeHorizon divides chapters into:
  - **Frozen:** Already compiled, inputs locked (Canon parent, Pack hash)
  - **Adjustable:** Future chapters, can update goals/constraints
- Supersession: v2.supersedes = v1, v1.superseded_by = v2

**Rationale:** Allows iterative refinement of future plans without invalidating past work.

### 3.3 Supersession Semantics

**Recommendation:**
- When v2 supersedes v1:
  - v1 marked `superseded_by: v2`
  - Compiling with v1 after supersession → error
  - v1 frozen chapters can be inherited by v2 if inputs unchanged
- Supersession requires explicit action, not automatic

**Rationale:** Prevents accidental use of stale plans, maintains audit trail.

### 3.4 Invalidation and Replanning

**Recommendation:**
- Canon/Pack/Input changes trigger InvalidationRecord
- System generates ReplanProposal (not auto-execute)
- Proposal requires approval (human or authorized agent)
- After approval, new PlanVersion created, contracts recompiled

**Rationale:** Prevents runaway replanning loops, maintains human oversight.

### 3.5 Canon Write Prohibition

**Recommendation:**
- Contract Compiler is pure read-only
- Replanning system proposes, never executes
- Only CanonCommitService writes Canon
- Violation → security error, not silent failure

**Rationale:** Enforces single write authority, prevents accidental Canon corruption.

---

## 4. Story Fixture Analysis

### 4.1 Urban Business Fixture (urban_business_startup_v1.yaml)

**Status:** DRAFT (human_review_ref: null)

**Strengths:**
- ✅ Clear protagonist goal with constraints
- ✅ Choice costs with immediate + delayed consequences
- ✅ Knowledge boundaries (Zhang doesn't know about backup investor)
- ✅ Secrets with revelation timing
- ✅ Relationship state with trust levels
- ✅ Explicit world constraints (equity ≤100%, etc.)

**Issues:**
- ⚠️ `first_arc_plan` has chapter beats but no explicit RequiredTransitions
- ⚠️ State changes described in natural language, need formalization
- ⚠️ Missing: explicit mapping from choice → state transition

**Recommendations for IMPLEMENT:**
1. Add `required_transitions` field to chapter beats
2. Map choice costs to NarrativeDelta operations
3. Formalize knowledge boundaries with character IDs

**Blocker:** Needs human review before production use (AT-V2-017-04 requirement).

### 4.2 Fantasy Eastern Fixture (fantasy_eastern_cultivation_v1.yaml)

**Status:** DRAFT (human_review_ref: null)

**Strengths:**
- ✅ Clear cultivation progression constraints
- ✅ Resource costs explicitly defined
- ✅ Knowledge boundaries (Wang Lin doesn't know about ancient cave)
- ✅ Multiple viable paths with different costs
- ✅ Relationship stakes integrated

**Issues:**
- ⚠️ Cultivation level progression needs mapping to CultivationRealm state type
- ⚠️ Resource consumption needs explicit tracking (1 pill → 0 pills)
- ⚠️ Missing: dao comprehension threshold checks in chapter requirements

**Recommendations for IMPLEMENT:**
1. Link chapter beats to V2-016 ProgressionStateValidator
2. Add explicit preconditions (dao >= 20 for breakthrough)
3. Map resource costs to ResourcePool state changes

**Blocker:** Same as urban—needs human review.

---

## 5. Dependencies and Blockers

### 5.1 Satisfied Dependencies ✅

- **V2-015 Business Extension:** Company/Equity/Resource types available
- **V2-016 Progression Extension:** CultivationRealm/Ability/Resource types available
- **NarrativeDelta:** Operation types (SET_FACT, END_FACT, UNDO_FACT) defined
- **CanonCommitService:** Sole write authority established
- **GenrePack System:** Pack ID/version/hash verification working

### 5.2 Required for IMPLEMENT

**Critical (P0):**
1. **ADR-008 Acceptance:** Planning versioning decisions must be formalized
2. **Story Fixture Human Review:** Both fixtures need `human_review_ref` populated

**Important (P1):**
3. **Fixture Format Stabilization:** Confirm YAML schema won't change during V2-017
4. **Canon Parent API:** Confirm how to query current Canon HEAD and parent commits

**Nice-to-Have (P2):**
5. **Plan Storage:** Where do PlanVersion records persist? (Files? Database?)
6. **Replan Approval UI:** How does human approve ReplanProposal? (Defer to workflow design)

### 5.3 NOT Required Yet ❌

- ❌ P10 Genesis (explicitly out of scope)
- ❌ Context Compiler (V2-018)
- ❌ Model Gateway (V2-019)
- ❌ Quality gates Q0-Q3 (V2-022-026)
- ❌ Automated story generation
- ❌ Full planning solver/optimizer

---

## 6. Implementation Scope for V2-017 IMPLEMENT

### 6.1 Minimal Deliverables

**Must Implement:**
1. `planning/models.py`: SeriesVision, ArcPlan, ChapterPlan
2. `planning/versions.py`: PlanVersion, FreezeHorizon, supersession logic
3. `contracts/models.py`: ChapterContract, RequiredTransition, KnowledgeBoundary
4. `contracts/compiler.py`: ContractCompiler.compile_chapter()
5. Story Fixture parser (YAML → SeriesVision)
6. 8 AT scenario tests in `tests/contract/test_v2_017.py`

**Implementation Order:**
1. Models first (planning + contracts)
2. Parser (fixture → SeriesVision)
3. Compiler (SeriesVision → ChapterContract)
4. Versioning (PlanVersion, invalidation)
5. Replanning (proposal generation)
6. Tests (all 8 AT scenarios)

### 6.2 Deferred to Later

**V2-018+:**
- Context compilation (contract → model context)
- Budget/overflow handling
- Context artifact caching

**V2-020+:**
- Full chapter workflow
- Actual narrative generation
- Delta extraction from prose

**Future:**
- Automated replanning loops
- Planning optimization/solver
- Multi-book plan management

---

## 7. Risks and Mitigations

### Risk 1: Story Fixtures Insufficient for Compilation

**Risk:** Fixtures lack structured data needed for RequiredTransition generation.

**Mitigation:** 
- PREPARE validates fixtures provide necessary inputs
- If gaps found, document required additions
- Don't block on fixture perfection—iterate

### Risk 2: RequiredTransition Semantics Unclear

**Risk:** Mapping story goals → NarrativeDelta operations not obvious.

**Mitigation:**
- Start with simple cases (equity change, resource change)
- Document mapping patterns
- Complex cases (relationship changes) can use structured metadata

### Risk 3: Versioning Complexity

**Risk:** FreezeHorizon and supersession logic becomes complex.

**Mitigation:**
- Start with simplest case: linear supersession (v1 → v2 → v3)
- No branching versions in P4
- Defer complex version graphs to later phases

### Risk 4: ADR-008 Delays

**Risk:** ADR-008 not accepted before IMPLEMENT starts.

**Mitigation:**
- This PREPARE provides ADR-008 recommendation and decision review
- Owner must formally accept ADR-008 before V2-017 IMPLEMENT
- IMPLEMENT cannot proceed with unapproved ADR-008 per formal decision governance

---

## 8. Next Steps

### Immediate (PREPARE Complete)

1. ✅ This review document created
2. 🔄 Create execution-packet.yaml
3. 🔄 Commit PREPARE artifacts to `prepare/v2-017-contract-compiler` branch
4. 🔄 Create GitHub PR for Owner review

### After Owner Approval

1. ⏳ Owner reviews fixtures, provides `human_review_ref`
2. ⏳ Owner accepts ADR-008 (or provides feedback)
3. ⏳ IMPLEMENT authorization granted

### V2-017 IMPLEMENT Phase

1. Implement models (planning + contracts)
2. Implement compiler core logic
3. Write 8 AT scenario tests
4. Verify with both story fixtures
5. Submit IMPLEMENT PR

---

## 9. Summary

**PREPARE Status:** Complete

**Key Deliverables:**
- ✅ Minimal architecture design (5 modules)
- ✅ 8 AT scenarios mapped to concrete tests
- ✅ ADR-008 recommendation drafted
- ✅ Story fixture analysis with blockers identified
- ✅ Implementation scope defined
- ✅ Risk assessment complete

**Blockers for IMPLEMENT:**
- ⚠️ ADR-008 acceptance (P0)
- ⚠️ Story fixture human review (P0)

**Readiness:** All technical dependencies satisfied. Waiting Owner approval to proceed to IMPLEMENT.

**Estimated IMPLEMENT Effort:** 3-5 sessions (models → parser → compiler → tests)

---

## Appendix: Module Interface Contracts

### ContractCompiler.compile_chapter()

```python
def compile_chapter(
    self,
    series_vision: SeriesVision,
    chapter_plan: ChapterPlan,
    canon_parent: str,
    plan_version: str,
) -> Result[ChapterContract, CompilationDiagnostic]:
    """
    Compile chapter plan into executable contract.
    
    Args:
        series_vision: Full story plan with goals/constraints
        chapter_plan: Specific chapter to compile
        canon_parent: Frozen Canon commit (sha256)
        plan_version: Planning version ID
        
    Returns:
        Success(ChapterContract) if compilation succeeds
        Failure(CompilationDiagnostic) if conflicts/unsatisfiable
        
    Preconditions:
        - plan_version not superseded
        - canon_parent exists in Canon
        - chapter_plan references valid series_vision
        
    Postconditions:
        - Contract.required_transitions use NarrativeDelta operations
        - Contract.canon_parent == canon_parent
        - No Canon writes performed
        
    Side Effects:
        None (pure function)
    """
```

### PlanningVersionService.check_supersession()

```python
def check_supersession(plan_version: str) -> Result[None, VersionError]:
    """
    Verify plan version is current (not superseded).
    
    Returns:
        Success if version is current
        Failure if version superseded
    """
```

### ReplanningService.generate_proposal()

```python
def generate_proposal(
    invalidation: InvalidationRecord,
    new_inputs: dict[str, str],
) -> ReplanProposal:
    """
    Generate replan proposal after invalidation.
    
    Does NOT execute replanning, only proposes.
    Requires explicit approval before new plan created.
    """
```

---

**Document Status:** PREPARE Review Complete  
**Next Action:** Owner review and IMPLEMENT authorization
