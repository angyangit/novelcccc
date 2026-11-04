"""Token counting abstraction for context budget management."""

from abc import ABC, abstractmethod

class TokenCounter(ABC):
    """Abstract token counter for different tokenizers per ADR-009.

    ADR-009 requirement: Use model-specific tokenizer, not cl100k_base as universal default.
    """

    @property
    @abstractmethod
    def encoding_name(self) -> str:
        """Return encoding name for logging."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        pass

class CL100kTokenCounter(TokenCounter):
    """OpenAI cl100k_base tokenizer (GPT-4 family)."""

    def __init__(self):
        import tiktoken
        self.encoding = tiktoken.get_encoding("cl100k_base")

    @property
    def encoding_name(self) -> str:
        return "cl100k_base"

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
