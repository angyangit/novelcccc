# ADR-008: Contract-Overlay Binding, Planning Versioning, and Replanning

**Status:** ACCEPTED  
**Date:** 2026-10-28  
**Scope:** V2-017 Contract Compiler  
**Related Tasks:** V2-017, V2-020  
**Owner:** planning-maintainer  
**Supersedes:** None  

---

## Context

V2-017 Contract Compiler transforms story plans into chapter contracts that constrain candidate narrative changes. This ADR defines:
1. How contracts bind to candidate overlays
2. Planning version tracking and supersession
3. Input invalidation and replanning semantics
4. Canon write prohibition for planning system

These decisions enable iterative plan refinement while maintaining Canon integrity.

---

## Decision

### 1. Contract and Candidate Overlay Binding

**Decision:** ChapterContract compiles against frozen Canon parent. Validation applies to candidate overlay `parent + proposed_delta`, never writes to Canon.

**Rationale:**
- Maintains CanonCommitService as sole write authority (ADR-006)
- Enables validation before commit
- Separates planning (read-only) from execution (write-controlled)

**Implementation:**
```python
@dataclass(frozen=True)
class ChapterContract:
    canon_parent: str  # Frozen commit sha256
    required_transitions: list[RequiredTransition]
    
def validate_candidate(contract: ChapterContract, delta: NarrativeDelta) -> ValidationResult:
    """Validate delta satisfies contract. Does NOT write Canon."""
    overlay = apply_delta(contract.canon_parent, delta)
    return check_requirements(contract, overlay)
```

### 2. Planning Version and Freeze Horizon

**Decision:** Plans have versions with supersession tracking. FreezeHorizon separates frozen inputs from adjustable future.

**Structure:**
```python
@dataclass(frozen=True)
class PlanVersion:
    plan_id: str  # e.g., "urban_v1"
    version: str  # e.g., "v2"
    supersedes: str | None  # e.g., "v1"
    superseded_by: str | None  # None if current
    
@dataclass(frozen=True)
class FreezeHorizon:
    frozen_chapters: list[str]  # Compiled, inputs locked
    frozen_inputs: dict[str, str]  # {canon_parent, pack_hash, ...}
    adjustable_chapters: list[str]  # Future, can modify
```

**Rationale:**
- Allows future plan updates without invalidating past work
- Clear boundary between committed and proposed
- Prevents accidental use of stale plans

### 3. Supersession Semantics

**Decision:** Supersession is explicit, not automatic. Compiling with superseded plan version errors.

**Rules:**
- v2 supersedes v1 → v1.superseded_by = v2, v2.supersedes = v1
- Compilation with superseded version → `VersionError`
- Frozen chapters from v1 can be inherited by v2 if inputs unchanged
- Supersession requires authorization, creates audit trail

**Rationale:**
- Prevents silent use of outdated plans
- Maintains versioning history
- Supports rollback if new plan fails

### 4. Invalidation and Replanning

**Decision:** Input changes trigger InvalidationRecord + ReplanProposal with precise dependency-based scope. System proposes, does not auto-execute.

**Workflow:**
1. Canon parent advances → InvalidationRecord created
2. System generates ReplanProposal (affected chapters, reason, proposed changes)
3. Proposal requires approval (human or authorized agent)
4. After approval, new PlanVersion created
5. Contracts recompiled with new inputs

**Structure:**
```python
@dataclass(frozen=True)
class InvalidationRecord:
    contract_id: str
    reason: str  # "canon_parent_changed", "pack_upgraded"
    invalidated_at: str
    affected_inputs: dict[str, str]
    dependency_chain: list[str]  # Trace why this contract was affected
    replan_proposal_id: str | None
    
@dataclass(frozen=True)
class ReplanProposal:
    proposal_id: str
    reason: str
    affected_chapters: list[str]
    proposed_changes: dict
    approval_status: str  # "pending", "approved", "rejected"
```

**Rationale:**
- Prevents runaway replanning loops
- Maintains human oversight
- Creates audit trail for plan evolution
- Explicit scope (which chapters affected, which inputs changed)

#### 4.1 Invalidation Scope Rules

**Eager Invalidation Detection:**
- Canon parent changes → immediately identify all compiled contracts bound to old parent
- Detection must happen before any downstream use (eager, not deferred)
- Incremental recompilation may be deferred, but invalidation detection cannot
- Uncompiled future plans are not subject to invalidation (they're adjustable, not compiled)

**Dependency-Based Invalidation:**
- GenrePack version/hash changed → invalidate contracts UNLESS verifiable compatibility proof exists
- Compatibility cannot be assumed from state type filtering alone (hash change = semantic change until proven otherwise)
- Compatibility exemption requires: input equivalence proof, semantic equivalence verification, explicit approval
- State type filtering is insufficient: must analyze full compilation input dependencies

**Contract State Boundaries:**
- **Committed Canon chapters**: Immutable, cannot be invalidated (history is frozen)
- **Compiled but uncommitted contracts**: Subject to invalidation when inputs change
- **Uncompiled future plans**: Can be modified without invalidation (not yet compiled into contracts)

**Input Dependency Analysis:**
- Synopsis, title, metadata exempt ONLY if proven not to affect compilation output
- Exemption verification: check ALL compilation inputs, not just RequiredTransition field references
- If field influences context, preconditions, or any compiled output → not exempt
- When uncertain, trigger invalidation (safe default)

**Invalidation Audit Trail:**
- Every InvalidationRecord must specify: which input changed, affected contracts, dependency chain
- Scope justification required: why these contracts, what dependency, old/new values
- No batch invalidation without per-contract dependency analysis
- Audit trail enables debugging and rollback

**Implementation Requirement:**
Compiler must track full input set for each contract (Canon parent, Pack hash, SeriesVision version, all referenced fields) to enable precise dependency analysis.

### 5. Canon Write Prohibition

**Decision:** Contract Compiler and Replanning system are strictly read-only. Only CanonCommitService writes Canon.

**Enforcement:**
- Compiler/Replanner have no Canon write permission
- Violation → security error (not silent failure)
- Proposals describe changes, execution is separate

**Rationale:**
- Single write authority (ADR-006)
- Prevents planning system from corrupting Canon
- Clear separation: planning proposes, Canon system executes

---

## Consequences

### Positive

- ✅ Clear boundary between planning and Canon execution
- ✅ Iterative plan refinement without Canon corruption
- ✅ Version tracking enables rollback and audit
- ✅ Invalidation logic prevents stale plan usage
- ✅ Explicit approval prevents runaway replanning
- ✅ Precise dependency-based scope prevents excessive replanning in long-form novels

### Negative

- ⚠️ Versioning adds complexity (mitigated by simple linear supersession in P4)
- ⚠️ Manual approval required for replanning (intended—human oversight)
- ⚠️ Plan storage mechanism TBD (files vs database)
- ⚠️ Full input dependency tracking requires careful implementation

### Neutral

- Planning system doesn't auto-optimize (deferred to future phases)
- Supersession is linear (v1→v2→v3), no branching (sufficient for P4)

---

## Verification

### AT-V2-017-07: Versioning
- Plan v1 frozen on chapters 1-3 → v2 can modify chapter 5, cannot modify chapter 2
- Compile with superseded plan v1 → `VersionError`

### AT-V2-017-08: Invalidation
- Canon advances → InvalidationRecord created → ReplanProposal generated
- Proposal approved → new PlanVersion → recompile contracts
- Invalid parent detected and rejected

### Integration Tests
- Round-trip: compile → approve → Canon commit → advance → invalidate → replan → approve → compile
- Verify no Canon writes from planning system
- Verify dependency-based invalidation scope correctness

---

## Implementation Notes

### Storage Considerations
- **Option A:** File-based (plan_versions/urban_v1.yaml, urban_v2.yaml)
- **Option B:** Database table (plan_versions, invalidation_records)
- **Recommendation:** Start file-based (simpler), migrate to DB if needed

### Approval Workflow
- P4: Manual approval (Owner reviews ReplanProposal)
- Future: Authorized agent approval (within defined bounds)
- Defer full workflow UI to V2-020+

### Performance
- Contract recompilation is expensive if many chapters invalidated
- Mitigation: Only recompile affected chapters (use FreezeHorizon and dependency analysis)
- Future optimization: Incremental recompilation

---

## References

- ADR-004: NarrativeDelta operations
- ADR-006: CanonCommitService write authority
- ADR-007: GenrePack binding and versioning
- V2-017 Task Packet: Planning/Contract responsibilities

---

## Examples

### Example 1: Canon Parent Advances
```
Scenario: Chapter 5 committed to Canon (parent: new_hash_789)
Action:
  - Immediately identify: chapter 6 contract compiled with old_hash_456 → INVALIDATE
  - Chapter 7-10 contracts: analyze dependencies
    - If chapter 7 bound to old parent → INVALIDATE
    - If chapter 7-10 not yet compiled → remain UNCOMPILED (not invalidated, just not compiled yet)
  - After chapter 6 recompiled: evaluate chapter 7 dependencies, continue chain
Rationale: Eager detection prevents stale chapter 6 from being used; uncompiled chapters remain adjustable
```

### Example 2: GenrePack Hash Changes
```
Scenario: urban.business.realistic Pack hash changes (bug fix in equity validator)
Action:
  - Cannot assume compatibility from state type filtering alone
  - Compatibility proof required: validator logic unchanged for all Equity operations used in contracts
  - If proof provided and verified → contracts remain valid
  - If no proof or verification fails → invalidate all contracts using Pack
  - State type filtering insufficient: must verify semantic equivalence
Rationale: Hash change signals potential semantic change; compatibility must be proven, not assumed
```

### Example 3: Synopsis Change
```
Scenario: Author updates series synopsis (typo fix)
Action:
  - Verify: does synopsis affect ANY compilation input or output?
  - Check: not just RequiredTransition references, but full compilation process
  - If synopsis never read during compilation → no invalidation
  - If synopsis used in context generation (future V2-018) → would trigger invalidation
  - When uncertain → invalidate (safe default)
Rationale: Metadata exemption requires proof of non-participation in compilation, not assumption
```

### Example 4: Uncompiled Future Plans
```
Scenario: Author adjusts chapter 50 goals (chapters 1-20 compiled, 21-49 uncompiled)
Action:
  - Chapters 1-20: compiled contracts, evaluate dependencies
    - If chapter 50 goal referenced in chapter 1-20 contracts → invalidate affected contracts
    - If not referenced → no invalidation
  - Chapters 21-49: not yet compiled → no invalidation (they're adjustable plans, not contracts)
  - Chapter 50: not yet compiled → adjustment is normal plan refinement
Rationale: Only compiled contracts can be invalidated; uncompiled plans are adjustable by design
```

---

## Decision Record

**Proposed by:** Claude Opus 4.7 (V2-017 PREPARE)  
**Decision date:** 2026-10-28  
**Accepted by:** ANovelOS Owner  
**Status:** ACCEPTED  
**Decision Evidence:** plan/validation/execution/V2-017/implement/adr-008-acceptance.yaml
