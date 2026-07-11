"""
Gitleaks Engine -- detect leaked API keys, passwords, tokens and secrets
inside repositories and git histories.

Wraps the `gitleaks` CLI.
Install: https://github.com/gitleaks/gitleaks/releases
Or: brew install gitleaks  /  go install github.com/zricethezav/gitleaks/v8@latest
"""
from __future__ import annotations
import json
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class SecretLeak:
    rule_id: str
    description: str
    file: str
    line: int
    match: str        # redacted for safety
    commit: str = ""
    author: str = ""
    entropy: float = 0.0

    def as_dict(self) -> dict:
        return {
            "ruleId": self.rule_id,
            "description": self.description,
            "file": self.file,
            "line": self.line,
            "match": "***REDACTED***",  # Never expose the actual secret
            "commit": self.commit,
            "author": self.author,
            "entropy": round(self.entropy, 3),
        }


@dataclass
class GitleaksResult:
    root: str
    leaks: list[SecretLeak]
    available: bool
    scan_mode: str = "directory"
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "root": self.root,
            "leaks": [l.as_dict() for l in self.leaks],
            "leakCount": len(self.leaks),
            "scanMode": self.scan_mode,
            "available": self.available,
            "error": self.error,
            "clean": len(self.leaks) == 0,
        }


class GitleaksEngine:
    """Detects secrets and leaked credentials using gitleaks."""

    BINARY = "gitleaks"

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.BINARY) is not None

    def scan_directory(self, root: str) -> GitleaksResult:
        return self._scan(root, mode="detect", scan_mode="directory")

    def scan_git_history(self, root: str) -> GitleaksResult:
        return self._scan(root, mode="detect", args=["--source", root, "--log-opts", "HEAD"], scan_mode="git-history")

    def _scan(self, root: str, mode: str = "detect", args: list[str] | None = None, scan_mode: str = "directory") -> GitleaksResult:
        if not self.available():
            return GitleaksResult(root=root, leaks=[], available=False, scan_mode=scan_mode,
                                  error="gitleaks not installed. See: https://github.com/gitleaks/gitleaks/releases")
        try:
            cmd = [self.BINARY, mode, "--report-format", "json", "--report-path", "/dev/stdout",
                   "--source", root, "--no-banner"]
            if args:
                cmd += args

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            # gitleaks exits 1 when leaks found, 0 when clean
            if proc.returncode not in (0, 1):
                return GitleaksResult(root=root, leaks=[], available=True, scan_mode=scan_mode,
                                      error=proc.stderr[:300])

            leaks: list[SecretLeak] = []
            if proc.stdout.strip():
                try:
                    data = json.loads(proc.stdout)
                    for item in (data if isinstance(data, list) else [data]):
                        leaks.append(SecretLeak(
                            rule_id=item.get("RuleID", ""),
                            description=item.get("Description", ""),
                            file=item.get("File", ""),
                            line=item.get("StartLine", 0),
                            match=item.get("Match", ""),
                            commit=item.get("Commit", ""),
                            author=item.get("Author", ""),
                            entropy=item.get("Entropy", 0.0),
                        ))
                except json.JSONDecodeError:
                    pass

            return GitleaksResult(root=root, leaks=leaks, available=True, scan_mode=scan_mode)
        except subprocess.TimeoutExpired:
            return GitleaksResult(root=root, leaks=[], available=True, scan_mode=scan_mode,
                                  error="Gitleaks scan timed out")
        except Exception as exc:
            return GitleaksResult(root=root, leaks=[], available=True, scan_mode=scan_mode, error=str(exc))
