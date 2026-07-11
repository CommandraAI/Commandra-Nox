"""
Reasoning Engine — Commandra Nox Monster Edition.

Forces the Brain to think before generating code. Two modes:

  1. Fast mode (default): template-based, deterministic, zero latency.
  2. Deep mode: optional LLM-powered reasoning that calls the provider to
     produce a richer analysis. Activated when DEEP_REASONING=true or when
     request complexity is COMPLEX.

Deep mode makes the model reason about the problem BEFORE coding — a form
of self-induced chain-of-thought that dramatically improves small-model
output quality on non-trivial requests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from context.context_engine import ContextSelection
from planning.planning_engine import Complexity, Plan


@dataclass
class ReasoningTrace:
    requirement_analysis: str
    architecture_notes: str
    approach: str
    alternatives_considered: str
    validation_criteria: str
    # Deep-mode extras
    llm_reasoning: str | None = None
    deep_mode: bool = False

    def as_prompt_block(self) -> str:
        parts = [
            "## Brain Reasoning",
            f"**Requirement analysis:** {self.requirement_analysis}",
            f"**Architecture notes:** {self.architecture_notes}",
            f"**Chosen approach:** {self.approach}",
            f"**Alternatives considered:** {self.alternatives_considered}",
            f"**Validation criteria:** {self.validation_criteria}",
        ]
        if self.llm_reasoning:
            parts.append(f"\n**Deep reasoning (LLM-generated):**\n{self.llm_reasoning}")
        return "\n\n".join(parts)

    def as_dict(self) -> dict:
        d = {
            "requirementAnalysis": self.requirement_analysis,
            "architectureNotes": self.architecture_notes,
            "approach": self.approach,
            "alternativesConsidered": self.alternatives_considered,
            "validationCriteria": self.validation_criteria,
            "deepMode": self.deep_mode,
        }
        if self.llm_reasoning:
            d["llmReasoning"] = self.llm_reasoning
        return d


_DEEP_REASONING_PROMPT = """\
You are Commandra Nox's internal reasoning engine. Your job is to analyze a
software request and produce a structured reasoning trace BEFORE any code is
written.

Request: {request}

Available files: {file_summary}

Produce a concise reasoning trace covering:
1. What EXACTLY needs to change (no assumptions — only what's explicitly requested)
2. Which files are affected and why
3. The safest implementation path that minimizes risk of breakage
4. What could go wrong and how to prevent it
5. How to verify the output is correct

Be precise. Be brief. No code yet — only reasoning.
"""


class ReasoningEngine:
    """Produces a reasoning trace before any code generation happens."""

    def __init__(self) -> None:
        self._provider = None  # injected by Brain after construction

    def set_provider(self, provider) -> None:  # type: ignore[no-untyped-def]
        self._provider = provider

    def reason(
        self,
        plan: Plan,
        context: ContextSelection,
        memory_block: str,
        *,
        deep: bool | None = None,
    ) -> ReasoningTrace:
        files = context.file_paths()
        file_summary = (
            f"{len(files)} relevant file(s): {', '.join(files[:8])}"
            + ("..." if len(files) > 8 else "")
            if files
            else "No repository indexed."
        )

        # ── fast template-based trace ────────────────────────────────────────
        requirement_analysis = (
            f'Request classified as "{plan.intent.value}" with estimated '
            f'"{plan.complexity.value}" complexity. {file_summary}.'
        )

        architecture_notes = (
            memory_block
            if memory_block
            else "No prior architecture notes for this repository."
        )

        approach = (
            f"Execute plan step by step via agents "
            f"({', '.join(sorted({s.agent for s in plan.steps}))}), "
            "grounding every decision in the retrieved context."
        )

        alternatives_considered = (
            "Considered full-repo context dump: rejected — exceeds context window and dilutes relevance. "
            "Considered skipping reasoning: rejected — degrades output quality on small models."
        )

        validation_criteria = (
            "Response must reference only retrieved files, respect project conventions, "
            "and leave the codebase in a buildable state."
        )

        # ── deep LLM reasoning (optional) ────────────────────────────────────
        use_deep = deep
        if use_deep is None:
            use_deep = (
                plan.complexity == Complexity.COMPLEX
                or os.environ.get("DEEP_REASONING", "false").lower() == "true"
            )

        llm_reasoning: str | None = None
        if use_deep and self._provider is not None:
            try:
                from providers.ai_provider import GenerationRequest
                prompt = _DEEP_REASONING_PROMPT.format(
                    request=plan.request[:800],
                    file_summary=file_summary,
                )
                result = self._provider.generate(
                    GenerationRequest(
                        prompt=prompt,
                        system="You are a concise software reasoning engine. Think step by step.",
                        temperature=0.1,
                        max_tokens=512,
                    )
                )
                llm_reasoning = result.text.strip()
            except Exception:
                # Deep reasoning is best-effort — never block the main pipeline
                pass

        return ReasoningTrace(
            requirement_analysis=requirement_analysis,
            architecture_notes=architecture_notes,
            approach=approach,
            alternatives_considered=alternatives_considered,
            validation_criteria=validation_criteria,
            llm_reasoning=llm_reasoning,
            deep_mode=llm_reasoning is not None,
        )
