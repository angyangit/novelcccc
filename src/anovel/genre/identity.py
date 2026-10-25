"""
GenrePack Identity Data Structures.

Implements ADR-007 GenrePack stable identity with immutable dataclasses:
- GenrePackIdentity: (pack_id, version, content_hash) triple
- GenrePackMetadata: Pack metadata with extension namespaces and world anchors
- ProjectGenreBinding: Immutable project-to-pack binding with traceability

All dataclasses are frozen to enforce immutability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from anovel.domain.identity import ProjectId

# --- Exceptions ---


class GenrePackIdentityError(ValueError):
    """Base exception for GenrePack identity validation errors."""

    pass


class InvalidPackIdError(GenrePackIdentityError):
    """Raised when pack_id format is invalid."""

    pass


class InvalidVersionError(GenrePackIdentityError):
    """Raised when version format is invalid."""

    pass


class InvalidContentHashError(GenrePackIdentityError):
    """Raised when content_hash format is invalid."""

    pass


# --- Data Structures ---


@dataclass(frozen=True)
class GenrePackIdentity:
    """
    Immutable GenrePack identity triple.

    Implements ADR-007 §1: Pack identity by (pack_id, version, content_hash).

    Attributes:
        pack_id: Stable logical ID (e.g., "urban.business.realistic")
                 Format: {category}.{subcategory}.{variant}
                 Must NOT contain version suffix (e.g., NOT "urban.business.realistic.v1")
        version: Semantic version (e.g., "1.0.0")
        content_hash: SHA-256 canonical hash of pack content (64 hex chars)

    Raises:
        InvalidPackIdError: If pack_id contains version suffix or invalid format
        InvalidVersionError: If version is not valid semantic version
        InvalidContentHashError: If content_hash is not 64 hex characters

    Example:
        >>> identity = GenrePackIdentity(
        ...     pack_id="urban.business.realistic",
        ...     version="1.0.0",
        ...     content_hash="a" * 64
        ... )
    """

    pack_id: str
    version: str
    content_hash: str

    def __post_init__(self) -> None:
        """Validate identity fields on construction."""
        # Validate pack_id format
        if not self.pack_id:
            raise InvalidPackIdError("pack_id cannot be empty")

        # Check for version suffix in pack_id (common mistake)
        if re.search(r"\.(v\d+|version)$", self.pack_id, re.IGNORECASE):
            raise InvalidPackIdError(
                f"pack_id must not contain version suffix: {self.pack_id}"
            )

        # Validate pack_id format: {category}.{subcategory}.{variant}
        if not re.match(r"^[a-z]+(\.[a-z]+)+$", self.pack_id):
            raise InvalidPackIdError(
                f"pack_id must match format {{category}}.{{subcategory}}.{{variant}}: {self.pack_id}"
            )

        # Validate version format (semantic versioning)
        if not re.match(r"^\d+\.\d+\.\d+$", self.version):
            raise InvalidVersionError(
                f"version must be semantic version (e.g., 1.0.0): {self.version}"
            )

        # Validate content_hash format (64 hex characters)
        if not re.match(r"^[a-f0-9]{64}$", self.content_hash):
            raise InvalidContentHashError(
                f"content_hash must be 64 hex characters: {self.content_hash}"
            )


@dataclass(frozen=True)
class GenrePackMetadata:
    """
    GenrePack metadata loaded from registry.

    Contains pack identity, file path reference, extension namespaces,
    and world anchors. Used by GenrePackRegistry.

    Attributes:
        identity: Pack identity triple
        pack_file_path: Relative path to Pack YAML file (e.g., "genres/urban_business_realistic_v1.yaml")
        extension_namespaces: List of extension namespaces provided by this Pack
        world_anchors: List of world anchors (P3: matches pack_id)

    Example:
        >>> metadata = GenrePackMetadata(
        ...     identity=GenrePackIdentity("urban.business.realistic", "1.0.0", "a" * 64),
        ...     pack_file_path="genres/urban_business_realistic_v1.yaml",
        ...     extension_namespaces=["urban", "business"],
        ...     world_anchors=["urban.business.realistic"]
        ... )
    """

    identity: GenrePackIdentity
    pack_file_path: str
    extension_namespaces: list[str]
    world_anchors: list[str]


@dataclass(frozen=True)
class ProjectGenreBinding:
    """
    Immutable project-to-GenrePack binding.

    Records which GenrePack a project is bound to, with timestamp and traceability.
    Once created, binding cannot be changed (projects must stay on their Pack version).

    Attributes:
        project_id: Project identifier
        pack_identity: Bound GenrePack identity
        bound_at: Binding timestamp (UTC)
        metadata: Optional traceability metadata (e.g., bound_by, reason)

    Example:
        >>> binding = ProjectGenreBinding(
        ...     project_id=ProjectId("project-123"),
        ...     pack_identity=GenrePackIdentity("urban.business.realistic", "1.0.0", "a" * 64),
        ...     bound_at=datetime.utcnow(),
        ...     metadata={"bound_by": "user-456"}
        ... )
    """

    project_id: ProjectId
    pack_identity: GenrePackIdentity
    bound_at: datetime
    metadata: dict[str, str] | None = None
