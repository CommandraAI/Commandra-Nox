"""
Workspace Engine -- tracks the "open workspace" state for each indexed
repository: root path, when it was opened, and freeform status notes other
engines can attach (e.g. "reindexing", "dirty files present").
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class WorkspaceState:
    repo_id: str
    root: str
    opened_at: float = field(default_factory=time.time)
    last_touched_at: float = field(default_factory=time.time)
    status: str = "ready"
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "repoId": self.repo_id,
            "root": self.root,
            "openedAt": self.opened_at,
            "lastTouchedAt": self.last_touched_at,
            "status": self.status,
            "notes": self.notes,
        }


class WorkspaceEngine:
    def __init__(self) -> None:
        self._workspaces: dict[str, WorkspaceState] = {}

    def open_workspace(self, repo_id: str, root: str) -> WorkspaceState:
        state = WorkspaceState(repo_id=repo_id, root=root)
        self._workspaces[repo_id] = state
        return state

    def get(self, repo_id: str) -> WorkspaceState | None:
        return self._workspaces.get(repo_id)

    def touch(self, repo_id: str, note: str | None = None) -> None:
        state = self._workspaces.get(repo_id)
        if state is None:
            return
        state.last_touched_at = time.time()
        if note:
            state.notes.append(note)

    def set_status(self, repo_id: str, status: str) -> None:
        state = self._workspaces.get(repo_id)
        if state is None:
            return
        state.status = status
        state.last_touched_at = time.time()

    def close_workspace(self, repo_id: str) -> None:
        self._workspaces.pop(repo_id, None)

    def list_open(self) -> list[dict]:
        return [w.as_dict() for w in self._workspaces.values()]
