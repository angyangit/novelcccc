# V2-017 REMEDIATION HANDOFF

**Session End**: 2026-10-30  
**Branch**: implement/v2-017-contract-compiler  
**Status**: REMEDIATION IN PROGRESS - WIP CHECKPOINT  
**Next Action**: Continue P0 remediation in new session

---

## Current Git State

**Repository**: angyangit/novelcccc  
**Branch**: implement/v2-017-contract-compiler  
**Latest Commit**: 5254b9c (docs: Add comprehensive implementation summary)  
**Remote Status**: Branch pushed to origin

**Uncommitted Changes**:
- `src/anovel/contracts/fixture_loader.py` (NEW, 226 lines) - WIP, not yet tested
- `plan/validation/execution/V2-017/implement/AT-MAPPING-VERIFICATION.md` (NEW)
- `plan/validation/execution/V2-017/implement/PRE-MERGE-VERIFICATION.md` (NEW)

---

## Owner Authorization

**Decision**: Option 1 - Continue in new session with all P0 priorities  
**Scope**: Complete P0-A through P0-E remediation  
**Authority**: V2-017 REMEDIATION authorization continues  
**No scope reduction**: All AT-V2-017-01~08 must be met

---

## Work Completed

### Initial Implementation (Commit 5254b9c)
✅ **5 Production Modules** (644 lines):
- `src/anovel/planning/models.py`
- `src/anovel/planning/versions.py`
- `src/anovel/planning/replanning.py`
- `src/anovel/contracts/models.py`
- `src/anovel/contracts/compiler.py`

✅ **1 Test Module** (583 lines):
- `tests/contract/test_v2_017_acceptance.py` (14 tests, all passing locally)

✅ **Documentation**:
- Entry gate verification
- Test results
- Implementation summary
- AT mapping analysis
- Pre-merge verification

### Remediation Started (Uncommitted)
⏳ **P0-A Fixture Loader** (PARTIAL):
- File: `src/anovel/contracts/fixture_loader.py` (226 lines)
- Functions: `load_series_vision_from_fixture()`, `validate_fixture_approval()`, parsing helpers
- Status: Code written, NOT TESTED, NOT COMMITTED
- Missing: Full YAML parsing, approval SHA-256 verification, integration tests

---

## Known Defects (Per Pre-Merge Verification)

### Critical Blockers
1. **Test file path**: test_v2_017_acceptance.py should be test_v2_017.py (per test-catalog.yaml)
2. **Incomplete AT coverage**: 5/8 AT have partial coverage with identified gaps
3. **Implementation gaps**: 6 areas require fixes (see below)
4. **No CI verification**: Not yet run

### Implementation Gaps

**Gap 1: Fixture Approval Not Enforced** (P0-A)
- Location: `src/anovel/contracts/compiler.py:99`
- Issue: Allows `human_review_ref: null` without checking production mode
- Fix: Enforce approval requirement, verify SHA-256 binding

**Gap 2: Placeholder fact_path** (P0-B)
- Location: `src/anovel/contracts/compiler.py:169-188`
- Issue: All state changes mapped to `state.chapter_x.change_i`
- Fix: Use proper typed state operations with stable fact paths

**Gap 3: No Actual Prose Hash Verification** (P0-C)
- Location: `src/anovel/contracts/compiler.py:195-200`
- Issue: Accepts any string as previous_chapter_hash
- Fix: Verify hash is actual Canon content hash, bind end state evidence

**Gap 4: Freeze Horizon Not Enforced** (P0-D)
- Location: `src/anovel/planning/versions.py:74-88`
- Issue: `can_modify_chapter()` exists but compiler doesn't call it
- Fix: Enforce freeze rules in compilation, reject invalid modifications

**Gap 5: Pack Invalidation Incomplete** (P0-E)
- Location: `src/anovel/planning/replanning.py:79-82`
- Issue: `pack_upgrade` case returns empty affected_chapters
- Fix: Implement full Pack invalidation logic

**Gap 6: Missing Invalidation on Revision** (P0-C + P0-E)
- Location: No code currently handles this
- Issue: Prior chapter revision doesn't invalidate dependent contracts
- Fix: Detect revision, trigger invalidation cascade

---

## P0 Remediation Checklist

### P0-A: 真实Fixture输入 ⏳ STARTED
- [x] Create fixture_loader.py skeleton
- [ ] Complete YAML parsing for all fixture sections
- [ ] Implement approval SHA-256 verification
- [ ] Load approved urban_business_startup_v1.yaml
- [ ] Load approved fantasy_eastern_cultivation_v1.yaml
- [ ] Verify human_review_ref binding to approval record
- [ ] Distinguish DRAFT vs APPROVED trust strategies
- [ ] Add tests for fixture loading and validation

### P0-B: 真实RequiredTransition语义 ❌ NOT STARTED
- [ ] Define typed fact paths (equity, resources, relationships, cultivation)
- [ ] Map fixture state changes to proper OperationType + fact_path
- [ ] Use NarrativeDelta semantics correctly
- [ ] Return diagnostic for uncertain mappings
- [ ] Add tests for equity changes (Urban fixture)
- [ ] Add tests for resource tracking (Fantasy fixture)
- [ ] Add tests for cultivation progression (Fantasy fixture)
- [ ] Verify preconditions are real, not empty

### P0-C: 前章接续证据绑定 ❌ NOT STARTED
- [ ] Enhance ContinuityConstraint with evidence binding
- [ ] Verify previous_chapter_hash is actual content hash
- [ ] Bind previous chapter end state evidence
- [ ] Bind current chapter start requirements
- [ ] Ensure chapter 1 explicitly has no prior
- [ ] Implement prior revision invalidation
- [ ] Add tests for continuity binding
- [ ] Add tests for invalidation on revision

### P0-D: 计划版本与冻结规则 ❌ NOT STARTED
- [ ] Call `can_modify_chapter()` in compiler
- [ ] Reject modifications to frozen chapters
- [ ] Allow reading frozen chapters for compilation
- [ ] Verify FrozenInputs match actual compile inputs
- [ ] Reject superseded PlanVersion
- [ ] Add tests for freeze enforcement
- [ ] Add tests for version expiry

### P0-E: ADR-008失效语义 ❌ NOT STARTED
- [ ] Complete Canon parent change invalidation (already partial)
- [ ] Complete Pack upgrade invalidation (currently empty)
- [ ] Add Plan supersession invalidation
- [ ] Add Fixture content change invalidation
- [ ] Add prior chapter revision invalidation
- [ ] Verify 5 Invalidation Scope Rules all implemented
- [ ] Generate ReplanProposal correctly
- [ ] Add tests for all 5 invalidation scenarios

### Testing & CI ❌ NOT STARTED
- [ ] Rename test file to test_v2_017.py
- [ ] Add 5+ missing tests for gaps
- [ ] Run local tests with real fixtures
- [ ] Run all applicable contract tests
- [ ] Run architecture dependency tests
- [ ] Run governance validators
- [ ] Run Ruff format & lint
- [ ] Run mypy type checking
- [ ] Create V2-017 IMPLEMENT PR
- [ ] Trigger GitHub Actions CI
- [ ] Verify CI PASS

---

## File Locations

**Production Code**:
- `src/anovel/planning/models.py`
- `src/anovel/planning/versions.py`
- `src/anovel/planning/replanning.py`
- `src/anovel/contracts/models.py`
- `src/anovel/contracts/compiler.py`
- `src/anovel/contracts/fixture_loader.py` (WIP, uncommitted)
- `src/anovel/contracts/__init__.py`
- `src/anovel/planning/__init__.py`

**Tests**:
- `tests/contract/test_v2_017_acceptance.py` (needs rename to test_v2_017.py)

**Fixtures** (approved):
- `specs/fixtures/urban_business_startup_v1.yaml` (approved SHA: f08ff29b...)
- `specs/fixtures/fantasy_eastern_cultivation_v1.yaml` (approved SHA: 7a793cec...)
- `specs/fixtures/reviews/owner_approval_2026_10_30.yaml`

**Documentation**:
- `plan/validation/execution/V2-017/implement/execution-packet.yaml`
- `plan/validation/execution/V2-017/implement/AT-MAPPING-VERIFICATION.md`
- `plan/validation/execution/V2-017/implement/PRE-MERGE-VERIFICATION.md`
- `plan/validation/execution/V2-017/implement/REMEDIATION_HANDOFF.md` (this file)

**Authority**:
- `plan/machine/test-catalog.yaml` (AT-V2-017-01~08 specifications)
- `plan/machine/implementation-backlog.yaml` (V2-017 task contract)
- `plan/machine/decision-register.yaml` (ADR-008 ACCEPTED)

---

## Next Session Direct Actions

### Step 1: Resume Context (5 min)
1. Read `AGENTS.md` and execution protocol
2. Read V2-017 IMPLEMENT execution packet
3. Read this REMEDIATION_HANDOFF.md
4. Check actual git status and uncommitted files
5. Verify test-catalog.yaml AT-V2-017 specifications

### Step 2: Complete P0-A Fixture Loader (30-60 min)
1. Test current fixture_loader.py imports
2. Complete YAML parsing for all sections (protagonist_goal, secrets, etc.)
3. Add approval SHA-256 verification logic
4. Test loading both approved fixtures
5. Add unit tests for loader
6. Commit working fixture loader

### Step 3: Fix P0-B RequiredTransition (60-90 min)
1. Define typed fact paths in new module or extend compiler
2. Map Urban equity changes to proper paths
3. Map Fantasy resource/cultivation changes to proper paths
4. Replace `state.chapter_x.change_i` placeholder
5. Add real preconditions
6. Test with actual fixtures
7. Commit fixes

### Step 4: Implement P0-C Continuity (60 min)
1. Enhance ContinuityConstraint model
2. Add evidence binding fields
3. Implement prior revision invalidation detection
4. Add tests for invalidation cascade
5. Commit fixes

### Step 5: Enforce P0-D Freeze/Version (45 min)
1. Call `can_modify_chapter()` in compiler
2. Add freeze violation detection
3. Add version expiry enforcement
4. Add tests
5. Commit fixes

### Step 6: Complete P0-E Invalidation (60 min)
1. Fix Pack upgrade invalidation (replanning.py:79-82)
2. Add Plan supersession invalidation
3. Add Fixture change invalidation
4. Verify all 5 ADR-008 rules
5. Add tests for all scenarios
6. Commit fixes

### Step 7: Testing & CI (60-90 min)
1. Rename test file to test_v2_017.py
2. Add 5+ missing tests for AT gaps
3. Run full local test suite
4. Run Ruff, mypy, governance validators
5. Commit test fixes
6. Push to remote
7. Create V2-017 IMPLEMENT PR (stacked on PR #15)
8. Trigger GitHub Actions CI
9. Document CI results

### Step 8: Final Verification (30 min)
1. Verify AT-01~08 coverage complete
2. Verify all P0 fixes implemented
3. Document remaining risks (if any)
4. Update merge readiness assessment
5. Submit for Owner review

**Estimated Total**: 6-9 hours of focused work

---

## Commands for Next Session

### Check Status
```bash
cd /Users/angyang/Documents/AI/ANovelOS_CC/ANovelOS
git status
git log --oneline -5
git branch -vv
```

### Test Fixture Loader (once complete)
```bash
PYTHONPATH=src:$PYTHONPATH uv run python3 -c "
from pathlib import Path
from anovel.contracts.fixture_loader import load_series_vision_from_fixture

urban = load_series_vision_from_fixture(
    Path('specs/fixtures/urban_business_startup_v1.yaml'),
    require_approval=True
)
print(f'Loaded: {urban.title}')
print(f'Review ref: {urban.human_review_ref}')
"
```

### Run Tests
```bash
PYTHONPATH=src:$PYTHONPATH uv run pytest tests/contract/test_v2_017.py -v
```

### Run Full Validation
```bash
uv run ruff format src/ tests/
uv run ruff check src/ tests/
PYTHONPATH=src:$PYTHONPATH uv run pytest tests/contract/ tests/architecture/ -v
```

---

## Authorization Scope

**Authorized**:
- Complete all P0-A through P0-E remediation
- Add missing tests for AT-01~08 gaps
- Run CI verification
- Create V2-017 IMPLEMENT PR
- Commit fixes to implement/v2-017-contract-compiler branch

**Not Authorized**:
- Merge any PR without Owner approval
- Start V2-018 implementation
- Make paid Provider API calls
- Modify task status to CLOSED
- Alter historical validation evidence
- Reduce AT acceptance requirements

**Stop Conditions**:
- Task scope expansion beyond V2-017 contract
- Need for new ADR or architectural authority change
- Paid API calls required
- All remediation complete and verified

---

## Current Session Actions

Before ending this session, I will:
1. ✅ Created REMEDIATION_HANDOFF.md (this file)
2. ⏳ Commit uncommitted WIP files with clear WIP marker
3. ⏳ Update task status to reflect in-progress remediation
4. ⏳ Push to remote for safety

---

**Handoff Status**: READY FOR NEW SESSION  
**Next Session Goal**: Complete all P0 remediation and achieve MERGE READY
