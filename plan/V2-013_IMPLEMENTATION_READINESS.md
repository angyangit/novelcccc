# V2-013 Implementation Readiness

**Task**: V2-013 GenreProfile and GenrePack loader  
**Phase**: P3  
**Status**: READY FOR IMPLEMENTATION (pending ADR-007 acceptance)  
**Prepared**: 2026-10-25

## Prerequisites

- [x] ADR-007 decision drafted
- [x] Current Canon Kernel interfaces reviewed (V2-005 Identity, ADR-005 Hash)
- [x] AT-V2-013 acceptance criteria confirmed
- [ ] **Owner acceptance of ADR-007 required before IMPLEMENT**

## Implementation Scope

V2-013 implements **GenrePack identity verification and project binding only**. Does NOT implement:
- Genre policy engine (V2-014)
- Transition rules execution (V2-014)
- Specific Pack Schemas for urban/fantasy (V2-015/V2-016)
- Semantic validation of extension fields (V2-014)

## File Manifest

### Core Implementation (New Files)

```
src/anovel/genre/
├── __init__.py                 # Module exports
├── identity.py                 # GenrePackIdentity, ProjectGenreBinding
├── registry.py                 # GenrePackRegistry
└── binding.py                  # ProjectGenreBindingService

specs/genres/
├── registry.yaml               # Global GenrePack registry
├── urban_business_realistic_v1.yaml    # Urban Pack definition
└── fantasy_eastern_progression_v1.yaml # Fantasy Pack definition

tests/contract/
└── test_v2_013.py              # AT-V2-013 contract tests
```

### Supporting Files (Updates)

```
src/anovel/domain/
└── identity.py                 # Import ProjectId (already exists)

plan/machine/
├── decision-register.yaml      # Mark ADR-007 decision_record after acceptance
└── implementation-backlog.yaml # Update V2-013 status after closure
```

## Data Structures

### 1. GenrePackIdentity

```python
# src/anovel/genre/identity.py

from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class GenrePackIdentity:
    """
    Immutable GenrePack identity triple.
    
    Attributes:
        pack_id: Stable logical identifier (e.g., "urban.business.realistic")
        version: Semantic version (e.g., "1.0.0")
        content_hash: SHA-256 canonical hash of Pack content (64 hex chars)
    
    Invariants:
        - Same (pack_id, version) must always have same content_hash
        - Different content → different content_hash or different version
        - pack_id does NOT include version suffix (e.g., NOT "urban.business.realistic.v1")
    """
    pack_id: str
    version: str
    content_hash: str
    
    def __post_init__(self):
        if not self.pack_id:
            raise ValueError("pack_id cannot be empty")
        if not self.version:
            raise ValueError("version cannot be empty")
        if len(self.content_hash) != 64:
            raise ValueError(f"content_hash must be 64 hex chars, got {len(self.content_hash)}")
        if ".v" in self.pack_id and self.pack_id.split(".")[-1].startswith("v"):
            raise ValueError(f"pack_id should not include version suffix: {self.pack_id}")



@dataclass(frozen=True)
class GenrePackMetadata:
    """
    GenrePack metadata loaded from registry.
    
    Attributes:
        identity: Pack identity triple
        extension_namespaces: Declared extension namespaces (e.g., "fantasy.eastern.cultivation")
        world_anchors: World mechanism anchors (e.g., "urban.business.realistic")
        pack_file_path: Relative path to Pack definition YAML
    """
    identity: GenrePackIdentity
    extension_namespaces: frozenset[str]
    world_anchors: frozenset[str]
    pack_file_path: str


@dataclass(frozen=True)
class ProjectGenreBinding:
    """
    Project's frozen GenrePack binding.
    
    Attributes:
        project_id: Project identifier (from V2-005 domain.identity)
        pack_identity: Frozen GenrePack identity triple
        bound_at: Timestamp of binding
        binding_hash: SHA-256 hash of this binding record (for verification)
    
    Invariants:
        - Once bound, Pack identity cannot change (frozen)
        - binding_hash = canonical_hash({project_id, pack_identity, bound_at})
    """
    project_id: str  # ProjectId from domain.identity
    pack_identity: GenrePackIdentity
    bound_at: datetime
    binding_hash: str
```

### 2. Exception Types

```python
# src/anovel/genre/registry.py

class GenrePackError(Exception):
    """Base exception for GenrePack errors."""
    pass


class GenrePackNotFoundError(GenrePackError):
    """Requested GenrePack does not exist in registry."""
    def __init__(self, pack_id: str, version: str):
        self.pack_id = pack_id
        self.version = version
        super().__init__(f"GenrePack not found: {pack_id} version {version}")


class GenrePackHashMismatchError(GenrePackError):
    """GenrePack content hash verification failed."""
    def __init__(self, pack_id: str, expected_hash: str, actual_hash: str):
        self.pack_id = pack_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            f"GenrePack {pack_id} hash mismatch: "
            f"expected {expected_hash[:8]}..., got {actual_hash[:8]}..."
        )


class UnknownExtensionNamespaceError(GenrePackError):
    """ChangeSet references undeclared extension namespace."""
    def __init__(self, namespace: str, declared_namespaces: frozenset[str]):
        self.namespace = namespace
        self.declared_namespaces = declared_namespaces
        super().__init__(
            f"Unknown extension namespace '{namespace}'. "
            f"Declared: {sorted(declared_namespaces)}"
        )


class ProjectGenreBindingNotFoundError(GenrePackError):
    """Project has no GenrePack binding."""
    def __init__(self, project_id: str):
        self.project_id = project_id
        super().__init__(f"Project {project_id} has no GenrePack binding")
```

## Public API

### GenrePackRegistry

```python
# src/anovel/genre/registry.py

import yaml
from pathlib import Path
from anovel.canon.hash import canonical_hash
from .identity import GenrePackIdentity, GenrePackMetadata

class GenrePackRegistry:
    """
    Global read-only GenrePack registry.
    
    Loads from specs/genres/registry.yaml and validates Pack identity.
    Registry is immutable after initialization.
    """
    
    def __init__(self, registry_path: str | Path = "specs/genres/registry.yaml"):
        """
        Load GenrePack registry from YAML.
        
        Args:
            registry_path: Path to registry.yaml (relative to repo root)
        
        Raises:
            FileNotFoundError: Registry file does not exist
            ValueError: Registry format invalid
        """
        self._registry_path = Path(registry_path)
        self._packs: dict[tuple[str, str], GenrePackMetadata] = {}
        self._load_registry()
    
    def get_pack(
        self,
        pack_id: str,
        version: str,
        expected_hash: str | None = None
    ) -> GenrePackMetadata:
        """
        Retrieve GenrePack metadata with optional hash verification.
        
        Args:
            pack_id: Logical pack identifier
            version: Semantic version
            expected_hash: Optional content hash for verification
        
        Returns:
            GenrePackMetadata with verified identity
        
        Raises:
            GenrePackNotFoundError: Pack ID or version not in registry
            GenrePackHashMismatchError: Content hash verification failed
        """
        key = (pack_id, version)
        if key not in self._packs:
            raise GenrePackNotFoundError(pack_id, version)
        
        metadata = self._packs[key]
        
        # Verify hash if provided
        if expected_hash is not None:
            if metadata.identity.content_hash != expected_hash:
                raise GenrePackHashMismatchError(
                    pack_id,
                    expected_hash,
                    metadata.identity.content_hash
                )
        
        return metadata
    
    def verify_pack_hash(self, pack_identity: GenrePackIdentity) -> bool:
        """
        Verify Pack content hash by recomputing from source YAML.
        
        Args:
            pack_identity: Pack identity with hash to verify
        
        Returns:
            True if hash matches recomputed hash, False otherwise
        
        Raises:
            GenrePackNotFoundError: Pack not in registry
        """
        metadata = self.get_pack(pack_identity.pack_id, pack_identity.version)
        
        # Load Pack YAML and recompute hash
        pack_path = self._registry_path.parent / metadata.pack_file_path
        with open(pack_path, "r", encoding="utf-8") as f:
            pack_content = yaml.safe_load(f)
        
        # Extract hashable content (exclude content_hash field to avoid self-reference)
        hashable_content = {
            "pack_id": pack_content["pack_id"],
            "version": pack_content["version"],
            "extension_schemas": pack_content.get("extension_schemas", []),
            "transition_rules": pack_content.get("transition_rules", []),
            "world_mechanics": pack_content.get("world_mechanics", {}),
            "quality_rubric": pack_content.get("quality_rubric", {})
        }
        
        # Compute canonical hash (ADR-005)
        actual_hash = canonical_hash(hashable_content)
        
        return actual_hash == pack_identity.content_hash
    
    def list_available_packs(self) -> list[GenrePackIdentity]:
        """
        List all registered GenrePacks.
        
        Returns:
            List of GenrePackIdentity (sorted by pack_id, version)
        """
        return sorted(
            [m.identity for m in self._packs.values()],
            key=lambda i: (i.pack_id, i.version)
        )
    
    def _load_registry(self) -> None:
        """Load and validate registry.yaml."""
        if not self._registry_path.exists():
            raise FileNotFoundError(f"Registry not found: {self._registry_path}")
        
        with open(self._registry_path, "r", encoding="utf-8") as f:
            registry_data = yaml.safe_load(f)
        
        if "packs" not in registry_data:
            raise ValueError("Registry must contain 'packs' list")
        
        for pack_entry in registry_data["packs"]:
            identity = GenrePackIdentity(
                pack_id=pack_entry["pack_id"],
                version=pack_entry["version"],
                content_hash=pack_entry["content_hash"]
            )
            
            metadata = GenrePackMetadata(
                identity=identity,
                extension_namespaces=frozenset(pack_entry.get("extension_namespaces", [])),
                world_anchors=frozenset(pack_entry.get("world_anchors", [])),
                pack_file_path=pack_entry["pack_file"]
            )
            
            key = (identity.pack_id, identity.version)
            if key in self._packs:
                raise ValueError(f"Duplicate Pack in registry: {identity.pack_id} v{identity.version}")
            
            self._packs[key] = metadata
```

### ProjectGenreBindingService

```python
# src/anovel/genre/binding.py

from datetime import datetime
from anovel.canon.hash import canonical_hash
from .identity import GenrePackIdentity, ProjectGenreBinding
from .registry import GenrePackRegistry, ProjectGenreBindingNotFoundError

class ProjectGenreBindingService:
    """
    Manage project-specific GenrePack bindings.
    
    Bindings are frozen: once a project is bound to a Pack, the identity
    cannot change without explicit migration.
    """
    
    def __init__(self, registry: GenrePackRegistry):
        """
        Initialize binding service.
        
        Args:
            registry: GenrePackRegistry for Pack validation
        """
        self._registry = registry
        # In-memory storage for P3 (V2-013)
        # Future: persist to database
        self._bindings: dict[str, ProjectGenreBinding] = {}
    
    def bind_pack(
        self,
        project_id: str,
        pack_identity: GenrePackIdentity
    ) -> ProjectGenreBinding:
        """
        Bind a GenrePack to a project (frozen) with mandatory hash verification.
        
        Verifies Pack exists and hash is valid by recomputing from source YAML.
        
        Args:
            project_id: Project identifier
            pack_identity: GenrePack identity triple
        
        Returns:
            ProjectGenreBinding record
        
        Raises:
            GenrePackNotFoundError: Pack does not exist in registry
            GenrePackHashMismatchError: Hash verification failed (content tampered)
            ValueError: Project already has a binding
        """
        # Verify Pack exists
        metadata = self._registry.get_pack(
            pack_identity.pack_id,
            pack_identity.version
        )
        
        # Load Pack YAML and recompute hash (mandatory verification)
        pack_path = self._registry_path.parent / metadata.pack_file_path
        with open(pack_path, "r", encoding="utf-8") as f:
            pack_content = yaml.safe_load(f)
        
        # Extract hashable content (exclude content_hash to avoid self-reference)
        hashable_content = {
            "pack_id": pack_content["pack_id"],
            "version": pack_content["version"],
            "extension_schemas": pack_content.get("extension_schemas", []),
            "transition_rules": pack_content.get("transition_rules", []),
            "world_mechanics": pack_content.get("world_mechanics", {}),
            "quality_rubric": pack_content.get("quality_rubric", {})
        }
        computed_hash = canonical_hash(hashable_content)
        
        # Verify hash matches
        if computed_hash != pack_identity.content_hash:
            raise GenrePackHashMismatchError(
                pack_identity.pack_id,
                pack_identity.content_hash,
                computed_hash
            )
        
        # Check for existing binding
        if project_id in self._bindings:
            existing = self._bindings[project_id]
            raise ValueError(
                f"Project {project_id} already bound to "
                f"{existing.pack_identity.pack_id} v{existing.pack_identity.version}"
            )
        
        # Create binding
        bound_at = datetime.utcnow()
        binding_data = {
            "project_id": project_id,
            "pack_id": pack_identity.pack_id,
            "version": pack_identity.version,
            "content_hash": pack_identity.content_hash,
            "bound_at": bound_at.isoformat()
        }
        binding_hash = canonical_hash(binding_data)
        
        binding = ProjectGenreBinding(
            project_id=project_id,
            pack_identity=pack_identity,
            bound_at=bound_at,
            binding_hash=binding_hash
        )
        
        self._bindings[project_id] = binding
        return binding
    
    def get_binding(self, project_id: str) -> ProjectGenreBinding:
        """
        Retrieve project's frozen GenrePack binding.
        
        Args:
            project_id: Project identifier
        
        Returns:
            ProjectGenreBinding record
        
        Raises:
            ProjectGenreBindingNotFoundError: Project has no binding
        """
        if project_id not in self._bindings:
            raise ProjectGenreBindingNotFoundError(project_id)
        
        return self._bindings[project_id]
    
    def validate_extension_namespace(
        self,
        project_id: str,
        namespace: str
    ) -> bool:
        """
        Check if namespace is declared in project's bound Pack.
        
        Args:
            project_id: Project identifier
            namespace: Extension namespace to validate
        
        Returns:
            True if namespace is declared in Pack, False otherwise
        
        Raises:
            ProjectGenreBindingNotFoundError: Project has no binding
        """
        binding = self.get_binding(project_id)
        pack_metadata = self._registry.get_pack(
            binding.pack_identity.pack_id,
            binding.pack_identity.version
        )
        
        return namespace in pack_metadata.extension_namespaces
```

## Test Matrix (AT-V2-013)

### Test Suite Structure

```python
# tests/contract/test_v2_013.py

import pytest
from anovel.genre.identity import GenrePackIdentity, GenrePackMetadata
from anovel.genre.registry import (
    GenrePackRegistry,
    GenrePackNotFoundError,
    GenrePackHashMismatchError
)
from anovel.genre.binding import ProjectGenreBindingService

class TestV2013GenrePackLoader:
    """AT-V2-013: GenrePack identity verification and binding."""
    
    # AT-V2-013-01: ID 版本 hash 均被绑定并核验
    def test_pack_identity_binding_and_verification(self):
        """Load Pack and verify all three identity components."""
        ...
    
    # AT-V2-013-02: 未知 Pack 与扩展拒绝而非默认 fallback
    def test_unknown_pack_explicit_failure(self):
        """Unknown Pack ID raises GenrePackNotFoundError."""
        ...
    
    def test_unknown_version_explicit_failure(self):
        """Unknown version raises GenrePackNotFoundError."""
        ...
    
    def test_unknown_extension_namespace_rejected(self):
        """Undeclared extension namespace validation fails."""
        ...
    
    # AT-V2-013-03: 全局只读目录绑定到项目后仍可追溯
    def test_global_pack_binding_traceability(self):
        """Project binding preserves Pack identity triple."""
        ...
    
    # AT-V2-013-04: 显式 Pack 存在而可选策略无命中时保留原 ID/version/hash
    def test_no_silent_pack_replacement(self):
        """Pack identity remains stable, no fallback to similar Packs."""
        ...
    
    # Additional critical scenarios
    def test_content_hash_mismatch_detected(self):
        """Tampered Pack content hash triggers GenrePackHashMismatchError."""
        ...
    
    def test_same_id_version_different_hash_rejected(self):
        """Same (pack_id, version) with different hash is rejected."""
        ...
    
    def test_project_isolation(self):
        """Two projects with different Pack bindings do not interfere."""
        ...
    
    def test_pack_version_upgrade_does_not_affect_existing_projects(self):
        """Existing project bindings remain frozen after Pack upgrade."""
        ...
    
    def test_idempotent_binding_query(self):
        """Repeated queries return same frozen binding."""
        ...
    
    def test_binding_hash_verification(self):
        """Binding hash is deterministic and verifiable."""
        ...
```

### Test Fixtures

```yaml
# tests/fixtures/genres/test_registry.yaml
version: 1.0.0
packs:
  - pack_id: urban.business.realistic
    version: 1.0.0
    content_hash: "TEST_HASH_URBAN_BUSINESS_V1_PLACEHOLDER"
    extension_namespaces:
      - urban.business.company
      - urban.business.finance
    world_anchors:
      - urban.business.realistic
    pack_file: test_urban_business.yaml
  
  - pack_id: fantasy.eastern.progression
    version: 1.0.0
    content_hash: "TEST_HASH_FANTASY_EASTERN_V1_PLACEHOLDER"
    extension_namespaces:
      - fantasy.eastern.cultivation
      - fantasy.eastern.realm
    world_anchors:
      - fantasy.eastern.progression
    pack_file: test_fantasy_eastern.yaml
```

### Negative Test Scenarios

1. **Pack Not Found**: Request non-existent pack_id → `GenrePackNotFoundError`
2. **Version Not Found**: Request non-existent version → `GenrePackNotFoundError`
3. **Hash Mismatch**: Provide wrong expected_hash → `GenrePackHashMismatchError`
4. **Tampered Content**: Pack file modified, hash no longer matches → `GenrePackHashMismatchError`
5. **Duplicate Pack**: Registry contains duplicate (pack_id, version) → `ValueError` during load
6. **Unknown Namespace**: Validate undeclared namespace → returns `False`
7. **No Binding**: Query unbound project → `ProjectGenreBindingNotFoundError`
8. **Double Binding**: Bind same project twice → `ValueError`

## Implementation Order

1. **Phase 1: Data Structures** (~30 min)
   - `genre/identity.py`: GenrePackIdentity, GenrePackMetadata, ProjectGenreBinding
   - Exception types

2. **Phase 2: Registry** (~1 hour)
   - `genre/registry.py`: GenrePackRegistry
   - Load, parse, validate registry.yaml
   - Pack lookup and hash verification

3. **Phase 3: Binding Service** (~45 min)
   - `genre/binding.py`: ProjectGenreBindingService
   - Bind, query, validate extension namespaces

4. **Phase 4: Test Fixtures** (~30 min)
   - `specs/genres/registry.yaml`: Production registry (placeholder hashes)
   - `tests/fixtures/genres/`: Test fixtures
   - Minimal Pack YAML definitions

5. **Phase 5: Contract Tests** (~2 hours)
   - `tests/contract/test_v2_013.py`: All AT-V2-013 scenarios
   - Positive and negative cases
   - Verify all 4 acceptance criteria

6. **Phase 6: Integration** (~30 min)
   - Update `genre/__init__.py` exports
   - Verify architecture fitness (no forbidden imports)
   - Local test run

## Dependencies on Existing Code

- `anovel.canon.hash.canonical_hash`: Used for Pack content hash and binding hash
- `anovel.domain.identity.ProjectId`: Type alias for project identifier (if needed)
- `yaml`: YAML parsing (already in dependencies)
- `pytest`: Testing framework (already in dependencies)

## Known Open Questions

None blocking V2-013. The following are deferred to later tasks:

- **V2-014**: How to execute transition rules and precondition checks?
- **V2-015/V2-016**: What are the complete Schemas for urban/fantasy Packs?
- **V2-014**: How to perform semantic validation (dream vs. reality, metaphor vs. fact)?
- **Future**: How to persist ProjectGenreBinding to database (V2-013 uses in-memory)?
- **Future**: How to handle Pack migration and version upgrades?

## Success Criteria

V2-013 is **IMPLEMENTATION COMPLETE** when:

1. ✅ All 4 AT-V2-013 scenarios pass
2. ✅ Architecture fitness tests pass (no forbidden dependencies)
3. ✅ Contract tests achieve 100% scenario coverage
4. ✅ Local pytest run: all tests pass
5. ✅ CI pipeline: all gates pass
6. ✅ Code review: passes maintainer review
7. ✅ ADR-007: accepted by Owner

## Estimated Effort

- **Implementation**: ~5 hours (data structures, registry, binding, fixtures)
- **Testing**: ~2 hours (contract tests, negative cases)
- **Integration & CI**: ~1 hour (verify gates, fix issues)
- **Total**: ~8 hours for a single focused implementation session

## Next Steps After V2-013

After V2-013 CLOSED:

1. **Owner reviews ADR-007** → Accept or request revisions
2. **V2-014 starts**: Genre hard policy engine
   - Implement transition rules execution
   - Implement semantic validation (dreams, metaphors)
   - Integrate with Q2 checker
3. **V2-015**: Urban Business canon extension
   - Complete urban Pack Schema
   - Implement business rules
4. **V2-016**: Eastern Fantasy canon extension
   - Complete fantasy Pack Schema
   - Implement cultivation rules
