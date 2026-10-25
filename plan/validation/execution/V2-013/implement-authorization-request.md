# V2-013 IMPLEMENT Authorization Request

**Task**: V2-013 GenreProfile and GenrePack loader  
**Phase**: P3 Genre Kernel  
**Requested Action**: IMPLEMENT  
**Prepared**: 2026-10-25  
**Request Status**: PENDING OWNER APPROVAL

---

## Executive Summary

V2-013 PREPARE phase is complete. All prerequisites verified, execution packet bound, test scenarios mapped. Requesting Owner authorization to proceed to IMPLEMENT phase.

**Prerequisites**: ✅ ALL MET
- G-P2 gate: VERIFIED
- ADR-007: ACCEPTED
- Execution packet: BOUND (validation/execution/V2-013/execution-packet.yaml)
- Test scenarios: MAPPED (4 scenarios documented)
- Plan validation: PASS (0 fatal errors)

**Estimated Effort**: 6-8 hours  
**Risk Level**: MEDIUM  
**Budget**: No paid API calls required

---

## IMPLEMENT Scope

### In Scope

**Core Implementation**:
1. **GenrePackIdentity** (`src/anovel/genre/identity.py`)
   - Immutable dataclass: (pack_id, version, content_hash)
   - Validation: pack_id format, version format, content_hash 64 hex chars
   - Prevent version suffix in pack_id

2. **GenrePackMetadata** (`src/anovel/genre/identity.py`)
   - Pack metadata structure
   - Extension namespaces list
   - World anchors list
   - Pack file path reference

3. **ProjectGenreBinding** (`src/anovel/genre/identity.py`)
   - Immutable binding: ProjectId → GenrePackIdentity
   - Binding timestamp
   - Traceability metadata

4. **GenrePackRegistry** (`src/anovel/genre/registry.py`)
   - Load registry from specs/genres/registry.yaml
   - get_pack(pack_id, version) → GenrePackMetadata
   - Three-way hash verification (registry, file, caller)
   - Unknown Pack/version rejection
   - Extension namespace validation

5. **ProjectGenreBindingService** (`src/anovel/genre/binding.py`)
   - bind_pack(project_id, pack_identity) → ProjectGenreBinding
   - get_binding(project_id) → ProjectGenreBinding | None
   - Binding immutability enforcement
   - Traceability queries

**Pack Definitions** (Two Frozen Anchors):
6. **specs/genres/urban_business_realistic_v1.yaml**
   - Pack ID: urban.business.realistic
   - Version: 1.0.0
   - Extension schemas stub
   - Transition rules stub
   - World mechanics stub
   - Quality rubric stub

7. **specs/genres/fantasy_eastern_progression_v1.yaml**
   - Pack ID: fantasy.eastern.progression
   - Version: 1.0.0
   - Extension schemas stub
   - Transition rules stub
   - World mechanics stub
   - Quality rubric stub

8. **specs/genres/registry.yaml**
   - Registry metadata for two Packs
   - Pack identities with content_hash
   - Pack file paths

**Contract Tests**:
9. **tests/contract/test_v2_013.py**
   - AT-V2-013-01: Identity verification (4 test cases)
   - AT-V2-013-02: Unknown Pack rejection (4 test cases)
   - AT-V2-013-03: Binding traceability (3 test cases)
   - AT-V2-013-04: Pack preservation (2 test cases)
   - Total: ~13 test cases

### Explicitly Out of Scope

**NOT Implemented in V2-013**:
- Genre policy engine (V2-014)
- State transition execution (V2-014)
- Semantic validation of extension fields (V2-014)
- Complete extension schemas for urban/fantasy (V2-015/V2-016)
- Transition rule enforcement (V2-014)
- World mechanics enforcement (V2-014)
- Quality rubric evaluation (future)
- 30 additional genre packs (future)
- Narrative strategy filtering (future)
- Pack version upgrades/migrations (future)

---

## Prerequisites Verification

### Entry Gate: G-P2 ✅ VERIFIED

**Source**: plan/machine/phase-gates.yaml  
**Status**: P2.status == VERIFIED  
**Evidence**: validation/closure/G-P2-65e2fc0/phase-decision.yaml  
**Exit Criteria**: Short transaction atomicity, unique root commit, snapshot rebuild ✅

### Required Decision: ADR-007 ✅ ACCEPTED

**Source**: plan/machine/decision-register.yaml  
**Status**: ADR-007.status == ACCEPTED  
**Decision Record**: validation/decisions/adr-007-acceptance-acff54b/adr-007-decision.yaml  
**Decision Due**: V2-013  
**Timing**: before_interface_implementation ✅

### Dependency: V2-005 ✅ CLOSED

**Status**: V2-005.status == CLOSED  
**Provides**: Entity Identity foundation, ProjectId available  
**Required For**: ProjectGenreBinding uses ProjectId

### Test Catalog: AT-V2-013 ✅ PLANNED

**Source**: plan/machine/test-catalog.yaml  
**Scenarios**: 4 scenarios mapped  
**Target**: tests/contract/test_v2_013.py  
**Mapping**: plan/validation/execution/V2-013/test-scenario-mapping.md

### Plan Validation: ✅ PASS

**Status**: PASS (0 fatal errors)  
**Informational**: V2-005/V2-006 execution packet absence (non-blocking)  
**Manifest**: e57a9e2e848fcc9d76131d8de8c832ad4fc6af38370ed8fc016d33678cc998d9

---

## Implementation Strategy

### Phase 1: Core Data Structures (1-2 hours)

**Deliverable**: `src/anovel/genre/identity.py`

1. GenrePackIdentity (frozen dataclass)
   - Validation in __post_init__
   - pack_id format check (no version suffix)
   - content_hash 64 hex chars check

2. GenrePackMetadata (frozen dataclass)
   - Pack metadata structure
   - Extension namespaces list
   - World anchors list

3. ProjectGenreBinding (frozen dataclass)
   - ProjectId → GenrePackIdentity binding
   - Timestamp and metadata

**Acceptance**: All dataclasses immutable, validation logic correct

### Phase 2: Registry Implementation (2-3 hours)

**Deliverable**: `src/anovel/genre/registry.py`, `specs/genres/registry.yaml`

1. GenrePackRegistry class
   - Load registry from YAML
   - get_pack() with three-way hash verification
   - Unknown Pack/version exceptions
   - Extension namespace validation

2. Registry YAML structure
   - Pack metadata entries
   - Pack file path mappings
   - Content hashes

**Acceptance**: Registry loads, get_pack() verifies hashes, unknown Packs rejected

### Phase 3: Pack Definitions (1 hour)

**Deliverable**: `specs/genres/urban_business_realistic_v1.yaml`, `specs/genres/fantasy_eastern_progression_v1.yaml`

1. Urban Pack YAML
   - Pack metadata (pack_id, version)
   - Stub extension_schemas
   - Stub transition_rules
   - Stub world_mechanics
   - Stub quality_rubric

2. Fantasy Pack YAML
   - Same structure as Urban Pack
   - Different pack_id

3. Compute content_hash for both Packs
   - Use anovel.canon.hash.canonical_hash()
   - Update registry.yaml with correct hashes

**Acceptance**: Pack files valid YAML, hashes computed correctly, registry references correct

### Phase 4: Binding Service (1-2 hours)

**Deliverable**: `src/anovel/genre/binding.py`

1. ProjectGenreBindingService class
   - bind_pack() with identity verification
   - get_binding() for traceability
   - In-memory storage (dict) for P3
   - Binding immutability enforcement

**Acceptance**: Binding creates immutable records, traceability queries work

### Phase 5: Contract Tests (2-3 hours)

**Deliverable**: `tests/contract/test_v2_013.py`

1. Test class per scenario (4 classes)
2. Test cases per class (~13 total)
3. Fixtures for valid/invalid Pack identities
4. Fixtures for registry and binding service
5. Positive and negative cases

**Acceptance**: All 13 tests pass, AT-V2-013 scenarios covered

### Phase 6: Integration & Validation (1 hour)

1. Run full test suite
2. Verify STATIC checks pass (ruff, mypy)
3. Verify plan validation still passes
4. Verify canonical authority check passes
5. Run AT-V2-013 contract tests
6. Create evidence records

**Acceptance**: All validations pass, ready for closure

---

## Acceptance Criteria (from Backlog)

**AC-1**: ✅ ID 版本 hash 均被绑定并核验  
**Verification**: AT-V2-013-01 tests pass, three-way hash verification implemented

**AC-2**: ✅ 未知 Pack 与扩展拒绝而非默认 fallback  
**Verification**: AT-V2-013-02 tests pass, UnknownPackError/UndeclaredExtensionError raised

**AC-3**: ✅ 全局只读目录绑定到项目后仍可追溯  
**Verification**: AT-V2-013-03 tests pass, binding traceability queries work

**AC-4**: ✅ 显式 Pack 存在而可选策略无命中时保留原 ID/version/hash  
**Verification**: AT-V2-013-04 tests pass, Pack identity unchanged despite strategy mismatch

---

## Risk Assessment

### Technical Risks: MEDIUM

**Risk 1**: Content hash computation discrepancy  
**Mitigation**: Use existing canonical_hash() from ADR-005, test with known inputs  
**Impact if occurs**: Hash mismatch errors, rebind Packs

**Risk 2**: Extension namespace validation complexity  
**Mitigation**: Start with simple list matching, expand if needed  
**Impact if occurs**: Additional validation logic required

**Risk 3**: Test fixture management  
**Mitigation**: Use pytest fixtures, separate valid/invalid Pack files  
**Impact if occurs**: Test maintenance overhead

### Process Risks: LOW

**Risk 1**: ADR-007 interpretation ambiguity  
**Mitigation**: ADR-007 is detailed and ACCEPTED, reference decision record  
**Impact if occurs**: Clarification discussion with Owner

**Risk 2**: Scope creep (implementing V2-014 features)  
**Mitigation**: Strict adherence to V2-013 scope, stub only  
**Impact if occurs**: Delays, out-of-scope work

---

## Budget

### Time Estimate

**Total**: 6-8 hours  
**Breakdown**:
- Data structures: 1-2 hours
- Registry: 2-3 hours
- Pack definitions: 1 hour
- Binding service: 1-2 hours
- Contract tests: 2-3 hours
- Integration: 1 hour

**Confidence**: MEDIUM (based on similar V2-009~012 pattern)

### Resource Requirements

**Paid API Calls**: None required  
**Model Cost Cap**: N/A  
**Infrastructure**: Local development only  
**Maximum Attempts**: 1  
**Maximum Runtime**: 28800 seconds (8 hours)

### CI Resources

**Expected CI Duration**: 5-10 minutes  
**CI Gates**: STATIC, SCHEMA_CONTRACT, UNIT, ARCH_FITNESS, POSTGRES_ENV, SECRET_DEPENDENCY  
**Expected Result**: 6/6 SUCCESS

---

## Stop Conditions

**Implementation must stop if**:
1. ADR-007 status changes from ACCEPTED
2. G-P2 gate status changes from VERIFIED
3. Plan validation produces fatal errors
4. Three-way hash verification proves infeasible
5. Extension namespace validation cannot be implemented per ADR-007
6. Owner requests scope change or halt

---

## Deliverables Checklist

### Code
- [ ] src/anovel/genre/__init__.py
- [ ] src/anovel/genre/identity.py (GenrePackIdentity, GenrePackMetadata, ProjectGenreBinding)
- [ ] src/anovel/genre/registry.py (GenrePackRegistry)
- [ ] src/anovel/genre/binding.py (ProjectGenreBindingService)

### Specs
- [ ] specs/genres/registry.yaml
- [ ] specs/genres/urban_business_realistic_v1.yaml
- [ ] specs/genres/fantasy_eastern_progression_v1.yaml

### Tests
- [ ] tests/contract/test_v2_013.py (~13 test cases)

### Evidence
- [ ] plan/validation/execution/V2-013/implement-validation-results.yaml
- [ ] plan/validation/execution/V2-013/test-results.yaml
- [ ] plan/validation/execution/V2-013/ci-results.yaml

### Machine Updates
- [ ] plan/machine/implementation-backlog.yaml (update V2-013.status → CLOSED)
- [ ] plan/FILE_MANIFEST.json (regenerate)
- [ ] plan/validation/plan-validation.json (regenerate)

---

## Authorization Decision Points

### Owner Must Approve

**Question 1**: Proceed with V2-013 IMPLEMENT as scoped above?  
**Options**: APPROVE / MODIFY SCOPE / DEFER / REJECT

**Question 2**: Time budget of 6-8 hours acceptable?  
**Options**: APPROVE / ADJUST BUDGET

**Question 3**: Pack stub structure (minimal extension_schemas/transition_rules) acceptable for P3?  
**Options**: APPROVE / REQUIRE MORE DETAIL

---

## Owner Authorization

**I, Owner, authorize V2-013 IMPLEMENT phase with the scope, budget, and deliverables defined above.**

**Authorization Status**: ⏳ PENDING

**Authorized by**: _____________  
**Date**: _____________  
**Notes**: _____________

---

## Next Steps After Authorization

1. Create IMPLEMENT branch: `impl/v2-013-genrepack-loader`
2. Update execution packet action: PREPARE → IMPLEMENT
3. Implement per phase plan (6 phases)
4. Run validations after each phase
5. Create evidence records
6. Submit PR for review
7. Request Owner closure authorization

---

**PREPARE phase complete. Awaiting Owner IMPLEMENT authorization.**
