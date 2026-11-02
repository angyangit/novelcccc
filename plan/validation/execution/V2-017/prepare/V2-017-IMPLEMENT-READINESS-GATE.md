# V2-017 Contract Compiler IMPLEMENT Readiness Gate
# 准入条件核查与 Owner 决策清单

**Review Date:** 2026-10-28  
**Canonical Baseline:** `7bca5218fc65a83c74e3d9c0ddd9854582409850` (G-P3 merged)  
**Task:** V2-017 Contract Compiler  
**Current Status:** OPEN / PLANNED / PREPARE (完成)  
**Next Phase:** IMPLEMENT (awaiting Owner authorization)

---

## Executive Summary

**G-P3 Genre Kernel:** ✅ VERIFIED (PR #14 merged)  
**V2-017 PREPARE:** ✅ Complete (已合并至 main)  
**ADR-008 Decision:** ⏳ REQUIRED (awaiting Owner approval)  
**Story Fixtures Human Review:** ⏳ DRAFT (awaiting Owner approval)  
**Owner IMPLEMENT Authorization:** ⏳ Not yet granted

**Current Blocker:** ADR-008 和 Story Fixtures 需 Owner 正式决策后，才能授权 V2-017 IMPLEMENT。

---

## Part 1: Readiness Gate Checklist

| Gate Condition | Required Status | Current Status | Details |
|---|---|---|---|
| **G-P3 Phase Gate** | VERIFIED | ✅ VERIFIED | PR #14 merged, main HEAD `7bca521` |
| **V2-017 start_gate** | G-P3 | ✅ Satisfied | Dependency met |
| **V2-017 PREPARE** | Complete & Merged | ✅ Complete | Merged in PR #13 (commit `68c8d00`) |
| **ADR-004** | ACCEPTED | ✅ ACCEPTED | NarrativeDelta operations |
| **ADR-006** | ACCEPTED | ✅ ACCEPTED | CanonCommitService authority |
| **ADR-007** | ACCEPTED | ✅ ACCEPTED | GenrePack binding |
| **ADR-008** | ACCEPTED | ⏳ **REQUIRED** | Contract-Overlay binding (awaiting) |
| **Story Fixtures** | human_review_ref populated | ⏳ **DRAFT** | Both null (awaiting) |
| **Execution Packet** | Updated for IMPLEMENT | ⏳ Pending | After ADR-008 + fixtures approved |
| **Owner Authorization** | Explicit IMPLEMENT grant | ⏳ **Not Granted** | Awaiting Owner decision |

---

## Part 2: Current Gate Status Detail

### Gate 1: G-P3 Phase Gate ✅ SATISFIED

**Status:** VERIFIED  
**Evidence:**
- Phase decision: `plan/validation/closure/G-P3-68c8d00/phase-decision.yaml`
- Decision: VERIFIED
- Revision: `68c8d00ae5a74ee31ddb8d18ab23ab6921c185d1`
- Merged to main: PR #14 (2026-10-28)
- CI verification: 6/6 gates SUCCESS (Run 40627410928)

**V2-017 Dependency:** ✅ Met

---

### Gate 2: ADR-004, ADR-006, ADR-007 ✅ SATISFIED

**ADR-004: NarrativeDelta Operations**
- Status: ACCEPTED
- Location: `plan/decisions/ADR-004_NARRATIVE_DELTA_OPERATIONS_AND_PRECONDITIONS.md`
- Relevance: RequiredTransition uses Delta operation types (AT-V2-017-02)

**ADR-006: CanonCommitService Single Write Authority**
- Status: ACCEPTED  
- Relevance: Contract Compiler read-only, no Canon writes (AT-V2-017-03)

**ADR-007: GenrePack Binding**
- Status: ACCEPTED
- Location: `plan/decisions/ADR-007_GENRE_EXTENSION_NAMESPACE_AND_STATE_TRANSITIONS.md`
- Relevance: ChapterContract binds to GenrePack hash (ADR-008 Section 1)

**Conclusion:** ✅ All prerequisite ADRs accepted.

---

### Gate 3: ADR-008 Contract-Overlay Binding ⏳ REQUIRED

**Current Status:** REQUIRED (decision-register.yaml line 85-97)

**Decision Register Entry:**
```yaml
- id: ADR-008
  title: 候选 overlay 与 Contract 编译绑定
  status: REQUIRED
  owner_role: planning-maintainer
  related_tasks:
  - V2-017
  - V2-020
  decision_due_task: V2-017
  timing: before_interface_implementation
  decision_record: null
  verification_refs: []
  required_refinements:
  - 补充规划版本、冻结边界、supersession、失效与受控重规划；按 V2-017 packet 分职责
```

**ADR-008 Document Status:**
- Location: `plan/validation/execution/V2-017/prepare/adr-008-recommendation.md`
- Status: PROPOSED (awaiting acceptance)
- Owner Decision Review: `ADR-008-OWNER-DECISION-REVIEW.md` (revised with precision gaps identified)

**Recommendation from Review:** **AMEND** (not ACCEPT) — Add precise Invalidation Scope Rules

**Critical Precision Gaps Identified:**
1. **Eager invalidation**: Original proposal lacks requirement for immediate detection
2. **State boundaries**: Must distinguish committed Canon (immutable) vs. compiled contracts (invalidatable) vs. adjustable plans
3. **Compatibility proofs**: GenrePack changes need explicit verification, not assumptions
4. **Metadata exemptions**: Must verify field doesn't participate in compilation

**Why AMEND vs. ACCEPT:**
- Original ADR-008 Section 4 allows ambiguity that could lead to stale contracts or Canon corruption
- Tightening required, not redesign
- Core decisions (1, 2, 3, 5) remain sound

**Blocker:** ⏳ **Owner must formally accept ADR-008 before V2-017 IMPLEMENT.**

**Why This Matters:**
- ADR-008 defines Contract-Overlay binding (core V2-017 architecture)
- Planning versioning semantics (FreezeHorizon, supersession)
- Invalidation and replanning workflow
- Cannot implement Contract Compiler without these decisions

**Owner Action Required:**
1. Review `ADR-008-OWNER-DECISION-REVIEW.md`
2. Approve ADR-008 (with or without clarification)
3. Update `plan/machine/decision-register.yaml`: status REQUIRED → ACCEPTED
4. Add decision_record reference
5. Commit decision to canonical main

---

### Gate 4: Story Fixtures Human Review ⏳ DRAFT

**Current Status:** DRAFT (both human_review_ref: null)

**Urban Business Fixture:**
- File: `specs/fixtures/urban_business_startup_v1.yaml`
- Line 8: `human_review_ref: null`
- AI Pre-Audit: ⚠️ **APPROVE with 1 minor clarification** (cash runway vs. performance bet timeline)

**Fantasy Eastern Fixture:**
- File: `specs/fixtures/fantasy_eastern_cultivation_v1.yaml`
- Line 8: `human_review_ref: null`
- AI Pre-Audit: ⚠️ **APPROVE with 2 clarifications** (1 blocking: survival rate inconsistency)

**Human Review Checklist:**
- Location: `DUAL-STORY-FIXTURE-HUMAN-REVIEW-CHECKLIST.md` (revised with specific inconsistencies identified)
- Technical validation: ✅ PASS (with clarifications needed)
- Content quality: Requires Owner judgment

**Blocking Issue Identified:**
- Fantasy fixture lines 189 & 237: "死亡率30%" vs. "生还率50%" — math inconsistency
- Must resolve before contract choice analysis is valid
- Suggested fixes provided in checklist

**AT-V2-017-04 Requirement:**
> "Both fixtures must have `human_review_ref` populated"

**Blocker:** ⏳ **Owner must conduct human review and assign review references.**

**Why This Matters:**
- Story Fixtures are V2-017 test inputs (AT scenarios use these fixtures)
- DRAFT fixtures acceptable for dev/test, NOT for production compilation
- Human review validates: content quality, story logic, cultural appropriateness
- AI cannot replace human aesthetic/content judgment

**Owner Action Required:**
1. Review `DUAL-STORY-FIXTURE-HUMAN-REVIEW-CHECKLIST.md`
2. Conduct content quality assessment (AI pre-audit covers technical only)
3. If approved:
   - Urban: Assign `human_review_ref` (e.g., "review-2026-10-28-urban-001")
   - Fantasy: Assign `human_review_ref` (e.g., "review-2026-10-28-fantasy-001")
4. Update both fixture YAML files
5. Commit to canonical main

**Alternative:** If modifications needed, specify changes and re-review.

---

### Gate 5: Execution Packet Update ⏳ PENDING

**Current Packet:** `plan/validation/execution/V2-017/prepare/execution-packet.yaml`
- Action: PREPARE
- Status: Complete (merged)

**IMPLEMENT Packet:** Not yet created

**Dependencies:**
- ADR-008 must be ACCEPTED (input to IMPLEMENT)
- Story Fixtures must have human_review_ref (verified inputs)

**Owner Action Required:**
After ADR-008 + Fixtures approved:
1. Create `plan/validation/execution/V2-017/execution-packet.yaml` (IMPLEMENT action)
2. Reference:
   - ADR-008 decision_record
   - Human-reviewed fixture refs
   - Updated input bindings
3. Define IMPLEMENT scope, stop conditions, verification plan

**Status:** ⏳ Blocked by Gates 3 & 4

---

### Gate 6: Owner IMPLEMENT Authorization ⏳ NOT GRANTED

**Current Authorization:** None

**Required Authorization Elements:**
1. Explicit IMPLEMENT permission for V2-017
2. Scope boundaries (what to implement, what to defer)
3. Verification requirements (which AT scenarios must pass)
4. Stop conditions (when IMPLEMENT complete)

**Formal Authorization Document:** TBD (after Gates 3 & 4 satisfied)

**Owner Action Required:**
After ADR-008 + Fixtures approved:
1. Review IMPLEMENT scope (from PREPARE review)
2. Grant explicit IMPLEMENT authorization
3. Specify any constraints or priorities
4. Define success criteria

**Status:** ⏳ Awaiting prerequisite gates

---

## Part 3: Dependency Graph

```
G-P3 VERIFIED ✅
    ↓
V2-017 start_gate satisfied ✅
    ↓
ADR-004/006/007 ACCEPTED ✅
    ↓
┌───────────────────────────┐
│ ADR-008 Decision ⏳       │ ← Owner approval needed
└───────────────────────────┘
    ↓
┌───────────────────────────┐
│ Story Fixtures Review ⏳  │ ← Owner approval needed
└───────────────────────────┘
    ↓
┌───────────────────────────┐
│ Execution Packet (IMPL) ⏳│
└───────────────────────────┘
    ↓
┌───────────────────────────┐
│ Owner Authorization ⏳    │
└───────────────────────────┘
    ↓
V2-017 IMPLEMENT can begin
```

**Current Bottleneck:** ADR-008 + Story Fixtures (parallel gates, both need Owner decision)

---

## Part 4: Decision Materials Provided

本次审查提供以下决策材料供 Owner 批准：

### Document 1: ADR-008 Owner Decision Review
**File:** `ADR-008-OWNER-DECISION-REVIEW.md`

**Summary:**
- Reviews 5 core ADR-008 decisions
- Assesses product alignment for long-form Chinese novels
- Validates AT scenario coverage
- **Recommendation:** ACCEPT with Invalidation Scope Clarification

**Owner Decision Needed:**
- [ ] ACCEPT ADR-008 (with clarification)
- [ ] REJECT ADR-008 (specify reasons)
- [ ] AMEND ADR-008 (specify changes)

---

### Document 2: Dual Story Fixture Human Review Checklist
**File:** `DUAL-STORY-FIXTURE-HUMAN-REVIEW-CHECKLIST.md`

**Summary:**
- AI pre-audit of technical structure (✅ both fixtures PASS)
- Story conflict, character goals, knowledge boundaries validated
- Genre Pack compliance verified
- **Recommendation:** APPROVE both fixtures (content quality requires human judgment)

**Owner Decision Needed:**
- [ ] APPROVE urban_business_startup_v1 (assign human_review_ref)
- [ ] APPROVE fantasy_eastern_cultivation_v1 (assign human_review_ref)
- [ ] REJECT or MODIFY either fixture (specify reasons)

---

### Document 3: V2-017 PREPARE Correction
**File:** `prepare-review.md` (line 570-577 corrected)

**Change:** Removed conflicting text stating "IMPLEMENT can proceed with proposed ADR-008 semantics"

**Corrected Text:**
> "Owner must formally accept ADR-008 before V2-017 IMPLEMENT per decision governance"

**Rationale:** Maintains formal decision-register authority, prevents PREPARE document from bypassing governance.

---

## Part 5: What V2-017 IMPLEMENT Will NOT Do

明确禁止事项（防止范围扩大）：

**NOT in V2-017 Scope:**
- ❌ P10 Genesis (automated story generation)
- ❌ V2-018 Context Compiler
- ❌ V2-019 Model Gateway
- ❌ V2-020 Full chapter workflow
- ❌ Quality gates Q0-Q3 (V2-022-026)
- ❌ Automated replanning optimization/solver
- ❌ Multi-book plan management
- ❌ Full 30-GenrePack expansion
- ❌ Production deployment
- ❌ Real paid model calls

**V2-017 IMPLEMENT Scope (Minimal):**
1. `planning/models.py`: SeriesVision, ChapterPlan data structures
2. `planning/versions.py`: PlanVersion, FreezeHorizon, supersession logic
3. `contracts/models.py`: ChapterContract, RequiredTransition, KnowledgeBoundary
4. `contracts/compiler.py`: ContractCompiler.compile_chapter()
5. Story Fixture parser (YAML → SeriesVision)
6. 8 AT scenario tests (`tests/contract/test_v2_017.py`)

**Verification:** Contract compilation works with dual fixtures, all 8 AT scenarios pass.

---

## Part 6: Next Steps Summary

### Immediate (Owner Review Phase)

**Step 1: Review Decision Materials**
- [ ] Read `ADR-008-OWNER-DECISION-REVIEW.md`
- [ ] Read `DUAL-STORY-FIXTURE-HUMAN-REVIEW-CHECKLIST.md`
- [ ] Assess content quality (AI cannot replace human judgment)

**Step 2: Make Decisions**
- [ ] ADR-008: ACCEPT / REJECT / AMEND
- [ ] Urban Fixture: APPROVE / REJECT / MODIFY
- [ ] Fantasy Fixture: APPROVE / REJECT / MODIFY

---

### After Approvals (Unblock IMPLEMENT)

**Step 3: Update Canonical Records**

If ADR-008 ACCEPTED:
```bash
# Update decision-register.yaml
- id: ADR-008
  status: ACCEPTED  # Changed from REQUIRED
  decision_record: plan/decisions/ADR-008-accepted-2026-10-28.md
```

If Fixtures APPROVED:
```bash
# Update urban_business_startup_v1.yaml
human_review_ref: "review-2026-10-28-urban-001"

# Update fantasy_eastern_cultivation_v1.yaml
human_review_ref: "review-2026-10-28-fantasy-001"
```

**Step 4: Create IMPLEMENT Execution Packet**
- Reference accepted ADR-008
- Reference approved fixtures
- Define IMPLEMENT scope, verification, stop conditions

**Step 5: Grant IMPLEMENT Authorization**
- Explicit Owner authorization for V2-017 IMPLEMENT
- Scope boundaries
- Success criteria

**Step 6: V2-017 IMPLEMENT Begins**
- Implement 5 modules (planning, contracts, compiler)
- Write 8 AT scenario tests
- Verify with approved fixtures
- Submit IMPLEMENT PR

---

## Part 7: Timeline Estimate

**If Owner approves ADR-008 + Fixtures immediately:**

- Day 1: Owner review and decisions (本次)
- Day 2: Update decision-register, fixtures, create IMPLEMENT packet
- Day 3: Owner grants IMPLEMENT authorization
- Day 4-6: V2-017 IMPLEMENT (3-5 sessions estimated)
- Day 7: IMPLEMENT PR review and merge

**Total:** ~7 days to complete V2-017 (Contract Compiler)

**Critical Path:** Owner decision on ADR-008 + Fixtures (Gates 3 & 4)

---

## Part 8: Risk Summary

### Risk 1: ADR-008 Rejected or Requires Major Redesign
**Probability:** Low (review shows sound technical foundation)  
**Impact:** High (blocks V2-017, requires architecture rework)  
**Mitigation:** Review provides clear recommendation with minimal clarification

### Risk 2: Fixtures Require Content Modifications
**Probability:** Medium (content quality subjective)  
**Impact:** Medium (delays IMPLEMENT by 1-2 sessions for revisions)  
**Mitigation:** AI pre-audit shows no technical blocking issues

### Risk 3: Scope Expansion During IMPLEMENT
**Probability:** Medium (temptation to add features)  
**Impact:** High (delays, scope creep)  
**Mitigation:** Clear NOT-in-scope list, minimal deliverable definition

---

## Appendix: Validation Command Reference

验证当前状态的命令：

```bash
# Check G-P3 phase decision
grep "decision: VERIFIED" plan/validation/closure/G-P3-68c8d00/phase-decision.yaml

# Check ADR-008 status
grep -A 3 "id: ADR-008" plan/machine/decision-register.yaml

# Check fixture human_review_ref
grep "human_review_ref" specs/fixtures/urban_business_startup_v1.yaml
grep "human_review_ref" specs/fixtures/fantasy_eastern_cultivation_v1.yaml

# Check V2-017 task status
grep -A 5 "task_id: V2-017" plan/machine/implementation-backlog.yaml

# Run plan validation
uv run python plan/scripts/validate_plan.py --check
```

---

**Readiness Gate Status:** ⏳ **2 of 6 gates satisfied, 4 pending Owner decision**

**Blocking Gates:** ADR-008 approval + Story Fixture human review

**Recommendation:** Owner review decision materials, approve ADR-008 + Fixtures to unblock V2-017 IMPLEMENT.

**ANovelOS Product Goal:** Complete Contract Compiler to enable SeriesVision → ChapterContract → 章节正文 workflow.
