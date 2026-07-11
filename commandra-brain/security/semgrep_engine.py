"""
Semgrep Engine -- static analysis, bug detection, security scanning,
and code quality inspection using Semgrep rules.

Wraps the `semgrep` CLI (pip install semgrep).
Falls back to the existing pattern-based scanner when unavailable.
"""
from __future__ import annotations
import json
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class SemgrepFinding:
    rule_id: str
    path: str
    line: int
    column: int
    message: str
    severity: str
    fix: str = ""
    cwe: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ruleId": self.rule_id,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "severity": self.severity,
            "fix": self.fix,
            "cwe": self.cwe,
        }


@dataclass
class SemgrepResult:
    root: str
    findings: list[SemgrepFinding]
    available: bool
    rules_used: list[str] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict:
        by_severity: dict[str, int] = {}
        for f in self.findings:
            by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        return {
            "root": self.root,
            "findings": [f.as_dict() for f in self.findings],
            "findingCount": len(self.findings),
            "bySeverity": by_severity,
            "rulesUsed": self.rules_used,
            "available": self.available,
            "error": self.error,
        }


class SemgrepEngine:
    """Real static analysis via the Semgrep CLI."""

    BINARY = "semgrep"

    # Default rule packs that work without a Semgrep account
    DEFAULT_CONFIGS = ["p/default", "p/owasp-top-ten", "p/secrets"]

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.BINARY) is not None

    def scan(
        self,
        root: str,
        configs: list[str] | None = None,
        timeout: int = 120,
    ) -> SemgrepResult:
        if not self.available():
            return SemgrepResult(root=root, findings=[], available=False,
                                 error="semgrep not installed. Run: pip install semgrep")

        rule_configs = configs or self.DEFAULT_CONFIGS
        cmd = [self.BINARY, "--json", "--quiet", "--timeout", str(timeout)]
        for cfg in rule_configs:
            cmd += ["--config", cfg]
        cmd.append(root)

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                return SemgrepResult(root=root, findings=[], available=True,
                                     error=f"Semgrep JSON parse error: {proc.stderr[:300]}")

            findings: list[SemgrepFinding] = []
            for r in data.get("results", []):
                extra = r.get("extra", {})
                meta = extra.get("metadata", {})
                findings.append(SemgrepFinding(
                    rule_id=r.get("check_id", ""),
                    path=r.get("path", ""),
                    line=r.get("start", {}).get("line", 0),
                    column=r.get("start", {}).get("col", 0),
                    message=extra.get("message", ""),
                    severity=extra.get("severity", "WARNING"),
                    fix=extra.get("fix", ""),
                    cwe=meta.get("cwe", []),
                ))

            return SemgrepResult(
                root=root,
                findings=findings,
                available=True,
                rules_used=rule_configs,
            )
        except subprocess.TimeoutExpired:
            return SemgrepResult(root=root, findings=[], available=True,
                                 rules_used=rule_configs, error="Semgrep scan timed out")
        except Exception as exc:
            return SemgrepResult(root=root, findings=[], available=True, error=str(exc))

    def scan_files(self, files: dict[str, str], configs: list[str] | None = None) -> SemgrepResult:
        """Scan in-memory file contents by writing them to a temp dir."""
        import tempfile, os, shutil as sh
        tmp = tempfile.mkdtemp(prefix="commandra_semgrep_")
        try:
            for path, content in files.items():
                full = os.path.join(tmp, path.lstrip("/"))
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(content)
            result = self.scan(tmp, configs)
            # Rewrite paths back to original relative paths
            for f in result.findings:
                f.path = f.path.replace(tmp, "").lstrip("/")
            result.root = ""
            return result
        finally:
            sh.rmtree(tmp, ignore_errors=True)
