"""
Model Profiles -- Commandra optimizes differently depending on which local
coding model Ollama is serving. Different models have different effective
context windows, instruction-following styles, and blind spots; this is the
lookup table the Ollama Optimizer and Prompt Compiler consult so the same
request produces a prompt tuned to the model actually answering it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelProfile:
    key: str
    display_name: str
    context_window_tokens: int
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    preferred_temperature: float = 0.2
    prompt_style: str = "structured_sections"  # or "minimal", "explicit_stepwise"
    supports_system_prompt: bool = True
    max_output_tokens: int = 2048

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "displayName": self.display_name,
            "contextWindowTokens": self.context_window_tokens,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "preferredTemperature": self.preferred_temperature,
            "promptStyle": self.prompt_style,
            "supportsSystemPrompt": self.supports_system_prompt,
            "maxOutputTokens": self.max_output_tokens,
        }


_PROFILES: dict[str, ModelProfile] = {
    "qwen2.5-coder": ModelProfile(
        key="qwen2.5-coder", display_name="Qwen Coder", context_window_tokens=32000,
        strengths=["multi-language breadth", "long context retention", "instruction following"],
        weaknesses=["can be verbose without explicit brevity constraints"],
        preferred_temperature=0.2, prompt_style="structured_sections", max_output_tokens=4096,
    ),
    "deepseek-coder": ModelProfile(
        key="deepseek-coder", display_name="DeepSeek Coder", context_window_tokens=16000,
        strengths=["strong at algorithmic reasoning", "good at refactoring tasks"],
        weaknesses=["smaller effective context; needs tighter file selection", "occasionally drops import statements"],
        preferred_temperature=0.15, prompt_style="explicit_stepwise", max_output_tokens=2048,
    ),
    "starcoder2": ModelProfile(
        key="starcoder2", display_name="StarCoder2", context_window_tokens=16000,
        strengths=["broad language coverage", "fill-in-the-middle completions"],
        weaknesses=["weaker multi-step reasoning; benefits from decomposed plans", "less reliable instruction following"],
        preferred_temperature=0.1, prompt_style="minimal", max_output_tokens=2048,
    ),
    "codellama": ModelProfile(
        key="codellama", display_name="Code Llama", context_window_tokens=16000,
        strengths=["stable general-purpose code generation", "decent at Python/JS/C-family"],
        weaknesses=["older training cutoff; may miss newer framework APIs", "needs explicit standards to stay consistent"],
        preferred_temperature=0.2, prompt_style="structured_sections", max_output_tokens=2048,
    ),
}

_DEFAULT = ModelProfile(
    key="generic", display_name="Unknown/Generic Model", context_window_tokens=8000,
    strengths=[], weaknesses=["capabilities unknown -- treat conservatively (small context, explicit instructions)"],
    preferred_temperature=0.2, prompt_style="structured_sections", max_output_tokens=1024,
)


def detect_profile(model_name: str) -> ModelProfile:
    """Matches a raw Ollama model tag (e.g. 'qwen2.5-coder:7b-instruct')
    against known profiles by prefix, falling back to a conservative
    generic profile for unrecognized models."""
    lowered = model_name.lower()
    for key, profile in _PROFILES.items():
        if key in lowered:
            return profile
    if "qwen" in lowered:
        return _PROFILES["qwen2.5-coder"]
    if "deepseek" in lowered:
        return _PROFILES["deepseek-coder"]
    if "starcoder" in lowered:
        return _PROFILES["starcoder2"]
    if "codellama" in lowered or "code-llama" in lowered:
        return _PROFILES["codellama"]
    return _DEFAULT


def available_profiles() -> list[str]:
    return sorted(_PROFILES.keys())
