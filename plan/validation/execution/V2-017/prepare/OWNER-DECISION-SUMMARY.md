# Owner Decision Summary — V2-017 IMPLEMENT Readiness

**Date:** 2026-10-28  
**Canonical Baseline:** `7bca5218fc65a83c74e3d9c0ddd9854582409850` (G-P3 merged)  
**Review Branch:** `review/adr-008-and-fixtures-decision`  
**Review HEAD:** `6452b345ad7a9b685d787a41995096375bfd8a7b` (to be updated)

---

## Required Owner Decisions (3 Items)

### Decision 1: ADR-008 Contract-Overlay Binding & Planning Versioning

**Current Status:** REQUIRED (decision-register.yaml line 87)

**AI Review Recommendation:** **AMEND** (not ACCEPT)

**Why AMEND:**
- Decisions 1, 2, 3, 5 technically sound ✅
- Decision 4 (Invalidation & Replanning) has **precision gaps**:
  - Lacks **eager invalidation** requirement (could allow stale contracts)
  - No distinction between **committed Canon** (immutable) vs. **compiled contracts** (invalidatable)
  - Lacks **compatibility proof** requirement for GenrePack changes
  - Metadata exemptions need **verification**, not assumptions

**Required Amendment:**
Add precise Invalidation Scope Rules to Section 4:
1. **Eager invalidation**: Detect immediately, no deferred detection
2. **Dependency-based scope**: Invalidate only contracts with actual dependencies
3. **State boundaries**: Committed Canon ≠ compiled contracts ≠ adjustable plans
4. **Compatibility proofs required**: GenrePack changes need explicit verification
5. **Audit trail mandatory**: Justify scope for every InvalidationRecord

**Owner Action:**
- [ ] **AMEND** ADR-008 with precision rules (recommended)
- [ ] ACCEPT as-is (risk: stale contracts, ambiguity)
- [ ] DEFER pending broader replanning design (blocks V2-017)

**If AMEND approved:** Update decision-register.yaml status → ACCEPTED

**Review Document:** `ADR-008-OWNER-DECISION-REVIEW.md` (detailed analysis)

---

### Decision 2: Urban Business Fixture (urban_business_startup_v1)

**Current Status:** DRAFT (`human_review_ref: null`)

**AI Review Recommendation:** **APPROVE with 1 minor clarification**

**Technical Validation:** ✅ PASS
- Story structure: Funding dilemma vs. control ✅
- Character goals: Zhang/Li/Wang authentic motivations ✅
- Knowledge boundaries: 2 secrets with reveal timing ✅
- World rules: Realistic business constraints, no pollution ✅
- Choice costs: 3 paths with genuine tradeoffs ✅

**Minor Clarification (Non-Blocking):**
- **Line 147:** "获得500万资金，18个月运营保障"
- **Issue:** 5.5M / 200k monthly = 27.5 months, not 18 months
- **Likely intent:** 18 months = performance bet deadline (not cash runway)
- **Suggested fix:** "获得500万资金，27个月现金续航（但对赌协议要求18个月内营收达3000万）"

**Content Quality (Human Judgment Required):**
- Story compelling? (创业融资困境)
- Character authenticity? (技术创始人 vs. 风险投资人)
- Dialogue potential? (商业谈判、价值冲突)
- Cultural fit? (中国创业环境)

**Owner Action:**
- [ ] **APPROVE as-is** (interpret 18 months as bet deadline)
- [ ] **APPROVE with clarification** (request line 147 revision)
- [ ] **MODIFY** (specify required changes)

**If approved:** Assign `human_review_ref: "review-2026-10-28-urban-001"` (or Owner's chosen ID)

**Review Document:** `DUAL-STORY-FIXTURE-HUMAN-REVIEW-CHECKLIST.md` Section G (urban)

---

### Decision 3: Fantasy Eastern Fixture (fantasy_eastern_cultivation_v1)

**Current Status:** DRAFT (`human_review_ref: null`)

**AI Review Recommendation:** **APPROVE with 2 clarifications (1 BLOCKING)**

**Technical Validation:** ⚠️ PASS with clarifications needed
- Story structure: Breakthrough vs. partner vs. freedom ✅
- Character goals: Wang/Liu/Zhao xianxia motivations ✅
- Knowledge boundaries: 3 secrets with reveal timing ✅
- World rules: Cultivation constraints, no modern pollution ✅
- Choice costs: 4 paths with xianxia tradeoffs ✅

**Blocking Clarification:**
- **Lines 189 & 237:** "死亡率30%" vs. "生还率50%"
- **Math inconsistency:** 30% death should = 70% survival, not 50%
- **Possible interpretations:**
  - Per-mission death (30%) vs. 3-year contract completion (50% cumulative)
  - Different risk scopes
- **Suggested fix A:** Change line 189 to "三年护卫契约完成率约50%（累积风险）"
- **Suggested fix B:** Change line 237 to "生还率70%"
- **Blocking?** **YES** — contract choice analysis requires consistent math

**Minor Clarification (Non-Blocking):**
- **Lines 20 & 259:** Dao comprehension 20 (initial) vs. 15→20 (chapters 1-3)
- **Timeline ambiguity:** Which is story opening value?
- **Suggested fixes:** Adjust line 259 OR line 20 OR add timeline note

**Content Quality (Human Judgment Required):**
- Story compelling? (散修资源困境)
- Character authenticity? (修仙进境 vs. 道侣之情)
- Xianxia conventions? (境界、代价、资源稀缺)
- Genre fit? (东方玄幻读者)

**Owner Action:**
- [ ] **RESOLVE blocking issue** (guild contract survival rates)
- [ ] **APPROVE with clarifications** (after math reconciled)
- [ ] **MODIFY** (specify required changes)

**If approved:** Assign `human_review_ref: "review-2026-10-28-fantasy-001"` (or Owner's chosen ID)

**Review Document:** `DUAL-STORY-FIXTURE-HUMAN-REVIEW-CHECKLIST.md` Section G (fantasy)

---

## V2-017 IMPLEMENT Remaining Gates

| Gate | Status | Blocker |
|---|---|---|
| G-P3 Phase Gate | ✅ VERIFIED | None |
| ADR-004/006/007 | ✅ ACCEPTED | None |
| **ADR-008** | ⏳ **REQUIRED** | **Awaiting AMEND decision** |
| **Urban Fixture** | ⏳ **DRAFT** | **Awaiting human_review_ref** |
| **Fantasy Fixture** | ⏳ **DRAFT** | **Blocking: survival rate math** |
| Execution Packet (IMPL) | ⏳ Pending | After above gates |
| Owner Authorization | ⏳ Not Granted | After above gates |

**Critical Path:** ADR-008 + Fantasy fixture blocking issue → Urban fixture → Authorization

---

## Human Judgment Required (AI Cannot Decide)

**ADR-008:**
- Accept ambiguity risk vs. precision requirement tradeoff
- Architectural philosophy: eager vs. lazy invalidation

**Urban Fixture:**
- Story literary quality and market appeal
- Cultural authenticity for Chinese startup environment
- Accept timeline ambiguity vs. require explicit clarification

**Fantasy Fixture:**
- Xianxia story quality and genre fit
- Math reconciliation approach (cumulative vs. per-mission)
- Dao comprehension timeline preference

**AI Pre-Audit Scope:** Technical structure, consistency checks, schema validation only

---

## Post-Decision Actions

**If all 3 decisions approved:**

1. **Update decision-register.yaml:**
   ```yaml
   - id: ADR-008
     status: ACCEPTED  # From REQUIRED
     decision_record: plan/decisions/ADR-008-accepted-2026-10-28.md
   ```

2. **Update fixture files:**
   ```yaml
   # urban_business_startup_v1.yaml line 8
   human_review_ref: "review-2026-10-28-urban-001"
   
   # fantasy_eastern_cultivation_v1.yaml line 8
   human_review_ref: "review-2026-10-28-fantasy-001"
   ```

3. **Create IMPLEMENT execution packet:**
   - Reference accepted ADR-008
   - Reference approved fixtures
   - Define scope, verification, stop conditions

4. **Grant IMPLEMENT authorization:**
   - Explicit V2-017 IMPLEMENT permission
   - Success criteria
   - Constraints

5. **V2-017 IMPLEMENT begins** (estimated 3-5 sessions)

---

## Timeline Estimate

**Fast Track (all approved immediately):**
- Day 1: Owner decisions (today)
- Day 2: Update records, resolve fixture blocking issue
- Day 3: Create IMPLEMENT packet, grant authorization
- Day 4-6: V2-017 IMPLEMENT
- Day 7: IMPLEMENT PR review
- **Total:** 7 days to Contract Compiler complete

**Critical Bottleneck:** Fantasy fixture survival rate math reconciliation

---

## What V2-017 Will NOT Do

**Out of Scope:**
- ❌ P10 Genesis (automated story generation)
- ❌ V2-018 Context Compiler
- ❌ V2-020 Full chapter workflow
- ❌ Production deployment
- ❌ Real paid model calls
- ❌ Automated replanning solver/optimizer

**V2-017 Minimal Scope:**
- ✅ Planning models (SeriesVision, ChapterPlan, PlanVersion)
- ✅ Contract models (ChapterContract, RequiredTransition)
- ✅ Compiler (compile_chapter pure function)
- ✅ 8 AT scenario tests

---

**ANovelOS Goal:** Enable SeriesVision → ChapterContract → 章节正文 workflow for Chinese long-form fiction.

**Next:** Owner makes 3 decisions, unblocks V2-017 IMPLEMENT.
