"""
Workspace manager -- resolves where an indexed repository actually lives on
disk. Supports pointing Commandra at an existing local directory, or
extracting an uploaded zip archive into a private working copy under
`data/repos/<repo_id>/`.
"""

from __future__ import annotations

import os
import shutil
import uuid
import zipfile

STORAGE_ROOT = "data/repos"


def new_repo_id() -> str:
    return uuid.uuid4().hex[:12]


def workspace_path(repo_id: str) -> str:
    return os.path.join(STORAGE_ROOT, repo_id)


def register_local_path(path: str) -> str:
    """Use an existing directory on disk directly (no copy)."""
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Not a directory: {path}")
    return os.path.realpath(path)


def extract_zip_upload(zip_path: str) -> tuple[str, str]:
    """Extract an uploaded zip into a fresh workspace dir. Returns (repo_id, root)."""
    repo_id = new_repo_id()
    dest = workspace_path(repo_id)
    os.makedirs(dest, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = os.path.realpath(os.path.join(dest, member.filename))
            if not member_path.startswith(os.path.realpath(dest)):
                continue  # zip-slip guard
        zf.extractall(dest)

    # If the archive has a single top-level folder, treat that as the root.
    entries = [e for e in os.listdir(dest) if not e.startswith("__MACOSX")]
    if len(entries) == 1 and os.path.isdir(os.path.join(dest, entries[0])):
        return repo_id, os.path.join(dest, entries[0])
    return repo_id, dest


def delete_workspace(repo_id: str) -> None:
    path = workspace_path(repo_id)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
