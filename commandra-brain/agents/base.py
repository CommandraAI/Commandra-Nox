"""
Base Agent -- shared contract for every specialist agent in Commandra's
multi-agent architecture. Each agent gets a slice of the reasoning trace,
the selected repository context, and long-term memory, then produces one
prompt tailored to its specialty. All actual text generation still goes
through the shared AIProvider -- agents never call a model directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from context.context_engine import ContextSelection
from planning.planning_engine import Plan
from providers.ai_provider import AIProvider, GenerationRequest
from brain.ollama_optimizer import OllamaOptimizer
from brain.prompt_compiler import PreviousAction, PromptCompiler
from brain.reasoning_engine import ReasoningTrace


@dataclass
class AgentInput:
    request: str
    plan: Plan
    reasoning: ReasoningTrace
    context: ContextSelection
    memory_block: str
    selected_files: list[str] | None = None
    previous_actions: list[PreviousAction] | None = None


@dataclass
class AgentOutput:
    agent: str
    text: str
    compiled_prompt_tokens: int = 0


_COMPILER = PromptCompiler()
_OPTIMIZER = OllamaOptimizer()


class Agent(ABC):
    """A single specialist in the multi-agent architecture."""

    name: str = "agent"
    system_prompt: str = "You are a careful, precise software engineer."

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def extra_standards(self) -> list[str]:
        """Optional agent-specific coding standards layered on top of the
        Prompt Compiler's defaults. Override in subclasses when useful."""
        return []

    def build_prompt(self, agent_input: AgentInput) -> str:
        """Every prompt is produced by the Prompt Compiler -- no agent hand-
        assembles raw prompt strings. Ollama never sees anything else."""
        compiled = _COMPILER.compile(
            system_prompt=self.system_prompt,
            specialty_instruction=self.specialty_instruction(),
            request=agent_input.request,
            plan=agent_input.plan,
            reasoning_block=agent_input.reasoning.as_prompt_block(),
            context=agent_input.context,
            memory_block=agent_input.memory_block,
            selected_files=agent_input.selected_files or agent_input.context.file_paths(),
            previous_actions=agent_input.previous_actions,
            extra_standards=self.extra_standards(),
        )
        return compiled.prompt

    @abstractmethod
    def specialty_instruction(self) -> str:
        """One paragraph telling the model what this agent focuses on."""

    # Coarse mapping from agent identity to the Ollama Optimizer's
    # temperature-profile categories.
    _TASK_KIND_BY_AGENT = {
        "coding_agent": "code_generation",
        "review_agent": "refactoring",
        "planner_agent": "brainstorm",
        "documentation_agent": "explanation",
    }

    def run(self, agent_input: AgentInput) -> AgentOutput:
        prompt = self.build_prompt(agent_input)
        model_name = getattr(self.provider, "model", self.provider.name)
        task_kind = self._TASK_KIND_BY_AGENT.get(self.name, "default")
        optimized = _OPTIMIZER.optimize(
            compiled_system=self.system_prompt,
            compiled_prompt=prompt,
            model_name=model_name,
            task_kind=task_kind,
        )
        result = self.provider.generate(
            GenerationRequest(
                prompt=optimized.prompt,
                system=optimized.system or self.system_prompt,
                temperature=optimized.temperature,
                max_tokens=optimized.max_output_tokens,
            )
        )
        return AgentOutput(agent=self.name, text=result.text, compiled_prompt_tokens=optimized.final_tokens)
