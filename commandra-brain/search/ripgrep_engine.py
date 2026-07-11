"""
ripgrep Engine -- extremely fast repository text search.
Wraps the `rg` CLI binary.
Install: cargo install ripgrep  OR  apt install ripgrep  OR  brew install ripgrep
"""
from __future__ import annotations
import json
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class RipgrepMatch:
    file: str
    line: int
    column: int
    text: str

    def as_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "column": self.column, "text": self.text}


@dataclass
class RipgrepResult:
    query: str
    matches: list[RipgrepMatch]
    available: bool
    elapsed_ms: float = 0.0
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "matches": [m.as_dict() for m in self.matches],
            "matchCount": len(self.matches),
            "available": self.available,
            "elapsedMs": round(self.elapsed_ms, 2),
            "error": self.error,
        }


class RipgrepEngine:
    """Ultra-fast text search using ripgrep."""

    BINARY = "rg"

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.BINARY) is not None

    def search(
        self,
        query: str,
        root: str,
        case_sensitive: bool = False,
        file_glob: str | None = None,
        max_results: int = 200,
        context_lines: int = 0,
    ) -> RipgrepResult:
        import time
        if not self.available():
            return RipgrepResult(query=query, matches=[], available=False,
                                 error="ripgrep not installed. Run: cargo install ripgrep")
        start = time.time()
        cmd = [self.BINARY, "--json", f"--max-count={max_results}"]
        if not case_sensitive:
            cmd.append("-i")
        if file_glob:
            cmd += ["-g", file_glob]
        if context_lines:
            cmd += ["-C", str(context_lines)]
        cmd += [query, root]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            elapsed_ms = (time.time() - start) * 1000
            matches: list[RipgrepMatch] = []
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "match":
                        data = obj["data"]
                        file_path = data.get("path", {}).get("text", "")
                        line_no = data.get("line_number", 0)
                        for sub in data.get("submatches", []):
                            col = sub.get("start", 0)
                            text = data.get("lines", {}).get("text", "").rstrip()
                            matches.append(RipgrepMatch(file=file_path, line=line_no, column=col, text=text))
                except (json.JSONDecodeError, KeyError):
                    continue

            return RipgrepResult(query=query, matches=matches, available=True, elapsed_ms=elapsed_ms)
        except subprocess.TimeoutExpired:
            return RipgrepResult(query=query, matches=[], available=True,
                                 elapsed_ms=30000, error="ripgrep timed out")
        except Exception as exc:
            return RipgrepResult(query=query, matches=[], available=True, error=str(exc))

    def search_files(self, pattern: str, root: str, file_glob: str | None = None) -> list[str]:
        """Return just the list of matching file paths."""
        if not self.available():
            return []
        cmd = [self.BINARY, "-l", "-i"]
        if file_glob:
            cmd += ["-g", file_glob]
        cmd += [pattern, root]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        except Exception:
            return []
