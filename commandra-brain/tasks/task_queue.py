"""
Task Queue -- builds an ordered list of engineering steps for a goal. Each
step is a plain dataclass (so `step.__dict__` serializes cleanly for the
API) tracking its own status, letting the caller mark steps done/failed as
work progresses.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class TaskStep:
    id: str
    name: str
    status: str = "pending"  # pending | in_progress | done | failed | skipped
    detail: str = ""


@dataclass
class TaskQueue:
    goal: str
    steps: list[TaskStep] = field(default_factory=list)

    def get(self, step_id: str) -> TaskStep | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def mark(self, step_id: str, status: str, detail: str = "") -> None:
        step = self.get(step_id)
        if step is None:
            raise KeyError(f"Unknown task step: {step_id}")
        step.status = status
        if detail:
            step.detail = detail

    def as_dict(self) -> dict:
        return {"goal": self.goal, "steps": [s.__dict__ for s in self.steps]}


_DEFAULT_STAGES = [
    "Understand the goal",
    "Analyze relevant repository context",
    "Design the approach",
    "Implement the change",
    "Validate and test",
    "Review and document",
]


def build_default_queue(goal: str, stages: list[str] | None = None) -> TaskQueue:
    names = stages if stages else _DEFAULT_STAGES
    steps = [TaskStep(id=uuid.uuid4().hex[:10], name=name) for name in names]
    return TaskQueue(goal=goal, steps=steps)
