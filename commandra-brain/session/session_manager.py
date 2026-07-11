"""
Session Manager -- tracks user sessions (one per active "conversation" with
the brain), each optionally bound to a repository. Sessions are in-memory
for now; swapping in persistent storage later doesn't change this API.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class SessionTurn:
    role: str
    text: str
    at: float = field(default_factory=time.time)


@dataclass
class Session:
    id: str
    repo_id: str | None
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)
    turns: list[SessionTurn] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "repoId": self.repo_id,
            "createdAt": self.created_at,
            "lastActiveAt": self.last_active_at,
            "turnCount": len(self.turns),
        }

    def summary(self) -> dict:
        d = self.as_dict()
        d["recentTurns"] = [
            {"role": t.role, "text": t.text, "at": t.at} for t in self.turns[-10:]
        ]
        return d


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, repo_id: str | None = None) -> Session:
        session = Session(id=uuid.uuid4().hex[:16], repo_id=repo_id)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def remember_turn(self, session_id: str, role: str, text: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        session.turns.append(SessionTurn(role=role, text=text))
        session.last_active_at = time.time()

    def resume_summary(self, session_id: str) -> dict:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        return session.summary()

    def list_sessions(self, repo_id: str | None = None) -> list[dict]:
        sessions = list(self._sessions.values())
        if repo_id is not None:
            sessions = [s for s in sessions if s.repo_id == repo_id]
        return [s.as_dict() for s in sorted(sessions, key=lambda s: s.last_active_at, reverse=True)]
