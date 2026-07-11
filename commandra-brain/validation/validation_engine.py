"""
Validation Engine -- the Brain never trusts model output blindly. Before a
generated project/file set is shown to the user, it is run through this
engine: syntax checks, import sanity, structural checks (missing files a
plan promised), dependency sanity, and formatting basics.

This works on the code-block level: callers pass a mapping of
`path -> generated content` (extracted from a model response or a Project
Generator plan) and get back a structured, rejectable report.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field

_JSON_EXTS = {".json"}
_PY_EXTS = {".py"}
_JS_LIKE_EXTS = {".js", ".jsx", ".ts", ".tsx"}


@dataclass
class ValidationIssue:
    path: str
    severity: str  # "error" | "warning"
    message: str
    line: int | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def add(self, path: str, severity: str, message: str, line: int | None = None) -> None:
        self.issues.append(ValidationIssue(path=path, severity=severity, message=message, line=line))

    def as_dict(self) -> dict:
        return {
            "isValid": self.is_valid,
            "issues": [
                {"path": i.path, "severity": i.severity, "message": i.message, "line": i.line}
                for i in self.issues
            ],
        }


def _check_python_syntax(report: ValidationReport, path: str, content: str) -> None:
    try:
        ast.parse(content)
    except SyntaxError as exc:
        report.add(path, "error", f"Python syntax error: {exc.msg}", exc.lineno)


def _check_json_syntax(report: ValidationReport, path: str, content: str) -> None:
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        report.add(path, "error", f"Invalid JSON: {exc.msg}", exc.lineno)


_UNBALANCED_BRACE_PAIRS = [("{", "}"), ("(", ")"), ("[", "]")]


def _check_js_like_basics(report: ValidationReport, path: str, content: str) -> None:
    for opener, closer in _UNBALANCED_BRACE_PAIRS:
        if content.count(opener) != content.count(closer):
            report.add(
                path, "warning",
                f"Unbalanced '{opener}{closer}' pairs ({content.count(opener)} vs {content.count(closer)}) -- possible truncated output.",
            )
    if re.search(r"\.\.\.\s*rest (of|unchanged)|// TODO: implement", content, re.I):
        report.add(path, "warning", "Contains a placeholder/ellipsis instead of real implementation.")


def _check_formatting(report: ValidationReport, path: str, content: str) -> None:
    if content.strip() == "":
        report.add(path, "error", "File is empty.")
    if "\t" in content and path.endswith((".py",)):
        report.add(path, "warning", "Mixed tabs in a Python file -- likely inconsistent indentation.")


def validate_generated_files(files: dict[str, str], expected_paths: list[str] | None = None) -> ValidationReport:
    """`files`: path -> generated content. `expected_paths`: files a plan
    promised to create/modify -- flags anything missing."""
    report = ValidationReport()

    for path, content in files.items():
        _check_formatting(report, path, content)
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        if ext in _PY_EXTS:
            _check_python_syntax(report, path, content)
        elif ext in _JSON_EXTS:
            _check_json_syntax(report, path, content)
        elif ext in _JS_LIKE_EXTS:
            _check_js_like_basics(report, path, content)

    if expected_paths:
        missing = [p for p in expected_paths if p not in files]
        for path in missing:
            report.add(path, "error", "Plan promised this file but it was not generated.")

    return report


def validate_dependency_references(declared_deps: set[str], imports_used: set[str]) -> ValidationReport:
    """Flags imports used in generated code that were never declared in the
    dependency manifest (package.json / requirements.txt / etc.), the most
    common cause of a generated project failing to install cleanly."""
    report = ValidationReport()
    stdlib_like = {"os", "sys", "json", "re", "typing", "pathlib", "React", "react"}
    for imp in imports_used - declared_deps - stdlib_like:
        root_module = imp.split(".")[0].split("/")[0]
        if root_module in declared_deps or root_module in stdlib_like:
            continue
        report.add("dependencies", "warning", f"Import '{imp}' is used but not declared as a dependency.")
    return report
