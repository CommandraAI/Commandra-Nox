"""Central registry mapping plan step agent names to Agent implementations."""

from __future__ import annotations

from agents.backend_agent import BackendAgent
from agents.base import Agent
from agents.coding_agent import CodingAgent
from agents.documentation_agent import DocumentationAgent
from agents.frontend_agent import FrontendAgent
from agents.performance_agent import PerformanceAgent
from agents.planner_agent import PlannerAgent
from agents.refactoring_agent import RefactoringAgent
from agents.review_agent import ReviewAgent
from agents.security_agent import SecurityAgent
from agents.testing_agent import TestingAgent
from providers.ai_provider import AIProvider

_AGENT_CLASSES = {
    "planner_agent": PlannerAgent,
    "coding_agent": CodingAgent,
    "review_agent": ReviewAgent,
    "testing_agent": TestingAgent,
    "documentation_agent": DocumentationAgent,
    "security_agent": SecurityAgent,
    "refactoring_agent": RefactoringAgent,
    "performance_agent": PerformanceAgent,
    "frontend_agent": FrontendAgent,
    "backend_agent": BackendAgent,
}


def build_agents(provider: AIProvider) -> dict[str, Agent]:
    return {key: cls(provider) for key, cls in _AGENT_CLASSES.items()}


def available_agents() -> list[str]:
    return sorted(_AGENT_CLASSES.keys())
