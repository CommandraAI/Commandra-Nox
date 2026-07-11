"""
Git Engine -- full git integration via GitPython.

Provides commits, branches, diffs, blame, log, file history, and
repository management.  Falls back to subprocess git when GitPython
is not installed.

Install: pip install gitpython
"""
from __future__ import annotations
import os
import subprocess
import shutil
from dataclasses import dataclass, field

_GITPYTHON_AVAILABLE = False
try:
    import git as gitpython  # type: ignore
    _GITPYTHON_AVAILABLE = True
except ImportError:
    pass


@dataclass
class GitCommit:
    sha: str
    message: str
    author: str
    email: str
    date: str
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0

    def as_dict(self) -> dict:
        return {
            "sha": self.sha[:12],
            "message": self.message,
            "author": self.author,
            "email": self.email,
            "date": self.date,
            "filesChanged": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
        }


@dataclass
class GitDiff:
    a_path: str
    b_path: str
    change_type: str  # A=added, D=deleted, M=modified, R=renamed
    diff_text: str
    insertions: int = 0
    deletions: int = 0

    def as_dict(self) -> dict:
        return {
            "aPath": self.a_path,
            "bPath": self.b_path,
            "changeType": self.change_type,
            "diff": self.diff_text[:4000],
            "insertions": self.insertions,
            "deletions": self.deletions,
        }


@dataclass
class GitBranch:
    name: str
    is_current: bool
    is_remote: bool
    tracking: str = ""
    last_commit_sha: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "isCurrent": self.is_current,
            "isRemote": self.is_remote,
            "tracking": self.tracking,
            "lastCommitSha": self.last_commit_sha[:12] if self.last_commit_sha else "",
        }


@dataclass
class BlameEntry:
    line: int
    sha: str
    author: str
    date: str
    content: str

    def as_dict(self) -> dict:
        return {"line": self.line, "sha": self.sha[:8], "author": self.author,
                "date": self.date, "content": self.content}


@dataclass
class GitRepoInfo:
    root: str
    current_branch: str
    is_dirty: bool
    untracked_files: list[str]
    modified_files: list[str]
    ahead: int
    behind: int
    remotes: list[str]
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "root": self.root,
            "currentBranch": self.current_branch,
            "isDirty": self.is_dirty,
            "untrackedFiles": self.untracked_files,
            "modifiedFiles": self.modified_files,
            "ahead": self.ahead,
            "behind": self.behind,
            "remotes": self.remotes,
            "available": self.available,
            "error": self.error,
        }


def _git_run(root: str, args: list[str], timeout: int = 30) -> tuple[str, str, int]:
    """Run a git command and return (stdout, stderr, returncode)."""
    binary = shutil.which("git")
    if not binary:
        return "", "git not installed", 127
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout)
    return proc.stdout, proc.stderr, proc.returncode


class GitEngine:
    """
    Git repository operations via GitPython with subprocess fallback.
    """

    def __init__(self, root: str) -> None:
        self.root = root
        self._repo = None
        if _GITPYTHON_AVAILABLE:
            try:
                self._repo = gitpython.Repo(root, search_parent_directories=True)
            except Exception:
                pass

    @staticmethod
    def is_git_repo(root: str) -> bool:
        out, _, rc = _git_run(root, ["rev-parse", "--is-inside-work-tree"])
        return rc == 0 and out.strip() == "true"

    def info(self) -> GitRepoInfo:
        if self._repo:
            try:
                repo = self._repo
                branch = repo.active_branch.name if not repo.head.is_detached else "HEAD detached"
                dirty = repo.is_dirty(untracked_files=True)
                untracked = [f for f in repo.untracked_files][:20]
                modified = [item.a_path for item in repo.index.diff(None)][:20]
                remotes = [r.name for r in repo.remotes]
                ahead = behind = 0
                try:
                    tracking = repo.active_branch.tracking_branch()
                    if tracking:
                        commits_ahead = list(repo.iter_commits(f"{tracking.name}..HEAD"))
                        commits_behind = list(repo.iter_commits(f"HEAD..{tracking.name}"))
                        ahead, behind = len(commits_ahead), len(commits_behind)
                except Exception:
                    pass
                return GitRepoInfo(root=self.root, current_branch=branch, is_dirty=dirty,
                                   untracked_files=untracked, modified_files=modified,
                                   ahead=ahead, behind=behind, remotes=remotes, available=True)
            except Exception as exc:
                pass

        # Subprocess fallback
        branch_out, _, _ = _git_run(self.root, ["branch", "--show-current"])
        branch = branch_out.strip() or "unknown"
        status_out, _, _ = _git_run(self.root, ["status", "--short"])
        modified = [l[3:].strip() for l in status_out.splitlines() if l.startswith(" M") or l.startswith("M ")]
        untracked = [l[3:].strip() for l in status_out.splitlines() if l.startswith("??")]
        remotes_out, _, _ = _git_run(self.root, ["remote"])
        remotes = [r.strip() for r in remotes_out.splitlines() if r.strip()]
        return GitRepoInfo(root=self.root, current_branch=branch, is_dirty=bool(status_out.strip()),
                           untracked_files=untracked, modified_files=modified,
                           ahead=0, behind=0, remotes=remotes,
                           available=shutil.which("git") is not None)

    def log(self, max_commits: int = 20, file_path: str | None = None) -> list[GitCommit]:
        if self._repo:
            try:
                args: dict = {"max_count": max_commits}
                commits_iter = self._repo.iter_commits(paths=file_path, **args) if file_path else self._repo.iter_commits(**args)
                result = []
                for c in commits_iter:
                    stats = c.stats.total
                    result.append(GitCommit(
                        sha=c.hexsha,
                        message=c.message.strip(),
                        author=str(c.author.name),
                        email=str(c.author.email),
                        date=str(c.authored_datetime),
                        files_changed=list(c.stats.files.keys())[:10],
                        insertions=stats.get("insertions", 0),
                        deletions=stats.get("deletions", 0),
                    ))
                return result
            except Exception:
                pass

        # Fallback
        fmt = "%H|%s|%an|%ae|%ci"
        args_cmd = ["log", f"-{max_commits}", f"--format={fmt}"]
        if file_path:
            args_cmd += ["--", file_path]
        out, _, _ = _git_run(self.root, args_cmd)
        result = []
        for line in out.splitlines():
            parts = line.split("|", 4)
            if len(parts) >= 5:
                result.append(GitCommit(sha=parts[0], message=parts[1], author=parts[2],
                                        email=parts[3], date=parts[4]))
        return result

    def diff(self, ref_a: str = "HEAD~1", ref_b: str = "HEAD", file_path: str | None = None) -> list[GitDiff]:
        if self._repo:
            try:
                diffs = self._repo.commit(ref_a).diff(ref_b, paths=file_path)
                result = []
                for d in diffs:
                    diff_text = ""
                    try:
                        diff_text = d.diff.decode("utf-8", errors="replace")
                    except Exception:
                        pass
                    result.append(GitDiff(
                        a_path=d.a_path or "",
                        b_path=d.b_path or "",
                        change_type=d.change_type,
                        diff_text=diff_text,
                    ))
                return result
            except Exception:
                pass

        cmd = ["diff", ref_a, ref_b]
        if file_path:
            cmd += ["--", file_path]
        out, _, _ = _git_run(self.root, cmd)
        return [GitDiff(a_path="", b_path="", change_type="M", diff_text=out[:10000])]

    def branches(self) -> list[GitBranch]:
        if self._repo:
            try:
                result = []
                current = self._repo.active_branch.name if not self._repo.head.is_detached else ""
                for b in self._repo.branches:
                    result.append(GitBranch(
                        name=b.name,
                        is_current=b.name == current,
                        is_remote=False,
                        last_commit_sha=b.commit.hexsha,
                    ))
                for rb in self._repo.remote().refs:
                    name = rb.name.split("/", 1)[-1]
                    result.append(GitBranch(name=name, is_current=False, is_remote=True,
                                            last_commit_sha=rb.commit.hexsha))
                return result
            except Exception:
                pass

        out, _, _ = _git_run(self.root, ["branch", "-a", "--format=%(refname:short)|%(HEAD)|%(objectname:short)"])
        result = []
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) >= 3:
                name, is_current_marker, sha = parts[0].strip(), parts[1].strip(), parts[2].strip()
                is_remote = name.startswith("remotes/") or "origin/" in name
                result.append(GitBranch(name=name, is_current=is_current_marker == "*",
                                        is_remote=is_remote, last_commit_sha=sha))
        return result

    def blame(self, file_path: str) -> list[BlameEntry]:
        out, _, rc = _git_run(self.root, ["blame", "--line-porcelain", file_path])
        if rc != 0:
            return []
        entries: list[BlameEntry] = []
        lines = out.splitlines()
        i = 0
        line_no = 0
        current: dict = {}
        while i < len(lines):
            line = lines[i]
            if line.startswith("author "):
                current["author"] = line[7:]
            elif line.startswith("author-time "):
                current["time"] = line[12:]
            elif line.startswith("summary "):
                current["sha"] = lines[i - 1].split()[0] if i > 0 else ""
            elif line.startswith("\t"):
                line_no += 1
                entries.append(BlameEntry(
                    line=line_no,
                    sha=current.get("sha", "")[:8],
                    author=current.get("author", ""),
                    date=current.get("time", ""),
                    content=line[1:],
                ))
                current = {}
            i += 1
        return entries

    def file_history(self, file_path: str, max_commits: int = 10) -> list[GitCommit]:
        return self.log(max_commits=max_commits, file_path=file_path)
