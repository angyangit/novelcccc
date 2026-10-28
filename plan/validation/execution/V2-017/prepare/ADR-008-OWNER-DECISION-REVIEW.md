# ADR-008 Owner Decision Review
# Contract-Overlay Binding, Planning Versioning, and Replanning

**Review Date:** 2026-10-28  
**Reviewer:** Claude Opus 4.7  
**Canonical Baseline:** `7bca5218fc65a83c74e3d9c0ddd9854582409850` (G-P3 merged)  
**ADR-008 Status:** REQUIRED (decision_register.yaml line 85-97)  
**Decision Due:** V2-017 (before IMPLEMENT)

---

## Executive Summary

**Recommendation: ACCEPT with one critical clarification on invalidation scope.**

ADR-008 provides sound technical foundation for V2-017 Contract Compiler. The five core decisions align with ANovelOS product goals: enable iterative Chinese long-form novel planning while maintaining Canon integrity and preventing planning system from corrupting narrative state.

**Critical Clarification Needed:** Section 4 (Invalidation) must distinguish between:
- **Full replan**: Canon parent changed for chapter N → all chapters N+1 onwards invalidated
- **Partial recompilation**: Minor input changes → only directly affected chapters recompiled

Without this distinction, every minor change triggers full series replanning—unacceptable for 100+ chapter novels.

---

## Part 1: Five Core Decisions Analysis

### Decision 1: Contract and Candidate Overlay Binding ✅ ACCEPT

**Current ADR-008 Text:**
> ChapterContract compiles against frozen Canon parent. Validation applies to candidate overlay `parent + proposed_delta`, never writes to Canon.

**Assessment:** ✅ **Sound and Sufficient**

**Rationale:**
- Maintains CanonCommitService as sole write authority (ADR-006 compliance)
- Contract Compiler is pure read-only function
- Enables validation before Canon commit
- Clear separation: planning proposes, Canon executes

**Product Alignment:**
- Supports "SeriesVision → ChapterPlan → ChapterContract → 章节正文" workflow
- Contract validates candidate overlay satisfies story requirements
- No auto-modification of Canon—human/agent explicitly approves commits

**Implementation Verification:**
- AT-V2-017-02: RequiredTransition uses NarrativeDelta operations ✅
- AT-V2-017-03: Conflicts return diagnostic, never modify Canon ✅

**No changes needed.** This decision directly supports core product goal.

---

### Decision 2: Planning Version and Freeze Horizon ✅ ACCEPT

**Current ADR-008 Text:**
> Plans have versions with supersession tracking. FreezeHorizon separates frozen inputs from adjustable future.

**Assessment:** ✅ **Essential for Long-Form Fiction**

**Rationale:**
- Enables iterative refinement without invalidating completed work
- FreezeHorizon critical for 100+ chapter novels:
  - Chapters 1-20 compiled → frozen
  - Chapters 21-100 adjustable based on actual chapter 20 outcome
- Prevents accidental rewriting of published chapters

**Product Alignment:**
- **Supports continuous creation**: Author writes chapter 20, updates vision for chapters 21-30, doesn't break chapters 1-19
- **Versioning enables rollback**: If new plan fails, revert to previous version
- **Clear boundary**: frozen = immutable inputs, adjustable = future planning

**Long-Form Novel Realism:**
- Real authors adjust future plans based on character development
- Already-written chapters constrain future possibilities
- Version tracking maintains audit trail of creative decisions

**Implementation Verification:**
- AT-V2-017-07: Versioning with freeze horizon ✅
- Test: v1 frozen on chapters 1-3 → v2 can modify chapter 5, cannot modify chapter 2 ✅

**No changes needed.** This decision is P0 for product viability.

---

### Decision 3: Supersession Semantics ✅ ACCEPT

**Current ADR-008 Text:**
> Supersession is explicit, not automatic. Compiling with superseded plan version errors.

**Assessment:** ✅ **Correct Safety Mechanism**

**Rationale:**
- Prevents silent use of stale plans
- Maintains version history for audit/debugging
- Supports rollback if new plan fails
- Explicit authorization creates decision trail

**Product Alignment:**
- **Prevents accidents**: Cannot accidentally compile chapter 50 using v1 when v5 is current
- **Audit trail**: Owner can review why v2 superseded v1 (e.g., "Canon parent advanced to chapter 15")
- **Rollback capability**: If v5 produces bad chapters, can create v6 that supersedes v5 and returns to v4 semantics

**Safety Consideration:**
- Frozen chapters from v1 can be inherited by v2 **if inputs unchanged**
- This is correct: if chapter 3 contract compiled against Canon parent X, and parent X still valid in v2, no need to recompile
- Efficiency for long series: avoid recompiling 50 chapters when only chapters 51-60 need adjustment

**Implementation Verification:**
- AT-V2-017-07: Compile with superseded v1 → `VersionError` ✅
- Test: v1 superseded by v2, attempt compilation → explicit error ✅

**No changes needed.** This protects against version confusion.

---

### Decision 4: Invalidation and Replanning ⚠️ NEEDS CLARIFICATION

**Current ADR-008 Text:**
> Input changes trigger InvalidationRecord + ReplanProposal. System proposes, does not auto-execute.

**Assessment:** ⚠️ **Sound Foundation, Needs Scope Clarification**

**Current Design Strength:**
- ✅ Prevents runaway replanning loops
- ✅ Human oversight required (approval_status: pending/approved/rejected)
- ✅ Audit trail (InvalidationRecord with reason, affected_inputs)
- ✅ Proposal-based workflow (describe changes, don't auto-execute)

**Critical Ambiguity:**

ADR-008 lists invalidation triggers but doesn't specify **scope of invalidation**:

**Scenario A: Canon Parent Advances (Chapter N Committed)**
- Chapter N committed to Canon → new parent hash
- Chapters N+1 onwards bound to old parent → **all invalidated?**
- Or only chapter N+1 invalidated, N+2 onwards remain valid until their turn?

**Scenario B: GenrePack Minor Update**
- Pack hash changes due to bug fix in state validator
- Does this invalidate ALL chapters? Or only chapters using affected state types?

**Scenario C: Character Goal Adjustment**
- Author updates protagonist goal in SeriesVision
- Does this invalidate all 100 chapters? Or only chapters explicitly referencing that goal?

**Proposed Clarification:**

Add to ADR-008 Section 4:

```markdown
### Invalidation Scope Rules

**Full Series Invalidation:**
- GenrePack ID changed (urban → fantasy)
- SeriesVision core conflict fundamentally altered
- Canon parent lost (data corruption, requires rebuild)

**Cascade Invalidation:**
- Canon parent advances (chapter N committed) → invalidate N+1
- Chapter N+1 recompiled with new parent → if successful, invalidate N+2
- Continue until recompilation stable or explicit stop

**Partial Invalidation:**
- GenrePack version/hash changed → only chapters using affected state types
- Character goal adjusted → only chapters with goal in required_transitions
- Knowledge boundary changed → only chapters with that knowledge constraint

**No Invalidation:**
- Typo fixes in chapter titles
- Metadata updates (synopsis, notes)
- Comments in SeriesVision
```

**Why This Matters for Long-Form Fiction:**

For a 100-chapter novel:
- **Without scope rules**: Any change invalidates all 100 chapters → replanning disaster
- **With scope rules**: Canon advances → cascade recompile chapters 51-52-53... as each completes
- **Efficiency**: Pack bug fix affects 3 chapters → recompile only those 3

**Product Impact:**

ANovelOS must support:
- Author writes chapter 50
- Reviews chapters 51-60 plan
- Adjusts protagonist sub-goal for chapter 55
- System: recompile chapters 55-60 (6 chapters), chapters 1-54 unchanged

This is **realistic creative workflow**, not invalidation explosion.

**Recommendation:**

**ACCEPT Decision 4 with addition of Invalidation Scope Rules** (as drafted above).

Without scope rules, invalidation becomes unusable for real novels.

---

### Decision 5: Canon Write Prohibition ✅ ACCEPT

**Current ADR-008 Text:**
> Contract Compiler and Replanning system are strictly read-only. Only CanonCommitService writes Canon.

**Assessment:** ✅ **Absolute Requirement, Non-Negotiable**

**Rationale:**
- **Single Write Authority** (ADR-006): Prevents Canon corruption
- **Security boundary**: Planning system cannot accidentally destroy narrative state
- **Separation of concerns**: Planning proposes, Canon executes, Quality gates verify

**Enforcement Mechanism:**
```python
# Compiler has NO Canon write permission
def compile_chapter(...) -> Result[ChapterContract, Diagnostic]:
    # Read-only operations:
    canon_parent = read_canon(parent_hash)  # ✅ Allowed
    overlay = apply_delta(canon_parent, delta)  # ✅ In-memory only
    
    # Write operations:
    commit_to_canon(overlay)  # ❌ SecurityError: no write permission
    return Success(contract)  # ✅ Returns contract, doesn't execute
```

**Product Safety:**
- Prevents planning bugs from corrupting 100 chapters of narrative state
- Failed replanning cannot destroy Canon
- Audit trail: all Canon changes via CanonCommitService, traceable

**Implementation Verification:**
- AT-V2-017-03: Compiler attempts Canon write → fails ✅
- Integration test: Verify planning system lacks write credentials ✅

**No changes needed.** This is architectural safety requirement.

---

## Part 2: Coverage of V2-017 AT Scenarios

All 8 AT scenarios adequately covered by ADR-008 decisions:

| AT Scenario | ADR-008 Coverage | Status |
|---|---|---|
| AT-V2-017-01: Compile from SeriesVision | Decision 1 (Contract binding) | ✅ Covered |
| AT-V2-017-02: RequiredTransition uses Delta ops | Decision 1 (Overlay validation) | ✅ Covered |
| AT-V2-017-03: Conflicts return diagnostic | Decision 5 (Read-only) | ✅ Covered |
| AT-V2-017-04: Human-reviewed fixtures | Out of ADR-008 scope (fixture policy) | N/A |
| AT-V2-017-05: Continuity binds to previous hash | Decision 1 (Canon parent binding) | ✅ Covered |
| AT-V2-017-06: Support quiet/cognitive chapters | Out of ADR-008 scope (compiler logic) | N/A |
| AT-V2-017-07: Planning versions with freeze horizon | Decision 2, 3 (Versioning, Supersession) | ✅ Covered |
| AT-V2-017-08: Invalidation + replan proposal | Decision 4 (Invalidation workflow) | ⚠️ Needs scope clarification |

**Clarification Unblocks:** AT-V2-017-08 needs invalidation scope rules to test properly.

---

## Part 3: Long-Form Chinese Novel Product Alignment

ADR-008 evaluated against ANovelOS's core product goal:

> "Story Fixture → SeriesVision → ChapterPlan → ChapterContract → 章节正文 → Canon 更新 → 连续性验证与受控重规划"

### Alignment Assessment: ✅ STRONG

**Supports Core Workflow:**

1. **SeriesVision → ChapterContract**: Decision 1 (overlay binding) enables compilation
2. **章节正文 → Canon 更新**: Decision 5 (write prohibition) maintains safety
3. **连续性验证**: Decision 1 (parent binding), AT-V2-017-05 (continuity constraints)
4. **受控重规划**: Decision 4 (invalidation + approval), Decision 3 (supersession)

**Supports Real Creative Needs:**

| Creative Need | ADR-008 Support |
|---|---|
| Adjust future plans based on actual chapter outcome | Decision 2 (FreezeHorizon) ✅ |
| Maintain consistency with written chapters | Decision 1 (Canon parent binding) ✅ |
| Rollback bad planning decisions | Decision 3 (Supersession with history) ✅ |
| Avoid accidental Canon corruption | Decision 5 (Write prohibition) ✅ |
| Iterative refinement without explosion | Decision 4 (Controlled replanning) ✅ |

**Does NOT Over-Constrain:**

- ✅ No forced combat/升级 in every chapter (AT-V2-017-06 out of scope)
- ✅ Supports quiet/relationship/cognitive chapters
- ✅ Supports non-combat conflict (business negotiation, cultivation resource choice)
- ✅ Allows character knowledge boundaries and secret revelation timing
- ✅ Enables long-term foreshadowing (frozen chapters maintain setup)

**Long-Form Scalability:**

100-chapter novel workflow:
1. Author creates SeriesVision for chapters 1-100
2. Compile chapter 1 (v1, frozen_chapters: [])
3. Write chapter 1 prose → commit to Canon (parent: abc123)
4. Chapter 1 committed → v1 invalidated (canon_parent_changed)
5. Create v2 (supersedes v1, frozen_chapters: [1], parent: abc123)
6. Compile chapter 2 using v2 (adjustable: [2-100])
7. Write chapter 2 → commit (parent: def456)
8. Repeat...

At chapter 50:
- Frozen: [1-49]
- Adjustable: [50-100]
- Author adjusts chapter 60 goal based on chapter 49 outcome
- System: recompile chapters 60-70 (affected range)
- Chapters 1-49: unchanged (already written)
- Chapters 71-100: may need adjustment based on 60-70 changes

**This is realistic novel writing workflow.**

---

## Part 4: Risks and Mitigations

### Risk 1: Invalidation Scope Explosion
**Risk:** Every change invalidates 100 chapters.  
**Mitigation:** Add invalidation scope rules (Part 1, Decision 4).  
**Status:** Clarification proposed.

### Risk 2: Versioning Complexity
**Risk:** FreezeHorizon and supersession become unmanageable.  
**Mitigation:** P4 uses linear supersession (v1→v2→v3), no branching.  
**Status:** ADR-008 already limits to linear chains.

### Risk 3: Manual Approval Bottleneck
**Risk:** Every Canon advance requires human approval of ReplanProposal.  
**Mitigation:** Future phases can add authorized agent approval within bounds.  
**Status:** Deferred to post-P4, explicit human oversight in P4 is correct.

### Risk 4: Plan Storage Mechanism TBD
**Risk:** ADR-008 doesn't specify file vs database storage.  
**Mitigation:** Start file-based (simpler), migrate if needed.  
**Status:** Implementation detail, not decision blocker.

---

## Part 5: Recommended Owner Decision

### Option A: ACCEPT (with Invalidation Scope Clarification) — RECOMMENDED

**Action:** Accept ADR-008 with addition of Invalidation Scope Rules to Section 4.

**Changes Required:**
1. Add "Invalidation Scope Rules" subsection to Section 4 (see Part 1, Decision 4)
2. Update decision_record in decision-register.yaml to reference clarified ADR-008
3. Mark ADR-008 status: REQUIRED → ACCEPTED

**Unblocks:**
- V2-017 IMPLEMENT can proceed
- AT-V2-017-08 (invalidation) has clear test criteria
- Long-form novel workflow validated

**Rationale:**
- Core decisions (1, 2, 3, 5) are sound and sufficient
- Decision 4 needs only scope clarification, not redesign
- Minimal change, maximum clarity
- Product-aligned, technically solid

---

### Option B: DEFER (pending broader replanning design)

**Action:** Defer ADR-008 until V2-020+ replanning workflow fully designed.

**Consequence:**
- ❌ V2-017 IMPLEMENT blocked
- ❌ P4 Planning & Contracts phase cannot start
- ❌ ANovelOS remains in Genre Kernel phase indefinitely

**Rationale Against:**
- ADR-008 is **minimal viable decision**, not comprehensive replanning system
- V2-017 needs only: compile contract, detect invalidation, propose replan
- Full replanning optimization/solver deferred to future phases (correct)
- No benefit to delaying P0 decisions for P8+ features

**Not Recommended.**

---

### Option C: AMEND (redesign contract binding model)

**Action:** Redesign Decision 1 (contract-overlay binding) with alternative approach.

**Rationale Against:**
- Current Decision 1 is **architecturally correct**
- Maintains ADR-006 (single write authority)
- Reuses NarrativeDelta (ADR-004) operations
- No identified technical flaw
- Redesign would delay without benefit

**Not Recommended.**

---

## Part 6: Formal Recommendation

**Recommended Decision: ACCEPT ADR-008 with Invalidation Scope Clarification**

**Summary:**
- Decisions 1, 2, 3, 5: Accept as-is ✅
- Decision 4: Accept with addition of Invalidation Scope Rules ⚠️→✅
- All 8 AT scenarios covered or correctly out-of-scope
- Product alignment validated for Chinese long-form fiction
- No blocking technical flaws
- Minimal change required (scope rules addition)

**Next Steps After Acceptance:**
1. Owner approves this recommendation
2. Update ADR-008 document with Invalidation Scope Rules
3. Update decision-register.yaml: status REQUIRED → ACCEPTED, add decision_record reference
4. V2-017 IMPLEMENT authorized (pending Story Fixture human review)

**Estimated Time to Acceptance:** Owner review + minimal ADR-008 edit: 1 session

---

## Appendix A: Invalidation Scope Rules (Proposed Addition)

```markdown
### 4.1 Invalidation Scope Rules

**Full Series Invalidation** (affects all chapters):
- GenrePack ID fundamentally changed (urban.business → fantasy.eastern)
- SeriesVision core conflict completely redesigned
- Canon parent lost due to data corruption

**Cascade Invalidation** (sequential recompilation):
- Canon parent advances (chapter N committed) → invalidate chapter N+1
- After chapter N+1 recompiled successfully → invalidate chapter N+2
- Continue until recompilation stable or manual stop

**Partial Invalidation** (targeted chapters only):
- GenrePack version/hash changed → only chapters using affected state types
- Character goal in SeriesVision adjusted → only chapters with that goal in required_transitions
- Knowledge boundary modified → only chapters with that knowledge constraint
- Resource initial value changed → only chapters with resource preconditions

**No Invalidation** (metadata changes):
- Typo fixes in chapter titles or synopsis
- Comment additions in SeriesVision YAML
- Metadata updates (partition, notes fields)

**Scope Determination Algorithm:**
1. Identify what changed (Canon parent, Pack, SeriesVision field)
2. Query: which chapters reference changed element?
3. Create InvalidationRecord for affected chapters only
4. Generate ReplanProposal with explicit scope justification
5. After approval, recompile only affected chapters
```

---

**Review Complete.**  
**Status:** Ready for Owner decision.  
**Recommendation:** ACCEPT with clarification (Option A).
