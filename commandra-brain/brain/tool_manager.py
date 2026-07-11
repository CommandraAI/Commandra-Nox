"""
Tool Manager -- safely applies multi-file edits proposed by the Coding
Agent to a repository's on-disk workspace copy, with automatic backups so
changes can be rolled back.

This is intentionally conservative: it only ever writes inside the
repository's own indexed root, never outside it, and never touches Brain
source files.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field


@dataclass
class FileEdit:
    path: str  # relative to repo root
    content: str


@dataclass
class EditResult:
    path: str
    bytes_written: int
    backed_up: bool


@dataclass
class ApplyEditsResult:
    applied: list[EditResult] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


class ToolManager:
    """Applies validated file edits within a repository root."""

    def apply_edits(self, repo_root: str, edits: list[FileEdit]) -> ApplyEditsResult:
        result = ApplyEditsResult()
        repo_root_abs = os.path.realpath(repo_root)

        for edit in edits:
            target = os.path.realpath(os.path.join(repo_root_abs, edit.path))
            if not target.startswith(repo_root_abs + os.sep) and target != repo_root_abs:
                result.rejected.append({"path": edit.path, "reason": "escapes repository root"})
                continue

            backed_up = False
            if os.path.exists(target):
                backup_dir = os.path.join(repo_root_abs, ".commandra_backups")
                os.makedirs(backup_dir, exist_ok=True)
                backup_name = f"{edit.path.replace('/', '__')}.{int(time.time())}.bak"
                with open(target, "r", encoding="utf-8", errors="ignore") as fh:
                    original = fh.read()
                with open(os.path.join(backup_dir, backup_name), "w", encoding="utf-8") as fh:
                    fh.write(original)
                backed_up = True

            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(edit.content)

            result.applied.append(
                EditResult(path=edit.path, bytes_written=len(edit.content.encode("utf-8")), backed_up=backed_up)
            )

        return result
