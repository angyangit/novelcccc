# V2-013 AT-V2-013 Test Scenario Mapping

**Task**: V2-013 GenreProfile and GenrePack loader  
**Test Suite**: AT-V2-013  
**Target Path**: `tests/contract/test_v2_013.py`  
**Status**: PLANNED (PREPARE phase)

---

## Test Suite Overview

AT-V2-013 validates GenrePack identity verification and project binding contracts as defined in ADR-007.

**Scope**: GenrePack loader, identity verification, registry, binding service  
**Out of Scope**: Genre policy engine (V2-014), transition rule execution (V2-014), specific Pack schemas (V2-015/V2-016)

---

## Scenario Mapping

### AT-V2-013-01: ID 版本 hash 均被绑定并核验

**Required Assertion**: Pack ID, version, and content_hash three-way identity must be bound and verified

**Test Design**:

**Positive Cases**:
- Load Pack with correct (pack_id, version, content_hash) triple
- Registry declares hash, Pack file computes to same hash, caller provides same hash
- Three-way consistency check passes
- Expected: Pack loads successfully, binding succeeds

**Negative Cases**:
- Registry hash ≠ Pack file hash → `RegistryPackFileMismatchError`
- Caller hash ≠ Registry hash → `GenrePackHashMismatchError`
- Pack file missing content_hash field → Load error
- Pack file content_hash self-reference → Validation error

**Fixtures Required**:
- `specs/genres/urban_business_realistic_v1.yaml` (valid Pack with correct hash)
- `specs/genres/fantasy_eastern_progression_v1.yaml` (valid Pack with correct hash)
- `specs/genres/registry.yaml` (registry with correct Pack metadata)
- Modified Pack files with intentional hash mismatches (for negative cases)

**Dependencies**:
- `anovel.canon.hash.canonical_hash()` (ADR-005)
- `GenrePackIdentity` dataclass
- `GenrePackRegistry.get_pack()`

**CI Attribution**: UNIT gate (contract tests)

**Pass Criteria**:
- Positive case: Pack loads, identity verified, no exceptions
- Negative cases: Specific exceptions raised with clear error messages

---

### AT-V2-013-02: 未知 Pack 与扩展拒绝而非默认 fallback

**Required Assertion**: Unknown Packs, unknown versions, and undeclared extensions must be explicitly rejected, not silent fallback

**Test Design**:

**Negative Cases (Must Fail)**:
- Request Pack ID not in registry → `UnknownPackError`
- Request Pack version not in registry → `UnknownPackVersionError`
- Pack declares extension namespace not in `extension_namespaces` → `UndeclaredExtensionError`
- Project binding requests undeclared extension → `UndeclaredExtensionError`
- Pack file contains unknown top-level fields → `ValueError`

**Anti-Patterns to Prevent**:
- Silent fallback to default Pack
- Ignoring unknown extensions
- Auto-creating missing Pack metadata
- Fuzzy matching of Pack IDs (e.g., "urban" matches "urban.business.realistic")

**Fixtures Required**:
- Registry with limited Pack set (only two Anchors)
- Project binding requests with invalid Pack IDs/versions
- Pack files with undeclared extensions
- Pack files with unknown fields

**Dependencies**:
- `GenrePackRegistry.get_pack()`
- `ProjectGenreBindingService.bind_pack()`
- Extension namespace validation logic

**CI Attribution**: UNIT gate (contract tests)

**Pass Criteria**:
- All unknown/undeclared requests raise specific exceptions
- No silent fallbacks occur
- Error messages clearly identify what was unknown/undeclared

---

### AT-V2-013-03: 全局只读目录绑定到项目后仍可追溯

**Required Assertion**: Global read-only registry bindings to projects must remain traceable

**Test Design**:

**Positive Cases**:
- Bind Pack to project → ProjectGenreBinding created
- Binding records (pack_id, version, content_hash) triple
- Binding is immutable (frozen dataclass)
- Binding can be queried by ProjectId
- Multiple projects can bind to same Pack (shared read-only)
- Binding records timestamp and binding metadata

**Traceability Requirements**:
- Given ProjectId → retrieve GenrePackIdentity
- Given GenrePackIdentity → verify Pack still in registry
- Given ProjectId → retrieve full Pack metadata via registry
- Binding history preserved (if project rebinds to different version)

**Fixtures Required**:
- Multiple ProjectId instances
- Single Pack bound to multiple projects
- Project rebinding scenarios (if version upgrades occur)

**Dependencies**:
- `ProjectGenreBinding` dataclass
- `ProjectGenreBindingService.bind_pack()`
- `ProjectGenreBindingService.get_binding()`
- `anovel.domain.identity.ProjectId`

**CI Attribution**: UNIT gate (contract tests)

**Pass Criteria**:
- Binding creation succeeds
- Binding immutability enforced
- Traceability queries return correct results
- Multiple projects can share same Pack

---

### AT-V2-013-04: 显式 Pack 存在而可选策略无命中时保留原 ID/version/hash

**Required Assertion**: When explicit Pack exists but optional strategy has no match, preserve original ID/version/hash, do not replace with first similar sub-genre

**Test Design**:

**Positive Cases**:
- Project binds to `urban.business.realistic` v1.0.0
- Optional narrative strategy filter applied (e.g., "underdog protagonist")
- Strategy has no matching templates in Pack
- Pack identity remains `urban.business.realistic` v1.0.0 (unchanged)
- No silent replacement with related Pack (e.g., not replaced with `urban.business.cutthroat`)

**Anti-Patterns to Prevent**:
- Auto-selecting "similar" Pack when strategy filter has no match
- Replacing Pack with first alphabetically sorted sub-genre
- Fuzzy matching based on keywords
- Defaulting to parent genre when sub-genre unavailable

**Key Invariant**:
> Explicit Pack binding is frozen and cannot be modified by filter strategies, recommendation systems, or missing optional components.

**Fixtures Required**:
- Pack with limited strategy templates
- Strategy filter requests with no matches
- Related but distinct Pack IDs in registry

**Dependencies**:
- `ProjectGenreBinding` (immutable)
- Optional strategy application logic (future V2-014, stub for V2-013)
- Pack identity preservation contract

**CI Attribution**: UNIT gate (contract tests)

**Pass Criteria**:
- Pack identity unchanged after strategy filter
- No automatic Pack replacement
- Clear indication of "strategy not found" vs. Pack identity preserved

---

## Test Organization

### Test File Structure

```python
# tests/contract/test_v2_013.py

import pytest
from anovel.genre.registry import GenrePackRegistry
from anovel.genre.binding import ProjectGenreBindingService
from anovel.genre.identity import GenrePackIdentity, ProjectGenreBinding
from anovel.domain.identity import ProjectId
from anovel.canon.hash import canonical_hash


class TestGenrePackIdentityVerification:
    """AT-V2-013-01: ID version hash binding and verification"""
    
    def test_correct_pack_identity_triple_validates(self):
        """Positive: Correct (pack_id, version, content_hash) passes"""
        pass
    
    def test_registry_pack_file_hash_mismatch_fails(self):
        """Negative: Registry hash ≠ Pack file hash → error"""
        pass
    
    def test_caller_registry_hash_mismatch_fails(self):
        """Negative: Caller hash ≠ Registry hash → error"""
        pass


class TestUnknownPackRejection:
    """AT-V2-013-02: Unknown Pack/extension rejection"""
    
    def test_unknown_pack_id_rejected(self):
        """Negative: Unknown Pack ID raises UnknownPackError"""
        pass
    
    def test_unknown_pack_version_rejected(self):
        """Negative: Unknown version raises UnknownPackVersionError"""
        pass
    
    def test_undeclared_extension_rejected(self):
        """Negative: Undeclared extension raises UndeclaredExtensionError"""
        pass
    
    def test_unknown_pack_fields_rejected(self):
        """Negative: Unknown top-level fields raise ValueError"""
        pass


class TestProjectBindingTraceability:
    """AT-V2-013-03: Global registry → project binding traceability"""
    
    def test_pack_binding_creates_immutable_record(self):
        """Positive: Binding creates frozen ProjectGenreBinding"""
        pass
    
    def test_binding_traceable_by_project_id(self):
        """Positive: Given ProjectId → retrieve GenrePackIdentity"""
        pass
    
    def test_multiple_projects_share_pack(self):
        """Positive: Multiple projects bind to same Pack"""
        pass


class TestExplicitPackPreservation:
    """AT-V2-013-04: Explicit Pack preserved despite strategy mismatch"""
    
    def test_pack_identity_unchanged_when_strategy_missing(self):
        """Positive: Pack ID/version/hash unchanged when optional strategy has no match"""
        pass
    
    def test_no_automatic_pack_replacement(self):
        """Negative: Pack NOT replaced with similar sub-genre"""
        pass
```

### Fixture Organization

```python
# tests/contract/conftest.py or test_v2_013.py fixtures

@pytest.fixture
def valid_urban_pack_identity():
    """Correct identity for urban.business.realistic v1.0.0"""
    return GenrePackIdentity(
        pack_id="urban.business.realistic",
        version="1.0.0",
        content_hash="<computed from actual Pack file>"
    )

@pytest.fixture
def valid_fantasy_pack_identity():
    """Correct identity for fantasy.eastern.progression v1.0.0"""
    return GenrePackIdentity(
        pack_id="fantasy.eastern.progression",
        version="1.0.0",
        content_hash="<computed from actual Pack file>"
    )

@pytest.fixture
def genre_registry():
    """Initialized GenrePackRegistry with two Anchors"""
    return GenrePackRegistry(registry_path="specs/genres/registry.yaml")

@pytest.fixture
def binding_service(genre_registry):
    """ProjectGenreBindingService with registry"""
    return ProjectGenreBindingService(registry=genre_registry)

@pytest.fixture
def project_id():
    """Sample ProjectId for binding tests"""
    return ProjectId("test-project-001")
```

---

## Implementation Notes (for IMPLEMENT Phase)

### Required Interfaces

**GenrePackIdentity** (immutable):
```python
@dataclass(frozen=True)
class GenrePackIdentity:
    pack_id: str
    version: str
    content_hash: str  # 64 hex chars SHA-256
```

**GenrePackRegistry**:
```python
class GenrePackRegistry:
    def get_pack(self, pack_id: str, version: str) -> GenrePackMetadata:
        """
        Retrieve Pack metadata, verify three-way hash consistency.
        Raises: UnknownPackError, UnknownPackVersionError, RegistryPackFileMismatchError
        """
        pass
```

**ProjectGenreBindingService**:
```python
class ProjectGenreBindingService:
    def bind_pack(self, project_id: ProjectId, pack_identity: GenrePackIdentity) -> ProjectGenreBinding:
        """
        Bind project to Pack, verify identity, create immutable binding.
        Raises: GenrePackHashMismatchError, UndeclaredExtensionError
        """
        pass
    
    def get_binding(self, project_id: ProjectId) -> ProjectGenreBinding | None:
        """Retrieve existing binding for project."""
        pass
```

### Extension Namespace Validation

Per ADR-007 §2:
- `extension_namespaces` list must match `extension_schemas` keys exactly
- Undeclared namespaces → immediate failure
- No silent ignoring of unknown extensions

### World Anchor Validation

Per ADR-007 §1:
- P3 首期: Two fixed Anchors
- `urban.business.realistic` ↔ `urban.business.realistic` (anchor)
- `fantasy.eastern.progression` ↔ `fantasy.eastern.progression` (anchor)
- pack_id and world_anchor must be strictly consistent

---

## Acceptance Criteria Pass/Fail

**AT-V2-013-01**: PASS if three-way hash verification implemented and all positive/negative cases execute correctly  
**AT-V2-013-02**: PASS if all unknown Pack/version/extension requests raise specific exceptions  
**AT-V2-013-03**: PASS if project bindings are traceable and immutable  
**AT-V2-013-04**: PASS if Pack identity unchanged despite strategy mismatches

**Overall AT-V2-013**: PASS if all 4 scenarios pass

---

## PREPARE Phase Deliverable

This document maps AT-V2-013 scenarios to test structure and design. **No test implementation code is included** in PREPARE phase.

**Next Phase (IMPLEMENT)**: Implement `GenrePackRegistry`, `ProjectGenreBindingService`, test fixtures, and execute all test cases.
