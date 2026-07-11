"""
AI Planning Timeline -- visual progress tracking for every Brain task.

Tracks the following standard stages for each task:
  Planning → Repository Analysis → Context Collection →
  Code Generation → Validation → Testing → Documentation → Completion

Each stage has a status (pending / in_progress / complete / skipped / failed)
and optional detail text.  The timeline is updated in real-time as the Brain
moves through its pipeline stages.  Clients can poll GET /timeline/{task_id}
to display live progress.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    SKIPPED = "skipped"
    FAILED = "failed"


class StageName(str, Enum):
    PLANNING = "planning"
    REPOSITORY_ANALYSIS = "repository_analysis"
    CONTEXT_COLLECTION = "context_collection"
    CODE_GENERATION = "code_generation"
    VALIDATION = "validation"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    COMPLETION = "completion"


_STAGE_LABELS: dict[StageName, str] = {
    StageName.PLANNING: "Planning",
    StageName.REPOSITORY_ANALYSIS: "Repository Analysis",
    StageName.CONTEXT_COLLECTION: "Context Collection",
    StageName.CODE_GENERATION: "Code Generation",
    StageName.VALIDATION: "Validation",
    StageName.TESTING: "Testing",
    StageName.DOCUMENTATION: "Documentation",
    StageName.COMPLETION: "Completion",
}

_DEFAULT_ORDER = [
    StageName.PLANNING,
    StageName.REPOSITORY_ANALYSIS,
    StageName.CONTEXT_COLLECTION,
    StageName.CODE_GENERATION,
    StageName.VALIDATION,
    StageName.TESTING,
    StageName.DOCUMENTATION,
    StageName.COMPLETION,
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TimelineStage:
    name: StageName
    label: str
    status: StageStatus = StageStatus.PENDING
    started_at: float | None = None
    finished_at: float | None = None
    detail: str = ""
    artifacts: list[str] = field(default_factory=list)   # file paths produced

    @property
    def elapsed_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at or time.time()
        return round(end - self.started_at, 3)

    def start(self, detail: str = "") -> None:
        self.status = StageStatus.IN_PROGRESS
        self.started_at = time.time()
        if detail:
            self.detail = detail

    def complete(self, detail: str = "", artifacts: list[str] | None = None) -> None:
        self.status = StageStatus.COMPLETE
        self.finished_at = time.time()
        if detail:
            self.detail = detail
        if artifacts:
            self.artifacts = artifacts

    def fail(self, reason: str = "") -> None:
        self.status = StageStatus.FAILED
        self.finished_at = time.time()
        if reason:
            self.detail = reason

    def skip(self, reason: str = "") -> None:
        self.status = StageStatus.SKIPPED
        if reason:
            self.detail = reason

    def as_dict(self) -> dict:
        return {
            "name": self.name.value,
            "label": self.label,
            "status": self.status.value,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "elapsedSeconds": self.elapsed_seconds,
            "detail": self.detail,
            "artifacts": self.artifacts,
        }


@dataclass
class TaskTimeline:
    task_id: str
    request: str
    created_at: float = field(default_factory=time.time)
    stages: list[TimelineStage] = field(default_factory=list)

    @property
    def current_stage(self) -> TimelineStage | None:
        for stage in self.stages:
            if stage.status == StageStatus.IN_PROGRESS:
                return stage
        return None

    @property
    def progress_percent(self) -> float:
        if not self.stages:
            return 0.0
        done = sum(1 for s in self.stages if s.status in (StageStatus.COMPLETE, StageStatus.SKIPPED))
        return round(done / len(self.stages) * 100, 1)

    @property
    def is_complete(self) -> bool:
        return all(s.status in (StageStatus.COMPLETE, StageStatus.SKIPPED, StageStatus.FAILED) for s in self.stages)

    @property
    def has_failures(self) -> bool:
        return any(s.status == StageStatus.FAILED for s in self.stages)

    def get_stage(self, name: StageName) -> TimelineStage | None:
        return next((s for s in self.stages if s.name == name), None)

    def total_elapsed(self) -> float:
        started = [s.started_at for s in self.stages if s.started_at]
        finished = [s.finished_at for s in self.stages if s.finished_at]
        if not started:
            return 0.0
        end = max(finished) if finished else time.time()
        return round(end - min(started), 3)

    def as_dict(self) -> dict:
        return {
            "taskId": self.task_id,
            "request": self.request,
            "createdAt": self.created_at,
            "stages": [s.as_dict() for s in self.stages],
            "currentStage": self.current_stage.name.value if self.current_stage else None,
            "progressPercent": self.progress_percent,
            "isComplete": self.is_complete,
            "hasFailures": self.has_failures,
            "totalElapsedSeconds": self.total_elapsed(),
        }


# ---------------------------------------------------------------------------
# PlanningTimeline -- manages a registry of active timelines
# ---------------------------------------------------------------------------

class PlanningTimeline:
    """
    Creates, updates, and queries task timelines.

    Brain orchestrator calls:
      - create_timeline(request) -> TaskTimeline
      - advance(task_id, stage_name, status, detail)
      - get(task_id) -> TaskTimeline
    """

    def __init__(self) -> None:
        self._timelines: dict[str, TaskTimeline] = {}

    def create_timeline(
        self,
        request: str,
        stages: list[StageName] | None = None,
        task_id: str | None = None,
    ) -> TaskTimeline:
        tid = task_id or str(uuid.uuid4())[:12]
        stage_names = stages or _DEFAULT_ORDER
        timeline_stages = [
            TimelineStage(name=sn, label=_STAGE_LABELS[sn])
            for sn in stage_names
        ]
        tl = TaskTimeline(task_id=tid, request=request, stages=timeline_stages)
        self._timelines[tid] = tl
        return tl

    def advance(
        self,
        task_id: str,
        stage: StageName,
        status: StageStatus,
        detail: str = "",
        artifacts: list[str] | None = None,
    ) -> TaskTimeline:
        tl = self._require(task_id)
        ts = tl.get_stage(stage)
        if ts is None:
            return tl
        if status == StageStatus.IN_PROGRESS:
            ts.start(detail)
        elif status == StageStatus.COMPLETE:
            ts.complete(detail, artifacts)
        elif status == StageStatus.FAILED:
            ts.fail(detail)
        elif status == StageStatus.SKIPPED:
            ts.skip(detail)
        return tl

    def get(self, task_id: str) -> TaskTimeline:
        return self._require(task_id)

    def list_active(self) -> list[dict]:
        return [tl.as_dict() for tl in self._timelines.values() if not tl.is_complete]

    def list_all(self) -> list[dict]:
        return [tl.as_dict() for tl in self._timelines.values()]

    def _require(self, task_id: str) -> TaskTimeline:
        tl = self._timelines.get(task_id)
        if tl is None:
            raise KeyError(f"Unknown task timeline: {task_id}")
        return tl

    # -- Convenience: auto-advance from a steps_trace (Brain orchestrator output)

    def apply_steps_trace(self, task_id: str, steps_trace: list[dict]) -> TaskTimeline:
        """
        Map Brain orchestrator step names → timeline stages and mark them complete.
        Called after brain.handle_request() returns its steps_trace.
        """
        _STEP_TO_STAGE: dict[str, StageName] = {
            "context_engine": StageName.CONTEXT_COLLECTION,
            "planning_engine": StageName.PLANNING,
            "reasoning_engine": StageName.PLANNING,
            "coding_agent": StageName.CODE_GENERATION,
            "planner_agent": StageName.PLANNING,
            "review_agent": StageName.VALIDATION,
            "testing_agent": StageName.TESTING,
            "documentation_agent": StageName.DOCUMENTATION,
            "repository_indexer": StageName.REPOSITORY_ANALYSIS,
        }
        for step in steps_trace:
            step_name = step.get("step", "")
            stage = _STEP_TO_STAGE.get(step_name)
            if stage:
                self.advance(task_id, stage, StageStatus.IN_PROGRESS, step.get("detail", ""))
                self.advance(task_id, stage, StageStatus.COMPLETE, step.get("detail", ""))

        # Mark completion
        tl = self._require(task_id)
        completion_stage = tl.get_stage(StageName.COMPLETION)
        if completion_stage and completion_stage.status == StageStatus.PENDING:
            completion_stage.complete("Task completed successfully")

        return tl
