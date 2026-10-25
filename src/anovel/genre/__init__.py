"""
ANovelOS Genre Pack System.

Provides GenrePack identity, registry, and project binding services.
Implements ADR-007 extension namespace and state transition contracts.

Public API:
    Types:
        GenrePackIdentity, GenrePackMetadata, ProjectGenreBinding
    Operations:
        GenrePackRegistry.get_pack()
        ProjectGenreBindingService.bind_pack(), get_binding()
    Exceptions:
        UnknownPackError, UnknownVersionError, UndeclaredExtensionError
        GenrePackHashMismatchError, RegistryPackFileMismatchError

Contract: V2-013 Implementation Contract
"""

from anovel.genre.identity import (
    GenrePackIdentity,
    GenrePackMetadata,
    ProjectGenreBinding,
)

__all__ = [
    "GenrePackIdentity",
    "GenrePackMetadata",
    "ProjectGenreBinding",
]
