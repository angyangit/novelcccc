# Stage 10 Full Workflow Acceptance - Analysis Report

**Date**: 2026-11-01  
**Test Status**: ✓✓ ALL VALIDATORS PASSED (Q0-Q3)  
**Critical Issues**: Sequential delta preconditions, semantic validation  

---

## Test Results Summary

**Execution**: Full workflow with Task 2 prose (1,484 chars)  
**Cost**: $0.12 (within $0.40 budget)  
**Status**: ✓ All Q0-Q3 passed  

### Operations Extracted (6 total)

```
1. protagonist.location = 科学类书籍区
   Evidence: chapter:236-260
   Precondition: ExpectAbsent ❌ (should be ExpectAbsent for first)

2. protagonist.activity = 取书  
   Evidence: chapter:562-602
   Precondition: ExpectAbsent ❌ (should be ExpectAbsent for first)

3. protagonist.location = 图书馆二楼阅览区靠窗位置
   Evidence: chapter:654-690
   Precondition: ExpectAbsent ❌ (should be ExpectValue("科学类书籍区"))

4. protagonist.activity = reading
   Evidence: chapter:726-744
   Precondition: ExpectAbsent ❌ (should be ExpectValue("取书"))

5. protagonist.activity = 休息/思考
   Evidence: chapter:1275-1309  
   Precondition: ExpectAbsent ❌ (should be ExpectValue("reading"))

6. protagonist.activity = reading
   Evidence: chapter:1437-1460
   Precondition: ExpectAbsent ❌ (should be ExpectValue("休息/思考"))
```

### Quality Validation Results

| Validator | Status | Checks | Issues |
|-----------|--------|--------|--------|
| Q0 (Deterministic) | ✓ PASS | 6/6 pass | Evidence verified, no hallucination |
| Q1 (Canon Consistency) | ✓ PASS | 3/3 pass | **BUT: didn't catch wrong preconditions!** |
| Q2 (Genre Rules) | ✓ PASS | 1/1 pass | Basic genre pack verified |
| Q3 (Required Transitions) | ✓ PASS | 2/2 pass | **BUT: only checks fact_path existence!** |
| **Overall** | ✓ PASS | 16/16 pass | 1 warning (op count ≠ transition count) |

---

## Critical Issue #1: Sequential Delta Preconditions

### Problem

All 6 operations use `ExpectAbsent()` precondition, which means:
- Each operation assumes the fact doesn't exist yet
- Sequential operations would fail in Q1 if properly validated
- Cannot apply delta sequentially to Canon

### Current Q1 Behavior

Looking at Q1 validator (src/anovel/quality/q1.py):

```python
# Q1-02: State preconditions check
def _check_state_preconditions(self, delta, canon_state, contract):
    # Checks if preconditions match Canon state
    # For ExpectAbsent: checks fact doesn't exist in Canon
    # For ExpectValue: checks fact has expected value in Canon
```

**Why It Passed**: Genesis state has NO facts, so first ExpectAbsent is correct. But Q1 doesn't validate the **sequence** of operations within the delta - it only validates against the **initial** Canon state.

### What's Missing

A proper **DeltaReducer** that:
1. Takes initial Canon state
2. Applies operations sequentially
3. Validates each operation's precondition against accumulated state
4. Returns final state or error

### Owner Requirement

> "必须解决同一实体、同一FactPath的连续变化问题"  
> "从可信CanonState计算每一步Precondition"  
> "后续赋值使用正确的前值"

### Implementation Needed

```python
# In structured_extractor.py or separate delta_sequencer.py

def sequence_operations_with_preconditions(
    operations: list[SetFactOperation],
    initial_state: CanonState
) -> list[SetFactOperation]:
    """
    Re-order operations by evidence position and set correct preconditions.
    
    1. Sort operations by evidence.source_ref position (chapter:START-END)
    2. Group by (subject, fact_path)
    3. For each group:
       - First operation: ExpectAbsent() if not in initial_state
                          ExpectValue(existing) if in initial_state
       - Subsequent operations: ExpectValue(previous_value)
    4. Return sequenced operations with correct preconditions
    """
    ...
```

---

## Critical Issue #2: Semantic Transition Validation

### Problem

Contract requires:
- `protagonist.location → "library"`
- `protagonist.activity → "reading"`

Operations provide:
- location: "科学类书籍区", "图书馆二楼阅览区靠窗位置"
- activity: "取书", "reading", "休息/思考", "reading"

**Q3 passed** because it only checks `fact_path` existence, not semantic value matching!

### Current Q3 Behavior

```python
# Q3-01: Required transitions (lines 98-140)
def _check_required_transitions(self, delta, contract):
    delta_fact_paths = {op.path.path for op in delta.operations}
    
    missing = []
    for transition in contract.required_transitions:
        if transition.fact_path not in delta_fact_paths:
            missing.append(transition.fact_path)
    
    # Only checks fact_path existence, NOT value!
```

### Owner Requirement

> "单纯发现相应FactPath，不等于目标已满足"  
> "具体图书馆地点是否属于Contract要求的library"  
> "章节最终Activity是否符合reading"  
> "不允许用字符串模糊相似度直接替代事实判断"

### Semantic Matching Questions

**Location: "library" vs "科学类书籍区/图书馆二楼阅览区靠窗位置"**

Options:
1. **Exact match**: "library" must appear in value → FAIL (too strict)
2. **Substring match**: "图书馆" contains library concept → PASS (reasonable)
3. **LLM semantic judgment**: Ask LLM if value satisfies target → costs money
4. **Ontology/taxonomy**: Define "library" includes {图书馆, 书店, 阅览室} → requires domain model

**Activity: "reading" vs "取书/reading/休息/思考/reading"**

Options:
1. **Any match**: At least one operation has target value → currently PASS
2. **Final state match**: Last activity operation must match → need "reading" at end
3. **Event vs state**: Contract may want "started reading" event, not final state
4. **LLM semantic judgment**: Ask if sequence represents "reading" → costs money

### Recommendation

**For MVP (current phase)**:
- Keep current fact_path-only check
- Add WARNING when no exact value match found
- Document as "partial semantic validation"

**For production**:
- Implement semantic matcher with configurable rules
- Support both exact and fuzzy matching per fact type
- Add LLM fallback for ambiguous cases with budget protection

---

## Critical Issue #3: Q1 Doesn't Validate Sequential Application

### Problem

Q1 "state_preconditions" check only validates preconditions against **initial** Canon state, not sequential application within the delta.

### Current Q1-02 Implementation

```python
# src/anovel/quality/q1.py lines ~120-160
def _check_state_preconditions(self, delta, canon_state, contract):
    for op in delta.operations:
        if isinstance(op.precondition, ExpectAbsent):
            # Check fact doesn't exist in INITIAL canon_state
            if fact_exists_in_canon(op.path, canon_state):
                return FAIL
        elif isinstance(op.precondition, ExpectValue):
            # Check fact has expected value in INITIAL canon_state  
            if get_canon_value(op.path, canon_state) != op.precondition.expected_value:
                return FAIL
```

**Why It Passed**: All preconditions are ExpectAbsent, genesis Canon has no facts, so all pass.

**Why It's Wrong**: Operations 3-6 should have ExpectValue preconditions, and Q1 should validate the sequence.

### What's Missing

Q1 should either:
1. **Option A**: Refuse deltas with same-path operations unless properly sequenced
2. **Option B**: Apply delta sequentially and validate each step
3. **Option C**: Delegate to DeltaReducer and only validate final state

### Owner Decision Needed

Which option should Q1 implement?

---

## Issue #4: JSON Evidence Escaping (FIXED)

**Was**: Line 290 suggested "使用单引号包裹字符串" (invalid JSON)  
**Now**: Line 290 says "JSON字符串中的双引号必须使用反斜杠转义：\\\\" (correct)  

✓ **RESOLVED** in this commit

---

## Issue #5: Budget Persistence

### Problem

Budget resets across test runs - cumulative tracking not persistent.

### Current Behavior

```
Test 1: BudgetProtectedGateway created → spent $0.12
Test 2: New BudgetProtectedGateway → spent resets to $0.00
```

### Owner Requirement

> "先核对真实费用及待核费用，确认预算状态在进程重启后仍能保留"

### Options

1. **Persistent ledger file**: Write to `.budget_ledger.json` after each call
2. **Report-based tracking**: Manual cumulative tracking in reports (current)
3. **External budget service**: API-based budget management

**Current workaround**: Manual tracking in test scripts ($1.54 + $0.12 = $1.66)

---

## Acceptance Criteria Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| Original prose valid | ✓ PASS | 1,484 chars |
| RequiredTransition satisfied | ⚠ PARTIAL | fact_path present, semantic unclear |
| Operations from real prose | ✓ PASS | Q0 evidence verified |
| Entity and Precondition correct | ✗ FAIL | All ExpectAbsent, need sequencing |
| Evidence accurate | ✓ PASS | Q0 verified locations |
| Q0-Q3 applicable checks pass | ✓ PASS | All 16 checks passed |
| Delta can be applied by DeltaReducer | ❓ UNKNOWN | Not tested |
| Isolated Canon final state correct | ❓ UNKNOWN | Not tested |
| Next chapter can read state | ❓ UNKNOWN | Not tested |
| No unauthorized production Canon | ✓ PASS | Mock mode enforced |

**Overall**: 5/10 PASS, 1/10 PARTIAL, 2/10 FAIL, 2/10 UNKNOWN

---

## Recommendations

### Immediate (Block three-chapter test)

1. **Implement sequential preconditions** in StructuredExtractor
   - Sort operations by evidence position
   - Calculate correct preconditions for same-path operations
   - Test DeltaReducer can apply sequentially

2. **Clarify semantic validation scope**
   - Owner decision: exact match, fuzzy match, or LLM judgment?
   - Document what Q3 actually validates (fact_path only)
   - Add semantic matcher if required

3. **Test DeltaReducer application**
   - Apply 6 operations to genesis Canon
   - Verify final state: location="图书馆二楼阅览区靠窗位置", activity="reading"
   - Confirm no errors

### Later (Before production)

4. **Enhance Q1 sequential validation**
   - Validate preconditions against accumulated state
   - Or defer to DeltaReducer and validate result

5. **Implement budget persistence**
   - Persistent ledger file
   - Cross-run cumulative tracking

6. **Complete Q2/Q3 unimplemented checks**
   - Q2: World rules, capability validation
   - Q3: Protected facts, knowledge boundaries

---

## Budget Summary

| Phase | Cost | Cumulative |
|-------|------|------------|
| Previous (reported) | $1.54 | $1.54 |
| Workflow acceptance | $0.12 | $1.66 |
| **Total** | | **$1.66 / $5.00** |
| **Remaining** | | **$3.34 (67%)** |

**Status**: ✓ Within limits

---

## Owner Decision Required

**Question 1**: Sequential preconditions
- Implement in StructuredExtractor? OR
- Implement in separate DeltaSequencer? OR
- Accept current ExpectAbsent-only for MVP?

**Question 2**: Semantic validation
- Require exact "library"/"reading" match? OR
- Allow fuzzy match ("图书馆" satisfies "library")? OR  
- Use LLM for semantic judgment (costs money)? OR
- Document as limitation and proceed?

**Question 3**: Three-chapter test timing
- Proceed now (with limitations documented)? OR
- Fix sequential preconditions first? OR
- Fix both preconditions + semantic validation?

---

**Analysis complete**: 2026-11-01  
**Test result**: All validators passed, but critical precondition/semantic issues identified  
**Recommendation**: Fix sequential preconditions before three-chapter test
