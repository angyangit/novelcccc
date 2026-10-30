# V2-017 AT Mapping and Verification

**Date**: 2026-10-30  
**Branch**: implement/v2-017-contract-compiler  
**Commit**: 5254b9c  
**Authority**: plan/machine/test-catalog.yaml (version 1.3.1)

---

## Official AT-V2-017 Specifications

### AT-V2-017-01: 从人工 SeriesVision 编译且不依赖 P10
**Requirement**: Compile from human-authored SeriesVision, not P10 Genesis

### AT-V2-017-02: RequiredTransition 与 Delta 使用同一语义
**Requirement**: RequiredTransition uses same semantics as NarrativeDelta

### AT-V2-017-03: 计划冲突或不可满足合约返回诊断而非改写 Canon
**Requirement**: Plan conflicts or unsatisfiable contracts return diagnostic, don't rewrite Canon

### AT-V2-017-04: 双书 fixture 经人工审定并包含知识及揭示边界
**Requirement**: Dual fixtures human-reviewed with knowledge and revelation boundaries

### AT-V2-017-05: 接续合约绑定前章正文 hash/实际结束证据及本章起点；前章修订使旧接续失效，第一章显式无前章
**Requirement**: Continuation contract binds prior chapter prose hash/actual end evidence and current start; prior revision invalidates continuation, chapter 1 explicitly has no prior

### AT-V2-017-06: 场景可消费角色目标/知识与预期代价；安静或认知推进章节无需强制升级战斗字段
**Requirement**: Scenes consume character goals/knowledge and expected costs; quiet or cognitive progression chapters don't force combat fields

### AT-V2-017-07: 规划输入有版本与 supersession，冻结区和可调整未来计划分离；失效输入不得静默编译
**Requirement**: Planning inputs have version and supersession, frozen zone separated from adjustable future; expired inputs must not silently compile

### AT-V2-017-08: Canon/Pack/计划修订触发有范围的失效和重规划提议，批准新计划后重新编译且不改写 Canon
**Requirement**: Canon/Pack/Plan revisions trigger scoped invalidation and replan proposal; recompile after approval without rewriting Canon

---

## Test Mapping to AT Requirements

### Current Test File
**Path**: `tests/contract/test_v2_017_acceptance.py` (583 lines)  
**Expected Path**: `tests/contract/test_v2_017.py`  
**Status**: ❌ PATH MISMATCH - Must rename to match test-catalog

### Test Class → AT Mapping

| Test Class | Tests | Maps To | Status |
|------------|-------|---------|--------|
| TestAT_V2_017_01_InitialChapterCompilation | 3 | AT-01 | ✅ CORRECT |
| TestAT_V2_017_02_RequiredTransitionSemantics | 1 | AT-02 | ✅ CORRECT |
| TestAT_V2_017_03_ConflictsReturnDiagnostic | 1 | AT-03 | ✅ CORRECT |
| TestAT_V2_017_04_ContinuityBindsToPreviousChapter | 2 | **AT-05** | ⚠️ MISMAPPED |
| TestAT_V2_017_05_KnowledgeBoundaries | 1 | **AT-04** | ⚠️ MISMAPPED |
| TestAT_V2_017_06_VersionExpiryDiagnostics | 1 | **AT-07** | ⚠️ MISMAPPED |
| TestAT_V2_017_07_InvalidationScoping | 3 | **AT-08** | ⚠️ MISMAPPED |
| TestAT_V2_017_08_QuietChaptersSupported | 2 | **AT-06** | ⚠️ MISMAPPED |

**Problem**: Test class numbers don't match official AT numbers. Tests were numbered sequentially during development but don't align with official requirements.

---

## Corrected AT Coverage Analysis

### ✅ AT-V2-017-01: 从人工 SeriesVision 编译且不依赖 P10
**Test Class**: TestAT_V2_017_01_InitialChapterCompilation  
**Tests**: 3 (test_compile_urban_chapter_1_success, test_compile_fantasy_chapter_1_success, test_missing_protagonist_goal_fails)

**Verification**:
- ✓ Loads Story Fixtures directly (urban_business_series_vision, fantasy_cultivation_series_vision)
- ✓ No P10 Genesis dependency
- ✓ Compiles from SeriesVision data structure
- ✓ No automated planning system involved

**Status**: COVERED

---

### ✅ AT-V2-017-02: RequiredTransition 与 Delta 使用同一语义
**Test Class**: TestAT_V2_017_02_RequiredTransitionSemantics  
**Tests**: 1 (test_required_transition_uses_operation_type)

**Verification**:
- ✓ Imports `from anovel.domain.delta import OperationType`
- ✓ RequiredTransition.operation_type uses OperationType enum
- ✓ Validates operations are SET_FACT, END_FACT, or UNDO_FACT

**Status**: COVERED

---

### ✅ AT-V2-017-03: 计划冲突或不可满足合约返回诊断而非改写 Canon
**Test Class**: TestAT_V2_017_03_ConflictsReturnDiagnostic  
**Tests**: 1 (test_conflicting_constraints_returns_diagnostic)

**Verification**:
- ✓ Conflicting equity constraints detected
- ✓ Returns CompilationDiagnostic
- ✓ No Canon modification (no CanonCommitService import)

**Status**: COVERED

---

### ⚠️ AT-V2-017-04: 双书 fixture 经人工审定并包含知识及揭示边界
**Test Class**: TestAT_V2_017_05_KnowledgeBoundaries  
**Tests**: 1 (test_knowledge_boundaries_compiled)

**Verification**:
- ✓ Both fixtures have human_review_ref populated
- ✓ Secrets include knowers list
- ✓ Revelation timing enforced (not_before_chapter_N)
- ✗ **MISSING**: Test doesn't verify human_review_ref presence requirement
- ✗ **MISSING**: Test doesn't verify fixture approval binding

**Status**: PARTIALLY COVERED - needs fixture approval verification test

---

### ✅ AT-V2-017-05: 接续合约绑定前章正文 hash/实际结束证据及本章起点
**Test Class**: TestAT_V2_017_04_ContinuityBindsToPreviousChapter  
**Tests**: 2 (test_chapter_2_requires_previous_hash, test_chapter_2_missing_previous_hash_fails)

**Verification**:
- ✓ Chapter 2+ requires previous_chapter_hash
- ✓ ContinuityConstraint binds previous_chapter_hash and previous_end_state
- ✓ Chapter 1 has previous_chapter_hash: None
- ✓ Missing previous_chapter_hash returns diagnostic
- ✗ **MISSING**: Test for prior chapter revision invalidating continuation
- ✗ **MISSING**: Test for actual prose hash binding (not just any hash)

**Status**: PARTIALLY COVERED - needs invalidation test

---

### ✅ AT-V2-017-06: 场景可消费角色目标/知识与预期代价
**Test Class**: TestAT_V2_017_08_QuietChaptersSupported  
**Tests**: 2 (test_quiet_relationship_chapter_compiles, test_internal_conflict_chapter_compiles)

**Verification**:
- ✓ QUIET_RELATIONSHIP scene type compiles
- ✓ INTERNAL_CONFLICT scene type (dao comprehension growth) compiles
- ✓ No forced combat requirements
- ✗ **MISSING**: Test for character goal consumption
- ✗ **MISSING**: Test for expected cost tracking

**Status**: PARTIALLY COVERED - validates quiet chapters but missing goal/cost consumption tests

---

### ✅ AT-V2-017-07: 规划输入有版本与 supersession
**Test Class**: TestAT_V2_017_06_VersionExpiryDiagnostics  
**Tests**: 1 (test_superseded_version_returns_diagnostic)

**Verification**:
- ✓ PlanVersion with superseded_by field
- ✓ validate_plan_version() checks supersession
- ✓ FreezeHorizon separates frozen/adjustable chapters
- ✓ Expired version returns diagnostic
- ✗ **MISSING**: Test for frozen vs adjustable chapter modification rules

**Status**: PARTIALLY COVERED - needs freeze horizon enforcement test

---

### ✅ AT-V2-017-08: Canon/Pack/计划修订触发有范围的失效和重规划提议
**Test Class**: TestAT_V2_017_07_InvalidationScoping  
**Tests**: 3 (test_canon_advance_invalidates_dependent_contracts, test_chapter_revision_invalidates_subsequent_chapters, test_replan_proposal_created_for_invalidation)

**Verification**:
- ✓ Canon advance invalidates contracts bound to old parent
- ✓ Chapter revision invalidates subsequent chapters
- ✓ ReplanProposal generated (not auto-rewrite)
- ✓ InvalidationScope with affected_chapters
- ✗ **MISSING**: Test for Pack upgrade invalidation
- ✗ **MISSING**: Test for recompilation after approval

**Status**: PARTIALLY COVERED - missing Pack upgrade scenario

---

## Coverage Summary

| AT | Requirement | Tests | Coverage | Gaps |
|----|-------------|-------|----------|------|
| 01 | SeriesVision not P10 | 3 | ✅ FULL | None |
| 02 | Delta semantics | 1 | ✅ FULL | None |
| 03 | Diagnostic not rewrite | 1 | ✅ FULL | None |
| 04 | Fixture human review | 1 | ⚠️ PARTIAL | Missing review requirement test |
| 05 | Continuity binding | 2 | ⚠️ PARTIAL | Missing invalidation on revision |
| 06 | Goal/cost consumption | 2 | ⚠️ PARTIAL | Missing goal/cost tests |
| 07 | Version supersession | 1 | ⚠️ PARTIAL | Missing freeze enforcement |
| 08 | Scoped invalidation | 3 | ⚠️ PARTIAL | Missing Pack upgrade |

**Total Tests**: 14  
**Full Coverage**: 3/8 AT (37.5%)  
**Partial Coverage**: 5/8 AT (62.5%)  
**No Coverage**: 0/8 AT (0%)

---

## Critical Gaps Requiring Fixes

### Gap 1: Test File Path
**Issue**: test_v2_017_acceptance.py vs test_v2_017.py  
**Impact**: CI won't find tests at expected path  
**Fix**: Rename file to match test-catalog

### Gap 2: AT-04 Human Review Verification
**Issue**: No test verifies human_review_ref requirement  
**Impact**: Contracts could compile from unapproved fixtures  
**Fix**: Add test rejecting fixtures with human_review_ref: null

### Gap 3: AT-05 Prior Revision Invalidation
**Issue**: No test for contract invalidation when prior chapter revised  
**Impact**: Core continuity guarantee untested  
**Fix**: Add test showing revision triggers invalidation

### Gap 4: AT-06 Goal/Cost Consumption
**Issue**: Tests validate scene types but not goal consumption  
**Impact**: Character objective tracking untested  
**Fix**: Add test showing chapter goals consumed from SeriesVision

### Gap 5: AT-07 Freeze Enforcement
**Issue**: FreezeHorizon exists but modification rules untested  
**Impact**: Frozen chapter protection untested  
**Fix**: Add test showing frozen chapter modification rejected

### Gap 6: AT-08 Pack Upgrade Scenario
**Issue**: Only Canon/Chapter invalidation tested, not Pack  
**Impact**: GenrePack upgrade path untested  
**Fix**: Add test for Pack hash change invalidation

---

## Implementation Code Review Flags

### ✅ Strengths
- Pure function compiler (no side effects)
- NarrativeDelta reuse correct
- Data structures well-defined
- Conflict detection implemented
- Version tracking present

### ⚠️ Concerns

1. **Fixture Approval Not Enforced** (AT-04)
   - Code: `if series_vision.human_review_ref is None: pass  # Allow for dev/test`
   - Issue: Should reject unapproved fixtures in production mode
   - Location: `src/anovel/contracts/compiler.py:99`

2. **Conflict Detection Heuristic** (AT-03)
   - Code: Text-based pattern matching for equity conflicts
   - Issue: Simplistic, may miss complex conflicts
   - Location: `src/anovel/contracts/compiler.py:131-167`

3. **No Actual Prose Hash Binding** (AT-05)
   - Code: Accepts any string as previous_chapter_hash
   - Issue: Doesn't verify hash is actual Canon content hash
   - Location: `src/anovel/contracts/compiler.py:195-200`

4. **Goal Consumption Not Implemented** (AT-06)
   - Code: Creates transitions but doesn't track goal consumption
   - Issue: No verification that goals are actually consumed
   - Location: `src/anovel/contracts/compiler.py:169-188`

5. **Freeze Enforcement Missing** (AT-07)
   - Code: FreezeHorizon defined but not enforced in compiler
   - Issue: Can modify frozen chapters without error
   - Location: `src/anovel/planning/versions.py:74-88`

6. **Pack Invalidation Incomplete** (AT-08)
   - Code: generate_invalidation_scope has pack_upgrade case but returns empty
   - Issue: Pack upgrade detection not fully implemented
   - Location: `src/anovel/planning/replanning.py:79-82`

---

## Required Actions

### 1. Rename Test File ✅ CAN FIX
```bash
mv tests/contract/test_v2_017_acceptance.py tests/contract/test_v2_017.py
```

### 2. Add Missing Tests ⚠️ REQUIRES WORK
- AT-04: test_unapproved_fixture_rejected_in_production
- AT-05: test_prior_chapter_revision_invalidates_continuation
- AT-06: test_chapter_goals_consumed_from_series_vision
- AT-07: test_frozen_chapter_modification_rejected
- AT-08: test_pack_upgrade_invalidates_contracts

### 3. Fix Implementation Gaps ⚠️ REQUIRES WORK
- Enforce human_review_ref in production mode
- Implement actual prose hash verification
- Add goal consumption tracking
- Enforce freeze horizon in compiler
- Complete Pack invalidation logic

---

## Merge Readiness Assessment

**LOCAL TESTS**: 14/14 PASSING  
**AT COVERAGE**: 3/8 FULL, 5/8 PARTIAL  
**CRITICAL GAPS**: 6 identified  
**CI STATUS**: NOT YET RUN  
**MERGE STATUS**: ❌ **BLOCKED**

**Blockers**:
1. Test file path mismatch
2. Incomplete AT coverage (gaps in AT-04, 05, 06, 07, 08)
3. Implementation gaps in fixture approval, goal consumption, freeze enforcement
4. No CI verification yet

**Recommendation**: FIX CRITICAL GAPS before CI submission and merge consideration
