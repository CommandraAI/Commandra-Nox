"""
Diff Engine -- minimal patch preview/apply/rollback used by the brain and by
`/diff/preview` in the server. Keeps an in-memory history of applied patches
so a change can be rolled back by id within the process lifetime.
"""

from __future__ import annotations

import difflib
import time
import uuid
from dataclasses import dataclass, field


def minimal_patch(path: str, original: str, updated: str) -> dict:
    """Produce a unified-diff style preview between two versions of a file."""
    original_lines = original.splitlines(keepends=True)
    updated_lines = updated.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            original_lines,
            updated_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )

    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

    return {
        "path": path,
        "diff": "".join(diff_lines),
        "linesAdded": added,
        "linesRemoved": removed,
        "unchanged": original == updated,
    }


@dataclass
class PatchRecord:
    id: str
    path: str
    original: str
    updated: str
    created_at: float = field(default_factory=time.time)
    rolled_back: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "createdAt": self.created_at,
            "rolledBack": self.rolled_back,
            **minimal_patch(self.path, self.original, self.updated),
        }


class DiffEngine:
    """Records applied patches in memory and supports rollback by id.

    This engine does not touch the filesystem itself -- callers own writing
    `updated`/`original` content to disk. It exists to give the brain and the
    API a consistent, inspectable history of what changed and why.
    """

    def __init__(self) -> None:
        self._patches: dict[str, PatchRecord] = {}

    def record_patch(self, path: str, original: str, updated: str) -> PatchRecord:
        record = PatchRecord(id=uuid.uuid4().hex[:12], path=path, original=original, updated=updated)
        self._patches[record.id] = record
        return record

    def get(self, patch_id: str) -> PatchRecord | None:
        return self._patches.get(patch_id)

    def rollback(self, patch_id: str) -> str:
        """Marks the patch as rolled back and returns the original content
        so the caller can write it back to disk."""
        record = self._patches.get(patch_id)
        if record is None:
            raise KeyError(f"Unknown patch: {patch_id}")
        record.rolled_back = True
        return record.original

    def history(self, path: str | None = None) -> list[PatchRecord]:
        records = list(self._patches.values())
        if path is not None:
            records = [r for r in records if r.path == path]
        return sorted(records, key=lambda r: r.created_at)
