"""
Prompt Compiler — Commandra Nox Monster Edition.

The single choke point through which every prompt to Ollama must pass.
This edition is tuned for SMALL models (3B–7B parameters) and forces them
to produce weapons-grade output through extreme structural discipline:

  1. Chain-of-thought preamble — model thinks before it acts.
  2. Anti-hallucination rules — model is forbidden from inventing context.
  3. Completeness enforcement — no placeholders, no stubs, ever.
  4. Output contract — rigid format the response optimizer can parse.

Small models are not weak. They are undertrained on discipline. This
compiler provides the discipline they lack out of the box.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from context.context_engine import ContextSelection
from planning.planning_engine import Plan


# ---------------------------------------------------------------------------
# Monster coding standards — injected into EVERY prompt
# ---------------------------------------------------------------------------

MONSTER_CODING_STANDARDS = [
    # Identity
    "You are Commandra Nox — a weapons-grade software intelligence operating with extreme precision.",
    # Completeness contract
    "NEVER produce incomplete code. No '...', no placeholders, no '# TODO', no '// rest unchanged'.",
    "Every function body must be FULLY implemented. Every import must resolve. Every edge case handled.",
    # Grounding contract
    "Ground every statement in the retrieved repository context. NEVER invent APIs, functions, or files "
    "that are not explicitly shown in the context. If something is unclear, use the safest correct approach.",
    # Output format
    "Return each modified or new file in its own fenced code block labeled with the exact file path.",
    "Format: ```language\\n// path: relative/file/path\\n<full file content>\\n```",
    # Chain-of-thought discipline
    "BEFORE writing any code: state your implementation approach in 1-2 sentences. Then execute.",
    # Verification discipline
    "After writing code, check: every function called is defined, every import exists, syntax is valid.",
    # Style discipline
    "Match the EXACT code style, naming conventions, and patterns found in the repository context.",
    "Prefer minimal targeted changes over broad rewrites unless a rewrite was explicitly requested.",
]

CHAIN_OF_THOUGHT_PREAMBLE = (
    "## Chain-of-Thought Instructions\n"
    "Work through this request step by step:\n"
    "1. **Understand**: What exactly is being asked? What must change?\n"
    "2. **Locate**: Which files and functions are involved? (use context below)\n"
    "3. **Plan**: What is the safest, most complete implementation path?\n"
    "4. **Execute**: Write complete, production-ready code for each affected file.\n"
    "5. **Verify**: Does every import resolve? Is every function body complete?\n"
)


@dataclass
class PreviousAction:
    step: str
    detail: str


@dataclass
class CompiledPrompt:
    system: str
    prompt: str
    sections: dict[str, str] = field(default_factory=dict)
    estimated_tokens: int = 0

    def as_dict(self) -> dict:
        return {
            "system": self.system,
            "prompt": self.prompt,
            "sections": list(self.sections.keys()),
            "estimatedTokens": self.estimated_tokens,
        }


class PromptCompiler:
    """Compiles every context source into one optimized, discipline-enforced prompt."""

    def __init__(self, coding_standards: list[str] | None = None) -> None:
        self.coding_standards = coding_standards or MONSTER_CODING_STANDARDS

    def compile(
        self,
        *,
        system_prompt: str,
        specialty_instruction: str,
        request: str,
        plan: Plan,
        reasoning_block: str,
        context: ContextSelection,
        memory_block: str,
        selected_files: list[str] | None = None,
        previous_actions: list[PreviousAction] | None = None,
        extra_standards: list[str] | None = None,
    ) -> CompiledPrompt:
        sections: dict[str, str] = {}

        # Chain-of-thought preamble always first
        sections["Chain-of-Thought"] = CHAIN_OF_THOUGHT_PREAMBLE

        sections["Reasoning"] = reasoning_block
        sections["Plan"] = self._format_plan(plan)
        sections["Repository context"] = (
            context.as_prompt_block()
            or "(No repository indexed yet — respond from general knowledge only, clearly labeling any assumptions.)"
        )

        if selected_files:
            sections["Selected files"] = "\n".join(f"- {f}" for f in selected_files)

        if memory_block:
            sections["Project memory"] = memory_block

        if previous_actions:
            sections["Previous actions"] = "\n".join(
                f"- [{a.step}] {a.detail}" for a in previous_actions
            )

        standards = self.coding_standards + (extra_standards or [])
        sections["Operating standards"] = "\n".join(f"{i+1}. {s}" for i, s in enumerate(standards))

        # User request is always last so it's nearest to the model's generation start
        sections["Your specialty"] = specialty_instruction
        sections["User request"] = f'"""\n{request}\n"""'

        body = "\n\n".join(
            f"## {title}\n{content}" for title, content in sections.items() if content
        )
        estimated_tokens = len(body) // 4

        return CompiledPrompt(
            system=system_prompt,
            prompt=body,
            sections=sections,
            estimated_tokens=estimated_tokens,
        )

    @staticmethod
    def _format_plan(plan: Plan) -> str:
        lines = [
            f"Intent: {plan.intent.value} | Complexity: {plan.complexity.value}",
            "",
        ]
        for s in plan.steps:
            status = "✓" if s.done else "○"
            lines.append(f"  {status} Step {s.id}: [{s.agent}] {s.title}")
        return "\n".join(lines)
