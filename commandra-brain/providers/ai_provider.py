"""
AIProvider — the abstraction boundary between Commandra Brain and any text
generation backend.

Commandra Nox Brain never calls a model API directly. Every module that needs
text generation goes through an AIProvider implementation. This keeps the
Brain fully backend-agnostic: today it ships with a MockProvider for local
development and an OllamaProvider (interface-complete, ready to use) for
real local inference. No cloud provider is ever implemented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass
class GenerationRequest:
    """A single request to generate text from a prompt."""

    prompt: str
    system: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 2048
    stop: Optional[list[str]] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class GenerationResult:
    """The result of a generation call, plus bookkeeping the Brain can use."""

    text: str
    provider: str
    model: str
    prompt_tokens_estimate: int = 0
    completion_tokens_estimate: int = 0
    raw: Optional[dict] = None


class AIProviderError(RuntimeError):
    """Raised when a provider cannot fulfil a generation request."""


class AIProvider(ABC):
    """
    Abstract base class every model backend must implement.

    The Brain only ever interacts with these three methods. Implementations
    are free to talk to a local subprocess, an HTTP server, or anything else
    -- as long as it stays local and offline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short machine-readable provider name, e.g. 'mock', 'ollama'."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is currently reachable/usable."""

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a complete response for the given request."""

    @abstractmethod
    def stream(self, request: GenerationRequest) -> Iterator[str]:
        """Yield response text incrementally (token/chunk at a time)."""

    def describe(self) -> dict:
        """Human-readable status block for the Model Manager UI."""
        return {
            "name": self.name,
            "available": self.is_available(),
        }
