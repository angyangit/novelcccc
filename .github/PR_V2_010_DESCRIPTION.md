# V2-010 CanonCommitService: Single-Transaction Narrative Commit Protocol

## Summary

Implements unified business service for Canon narrative commits with **single-transaction protocol** that eliminates TOCTOU races, proper idempotent recovery, and complete test coverage.

### Critical Fixes

1. **Single-Transaction Protocol**: Eliminates race condition between state validation and commit creation
2. **Idempotent Recovery First**: Checks idempotency BEFORE validation (doesn't re-validate successful old commits)
3. **Proper CanonState Reconstruction**: Includes cycle detection, chain limits, and correct UNDO_FACT handling
4. **Type-Safe Serialization**: Rejects unsupported types (fail-closed)
5. **Complete Test Coverage**: 11 tests including concurrent race condition verification

## Architecture

### Single Transaction Protocol (13 Steps)

```
1. Validate permit (external, no database access)
2. Compute payload hash (deterministic, no database access)
3. BEGIN TRANSACTION
4-5. Check idempotency, return if recovered (BEFORE validation)
6. Lock execution_control, validate version
7. Get and verify expected branch HEAD
8. Reconstruct CanonState from HEAD in this transaction view
9. Validate NarrativeDelta with DeltaReducer (preconditions, types)
10. INSERT canon_commit
11. INSERT canon_event
12. UPDATE branch_head (CAS)
13. COMMIT and return receipt
```

**Key Property**: Steps 6-12 execute atomically within a single PostgreSQL transaction, preventing TOCTOU races.

### Idempotent Recovery

- **Check FIRST** (step 4-5): Before state reconstruction and validation
- **Same key + same payload** → Return original receipt (recovered=true)
- **Same key + different payload** → Reject with IdempotencyConflictError
- **Benefit**: Old successful commits don't fail when state has changed

### State Reconstruction

- Traverse commit chain from HEAD to root
- Cycle detection (fail if commit appears twice)
- Chain length limit (max 10000 commits)
- Apply operations in order with proper UNDO_FACT restoration
- Fail-closed on errors

## Test Coverage

### Complete AT-V2-010 Test Suite (11 tests)

- **AT-V2-010-01**: No permit rejection ✓
- **AT-V2-010-02**: Valid permit and delta succeeds ✓
- **AT-V2-010-03**: Atomic commit+event+HEAD ✓
- **AT-V2-010-04**: CAS conflict triggers full rollback ✓
- **AT-V2-010-05**: Idempotent recovery after state change ✓
- **AT-V2-010-06**: Same key different payload rejection ✓
- **AT-V2-010-07**: Character creation persists and rebuilds ✓
- **AT-V2-010-08**: Character state change with precondition ✓
- **AT-V2-010-09**: Service restart recovery ✓
- **AT-V2-010-10**: Invalid precondition rejection ✓
- **AT-V2-010-11**: Concurrent writes race (only one succeeds) ✓

### Concurrent Race Test (AT-V2-010-11)

**Scenario**: Two threads both read `age=25`, both try to update with `ExpectValue(25)`

**One tries**: `age=25 → age=26`  
**Other tries**: `age=25 → age=27`

**Result**:
- Exactly ONE succeeds (database serialization isolation)
- Other gets precondition or HEAD CAS failure
- Final database state: 3 commits total (root + setup + ONE winner)
- No contradictory facts

**Verification**:
- Commit count: exactly 3
- Event count: exactly 2 (setup + winner)
- HEAD points to winner's commit
- Age is either 26 or 27 (not both)

## Serialization & Schema

### Type-Safe Serialization

```python
def _serialize_value(self, value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)):
        return value
    # ... handle FactValue.UNKNOWN, list, dict ...
    raise InvalidDeltaError(f"Unsupported value type: {type(value)}")
```

**Rejects**: Objects, functions, arbitrary types (fail-closed)

### CommitReceipt JSON Schema

Created `specs/schemas/commit-receipt.schema.json` with:
- Pattern validation for `commit_id` and `payload_hash`
- ISO 8601 datetime format
- Required fields enforcement
- No additional properties allowed

## Regression Testing

- **V2-009 tests**: 6/6 pass ✓
- **V2-010 tests**: 11/11 pass ✓
- **STATIC gate**: format, lint, type checks all pass ✓

## Contract Compliance

- **ADR-005**: Canonical hash with NFC normalization
- **ADR-006**: Idempotent commit with execution version fencing
- **03_DOMAIN_CANON_AND_ARTIFACT_CONTRACTS**: Domain model integration

## Production Readiness Notes

### PermitVerifier

Current implementation uses `TestPermitVerifier` for integration testing with explicit allow-list.

**Production blocker**: Real permit issuance, signing, and revocation system not yet implemented.

**Required for production**:
- Trusted permit authority
- Cryptographic signature verification
- Expiration and revocation checks
- Audit logging

### Known Limitations

1. **No snapshot optimization**: Full chain traversal on every commit
2. **UNDO_FACT historical reconstruction**: Limited validation (restores from CommitChange)
3. **Chain length limit**: 10000 commits per branch
4. **No partial deserialization**: Entire changeset loaded into memory

## Files Changed

- `src/anovel/canon/commit_service.py`: Complete rewrite with single-transaction protocol
- `tests/integration/test_v2_010.py`: Added 6 new tests (AT-V2-010-02 through 06, 11)
- `specs/schemas/commit-receipt.schema.json`: New JSON Schema

## Database Tables Used

- `canon_commit`: Commit records with idempotency keys
- `canon_event`: Event log
- `branch_head`: Branch HEAD pointers
- `execution_control`: Version fencing with row-level locks

## Migration Path

No schema migrations required. Uses existing V2-009 tables.

## Answer to Critical Question

**Q: If 林舟 is currently 25 years old, and two writing agents simultaneously try to change the age to 26 and 27 (both claiming old age was 25), can ANovelOS ensure at most ONE change enters Canon? Can the successful one be recovered with its idempotency key after interruption?**

**A: YES.**

**Proof**: Test `test_at_v2_010_11_concurrent_writes_race` demonstrates:
1. Setup: character with `age=25`
2. Two threads concurrently submit: `age=26` with `ExpectValue(25)` and `age=27` with `ExpectValue(25)`
3. Result: Exactly 1 success, exactly 1 failure
4. Final state: 3 commits total (root + setup + ONE winner), not 4
5. HEAD points to exactly one winner

**Idempotent recovery**: Test `test_at_v2_010_05_idempotent_recovery_after_state_change` proves:
1. Commit succeeds with `ExpectValue(25)`
2. State changes (new commits make age=26)
3. Retry with same key+payload recovers original receipt WITHOUT re-validating
4. Returns `recovered=True` with original `commit_id` and `committed_at`

**Mechanism**: PostgreSQL transaction isolation + execution_control row lock + idempotency check before validation.

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
