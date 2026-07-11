"""
Index cache -- persists a RepositoryIndex to disk so re-opening a
previously indexed repository (or restarting the Brain process) doesn't
require a full re-scan. Supports incremental indexing: on load, callers can
diff file mtimes/hashes against the cache and only re-index what changed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

CACHE_ROOT = "data/index_cache"


def _cache_path(repo_id: str) -> str:
    return os.path.join(CACHE_ROOT, f"{repo_id}.json")


def content_hash(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()


def save_index(index: "object") -> None:
    os.makedirs(CACHE_ROOT, exist_ok=True)
    payload = {
        "repoId": index.repo_id,
        "root": index.root,
        "indexedAt": index.indexed_at,
        "skipped": index.skipped,
        "languages": index.languages,
        "frameworks": index.frameworks,
        "files": {
            path: {
                "language": f.language,
                "size": f.size,
                "hash": content_hash(f.content),
                "symbolCount": len(f.symbols.symbols),
                "importCount": len(f.symbols.imports),
            }
            for path, f in index.files.items()
        },
        "cachedAt": time.time(),
    }
    with open(_cache_path(index.repo_id), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def load_cache_manifest(repo_id: str) -> dict | None:
    """Returns the lightweight manifest (path -> hash) saved for a repo, or
    None if nothing is cached. Used to decide which files changed since the
    last index without re-reading every file's full content twice."""
    path = _cache_path(repo_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def diff_against_cache(repo_id: str, current_files: dict) -> dict:
    """current_files: path -> content. Returns {"changed": [...], "added": [...],
    "removed": [...], "unchanged": [...]} relative to the last cached manifest."""
    manifest = load_cache_manifest(repo_id)
    cached_files = (manifest or {}).get("files", {})

    changed, added, unchanged = [], [], []
    for path, content in current_files.items():
        h = content_hash(content)
        if path not in cached_files:
            added.append(path)
        elif cached_files[path]["hash"] != h:
            changed.append(path)
        else:
            unchanged.append(path)

    removed = [p for p in cached_files if p not in current_files]
    return {"changed": changed, "added": added, "removed": removed, "unchanged": unchanged}


def invalidate(repo_id: str) -> None:
    path = _cache_path(repo_id)
    if os.path.exists(path):
        os.remove(path)
