"""
AT-V2-013: GenrePack Identity Verification and Project Binding Contract Tests.

Tests the GenrePack loader implementation against ADR-007 requirements:
- AT-V2-013-01: ID/version/hash three-way verification
- AT-V2-013-02: Unknown Pack/extension explicit rejection
- AT-V2-013-03: Project binding traceability
- AT-V2-013-04: Pack identity preservation under optional strategies

Contract: V2-013 Implementation Contract
"""

from pathlib import Path

import pytest

from anovel.domain.identity import ProjectId
from anovel.genre.binding import (
    ProjectAlreadyBoundError,
    ProjectGenreBindingService,
    ProjectNotBoundError,
)
from anovel.genre.identity import (
    GenrePackIdentity,
    InvalidContentHashError,
    InvalidPackIdError,
    InvalidVersionError,
)
from anovel.genre.registry import (
    GenrePackHashMismatchError,
    GenrePackRegistry,
    UndeclaredExtensionError,
    UnknownPackError,
    UnknownVersionError,
)

# --- Fixtures ---


@pytest.fixture
def registry_path():
    """Path to test registry file."""
    return Path("specs/genres/registry.yaml")


@pytest.fixture
def specs_root():
    """Root directory for Pack YAML files."""
    return Path("specs")


@pytest.fixture
def registry(registry_path, specs_root):
    """Loaded GenrePackRegistry."""
    return GenrePackRegistry.load_from_file(registry_path, specs_root)


@pytest.fixture
def binding_service(registry):
    """ProjectGenreBindingService instance."""
    return ProjectGenreBindingService(registry)


@pytest.fixture
def urban_pack_identity():
    """Valid urban.business.realistic Pack identity."""
    return GenrePackIdentity(
        pack_id="urban.business.realistic",
        version="1.0.0",
        content_hash="21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336",
    )


@pytest.fixture
def fantasy_pack_identity():
    """Valid fantasy.eastern.progression Pack identity."""
    return GenrePackIdentity(
        pack_id="fantasy.eastern.progression",
        version="1.0.0",
        content_hash="6e835c0a4197cbae2e88ee55b52201f7af47f3ca8bfb3088f776cc5e21598757",
    )


# --- AT-V2-013-01: ID version hash binding and verification ---


class TestGenrePackIdentityVerification:
    """AT-V2-013-01: ID version hash binding and verification."""

    def test_correct_pack_identity_triple_validates(
        self, registry, urban_pack_identity
    ):
        """Positive: Correct (pack_id, version, content_hash) passes three-way check."""
        metadata = registry.get_pack(urban_pack_identity)
        assert metadata.identity.pack_id == "urban.business.realistic"
        assert metadata.identity.version == "1.0.0"
        assert metadata.identity.content_hash == urban_pack_identity.content_hash

    def test_both_packs_validate_correctly(
        self, registry, urban_pack_identity, fantasy_pack_identity
    ):
        """Positive: Both frozen Anchor Packs pass verification."""
        urban_metadata = registry.get_pack(urban_pack_identity)
        fantasy_metadata = registry.get_pack(fantasy_pack_identity)

        assert urban_metadata.identity.pack_id == "urban.business.realistic"
        assert fantasy_metadata.identity.pack_id == "fantasy.eastern.progression"

    def test_caller_hash_mismatch_rejected(self, registry):
        """Negative: Caller hash != registry hash raises GenrePackHashMismatchError."""
        wrong_identity = GenrePackIdentity(
            pack_id="urban.business.realistic",
            version="1.0.0",
            content_hash="0" * 64,  # Wrong hash
        )

        with pytest.raises(GenrePackHashMismatchError) as exc_info:
            registry.get_pack(wrong_identity)

        assert "caller expects" in str(exc_info.value)
        assert "registry declares" in str(exc_info.value)

    def test_pack_id_with_version_suffix_rejected(self):
        """Negative: Pack ID with version suffix rejected."""
        with pytest.raises(InvalidPackIdError) as exc_info:
            GenrePackIdentity(
                pack_id="urban.business.realistic.v1",  # Invalid: contains version suffix
                version="1.0.0",
                content_hash="a" * 64,
            )

        assert "version suffix" in str(exc_info.value).lower()


# --- AT-V2-013-02: Unknown Pack/extension explicit rejection ---


class TestUnknownPackRejection:
    """AT-V2-013-02: Unknown Pack and extension explicit rejection."""

    def test_unknown_pack_id_rejected(self, registry):
        """Negative: Unknown Pack ID raises UnknownPackError."""
        unknown_identity = GenrePackIdentity(
            pack_id="unknown.pack.id",
            version="1.0.0",
            content_hash="a" * 64,
        )

        with pytest.raises(UnknownPackError) as exc_info:
            registry.get_pack(unknown_identity)

        assert "unknown.pack.id" in str(exc_info.value).lower()

    def test_unknown_version_rejected(self, registry):
        """Negative: Unknown version raises UnknownVersionError."""
        unknown_version_identity = GenrePackIdentity(
            pack_id="urban.business.realistic",
            version="2.0.0",  # Version 2.0.0 does not exist
            content_hash="a" * 64,
        )

        with pytest.raises(UnknownVersionError) as exc_info:
            registry.get_pack(unknown_version_identity)

        assert "2.0.0" in str(exc_info.value)
        assert "available" in str(exc_info.value).lower()

    def test_invalid_pack_id_format_rejected(self):
        """Negative: Invalid pack_id format rejected."""
        with pytest.raises(InvalidPackIdError):
            GenrePackIdentity(
                pack_id="InvalidFormat",  # Must be lowercase with dots
                version="1.0.0",
                content_hash="a" * 64,
            )

    def test_invalid_version_format_rejected(self):
        """Negative: Invalid semantic version rejected."""
        with pytest.raises(InvalidVersionError):
            GenrePackIdentity(
                pack_id="urban.business.realistic",
                version="v1.0",  # Invalid: must be X.Y.Z
                content_hash="a" * 64,
            )

    def test_invalid_content_hash_format_rejected(self):
        """Negative: Invalid content_hash format rejected."""
        with pytest.raises(InvalidContentHashError):
            GenrePackIdentity(
                pack_id="urban.business.realistic",
                version="1.0.0",
                content_hash="invalid_hash",  # Must be 64 hex chars
            )


# --- AT-V2-013-03: Project binding traceability ---


class TestProjectBindingTraceability:
    """AT-V2-013-03: Project binding traceability."""

    def test_project_binding_creates_immutable_record(
        self, binding_service, urban_pack_identity
    ):
        """Positive: Binding creates immutable ProjectGenreBinding."""
        project_id = ProjectId("project-001")

        binding = binding_service.bind_pack(project_id, urban_pack_identity)

        assert binding.project_id == project_id
        assert binding.pack_identity == urban_pack_identity
        assert binding.bound_at is not None

    def test_binding_can_be_retrieved_by_project_id(
        self, binding_service, urban_pack_identity
    ):
        """Positive: Binding retrievable by ProjectId."""
        project_id = ProjectId("project-002")

        created_binding = binding_service.bind_pack(project_id, urban_pack_identity)
        retrieved_binding = binding_service.get_binding(project_id)

        assert retrieved_binding == created_binding

    def test_multiple_projects_can_bind_same_pack(
        self, binding_service, urban_pack_identity
    ):
        """Positive: Multiple projects can bind to same Pack (shared read-only)."""
        project_1 = ProjectId("project-003")
        project_2 = ProjectId("project-004")

        binding_1 = binding_service.bind_pack(project_1, urban_pack_identity)
        binding_2 = binding_service.bind_pack(project_2, urban_pack_identity)

        assert binding_1.pack_identity == binding_2.pack_identity
        assert binding_1.project_id != binding_2.project_id

    def test_unbound_project_query_raises_error(self, binding_service):
        """Negative: Querying unbound project raises ProjectNotBoundError."""
        project_id = ProjectId("unbound-project")

        with pytest.raises(ProjectNotBoundError) as exc_info:
            binding_service.get_binding(project_id)

        assert "not bound" in str(exc_info.value).lower()

    def test_project_already_bound_rejected(
        self, binding_service, urban_pack_identity, fantasy_pack_identity
    ):
        """Negative: Rebinding project raises ProjectAlreadyBoundError."""
        project_id = ProjectId("project-005")

        binding_service.bind_pack(project_id, urban_pack_identity)

        with pytest.raises(ProjectAlreadyBoundError) as exc_info:
            binding_service.bind_pack(project_id, fantasy_pack_identity)

        assert "already bound" in str(exc_info.value).lower()

    def test_traceability_query_for_pack(
        self, binding_service, urban_pack_identity, fantasy_pack_identity
    ):
        """Positive: Can query all projects bound to specific Pack."""
        project_1 = ProjectId("project-006")
        project_2 = ProjectId("project-007")
        project_3 = ProjectId("project-008")

        binding_service.bind_pack(project_1, urban_pack_identity)
        binding_service.bind_pack(project_2, urban_pack_identity)
        binding_service.bind_pack(project_3, fantasy_pack_identity)

        urban_bindings = binding_service.get_bindings_for_pack(
            "urban.business.realistic", "1.0.0"
        )

        assert len(urban_bindings) == 2
        assert all(
            b.pack_identity.pack_id == "urban.business.realistic"
            for b in urban_bindings
        )


# --- AT-V2-013-04: Pack identity preservation ---


class TestPackIdentityPreservation:
    """AT-V2-013-04: Pack identity preservation under optional strategies."""

    def test_pack_identity_preserved_after_binding(
        self, binding_service, urban_pack_identity
    ):
        """Positive: Pack identity unchanged after binding."""
        project_id = ProjectId("project-009")

        binding = binding_service.bind_pack(project_id, urban_pack_identity)

        # Pack identity remains exactly as provided
        assert binding.pack_identity.pack_id == "urban.business.realistic"
        assert binding.pack_identity.version == "1.0.0"
        assert binding.pack_identity.content_hash == urban_pack_identity.content_hash

    def test_binding_immutability_enforced(self, binding_service, urban_pack_identity):
        """Positive: ProjectGenreBinding is immutable (frozen dataclass)."""
        project_id = ProjectId("project-010")

        binding = binding_service.bind_pack(project_id, urban_pack_identity)

        # Attempt to modify should fail (frozen dataclass)
        with pytest.raises(AttributeError):
            binding.pack_identity = GenrePackIdentity(
                "different.pack", "2.0.0", "b" * 64
            )

    def test_no_automatic_pack_replacement(self, binding_service, urban_pack_identity):
        """Positive: No automatic Pack replacement when strategy not found (stub test for V2-014)."""
        project_id = ProjectId("project-011")

        binding_service.bind_pack(project_id, urban_pack_identity)

        # Even if optional strategy filter is applied in future (V2-014),
        # Pack identity must remain unchanged
        retrieved_binding = binding_service.get_binding(project_id)
        assert retrieved_binding.pack_identity == urban_pack_identity


# --- Enhanced validation tests ---


class TestDefaultRegistryAndSimplifiedInterface:
    """Test default registry loading and simplified get_pack_by_id interface."""

    def test_default_registry_loads_successfully(self):
        """Positive: default_registry() loads from specs/genres/registry.yaml."""
        registry = GenrePackRegistry.default_registry()
        assert registry is not None
        assert len(registry.list_packs()) == 2

    def test_get_pack_by_id_simplified_interface(self):
        """Positive: get_pack_by_id() provides simplified interface."""
        registry = GenrePackRegistry.default_registry()
        metadata = registry.get_pack_by_id(
            "urban.business.realistic",
            "1.0.0",
            "21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336",
        )
        assert metadata.identity.pack_id == "urban.business.realistic"

    def test_get_pack_by_id_with_wrong_hash_rejected(self):
        """Negative: get_pack_by_id() rejects wrong hash."""
        registry = GenrePackRegistry.default_registry()
        with pytest.raises(GenrePackHashMismatchError):
            registry.get_pack_by_id("urban.business.realistic", "1.0.0", "0" * 64)


class TestPackFileValidation:
    """Test Pack file content_hash and unknown fields validation."""

    def test_pack_file_declares_content_hash(self, registry, urban_pack_identity):
        """Positive: Pack files declare content_hash field."""
        # This test verifies content_hash exists by successfully loading
        metadata = registry.get_pack(urban_pack_identity)
        assert metadata.identity.content_hash == urban_pack_identity.content_hash

    def test_metadata_fields_immutable(self, registry, urban_pack_identity):
        """Positive: Metadata extension_namespaces and world_anchors are tuples."""
        metadata = registry.get_pack(urban_pack_identity)
        assert isinstance(metadata.extension_namespaces, tuple)
        assert isinstance(metadata.world_anchors, tuple)

        # Verify they cannot be modified (tuples are immutable)
        with pytest.raises(AttributeError):
            metadata.extension_namespaces.append("new_namespace")


class TestWorldAnchorValidation:
    """Test world_anchor consistency validation per ADR-007 P3."""

    def test_world_anchor_matches_pack_id(self, registry, urban_pack_identity):
        """Positive: world_anchor matches pack_id for P3 Anchors."""
        metadata = registry.get_pack(urban_pack_identity)
        assert len(metadata.world_anchors) == 1
        assert metadata.world_anchors[0] == urban_pack_identity.pack_id

    def test_both_packs_have_matching_world_anchors(
        self, registry, urban_pack_identity, fantasy_pack_identity
    ):
        """Positive: Both frozen Anchors have matching world_anchors."""
        urban = registry.get_pack(urban_pack_identity)
        fantasy = registry.get_pack(fantasy_pack_identity)

        assert urban.world_anchors[0] == "urban.business.realistic"
        assert fantasy.world_anchors[0] == "fantasy.eastern.progression"


class TestGetPackOverloads:
    """Test get_pack overloaded interface per ADR-007."""

    def test_get_pack_with_identity_object(self, registry, urban_pack_identity):
        """Positive: Original get_pack(GenrePackIdentity) still works."""
        metadata = registry.get_pack(urban_pack_identity)
        assert metadata.identity.pack_id == "urban.business.realistic"

    def test_get_pack_with_separate_args_and_hash(self, registry):
        """Positive: get_pack(pack_id, version, hash) simplified interface."""
        metadata = registry.get_pack(
            "urban.business.realistic",
            "1.0.0",
            "21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336",
        )
        assert metadata.identity.pack_id == "urban.business.realistic"

    def test_get_pack_without_hash_uses_registry(self, registry):
        """Positive: get_pack(pack_id, version) uses registry hash."""
        metadata = registry.get_pack("urban.business.realistic", "1.0.0")
        assert metadata.identity.pack_id == "urban.business.realistic"
        assert (
            metadata.identity.content_hash
            == "21aa232995b76cd5d958bd1302f30a87dc56db69a3f62fcbf023f09352962336"
        )

    def test_get_pack_with_wrong_hash_rejected(self, registry):
        """Negative: get_pack with wrong hash raises error."""
        with pytest.raises(GenrePackHashMismatchError):
            registry.get_pack("urban.business.realistic", "1.0.0", "0" * 64)

    def test_get_pack_without_version_raises_error(self, registry):
        """Negative: get_pack(pack_id) without version raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            registry.get_pack("urban.business.realistic")  # type: ignore
        assert "version is required" in str(exc_info.value)


class TestExtensionNamespaceValidation:
    """Test extension namespace validation in ProjectGenreBindingService."""

    def test_validate_declared_extension(self, binding_service, urban_pack_identity):
        """Positive: Validate declared extension namespace."""
        project_id = ProjectId("project-ext-001")
        binding_service.bind_pack(project_id, urban_pack_identity)

        # urban pack declares "urban" and "business" namespaces
        assert binding_service.validate_extension_namespace(project_id, "urban")
        assert binding_service.validate_extension_namespace(project_id, "business")

    def test_validate_undeclared_extension_rejected(
        self, binding_service, urban_pack_identity
    ):
        """Negative: Undeclared extension namespace rejected."""
        project_id = ProjectId("project-ext-002")
        binding_service.bind_pack(project_id, urban_pack_identity)

        # "fantasy" is not declared in urban pack
        with pytest.raises(UndeclaredExtensionError) as exc_info:
            binding_service.validate_extension_namespace(project_id, "fantasy")

        assert "fantasy" in str(exc_info.value).lower()

    def test_validate_extension_for_unbound_project(self, binding_service):
        """Negative: Validation for unbound project raises error."""
        project_id = ProjectId("unbound-ext-project")

        with pytest.raises(ProjectNotBoundError):
            binding_service.validate_extension_namespace(project_id, "urban")

    def test_both_packs_have_different_extensions(
        self, binding_service, urban_pack_identity, fantasy_pack_identity
    ):
        """Positive: Different packs have different valid extensions."""
        urban_project = ProjectId("project-urban")
        fantasy_project = ProjectId("project-fantasy")

        binding_service.bind_pack(urban_project, urban_pack_identity)
        binding_service.bind_pack(fantasy_project, fantasy_pack_identity)

        # Urban pack has "urban", "business"
        assert binding_service.validate_extension_namespace(urban_project, "urban")
        with pytest.raises(UndeclaredExtensionError):
            binding_service.validate_extension_namespace(urban_project, "fantasy")

        # Fantasy pack has "fantasy", "eastern"
        assert binding_service.validate_extension_namespace(fantasy_project, "fantasy")
        with pytest.raises(UndeclaredExtensionError):
            binding_service.validate_extension_namespace(fantasy_project, "urban")
