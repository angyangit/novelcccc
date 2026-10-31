"""Model Gateway for V2-019.

Unified interface for AI model providers with budget control and error handling.
"""

from .gateway import ModelGateway
from .mock_provider import MockProvider
from .models import (
    BudgetStatus,
    GenerationError,
    GenerationRequest,
    GenerationResult,
    ProviderAdapter,
)

__all__ = [
    "ModelGateway",
    "GenerationRequest",
    "GenerationResult",
    "GenerationError",
    "ProviderAdapter",
    "BudgetStatus",
    "MockProvider",
]
