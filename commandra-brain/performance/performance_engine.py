"""
Performance Engine -- static heuristics for spotting likely performance
problems without executing anything: nested-loop / Big-O red flags,
N+1 query patterns, unbounded data loads, render-thrashing patterns in
frontend code, and bundle-size smells (heavy imports). Pattern-based, not a
profiler -- it points the Coding/Refactoring Agent at concrete lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_NPLUS1_RE = re.compile(r"(?i)for\s+\w+\s+in\s+.+:\s*$")
_QUERY_CALL_RE = re.compile(r"(?i)\.(query|execute|find|get|filter)\(")
_NESTED_LOOP_RE = re.compile(r"^(\s*)for\b")
_UNBOUNDED_QUERY_RE = re.compile(r"(?i)(SELECT\s+\*\s+FROM|\.find\(\)|\.all\(\))(?!.*\blimit\b)")
_HEAVY_IMPORT_RE = re.compile(r"""(?i)import\s+(moment|lodash|jquery)\b""")
_REACT_INLINE_FN_IN_JSX_RE = re.compile(r"""on[A-Z]\w+=\{\s*\([^)]*\)\s*=>""")


@dataclass
class PerformanceFinding:
    path: str
    line: int
    category: str  # complexity | n_plus_1 | unbounded_query | bundle_size | render
    severity: str
    message: str


@dataclass
class PerformanceReport:
    findings: list[PerformanceFinding] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"findingCount": len(self.findings), "findings": [f.__dict__ for f in self.findings]}


def _detect_nested_loops(path: str, lines: list[str]) -> list[PerformanceFinding]:
    findings = []
    loop_indents: list[int] = []
    for lineno, line in enumerate(lines, start=1):
        m = _NESTED_LOOP_RE.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        loop_indents = [i for i in loop_indents if i < indent]
        depth = len(loop_indents) + 1
        loop_indents.append(indent)
        if depth >= 3:
            findings.append(
                PerformanceFinding(
                    path=path, line=lineno, category="complexity", severity="medium",
                    message=f"Loop nested {depth} levels deep -- likely O(n^{depth}) or worse; consider a better data structure or algorithm.",
                )
            )
    return findings


def _detect_n_plus_1(path: str, lines: list[str]) -> list[PerformanceFinding]:
    findings = []
    for lineno, line in enumerate(lines, start=1):
        if _NPLUS1_RE.search(line):
            for lookahead in lines[lineno:lineno + 4]:
                if _QUERY_CALL_RE.search(lookahead):
                    findings.append(
                        PerformanceFinding(
                            path=path, line=lineno, category="n_plus_1", severity="high",
                            message="Database/query call inside a loop -- likely N+1 query pattern; batch-load instead.",
                        )
                    )
                    break
    return findings


def _detect_unbounded_queries(path: str, lines: list[str]) -> list[PerformanceFinding]:
    return [
        PerformanceFinding(path=path, line=i, category="unbounded_query", severity="medium",
                            message="Query with no LIMIT/pagination -- can load unbounded rows into memory.")
        for i, line in enumerate(lines, start=1) if _UNBOUNDED_QUERY_RE.search(line)
    ]


def _detect_bundle_smells(path: str, lines: list[str]) -> list[PerformanceFinding]:
    return [
        PerformanceFinding(path=path, line=i, category="bundle_size", severity="low",
                            message="Heavy dependency import -- consider a lighter alternative or a tree-shakeable named import.")
        for i, line in enumerate(lines, start=1) if _HEAVY_IMPORT_RE.search(line)
    ]


def _detect_render_smells(path: str, lines: list[str]) -> list[PerformanceFinding]:
    if not path.endswith((".jsx", ".tsx")):
        return []
    return [
        PerformanceFinding(path=path, line=i, category="render", severity="low",
                            message="Inline arrow function passed as an event handler in JSX -- causes a new function every render; consider useCallback for hot paths.")
        for i, line in enumerate(lines, start=1) if _REACT_INLINE_FN_IN_JSX_RE.search(line)
    ]


def scan_file(path: str, content: str) -> list[PerformanceFinding]:
    lines = content.splitlines()
    findings: list[PerformanceFinding] = []
    findings += _detect_nested_loops(path, lines)
    findings += _detect_n_plus_1(path, lines)
    findings += _detect_unbounded_queries(path, lines)
    findings += _detect_bundle_smells(path, lines)
    findings += _detect_render_smells(path, lines)
    return findings


class PerformanceEngine:
    def scan_project(self, files: dict[str, str]) -> PerformanceReport:
        report = PerformanceReport()
        for path, content in files.items():
            report.findings.extend(scan_file(path, content))
        return report
