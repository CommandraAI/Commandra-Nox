"""
Memory Engine -- gives Commandra Brain continuity across a session (short
term) and across sessions/days (long term). Nothing here ever leaves the
local machine: long-term memory is a JSON file under `data/`.

Short-term memory: the running conversation and the task list for the
current session.

Long-term memory: architecture notes, detected coding style/conventions,
preferred frameworks, past decisions, and unfinished tasks, keyed per
repository so multiple projects don't bleed into each other.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field


@dataclass
class MemoryEntry:
    id: str
    category: str  # architecture | style | decision | task | pattern
    content: str
    created_at: float = field(default_factory=time.time)


@dataclass
class ConversationTurn:
    role: str  # user | brain
    content: str
    created_at: float = field(default_factory=time.time)


class ShortTermMemory:
    """In-process memory for the current session only."""

    def __init__(self) -> None:
        self.turns: list[ConversationTurn] = []
        self.pending_tasks: list[str] = []

    def remember_turn(self, role: str, content: str) -> None:
        self.turns.append(ConversationTurn(role=role, content=content))

    def recent(self, n: int = 8) -> list[ConversationTurn]:
        return self.turns[-n:]


class LongTermMemory:
    """Durable, per-repository memory persisted to a local JSON file."""

    def __init__(self, storage_path: str) -> None:
        self.storage_path = storage_path
        self._data: dict[str, list[dict]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def add(self, repo_id: str, category: str, content: str) -> MemoryEntry:
        entry = MemoryEntry(
            id=f"{category}-{int(time.time() * 1000)}",
            category=category,
            content=content,
        )
        self._data.setdefault(repo_id, []).append(asdict(entry))
        self._save()
        return entry

    def all_for(self, repo_id: str) -> list[dict]:
        return self._data.get(repo_id, [])

    def by_category(self, repo_id: str, category: str) -> list[dict]:
        return [e for e in self.all_for(repo_id) if e["category"] == category]

    def unfinished_tasks(self, repo_id: str) -> list[dict]:
        return self.by_category(repo_id, "task")

    def as_prompt_block(self, repo_id: str, limit: int = 12) -> str:
        entries = self.all_for(repo_id)[-limit:]
        if not entries:
            return "No long-term memory recorded yet for this repository."
        lines = [f"- [{e['category']}] {e['content']}" for e in entries]
        return "Known project memory:\n" + "\n".join(lines)


class ProjectMemory:
    """Facts about a specific project that outlive any one conversation:
    detected conventions, architecture notes, unfinished tasks."""

    def __init__(self, long_term: "LongTermMemory") -> None:
        self._long_term = long_term

    def record_architecture_note(self, repo_id: str, content: str) -> None:
        self._long_term.add(repo_id, "architecture", content)

    def record_task(self, repo_id: str, content: str) -> None:
        self._long_term.add(repo_id, "task", content)

    def unfinished_tasks(self, repo_id: str) -> list[dict]:
        return self._long_term.unfinished_tasks(repo_id)


class ConversationMemory:
    """Wraps ShortTermMemory with a clearer name for the per-session
    back-and-forth between the user and the Brain."""

    def __init__(self, short_term: "ShortTermMemory") -> None:
        self._short_term = short_term

    def remember_turn(self, role: str, content: str) -> None:
        self._short_term.remember_turn(role, content)

    def recent(self, n: int = 8) -> list[ConversationTurn]:
        return self._short_term.recent(n)


class RepositoryMemory:
    """Facts specifically about repository shape/conventions -- separate
    category from architecture notes so Repository Intelligence findings
    (frameworks, package managers, hubs) don't mix with free-form notes."""

    def __init__(self, long_term: "LongTermMemory") -> None:
        self._long_term = long_term

    def record_pattern(self, repo_id: str, content: str) -> None:
        self._long_term.add(repo_id, "pattern", content)

    def patterns(self, repo_id: str) -> list[dict]:
        return self._long_term.by_category(repo_id, "pattern")


class DecisionMemory:
    """Durable record of engineering decisions made during a session --
    tradeoffs, chosen approaches, rejected alternatives -- so future
    requests are consistent with what was already decided."""

    def __init__(self, long_term: "LongTermMemory") -> None:
        self._long_term = long_term

    def record(self, repo_id: str, content: str) -> None:
        self._long_term.add(repo_id, "decision", content)

    def all(self, repo_id: str) -> list[dict]:
        return self._long_term.by_category(repo_id, "decision")


class MemoryEngine:
    """Facade combining short- and long-term memory for the Brain, exposed
    both as flat convenience methods and as the four named memory kinds
    (Project, Conversation, Repository, Decision)."""

    def __init__(self, storage_path: str = "data/memory.json") -> None:
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(storage_path)
        self.project_memory = ProjectMemory(self.long_term)
        self.conversation_memory = ConversationMemory(self.short_term)
        self.repository_memory = RepositoryMemory(self.long_term)
        self.decision_memory = DecisionMemory(self.long_term)

    def record_decision(self, repo_id: str, content: str) -> None:
        self.decision_memory.record(repo_id, content)

    def record_pattern(self, repo_id: str, content: str) -> None:
        self.repository_memory.record_pattern(repo_id, content)

    def record_task(self, repo_id: str, content: str) -> None:
        self.project_memory.record_task(repo_id, content)

    def record_architecture_note(self, repo_id: str, content: str) -> None:
        self.project_memory.record_architecture_note(repo_id, content)
