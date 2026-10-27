# ADR-008: Contract-Overlay Binding, Planning Versioning, and Replanning

**Status:** PROPOSED (awaiting acceptance)  
**Date:** 2026-10-27  
**Scope:** V2-017 Contract Compiler  
**Related Tasks:** V2-017, V2-020  
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

**Decision:** Input changes trigger InvalidationRecord + ReplanProposal. System proposes, does not auto-execute.

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

### Negative

- ⚠️ Versioning adds complexity (mitigated by simple linear supersession in P4)
- ⚠️ Manual approval required for replanning (intended—human oversight)
- ⚠️ Plan storage mechanism TBD (files vs database)

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
- Mitigation: Only recompile affected chapters (use FreezeHorizon)
- Future optimization: Incremental recompilation

---

## References

- ADR-004: NarrativeDelta operations
- ADR-006: CanonCommitService write authority
- ADR-007: GenrePack binding and versioning
- V2-017 Task Packet: Planning/Contract responsibilities

---

## Decision Record

**Proposed by:** Claude Opus 4.7 (V2-017 PREPARE)  
**Decision date:** Pending  
**Accepted by:** Pending Owner approval  
**Status:** PROPOSED → ACCEPTED (after Owner review)

---

## Appendix: Example Supersession Timeline

```
2026-10-27: urban_v1 created
  frozen_chapters: []
  adjustable_chapters: [1-15]
  
2026-10-28: Chapter 1-3 compiled from urban_v1
  frozen_chapters: [1-3]
  adjustable_chapters: [4-15]
  
2026-10-29: Chapter 1 committed to Canon (parent: abc123)
  → urban_v1 invalidated (canon_parent_changed)
  → ReplanProposal created
  
2026-10-30: Owner approves replan
  → urban_v2 created (supersedes: urban_v1)
  → Frozen chapters [1] inherited (inputs match)
  → Chapters [2-3] recompiled with new parent
  → urban_v1.superseded_by = urban_v2
  
2026-10-31: Attempt compile with urban_v1
  → VersionError: "Plan version urban_v1 superseded by urban_v2"
```
