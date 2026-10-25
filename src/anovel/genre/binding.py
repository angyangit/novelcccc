"""
Project-to-GenrePack binding service.

Implements ADR-007 project binding with immutability and traceability:
- bind_pack(): Create immutable project-to-pack binding
- get_binding(): Query binding for project
- Binding immutability: once bound, project cannot change Pack
- Cross-project isolation: bindings are project-scoped

Storage: In-memory dict for P3 (future: persistent storage)
"""

from __future__ import annotations

from datetime import UTC, datetime

from anovel.domain.identity import ProjectId
from anovel.genre.identity import GenrePackIdentity, ProjectGenreBinding
from anovel.genre.registry import GenrePackRegistry

# --- Exceptions ---


class ProjectGenreBindingError(Exception):
    """Base exception for project genre binding errors."""

    pass


class ProjectAlreadyBoundError(ProjectGenreBindingError):
    """Raised when attempting to bind project that is already bound."""

    def __init__(self, project_id: ProjectId, existing_binding: ProjectGenreBinding):
        super().__init__(
            f"Project {project_id} already bound to "
            f"{existing_binding.pack_identity.pack_id} v{existing_binding.pack_identity.version}"
        )
        self.project_id = project_id
        self.existing_binding = existing_binding


class ProjectNotBoundError(ProjectGenreBindingError):
    """Raised when querying binding for unbound project."""

    def __init__(self, project_id: ProjectId):
        super().__init__(f"Project {project_id} is not bound to any GenrePack")
        self.project_id = project_id


# --- Binding Service ---


class ProjectGenreBindingService:
    """
    Project-to-GenrePack binding service with immutability enforcement.

    Manages project bindings with the following guarantees:
    - Immutability: Once bound, project cannot change Pack (no rebinding)
    - Traceability: Bindings record timestamp and metadata
    - Isolation: Bindings are project-scoped (no cross-project queries)
    - Verification: Pack identity is verified through registry before binding

    Storage: In-memory dict for P3 (future: persistent storage in Canon DB)

    Attributes:
        registry: GenrePackRegistry for Pack verification
        _bindings: Internal storage of bindings by project_id

    Example:
        >>> service = ProjectGenreBindingService(registry)
        >>> identity = GenrePackIdentity("urban.business.realistic", "1.0.0", "abc...")
        >>> binding = service.bind_pack(ProjectId("proj-1"), identity)
        >>> retrieved = service.get_binding(ProjectId("proj-1"))
        >>> assert retrieved == binding
    """

    def __init__(self, registry: GenrePackRegistry):
        """
        Initialize binding service.

        Args:
            registry: GenrePackRegistry for Pack verification
        """
        self.registry = registry
        self._bindings: dict[ProjectId, ProjectGenreBinding] = {}

    def bind_pack(
        self,
        project_id: ProjectId,
        pack_identity: GenrePackIdentity,
        metadata: dict[str, str] | None = None,
    ) -> ProjectGenreBinding:
        """
        Bind project to GenrePack with identity verification.

        Creates immutable binding after verifying Pack identity through registry.
        If project is already bound, raises ProjectAlreadyBoundError.

        Args:
            project_id: Project to bind
            pack_identity: Pack identity to bind to (must pass registry verification)
            metadata: Optional traceability metadata (e.g., bound_by, reason)

        Returns:
            Created ProjectGenreBinding

        Raises:
            ProjectAlreadyBoundError: If project already has binding
            UnknownPackError: If Pack not in registry
            UnknownVersionError: If version not found for Pack
            GenrePackHashMismatchError: If hash verification fails
        """
        # Check if already bound
        if project_id in self._bindings:
            raise ProjectAlreadyBoundError(project_id, self._bindings[project_id])

        # Verify Pack identity through registry (three-way hash check)
        self.registry.get_pack(pack_identity)

        # Create immutable binding
        binding = ProjectGenreBinding(
            project_id=project_id,
            pack_identity=pack_identity,
            bound_at=datetime.now(UTC),
            metadata=metadata,
        )

        # Store binding
        self._bindings[project_id] = binding

        return binding

    def get_binding(self, project_id: ProjectId) -> ProjectGenreBinding:
        """
        Get binding for project.

        Args:
            project_id: Project to query

        Returns:
            ProjectGenreBinding for project

        Raises:
            ProjectNotBoundError: If project has no binding
        """
        if project_id not in self._bindings:
            raise ProjectNotBoundError(project_id)
        return self._bindings[project_id]

    def has_binding(self, project_id: ProjectId) -> bool:
        """
        Check if project has binding.

        Args:
            project_id: Project to check

        Returns:
            True if project is bound, False otherwise
        """
        return project_id in self._bindings

    def list_bindings(self) -> list[ProjectGenreBinding]:
        """
        List all bindings.

        Returns:
            List of all ProjectGenreBinding instances
        """
        return list(self._bindings.values())

    def get_bindings_for_pack(
        self, pack_id: str, version: str | None = None
    ) -> list[ProjectGenreBinding]:
        """
        Get all bindings for a specific Pack (traceability query).

        Args:
            pack_id: Pack ID to query
            version: Optional version filter

        Returns:
            List of bindings for the Pack
        """
        results = []
        for binding in self._bindings.values():
            if binding.pack_identity.pack_id == pack_id:
                if version is None or binding.pack_identity.version == version:
                    results.append(binding)
        return results
