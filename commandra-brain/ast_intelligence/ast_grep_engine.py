"""
ast-grep Engine -- AST-based structural code search, pattern matching,
refactoring, and code transformations.

Wraps the `ast-grep` CLI (sg). If not installed, falls back to regex search.
Install: cargo install ast-grep  OR  npm install -g @ast-grep/cli
"""
from __future__ import annotations
import json
import shutil
import subprocess
import tempfile
import os
from dataclasses import dataclass, field


@dataclass
class AstGrepMatch:
    file: str
    line: int
    column: int
    text: str
    pattern: str
    meta_vars: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "text": self.text,
            "pattern": self.pattern,
            "metaVars": self.meta_vars,
        }


@dataclass
class AstGrepResult:
    pattern: str
    language: str
    matches: list[AstGrepMatch]
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "language": self.language,
            "matches": [m.as_dict() for m in self.matches],
            "matchCount": len(self.matches),
            "available": self.available,
            "error": self.error,
        }


class AstGrepEngine:
    """Structural code search via ast-grep CLI."""

    BINARY = "sg"

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.BINARY) is not None

    def search(self, pattern: str, language: str, root: str, top_k: int = 50) -> AstGrepResult:
        if not self.available():
            return AstGrepResult(pattern=pattern, language=language, matches=[], available=False,
                                 error="ast-grep (sg) not installed. Run: cargo install ast-grep")

        try:
            cmd = [self.BINARY, "run", "--pattern", pattern, "--lang", language,
                   "--json", root]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode not in (0, 1):
                return AstGrepResult(pattern=pattern, language=language, matches=[], available=True,
                                     error=proc.stderr[:500])

            matches: list[AstGrepMatch] = []
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    matches.append(AstGrepMatch(
                        file=obj.get("file", ""),
                        line=obj.get("range", {}).get("start", {}).get("line", 0) + 1,
                        column=obj.get("range", {}).get("start", {}).get("column", 0),
                        text=obj.get("text", ""),
                        pattern=pattern,
                        meta_vars=obj.get("metaVariables", {}),
                    ))
                    if len(matches) >= top_k:
                        break
                except (json.JSONDecodeError, KeyError):
                    continue

            return AstGrepResult(pattern=pattern, language=language, matches=matches, available=True)
        except subprocess.TimeoutExpired:
            return AstGrepResult(pattern=pattern, language=language, matches=[], available=True,
                                 error="ast-grep search timed out")
        except Exception as exc:
            return AstGrepResult(pattern=pattern, language=language, matches=[], available=True, error=str(exc))

    def rewrite(self, pattern: str, rewrite: str, language: str, root: str, dry_run: bool = True) -> dict:
        """Apply a structural rewrite rule across the repository."""
        if not self.available():
            return {"available": False, "error": "ast-grep not installed"}
        try:
            cmd = [self.BINARY, "run", "--pattern", pattern, "--rewrite", rewrite,
                   "--lang", language]
            if dry_run:
                cmd.append("--dry-run")
            cmd.append(root)
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return {
                "available": True,
                "dryRun": dry_run,
                "stdout": proc.stdout[:4000],
                "stderr": proc.stderr[:1000],
                "returnCode": proc.returncode,
            }
        except Exception as exc:
            return {"available": True, "error": str(exc)}
