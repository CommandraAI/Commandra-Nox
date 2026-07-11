"""
fd Engine -- extremely fast file discovery.
Wraps the `fd` CLI (sharkdp/fd).
Install: cargo install fd-find  OR  apt install fd-find  OR  brew install fd
"""
from __future__ import annotations
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class FdResult:
    pattern: str
    files: list[str]
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "files": self.files,
            "fileCount": len(self.files),
            "available": self.available,
            "error": self.error,
        }


class FdEngine:
    """Fast file discovery via fd."""

    # fd may be installed as 'fd' or 'fdfind' on Debian/Ubuntu
    @classmethod
    def _binary(cls) -> str | None:
        for name in ("fd", "fdfind"):
            if shutil.which(name):
                return name
        return None

    @classmethod
    def available(cls) -> bool:
        return cls._binary() is not None

    def find(
        self,
        root: str,
        pattern: str = "",
        extensions: list[str] | None = None,
        hidden: bool = False,
        max_results: int = 1000,
        exclude: list[str] | None = None,
    ) -> FdResult:
        binary = self._binary()
        if not binary:
            return FdResult(pattern=pattern, files=[], available=False,
                            error="fd not installed. Run: cargo install fd-find")

        cmd = [binary, "--type", "f", "--absolute-path"]
        if pattern:
            cmd.append(pattern)
        if extensions:
            for ext in extensions:
                cmd += ["--extension", ext.lstrip(".")]
        if hidden:
            cmd.append("--hidden")
        for ex in (exclude or []):
            cmd += ["--exclude", ex]
        cmd.append(root)

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            files = [l.strip() for l in proc.stdout.splitlines() if l.strip()][:max_results]
            return FdResult(pattern=pattern, files=files, available=True)
        except subprocess.TimeoutExpired:
            return FdResult(pattern=pattern, files=[], available=True, error="fd timed out")
        except Exception as exc:
            return FdResult(pattern=pattern, files=[], available=True, error=str(exc))

    def find_by_extension(self, root: str, extensions: list[str]) -> FdResult:
        return self.find(root, extensions=extensions)
