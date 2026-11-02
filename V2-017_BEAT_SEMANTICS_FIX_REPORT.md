# V2-017 Contract Compiler: Beat Semantics Fix & Verification Report

**Date**: 2026-11-02  
**Branch**: `implement/v2-017-contract-compiler`  
**Commit**: `46544d4` - Beat outcomes vs Chapter scheduled transitions fix

---

## Executive Summary

Successfully resolved the core creative semantics issue in V2-017 Contract Compiler: **Beat-level state changes were incorrectly treated as chapter-specific scheduled transitions**, causing false temporal constraints.

**Impact**: Contract Compiler now correctly distinguishes between:
- **Beat Outcome Constraints**: Goals that must be true by END of beat (not chapter-specific)
- **Required State Changes**: Transitions scheduled for a SPECIFIC chapter

This enables downstream Context Compiler and Writer to allocate beat outcomes to appropriate chapters based on actual narrative flow, rather than being forced to schedule everything in the last chapter.

---

## A. Completed Creative Capability Fixes

### 1. Beat → Chapter → Transition Semantic Distinction

**Problem Identified:**
```
Beat 1 (Chapters 1-3): "公司现状、资金压力、王总提出融资方案"
State changes:
  - 王总从陌生人变为潜在投资人
  - 公司账户余额从50万降至30万

OLD BEHAVIOR (INCORRECT):
  Chapter 1: required_state_changes = []
  Chapter 2: required_state_changes = []
  Chapter 3: required_state_changes = [both state changes]  ← ALL assigned to last chapter
  
This falsely implied both changes MUST happen in chapter 3.
```

**Solution Implemented:**
```
NEW BEHAVIOR (CORRECT):
  Chapter 1: beat_outcome_constraints = [both outcomes]
  Chapter 2: beat_outcome_constraints = [both outcomes]
  Chapter 3: beat_outcome_constraints = [both outcomes]
  
  All chapters: required_state_changes = []  (no chapter-level allocation in fixture)
  
This correctly indicates: "These outcomes must be true BY END of the beat,
but NOT necessarily scheduled for any specific chapter."
```

**Code Changes:**
1. Added `beat_outcome_constraints` field to `ChapterPlan` (planning/models.py)
2. Added `beat_outcome_constraints` field to `ChapterContract` (contracts/models.py)
3. Updated fixture loader to assign beat state_changes to beat_outcome_constraints for ALL chapters in beat
4. Updated compiler to pass beat_outcome_constraints to compiled contracts

---

## B. Beat → Chapter → RequiredTransition Final Semantics

### Data Model

```python
@dataclass(frozen=True)
class ChapterPlan:
    """Single chapter planning intent."""
    
    # Chapter-specific scheduled transitions (empty until fixture provides)
    required_state_changes: list[str]
    
    # Beat-level outcome goals (apply to all chapters in beat)
    beat_outcome_constraints: list[str]
```

### Fixture Loading Behavior

**Fixture Format** (unchanged):
```yaml
key_beats:
  - chapter: 1-3
    content: "公司现状、资金压力、王总提出融资方案"
    state_changes:
      - "王总从陌生人变为潜在投资人"
      - "公司账户余额从50万降至30万"
```

**Parsing Logic** (fixed):
```python
# OLD: Assigned to last chapter only
required_state_changes=state_changes if is_last_in_beat else []

# NEW: Assigned to all chapters as beat-level goals
beat_outcome_constraints=state_changes  # All chapters get the same constraints
required_state_changes=[]  # Empty (no chapter-level allocation)
```

### Contract Compilation

Contracts now include:
- `required_transitions`: Derived from `required_state_changes` (currently empty)
- `beat_outcome_constraints`: Informational context for downstream allocation

**Key Insight**: Beat outcomes are NOT converted to RequiredTransitions. They remain as textual constraints for Context Compiler to interpret and allocate based on narrative flow.

---

## C. Representative Chapter Contract Examples

### Urban Business Fixture

**Chapter 1** (Beat 1 start):
- Goals: "公司现状、资金压力、王总提出融资方案"
- Required transitions: 0
- Beat outcome constraints: 2
  - 王总从陌生人变为潜在投资人
  - 公司账户余额从50万降至30万
- Knowledge boundaries: 2
- Continuity: No (first chapter)

**Chapter 5** (Beat 2 mid):
- Goals: "团队内部分歧，李华强烈反对，张明左右为难"
- Required transitions: 0
- Beat outcome constraints: 2
  - 张明与李华信任度降低
  - 尝试寻找其他投资人，但进展缓慢
- Knowledge boundaries: 2
- Continuity: Yes (binds to chapter 4)

### Fantasy Cultivation Fixture

**Chapter 1** (Beat 1 start):
- Goals: "王林炼气九层，获得筑基丹，准备闭关突破"
- Required transitions: 0
- Beat outcome constraints: 2
  - 获得古修洞府资源
  - 道韵从15提升至20
- Knowledge boundaries: 3
- Continuity: No (first chapter)

**Chapter 10** (Beat 4 escalation):
- Goals: "寻求治疗方案，遇到天宝商会赵长老"
- Required transitions: 0
- Beat outcome constraints: 2
  - 了解契约条款和隐藏风险
  - 与其他散修接触，了解商会信誉
- Knowledge boundaries: 3
- Continuity: Yes (binds to chapter 9)

---

## D. Code Modification Summary

| File | Changes | Purpose |
|------|---------|---------|
| `src/anovel/planning/models.py` | +2 lines | Add `beat_outcome_constraints` to ChapterPlan |
| `src/anovel/contracts/models.py` | +2 lines | Add `beat_outcome_constraints` to ChapterContract |
| `src/anovel/contracts/fixture_loader.py` | -22, +19 lines | Fix beat parsing logic, update docstring |
| `src/anovel/contracts/compiler.py` | +1 line | Pass beat_outcome_constraints to contract |

**Total**: 4 files, 22 lines changed (net -3 deletions)

---

## E. Verification Evidence

### Test 1: Beat Semantics
```
✅ Beat 1 (chapters 1-3) outcomes appear in ALL 3 chapters
✅ required_state_changes correctly empty (no chapter allocation)
✅ beat_outcome_constraints correctly populated
```

### Test 2: Contract Compilation
```
✅ Urban Business fixture: All representative chapters compile
✅ Fantasy Cultivation fixture: All representative chapters compile
✅ Contracts preserve beat_outcome_constraints for downstream use
```

### Test 3: Continuity Constraints
```
✅ Chapter 1 has no continuity_constraints
✅ Chapter 2+ require previous_chapter_hash (enforced)
✅ Chapter 2+ bind to previous prose hash
✅ Canon parent binding consistent across chapters
```

---

## F. PR #15 / #16 Dependencies & Owner Authorization

### Current Status

- **PR #15**: ADR-008 and Story Fixture decisions (not merged)
- **PR #16**: V2-017 Contract Compiler implementation (Draft)
- **This work**: Committed to `implement/v2-017-contract-compiler` branch

### Owner Authorization Required

This implementation does NOT require additional Owner decisions. All changes work within existing:
- Approved Story Fixtures (urban_business_startup_v1, fantasy_eastern_cultivation_v1)
- Existing ADR-008 semantics
- Current V2-017 scope

### Next Steps

1. Owner reviews this semantic fix
2. If approved, PR #16 can be updated with this commit
3. PR #16 remains blocked on PR #15 merge

---

## G. V2-018 Context Compiler Interface

### Ready for Downstream Consumption

ChapterContract now provides:

```python
@dataclass(frozen=True)
class ChapterContract:
    # Chapter-specific transitions (when fixture provides)
    required_transitions: list[RequiredTransition]
    
    # Beat-level outcome goals (for allocation by Context Compiler)
    beat_outcome_constraints: list[str]
    
    # Continuity binding
    continuity_constraints: ContinuityConstraint | None
    
    # Knowledge boundaries
    knowledge_boundaries: list[KnowledgeBoundary]
    
    # World constraints
    protected_facts: list[ProtectedFact]
    prohibited_transitions: list[ProhibitedTransition]
```

**Context Compiler can now**:
- Read beat_outcome_constraints to understand beat-level goals
- Allocate outcomes to specific chapters based on narrative flow
- Generate RequiredTransitions for chapter-specific allocation
- Maintain continuity with previous chapter end state

---

## H. Technical Readiness for V2-018

✅ **Ready to proceed** with Context Compiler development

**Confirmed capabilities**:
1. ✅ Contract Compiler distinguishes beat outcomes from chapter transitions
2. ✅ Contracts compile successfully for both Urban and Fantasy fixtures
3. ✅ Chapter continuity constraints work correctly
4. ✅ Knowledge boundaries preserved
5. ✅ Genre Pack and Canon parent bindings consistent
6. ✅ Beat outcomes available for downstream allocation

**No blockers** for starting V2-018 Context Compiler implementation on the contract compilation side.

---

## Conclusion

V2-017 Contract Compiler now correctly handles the creative semantics of **beat-level narrative goals vs chapter-specific scheduled actions**. This fundamental fix enables:

- **Writers** to understand beat goals without false timing constraints
- **Context Compiler** to allocate beat outcomes intelligently across chapters
- **Quality gates** to validate beat outcomes are achieved, not micromanage when

The system preserves creative freedom while maintaining structural rigor.

---

**Report Status**: Complete  
**Verification**: All tests passing  
**Branch Status**: Clean, ready for review  
**Next Action**: Owner review of semantic fix, then PR #16 update
