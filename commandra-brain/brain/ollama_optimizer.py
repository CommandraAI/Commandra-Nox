"""
Ollama Optimizer -- sits directly below the Prompt Compiler. Every request
that will actually reach Ollama passes through here first: this is where
the compiled prompt gets fitted to the specific model's context window,
temperature is chosen, retries are planned, and streaming is configured.
The Prompt Compiler decides *what* to say; this decides *how* to say it to
this particular model, in this particular provider, reliably.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from providers.model_profiles import ModelProfile, detect_profile

CHARS_PER_TOKEN = 4


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: list[float] = field(default_factory=lambda: [0.5, 2.0, 5.0])

    def delay_for(self, attempt: int) -> float:
        idx = min(attempt, len(self.backoff_seconds) - 1)
        return self.backoff_seconds[idx]


@dataclass
class OptimizedRequest:
    prompt: str
    system: str
    temperature: float
    max_output_tokens: int
    stream: bool
    model_profile: ModelProfile
    retry_policy: RetryPolicy
    compression_applied: bool
    original_tokens: int
    final_tokens: int

    def as_dict(self) -> dict:
        return {
            "temperature": self.temperature,
            "maxOutputTokens": self.max_output_tokens,
            "stream": self.stream,
            "modelProfile": self.model_profile.as_dict(),
            "retryPolicy": {"maxAttempts": self.retry_policy.max_attempts, "backoffSeconds": self.retry_policy.backoff_seconds},
            "compressionApplied": self.compression_applied,
            "originalTokens": self.original_tokens,
            "finalTokens": self.final_tokens,
        }


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def compress_context(prompt: str, budget_tokens: int) -> tuple[str, bool]:
    """Context Compression -- if the compiled prompt exceeds the model's
    usable input budget, drop from the middle of the "Repository context"
    section first (least recently referenced material) rather than
    truncating the user's actual request or the coding standards, which
    must always survive intact."""
    if _estimate_tokens(prompt) <= budget_tokens:
        return prompt, False

    budget_chars = budget_tokens * CHARS_PER_TOKEN
    marker = "## Repository context"
    idx = prompt.find(marker)
    if idx == -1:
        # No identifiable context section -- fall back to a tail-preserving trim.
        return prompt[-budget_chars:], True

    next_section_idx = prompt.find("\n## ", idx + len(marker))
    section_end = next_section_idx if next_section_idx != -1 else len(prompt)
    head, context_section, tail = prompt[:idx], prompt[idx:section_end], prompt[section_end:]

    overflow_chars = len(prompt) - budget_chars
    trimmed_context = context_section[: max(0, len(context_section) - overflow_chars)]
    if trimmed_context and not trimmed_context.endswith("\n"):
        trimmed_context += "\n...[context truncated by Ollama Optimizer to fit the model's window]...\n"

    return head + trimmed_context + tail, True


def temperature_for(task_kind: str, profile: ModelProfile) -> "TemperatureProfile":
    return _TEMPERATURE_PROFILES.get(task_kind, _TEMPERATURE_PROFILES["default"])(profile)


@dataclass
class TemperatureProfile:
    value: float
    rationale: str


_TEMPERATURE_PROFILES = {
    "default": lambda p: TemperatureProfile(p.preferred_temperature, "Model's preferred baseline temperature."),
    "code_generation": lambda p: TemperatureProfile(min(p.preferred_temperature, 0.2), "Low temperature for deterministic, compilable code."),
    "refactoring": lambda p: TemperatureProfile(min(p.preferred_temperature, 0.15), "Very low temperature -- refactors must preserve behavior."),
    "brainstorm": lambda p: TemperatureProfile(max(p.preferred_temperature, 0.7), "Higher temperature to encourage varied architectural options."),
    "explanation": lambda p: TemperatureProfile(0.4, "Moderate temperature for natural, readable explanations."),
}


class OllamaOptimizer:
    """The single choke point every compiled prompt passes through before
    being sent to Ollama."""

    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self.retry_policy = retry_policy or RetryPolicy()

    def optimize(
        self,
        compiled_system: str,
        compiled_prompt: str,
        model_name: str,
        task_kind: str = "code_generation",
        stream: bool = False,
        reserved_output_tokens: int | None = None,
    ) -> OptimizedRequest:
        profile = detect_profile(model_name)
        reserved = reserved_output_tokens or profile.max_output_tokens
        input_budget = max(512, profile.context_window_tokens - reserved)

        original_tokens = _estimate_tokens(compiled_prompt) + _estimate_tokens(compiled_system)
        compressed_prompt, compressed = compress_context(compiled_prompt, input_budget)
        final_tokens = _estimate_tokens(compressed_prompt) + _estimate_tokens(compiled_system)

        temp_profile = temperature_for(task_kind, profile)

        return OptimizedRequest(
            prompt=compressed_prompt,
            system=compiled_system if profile.supports_system_prompt else "",
            temperature=temp_profile.value,
            max_output_tokens=profile.max_output_tokens,
            stream=stream and profile.context_window_tokens >= 8000,
            model_profile=profile,
            retry_policy=self.retry_policy,
            compression_applied=compressed,
            original_tokens=original_tokens,
            final_tokens=final_tokens,
        )
