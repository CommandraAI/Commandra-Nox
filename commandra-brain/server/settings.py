"""
Runtime settings for the Commandra Brain server. The active AI provider is
selected here: MockProvider by default (so the whole Brain works with zero
external dependencies), OllamaProvider once a user has Ollama running
locally and switches AI_PROVIDER=ollama (see docs/OLLAMA_SETUP.md).
"""

from __future__ import annotations

import os

from providers.ai_provider import AIProvider
from providers.mock_provider import MockProvider
from providers.ollama_provider import DEFAULT_BASE_URL, DEFAULT_MODEL, OllamaProvider

_state: dict[str, AIProvider] = {}


def build_provider_from_env() -> AIProvider:
    provider_name = os.environ.get("AI_PROVIDER", "mock").lower()
    if provider_name == "ollama":
        return OllamaProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL),
            model=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL),
        )
    return MockProvider()


def get_provider() -> AIProvider:
    if "provider" not in _state:
        _state["provider"] = build_provider_from_env()
    return _state["provider"]


def set_provider(provider: AIProvider) -> None:
    _state["provider"] = provider
