"""
ANovelOS Genre Pack System.

Provides GenrePack identity, registry, project binding services, and hard policy engine.
Implements ADR-007 extension namespace and state transition contracts.

Public API:
    Types:
        GenrePackIdentity, GenrePackMetadata, ProjectGenreBinding
        NarrativeFact, OptionalStrategy, PolicyJudgment, StrategyJudgment
    Operations:
        GenrePackRegistry.get_pack()
        ProjectGenreBindingService.bind_pack(), get_binding()
        GenreHardPolicyEngine.judge_fact(), judge_optional_strategy()
    Exceptions:
        UnknownPackError, UnknownVersionError, UndeclaredExtensionError
        GenrePackHashMismatchError, RegistryPackFileMismatchError

Contract: V2-013 and V2-014 Implementation Contracts
"""

from anovel.genre.binding import ProjectGenreBindingService, ProjectNotBoundError
from anovel.genre.identity import (
    GenrePackIdentity,
    GenrePackMetadata,
    ProjectGenreBinding,
)
from anovel.genre.policy import (
    FactContextType,
    GenreHardPolicyEngine,
    NarrativeFact,
    OptionalStrategy,
    PolicyJudgment,
    PolicyVerdict,
    StrategyJudgment,
)
from anovel.genre.registry import (
    GenrePackHashMismatchError,
    GenrePackRegistry,
    RegistryPackFileMismatchError,
    UndeclaredExtensionError,
    UnknownPackError,
    UnknownVersionError,
)

__all__ = [
    # Identity
    "GenrePackIdentity",
    "GenrePackMetadata",
    "ProjectGenreBinding",
    # Registry
    "GenrePackRegistry",
    "UnknownPackError",
    "UnknownVersionError",
    "GenrePackHashMismatchError",
    "RegistryPackFileMismatchError",
    "UndeclaredExtensionError",
    # Binding service
    "ProjectGenreBindingService",
    "ProjectNotBoundError",
    # Policy engine
    "GenreHardPolicyEngine",
    "PolicyVerdict",
    "FactContextType",
    "NarrativeFact",
    "OptionalStrategy",
    "PolicyJudgment",
    "StrategyJudgment",
]
