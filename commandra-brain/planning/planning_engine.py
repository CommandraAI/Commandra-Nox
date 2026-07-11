"""
Planning Engine -- the first thing that runs on every request.

Responsibilities: classify intent, estimate complexity, break the request
into ordered, dependency-aware subtasks, and decide which agent should own
each subtask. This plan is what the Reasoning Engine reasons over and what
the Brain orchestrator executes step by step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    EXPLAIN = "explain"
    ADD_FEATURE = "add_feature"
    FIX_BUG = "fix_bug"
    REFACTOR = "refactor"
    WRITE_TESTS = "write_tests"
    SECURITY_REVIEW = "security_review"
    DOCUMENT = "document"
    GENERAL = "general"


class Complexity(str, Enum):
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"


_INTENT_PATTERNS: list[tuple[Intent, re.Pattern]] = [
    (Intent.FIX_BUG, re.compile(r"\b(fix|bug|crash|error|broken|failing|traceback|exception)\b", re.I)),
    (Intent.ADD_FEATURE, re.compile(r"\b(add|implement|build|create|new feature|support for)\b", re.I)),
    (Intent.REFACTOR, re.compile(r"\b(refactor|clean up|restructure|simplify|rename)\b", re.I)),
    (Intent.WRITE_TESTS, re.compile(r"\b(test|tests|unit test|coverage|e2e)\b", re.I)),
    (Intent.SECURITY_REVIEW, re.compile(r"\b(security|vulnerab|injection|xss|csrf|secret)\b", re.I)),
    (Intent.DOCUMENT, re.compile(r"\b(document|readme|docs|explain how)\b", re.I)),
    (Intent.EXPLAIN, re.compile(r"\b(explain|what does|how does|why|walk me through)\b", re.I)),
]

_AGENT_BY_INTENT = {
    Intent.EXPLAIN: "review_agent",
    Intent.ADD_FEATURE: "coding_agent",
    Intent.FIX_BUG: "coding_agent",
    Intent.REFACTOR: "refactoring_agent",
    Intent.WRITE_TESTS: "testing_agent",
    Intent.SECURITY_REVIEW: "security_agent",
    Intent.DOCUMENT: "documentation_agent",
    Intent.GENERAL: "coding_agent",
}


@dataclass
class PlanStep:
    id: int
    title: str
    agent: str
    depends_on: list[int] = field(default_factory=list)
    done: bool = False


@dataclass
class Plan:
    request: str
    intent: Intent
    complexity: Complexity
    steps: list[PlanStep] = field(default_factory=list)

    def mark_done(self, step_id: int) -> None:
        for step in self.steps:
            if step.id == step_id:
                step.done = True

    def as_dict(self) -> dict:
        return {
            "request": self.request,
            "intent": self.intent.value,
            "complexity": self.complexity.value,
            "steps": [
                {
                    "id": s.id,
                    "title": s.title,
                    "agent": s.agent,
                    "dependsOn": s.depends_on,
                    "done": s.done,
                }
                for s in self.steps
            ],
        }


def _classify_intent(request: str) -> Intent:
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(request):
            return intent
    return Intent.GENERAL


def _estimate_complexity(request: str, files_considered: int) -> Complexity:
    word_count = len(request.split())
    if files_considered > 25 or word_count > 60:
        return Complexity.COMPLEX
    if files_considered > 5 or word_count > 20:
        return Complexity.MODERATE
    return Complexity.TRIVIAL


class PlanningEngine:
    """Turns a raw user request into an executable, agent-assigned plan."""

    def create_plan(self, request: str, files_considered: int = 0) -> Plan:
        intent = _classify_intent(request)
        complexity = _estimate_complexity(request, files_considered)
        agent = _AGENT_BY_INTENT[intent]

        steps: list[PlanStep] = [
            PlanStep(id=1, title="Understand the request and gather repository context", agent="context_engine"),
            PlanStep(id=2, title="Reason about the approach and trade-offs", agent="reasoning_engine", depends_on=[1]),
        ]

        step_id = 3
        if intent == Intent.ADD_FEATURE:
            steps += [
                PlanStep(step_id, "Design the implementation across affected files", agent="planner_agent", depends_on=[2]),
                PlanStep(step_id + 1, "Implement the feature", agent="coding_agent", depends_on=[step_id]),
                PlanStep(step_id + 2, "Review the generated changes", agent="review_agent", depends_on=[step_id + 1]),
            ]
            if complexity != Complexity.TRIVIAL:
                steps.append(
                    PlanStep(step_id + 3, "Generate tests for the new behavior", agent="testing_agent", depends_on=[step_id + 1])
                )
        elif intent == Intent.FIX_BUG:
            steps += [
                PlanStep(step_id, "Locate the root cause", agent="coding_agent", depends_on=[2]),
                PlanStep(step_id + 1, "Apply and verify the fix", agent="coding_agent", depends_on=[step_id]),
                PlanStep(step_id + 2, "Review the fix", agent="review_agent", depends_on=[step_id + 1]),
            ]
        elif intent == Intent.REFACTOR:
            steps.append(PlanStep(step_id, "Refactor the identified code", agent="refactoring_agent", depends_on=[2]))
            steps.append(PlanStep(step_id + 1, "Review for behavior preservation", agent="review_agent", depends_on=[step_id]))
        elif intent == Intent.WRITE_TESTS:
            steps.append(PlanStep(step_id, "Generate tests", agent="testing_agent", depends_on=[2]))
        elif intent == Intent.SECURITY_REVIEW:
            steps.append(PlanStep(step_id, "Scan for vulnerabilities and unsafe patterns", agent="security_agent", depends_on=[2]))
        elif intent == Intent.DOCUMENT:
            steps.append(PlanStep(step_id, "Generate documentation", agent="documentation_agent", depends_on=[2]))
        else:
            steps.append(PlanStep(step_id, "Compose the response", agent=agent, depends_on=[2]))

        return Plan(request=request, intent=intent, complexity=complexity, steps=steps)
