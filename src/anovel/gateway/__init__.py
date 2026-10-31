"""Model Gateway for V2-019.

Unified interface for AI model providers with budget control and error handling.
"""

from .gateway import ModelGateway
from .models import (
    GenerationRequest,
    GenerationResult,
    GenerationError,
    ProviderAdapter,
    BudgetStatus,
)
from .mock_provider import MockProvider

__all__ = [
    "ModelGateway",
    "GenerationRequest",
    "GenerationResult",
    "GenerationError",
    "ProviderAdapter",
    "BudgetStatus",
    "MockProvider",
]
