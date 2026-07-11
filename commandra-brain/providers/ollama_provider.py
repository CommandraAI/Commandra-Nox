"""
OllamaProvider — real local-inference backend for Commandra Nox Brain.

This talks to a locally running Ollama server (default
http://localhost:11434) using Ollama's HTTP API. It is fully implemented and
ready to use the moment a user runs Ollama locally and points Commandra at
it -- see docs/OLLAMA_SETUP.md for setup instructions.

No cloud endpoints are ever contacted. If `base_url` is not local, that is a
user configuration choice (e.g. Ollama running on another machine on their
own network); Commandra never ships a remote/cloud default.
"""

from __future__ import annotations

import json
from typing import Iterator, Optional

import httpx

from providers.ai_provider import (
    AIProvider,
    AIProviderError,
    GenerationRequest,
    GenerationResult,
)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"


class OllamaProvider(AIProvider):
    """Provider backed by a local Ollama server."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc

    def _payload(self, request: GenerationRequest, stream: bool) -> dict:
        return {
            "model": self.model,
            "prompt": request.prompt,
            "system": request.system or "",
            "stream": stream,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                **({"stop": request.stop} if request.stop else {}),
            },
        }

    def generate(self, request: GenerationRequest) -> GenerationResult:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json=self._payload(request, stream=False),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"Ollama request failed ({self.base_url}, model={self.model}): {exc}"
            ) from exc

        return GenerationResult(
            text=data.get("response", ""),
            provider=self.name,
            model=self.model,
            prompt_tokens_estimate=data.get("prompt_eval_count", 0),
            completion_tokens_estimate=data.get("eval_count", 0),
            raw=data,
        )

    def stream(self, request: GenerationRequest) -> Iterator[str]:
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=self._payload(request, stream=True),
                timeout=self.timeout,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("response"):
                        yield chunk["response"]
                    if chunk.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"Ollama streaming request failed ({self.base_url}): {exc}"
            ) from exc

    def describe(self) -> dict:
        base = super().describe()
        base.update({"base_url": self.base_url, "model": self.model})
        return base


def build_ollama_provider(
    base_url: Optional[str] = None, model: Optional[str] = None
) -> OllamaProvider:
    """Factory used by settings/config wiring."""
    return OllamaProvider(
        base_url=base_url or DEFAULT_BASE_URL,
        model=model or DEFAULT_MODEL,
    )
