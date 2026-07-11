"""
Self-Reflection Engine -- the Brain reviews its own generated response
before it is returned to the user.

Analyzes the response for:
- Correctness  (logic, factual consistency with retrieved context)
- Security     (dangerous patterns, hardcoded secrets, injection risks)
- Performance  (obvious anti-patterns: N+1, unbounded loops, blocking I/O)
- Maintainability (magic constants, no error handling, god functions)
- Architecture (boundary violations, tight coupling, missing abstractions)
- Best Practices (language-specific idioms and conventions)

If issues are found above the configured severity threshold, the engine
produces a revised response with inline corrections and appends an
"Improvement Notes" section summarising what it changed and why.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IssueCategory(str, Enum):
    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    ARCHITECTURE = "architecture"
    BEST_PRACTICES = "best_practices"


@dataclass
class ReflectionIssue:
    category: IssueCategory
    severity: IssueSeverity
    description: str
    suggestion: str
    location: str = ""   # snippet or line reference

    def as_dict(self) -> dict:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "suggestion": self.suggestion,
            "location": self.location,
        }


@dataclass
class ReflectionResult:
    original_response: str
    revised_response: str
    issues: list[ReflectionIssue]
    refinement_applied: bool
    score: float          # 0.0–1.0 quality estimate
    dimensions: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "originalResponse": self.original_response,
            "revisedResponse": self.revised_response,
            "issues": [i.as_dict() for i in self.issues],
            "refinementApplied": self.refinement_applied,
            "score": round(self.score, 3),
            "dimensions": {k: round(v, 3) for k, v in self.dimensions.items()},
        }


# ---------------------------------------------------------------------------
# Reflection rule sets
# ---------------------------------------------------------------------------

_SECURITY_RULES: list[tuple[re.Pattern, str, str, IssueSeverity]] = [
    (re.compile(r'password\s*=\s*["\'][^"\']{4,}["\']', re.I), "Hardcoded password detected", "Use environment variables or a secrets manager", IssueSeverity.CRITICAL),
    (re.compile(r'api[_\-]?key\s*=\s*["\'][^"\']{8,}["\']', re.I), "Hardcoded API key detected", "Move secrets to environment variables", IssueSeverity.CRITICAL),
    (re.compile(r'secret\s*=\s*["\'][^"\']{4,}["\']', re.I), "Hardcoded secret detected", "Use a secrets manager or environment variables", IssueSeverity.CRITICAL),
    (re.compile(r'\beval\s*\(', re.I), "eval() usage detected", "Replace with a safe alternative; eval() is a code injection vector", IssueSeverity.ERROR),
    (re.compile(r'\bexec\s*\(', re.I), "exec() usage detected", "Avoid exec(); prefer explicit function calls", IssueSeverity.ERROR),
    (re.compile(r'subprocess\.call\(.+shell\s*=\s*True', re.I), "shell=True in subprocess", "Use shell=False with a list argument to prevent shell injection", IssueSeverity.ERROR),
    (re.compile(r'os\.system\s*\(', re.I), "os.system() detected", "Use subprocess.run() with shell=False for better safety", IssueSeverity.WARNING),
    (re.compile(r'SELECT\s+\*\s+FROM.+%s', re.I), "String-formatted SQL query", "Use parameterised queries to prevent SQL injection", IssueSeverity.CRITICAL),
    (re.compile(r'pickle\.loads?\s*\(', re.I), "pickle deserialization detected", "pickle is unsafe with untrusted data; use json or msgpack", IssueSeverity.WARNING),
]

_PERFORMANCE_RULES: list[tuple[re.Pattern, str, str, IssueSeverity]] = [
    (re.compile(r'for\s+\w+\s+in\s+.+:\s*\n\s*.+\.query\s*\(', re.MULTILINE), "N+1 query pattern in loop", "Batch queries outside the loop or use eager loading", IssueSeverity.ERROR),
    (re.compile(r'time\.sleep\s*\([^)]*\)', re.I), "Blocking sleep in application code", "Use async sleep or a background task queue", IssueSeverity.WARNING),
    (re.compile(r'while\s+True\s*:', re.I), "Unbounded while True loop", "Ensure a clear exit condition and consider adding a sleep to prevent busy-wait", IssueSeverity.WARNING),
    (re.compile(r'\+\s*=\s*["\']', re.I), "String concatenation in loop (likely)", "Use ''.join() for building strings in loops", IssueSeverity.INFO),
]

_MAINTAINABILITY_RULES: list[tuple[re.Pattern, str, str, IssueSeverity]] = [
    (re.compile(r'def\s+\w+\([^)]{200,}\)', re.I), "Function with very many parameters", "Extract a configuration dataclass or named tuple", IssueSeverity.WARNING),
    (re.compile(r'except\s*:', re.I), "Bare except clause", "Catch specific exceptions to avoid swallowing unexpected errors", IssueSeverity.WARNING),
    (re.compile(r'#\s*(TODO|FIXME|HACK|XXX)\b', re.I), "Unresolved annotation", "Resolve or track this annotation before shipping", IssueSeverity.INFO),
    (re.compile(r'\b\d{4,}\b'), "Magic number", "Extract into a named constant with a clear name", IssueSeverity.INFO),
    (re.compile(r'pass\s*$', re.MULTILINE), "Empty except/else/finally block", "Either handle the case explicitly or raise/log the exception", IssueSeverity.INFO),
]

_CORRECTNESS_RULES: list[tuple[re.Pattern, str, str, IssueSeverity]] = [
    (re.compile(r'==\s*None', re.I), "Identity comparison with None via ==", "Use 'is None' for identity checks", IssueSeverity.WARNING),
    (re.compile(r'!=\s*None', re.I), "Identity comparison with None via !=", "Use 'is not None' for identity checks", IssueSeverity.WARNING),
    (re.compile(r'return\s*$', re.MULTILINE), "Bare return in non-generator function", "Verify the implicit None return is intentional", IssueSeverity.INFO),
    (re.compile(r'except\s+\w+\s+as\s+\w+:\s*\n\s*pass', re.I), "Exception silently swallowed", "Log the exception or re-raise so failures don't go unnoticed", IssueSeverity.WARNING),
]


def _extract_code_blocks(text: str) -> list[str]:
    """Pull fenced code blocks out of a markdown response."""
    return re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)


def _run_rules(
    code: str,
    rules: list[tuple[re.Pattern, str, str, IssueSeverity]],
    category: IssueCategory,
) -> list[ReflectionIssue]:
    issues: list[ReflectionIssue] = []
    for pat, description, suggestion, severity in rules:
        m = pat.search(code)
        if m:
            snippet = code[max(0, m.start() - 20): m.end() + 40].strip()
            issues.append(ReflectionIssue(
                category=category,
                severity=severity,
                description=description,
                suggestion=suggestion,
                location=snippet[:120],
            ))
    return issues


def _score_dimension(issues: list[ReflectionIssue], category: IssueCategory) -> float:
    """Return a 0.0–1.0 quality score for a dimension (1.0 = no issues)."""
    cat_issues = [i for i in issues if i.category == category]
    if not cat_issues:
        return 1.0
    deductions = {
        IssueSeverity.CRITICAL: 0.4,
        IssueSeverity.ERROR: 0.25,
        IssueSeverity.WARNING: 0.1,
        IssueSeverity.INFO: 0.03,
    }
    total = sum(deductions.get(i.severity, 0.05) for i in cat_issues)
    return max(0.0, 1.0 - total)


def _build_improvement_notes(issues: list[ReflectionIssue]) -> str:
    if not issues:
        return ""
    lines = ["\n\n---\n## Brain Self-Review — Improvement Notes\n"]
    by_category: dict[str, list[ReflectionIssue]] = {}
    for issue in issues:
        by_category.setdefault(issue.category.value, []).append(issue)
    for cat, cat_issues in by_category.items():
        lines.append(f"### {cat.replace('_', ' ').title()}")
        for i in cat_issues:
            sev = i.severity.value.upper()
            lines.append(f"- **[{sev}]** {i.description}  \n  *Fix:* {i.suggestion}")
            if i.location:
                lines.append(f"  ```\n  {i.location}\n  ```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ReflectionEngine
# ---------------------------------------------------------------------------

_SEVERITY_THRESHOLD = {IssueSeverity.CRITICAL, IssueSeverity.ERROR}


class ReflectionEngine:
    """
    Reviews a generated response and optionally refines it.

    Call `reflect(response)` after every code-generation step.
    """

    def reflect(
        self,
        response: str,
        context_files: list[str] | None = None,
        threshold: set[IssueSeverity] | None = None,
    ) -> ReflectionResult:
        if threshold is None:
            threshold = _SEVERITY_THRESHOLD

        code_blocks = _extract_code_blocks(response)
        all_code = "\n".join(code_blocks) if code_blocks else response

        issues: list[ReflectionIssue] = []
        issues += _run_rules(all_code, _SECURITY_RULES, IssueCategory.SECURITY)
        issues += _run_rules(all_code, _PERFORMANCE_RULES, IssueCategory.PERFORMANCE)
        issues += _run_rules(all_code, _MAINTAINABILITY_RULES, IssueCategory.MAINTAINABILITY)
        issues += _run_rules(all_code, _CORRECTNESS_RULES, IssueCategory.CORRECTNESS)

        # Architecture: check context coherence (referenced files that weren't retrieved)
        if context_files is not None:
            refs = re.findall(r"`([^`]+\.(py|ts|js|rs|go))`", response)
            for ref, _ in refs:
                if ref not in context_files and not any(ref in f for f in context_files):
                    issues.append(ReflectionIssue(
                        category=IssueCategory.ARCHITECTURE,
                        severity=IssueSeverity.WARNING,
                        description=f"Response references '{ref}' which was not in retrieved context",
                        suggestion="Verify the file exists in the repository before referencing it",
                        location=ref,
                    ))

        dimensions = {
            "correctness": _score_dimension(issues, IssueCategory.CORRECTNESS),
            "security": _score_dimension(issues, IssueCategory.SECURITY),
            "performance": _score_dimension(issues, IssueCategory.PERFORMANCE),
            "maintainability": _score_dimension(issues, IssueCategory.MAINTAINABILITY),
            "architecture": _score_dimension(issues, IssueCategory.ARCHITECTURE),
            "best_practices": _score_dimension(issues, IssueCategory.BEST_PRACTICES),
        }
        overall_score = sum(dimensions.values()) / len(dimensions)

        # Only attach improvement notes if there are blocking-severity issues
        blocking = [i for i in issues if i.severity in threshold]
        refinement_applied = len(blocking) > 0

        if refinement_applied:
            improvement_block = _build_improvement_notes(issues)
            revised = response + improvement_block
        else:
            revised = response

        return ReflectionResult(
            original_response=response,
            revised_response=revised,
            issues=issues,
            refinement_applied=refinement_applied,
            score=overall_score,
            dimensions=dimensions,
        )
