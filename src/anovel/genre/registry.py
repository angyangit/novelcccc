"""
GenrePack Registry with three-way hash verification.

Implements ADR-007 §1 GenrePackRegistry:
- Load registry from specs/genres/registry.yaml
- get_pack(pack_id, version) with strict validation
- Three-way hash verification (registry, file, caller)
- Fail-closed on unknown Pack/version or hash mismatch

Registry YAML format:
    packs:
      - pack_id: "urban.business.realistic"
        version: "1.0.0"
        content_hash: "abc123..."
        pack_file_path: "genres/urban_business_realistic_v1.yaml"
        extension_namespaces: ["urban", "business"]
        world_anchors: ["urban.business.realistic"]
"""

from __future__ import annotations

from pathlib import Path

import yaml

from anovel.canon.hash import canonical_hash
from anovel.genre.identity import GenrePackIdentity, GenrePackMetadata

# --- Exceptions ---


class GenrePackRegistryError(Exception):
    """Base exception for GenrePack registry errors."""

    pass


class UnknownPackError(GenrePackRegistryError):
    """Raised when requested Pack ID does not exist in registry."""

    def __init__(self, pack_id: str):
        super().__init__(f"Unknown Pack: {pack_id}")
        self.pack_id = pack_id


class UnknownVersionError(GenrePackRegistryError):
    """Raised when requested version does not exist for Pack."""

    def __init__(self, pack_id: str, version: str, available_versions: list[str]):
        super().__init__(
            f"Unknown version {version} for Pack {pack_id}. "
            f"Available: {', '.join(available_versions)}"
        )
        self.pack_id = pack_id
        self.version = version
        self.available_versions = available_versions


class GenrePackHashMismatchError(GenrePackRegistryError):
    """Raised when caller-provided hash does not match registry hash."""

    def __init__(
        self, pack_id: str, version: str, caller_hash: str, registry_hash: str
    ):
        super().__init__(
            f"Hash mismatch for {pack_id} v{version}: "
            f"caller expects {caller_hash[:8]}..., "
            f"but registry declares {registry_hash[:8]}..."
        )
        self.pack_id = pack_id
        self.version = version
        self.caller_hash = caller_hash
        self.registry_hash = registry_hash


class RegistryPackFileMismatchError(GenrePackRegistryError):
    """Raised when Pack file content hash does not match registry declaration."""

    def __init__(self, pack_id: str, version: str, registry_hash: str, file_hash: str):
        super().__init__(
            f"Pack file mismatch for {pack_id} v{version}: "
            f"registry declares {registry_hash[:8]}..., "
            f"but Pack file computes to {file_hash[:8]}..."
        )
        self.pack_id = pack_id
        self.version = version
        self.registry_hash = registry_hash
        self.file_hash = file_hash


class UndeclaredExtensionError(GenrePackRegistryError):
    """Raised when extension namespace is not declared in Pack."""

    def __init__(self, pack_id: str, version: str, extension: str):
        super().__init__(f"Undeclared extension '{extension}' for {pack_id} v{version}")
        self.pack_id = pack_id
        self.version = version
        self.extension = extension


# --- Registry ---


class GenrePackRegistry:
    """
    GenrePack registry with three-way hash verification.

    Loads Pack metadata from registry.yaml and performs strict validation:
    1. Registry declares (pack_id, version, content_hash)
    2. Pack file content must compute to same hash
    3. Caller-provided identity must match registry

    Attributes:
        registry_path: Path to registry YAML file
        specs_root: Root directory for Pack YAML files
        _index: Internal index of Pack metadata by (pack_id, version)

    Example:
        >>> registry = GenrePackRegistry.load_from_file("specs/genres/registry.yaml")
        >>> identity = GenrePackIdentity("urban.business.realistic", "1.0.0", "abc...")
        >>> metadata = registry.get_pack(identity)
    """

    def __init__(
        self,
        registry_path: Path,
        specs_root: Path,
        index: dict[tuple[str, str], GenrePackMetadata],
    ):
        """Internal constructor. Use load_from_file() to create instances."""
        self.registry_path = registry_path
        self.specs_root = specs_root
        self._index = index

    @classmethod
    def load_from_file(
        cls, registry_path: str | Path, specs_root: str | Path | None = None
    ) -> GenrePackRegistry:
        """
        Load registry from YAML file.

        Args:
            registry_path: Path to registry.yaml
            specs_root: Root directory for Pack files (default: parent of registry_path)

        Returns:
            Loaded GenrePackRegistry instance

        Raises:
            FileNotFoundError: If registry file does not exist
            ValueError: If registry format is invalid
        """
        registry_path = Path(registry_path)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry not found: {registry_path}")

        if specs_root is None:
            specs_root = registry_path.parent
        else:
            specs_root = Path(specs_root)

        with open(registry_path, encoding="utf-8") as f:
            registry_data = yaml.safe_load(f)

        if not isinstance(registry_data, dict) or "packs" not in registry_data:
            raise ValueError("Registry must contain 'packs' key")

        index: dict[tuple[str, str], GenrePackMetadata] = {}

        for pack_entry in registry_data["packs"]:
            identity = GenrePackIdentity(
                pack_id=pack_entry["pack_id"],
                version=pack_entry["version"],
                content_hash=pack_entry["content_hash"],
            )

            metadata = GenrePackMetadata(
                identity=identity,
                pack_file_path=pack_entry["pack_file_path"],
                extension_namespaces=pack_entry.get("extension_namespaces", []),
                world_anchors=pack_entry.get("world_anchors", []),
            )

            key = (identity.pack_id, identity.version)
            if key in index:
                raise ValueError(
                    f"Duplicate Pack entry: {identity.pack_id} v{identity.version}"
                )
            index[key] = metadata

        return cls(registry_path, specs_root, index)

    def get_pack(self, pack_identity: GenrePackIdentity) -> GenrePackMetadata:
        """
        Get Pack metadata with three-way hash verification.

        Performs strict validation:
        1. Check Pack exists in registry
        2. Verify caller hash matches registry hash
        3. Load Pack file and verify content hash
        4. Validate extension namespaces

        Args:
            pack_identity: Pack identity with (pack_id, version, content_hash)

        Returns:
            GenrePackMetadata with validated identity

        Raises:
            UnknownPackError: If pack_id not in registry
            UnknownVersionError: If version not found for pack_id
            GenrePackHashMismatchError: If caller hash != registry hash
            RegistryPackFileMismatchError: If file hash != registry hash
            UndeclaredExtensionError: If Pack uses undeclared extension
        """
        # Step 1: Registry lookup
        key = (pack_identity.pack_id, pack_identity.version)
        if pack_identity.pack_id not in {k[0] for k in self._index.keys()}:
            raise UnknownPackError(pack_identity.pack_id)

        if key not in self._index:
            available_versions = [
                v for pid, v in self._index.keys() if pid == pack_identity.pack_id
            ]
            raise UnknownVersionError(
                pack_identity.pack_id, pack_identity.version, available_versions
            )

        registry_metadata = self._index[key]
        registry_hash = registry_metadata.identity.content_hash

        # Step 2: Caller hash verification
        caller_hash = pack_identity.content_hash
        if caller_hash != registry_hash:
            raise GenrePackHashMismatchError(
                pack_identity.pack_id,
                pack_identity.version,
                caller_hash,
                registry_hash,
            )

        # Step 3: Pack file hash verification
        pack_file_path = self.specs_root / registry_metadata.pack_file_path
        if not pack_file_path.exists():
            raise FileNotFoundError(f"Pack file not found: {pack_file_path}")

        with open(pack_file_path, encoding="utf-8") as f:
            pack_content = yaml.safe_load(f)

        # Extract hashable content (exclude content_hash field)
        hashable_content = {
            "pack_id": pack_content["pack_id"],
            "version": pack_content["version"],
            "extension_schemas": pack_content.get("extension_schemas", []),
            "transition_rules": pack_content.get("transition_rules", []),
            "world_mechanics": pack_content.get("world_mechanics", {}),
            "quality_rubric": pack_content.get("quality_rubric", {}),
        }

        file_hash = canonical_hash(hashable_content)

        if registry_hash != file_hash:
            raise RegistryPackFileMismatchError(
                pack_identity.pack_id,
                pack_identity.version,
                registry_hash,
                file_hash,
            )

        # Step 4: Extension namespace validation
        # Verify declared extension_namespaces match extension_schemas
        declared_namespaces = set(registry_metadata.extension_namespaces)
        schema_namespaces = set()
        for schema in pack_content.get("extension_schemas", []):
            if isinstance(schema, dict) and "namespace" in schema:
                schema_namespaces.add(schema["namespace"])

        if declared_namespaces != schema_namespaces:
            raise ValueError(
                f"Extension namespace mismatch for {pack_identity.pack_id}: "
                f"declared {declared_namespaces}, schemas define {schema_namespaces}"
            )

        return registry_metadata

    def list_packs(self) -> list[GenrePackMetadata]:
        """List all registered Packs."""
        return list(self._index.values())

    def get_versions(self, pack_id: str) -> list[str]:
        """Get all available versions for a Pack ID."""
        return [v for pid, v in self._index.keys() if pid == pack_id]
