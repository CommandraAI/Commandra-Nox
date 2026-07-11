"""
Repository scanner — walks a directory tree and produces a normalized list
of files with basic metadata, while filtering out noise (dependency
folders, build output, VCS internals).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".pythonlibs",
    "dist", "build", ".next", ".turbo", ".cache", "target", "vendor",
    ".pytest_cache", ".mypy_cache", "coverage", ".idea", ".vscode",
    "data", "storage", ".replit-artifact",
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".pdf",
    ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".eot", ".mp4",
    ".mp3", ".wav", ".lock", ".map",
}

MAX_FILE_BYTES = 700_000

LANGUAGE_BY_EXT = {
    ".py": "python", ".rs": "rust", ".go": "go", ".java": "java",
    ".kt": "kotlin", ".swift": "swift", ".js": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".cs": "csharp", ".cpp": "cpp", ".cc": "cpp", ".h": "cpp",
    ".hpp": "cpp", ".php": "php", ".dart": "dart", ".sql": "sql",
    ".sh": "bash", ".bash": "bash", ".yml": "yaml", ".yaml": "yaml",
    ".json": "json", ".md": "markdown", ".html": "html", ".css": "css",
    ".vue": "vue", ".svelte": "svelte",
}


@dataclass
class RepoFile:
    path: str  # relative to repo root, posix-style
    abs_path: str
    size: int
    language: str
    content: str = ""


@dataclass
class ScanResult:
    root: str
    files: list[RepoFile] = field(default_factory=list)
    skipped: int = 0


def detect_language(path: str) -> str:
    _, ext = os.path.splitext(path)
    return LANGUAGE_BY_EXT.get(ext.lower(), "text")


def scan_repository(root: str, max_files: int = 20000) -> ScanResult:
    """Walk `root`, returning readable text files with their content."""
    result = ScanResult(root=root)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".git")]

        for filename in filenames:
            if len(result.files) >= max_files:
                return result

            _, ext = os.path.splitext(filename)
            if ext.lower() in IGNORED_EXTENSIONS:
                result.skipped += 1
                continue

            abs_path = os.path.join(dirpath, filename)
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                result.skipped += 1
                continue

            if size > MAX_FILE_BYTES:
                result.skipped += 1
                continue

            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except OSError:
                result.skipped += 1
                continue

            rel_path = os.path.relpath(abs_path, root).replace(os.sep, "/")
            result.files.append(
                RepoFile(
                    path=rel_path,
                    abs_path=abs_path,
                    size=size,
                    language=detect_language(filename),
                    content=content,
                )
            )

    return result
