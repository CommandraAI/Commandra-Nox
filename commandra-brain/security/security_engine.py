"""
Security Engine -- static, dependency-free scanning for the most common
vulnerability classes in generated or existing code. This is a first line
of defense (pattern-based, not a full taint analysis) that runs before any
code is shown to the user, and feeds the Security Agent concrete findings
to explain and fix rather than asking the model to spot issues blind.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HARDCODED_SECRET_RE = re.compile(
    r"""(?i)\b(api[_-]?key|secret|token|password|passwd|access[_-]?key)\b\s*[=:]\s*["'][A-Za-z0-9_\-/+=]{8,}["']"""
)

_RULES: list[tuple[str, str, re.Pattern, str]] = [
    (
        "sql_injection",
        "critical",
        re.compile(r"""(?i)(execute|cursor\.execute|query)\s*\(\s*f?["'].*?(%s|\{.*?\}|\+)\s*.*?["']"""),
        "Possible SQL injection: query string built with string formatting/concatenation instead of parameterized bindings.",
    ),
    (
        "sql_injection",
        "critical",
        re.compile(r"""(?i)(SELECT|INSERT|UPDATE|DELETE)\b.*?["']\s*\+\s*\w+"""),
        "Possible SQL injection: SQL string concatenated with a variable.",
    ),
    (
        "xss",
        "high",
        re.compile(r"""dangerouslySetInnerHTML|innerHTML\s*=(?!\s*['"]\s*['"])|document\.write\("""),
        "Possible XSS: raw HTML injection without sanitization.",
    ),
    (
        "csrf",
        "medium",
        re.compile(r"""(?i)@app\.(post|put|delete)\(|app\.(post|put|delete)\("""),
        "State-changing route detected -- verify CSRF protection is applied (double-submit cookie, SameSite, or token check).",
    ),
    (
        "ssrf",
        "high",
        re.compile(r"""(?i)(requests\.get|requests\.post|fetch|httpx\.get|axios\.get)\s*\(\s*(?!["'])[a-zA-Z_]"""),
        "Possible SSRF: outbound request URL built from a variable -- validate/allowlist the target before fetching.",
    ),
    (
        "weak_auth",
        "high",
        re.compile(r"""(?i)md5\(|sha1\(|hashlib\.md5|hashlib\.sha1"""),
        "Weak hashing algorithm used for security-sensitive data -- use bcrypt/argon2/scrypt for passwords, sha256+ elsewhere.",
    ),
    (
        "unsafe_api",
        "critical",
        re.compile(r"""(?i)\beval\(|\bexec\(|subprocess\.\w+\([^)]*shell\s*=\s*True"""),
        "Unsafe dynamic execution (eval/exec/shell=True) -- avoid executing dynamic strings as code/commands.",
    ),
    (
        "unsafe_api",
        "medium",
        re.compile(r"""(?i)pickle\.loads?\("""),
        "Unsafe deserialization via pickle -- do not unpickle untrusted input.",
    ),
]


@dataclass
class SecurityFinding:
    path: str
    line: int
    category: str
    severity: str  # critical | high | medium | low
    message: str
    snippet: str


@dataclass
class SecurityReport:
    findings: list[SecurityFinding] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "findingCount": len(self.findings),
            "bySeverity": self._counts(),
            "findings": [f.__dict__ for f in self.findings],
        }

    def _counts(self) -> dict:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts


def scan_file(path: str, content: str) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    lines = content.splitlines()

    for lineno, line in enumerate(lines, start=1):
        if _HARDCODED_SECRET_RE.search(line):
            findings.append(
                SecurityFinding(
                    path=path, line=lineno, category="hardcoded_secret", severity="critical",
                    message="Hardcoded credential/secret literal detected -- move to environment variables/secret storage.",
                    snippet=line.strip()[:160],
                )
            )
        for category, severity, pattern, message in _RULES:
            if pattern.search(line):
                findings.append(
                    SecurityFinding(path=path, line=lineno, category=category, severity=severity, message=message, snippet=line.strip()[:160])
                )

    return findings


def scan_dependency_manifest(manifest_content: str, known_vulnerable: dict[str, str] | None = None) -> list[SecurityFinding]:
    """`known_vulnerable`: package name -> advisory message. Without a live
    advisory feed this only flags packages the caller explicitly knows are
    risky (e.g. seeded from an offline vulnerability list)."""
    findings: list[SecurityFinding] = []
    if not known_vulnerable:
        return findings
    for package, advisory in known_vulnerable.items():
        if package in manifest_content:
            findings.append(
                SecurityFinding(path="dependencies", line=0, category="dependency_vulnerability", severity="high", message=advisory, snippet=package)
            )
    return findings


class SecurityEngine:
    def scan_project(self, files: dict[str, str]) -> SecurityReport:
        report = SecurityReport()
        for path, content in files.items():
            report.findings.extend(scan_file(path, content))
        return report
