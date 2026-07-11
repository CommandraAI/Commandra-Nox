"""
Benchmark Suite -- internal benchmarking framework for Commandra Brain.

Measures:
- Code Quality       (static analysis pass rate)
- Generation Speed   (tokens/sec, elapsed time)
- Repository Understanding (symbol coverage, file recall accuracy)
- Accuracy           (correct intent classification rate)
- Validation Success (files that pass validation without errors)
- Tool Performance   (latency of individual Brain tools)
- Brain Performance  (end-to-end request latency)

Reports are serialised to data/benchmarks/ and returned as structured dicts.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class BenchmarkKind(str, Enum):
    CODE_QUALITY = "code_quality"
    GENERATION_SPEED = "generation_speed"
    REPOSITORY_UNDERSTANDING = "repository_understanding"
    ACCURACY = "accuracy"
    VALIDATION_SUCCESS = "validation_success"
    TOOL_PERFORMANCE = "tool_performance"
    BRAIN_PERFORMANCE = "brain_performance"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkSample:
    name: str
    value: float
    unit: str
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"name": self.name, "value": round(self.value, 4), "unit": self.unit, "metadata": self.metadata}


@dataclass
class BenchmarkRun:
    kind: BenchmarkKind
    timestamp: float
    samples: list[BenchmarkSample] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    passed: bool = True

    def as_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "timestamp": self.timestamp,
            "samples": [s.as_dict() for s in self.samples],
            "summary": self.summary,
            "passed": self.passed,
        }


@dataclass
class BenchmarkReport:
    generated_at: float
    runs: list[BenchmarkRun] = field(default_factory=list)
    overall_score: float = 0.0

    def as_dict(self) -> dict:
        return {
            "generatedAt": self.generated_at,
            "runs": [r.as_dict() for r in self.runs],
            "overallScore": round(self.overall_score, 3),
        }


# ---------------------------------------------------------------------------
# Individual benchmark executors
# ---------------------------------------------------------------------------

class _TimingBench:
    """Measures wall-clock time of a callable."""

    @staticmethod
    def measure(fn: Callable, *args: Any, **kwargs: Any) -> tuple[Any, float]:
        start = time.time()
        result = fn(*args, **kwargs)
        return result, time.time() - start


class CodeQualityBench:
    """Runs static quality checks against provided code samples."""

    # Simple static heuristics — no external linter dependency needed
    _ISSUES = [
        ("bare_except", __import__("re").compile(r"except\s*:")),
        ("eval_use", __import__("re").compile(r"\beval\s*\(")),
        ("hardcoded_secret", __import__("re").compile(r"password\s*=\s*['\"][^'\"]{4,}['\"]", __import__("re").I)),
        ("print_statement", __import__("re").compile(r"\bprint\s*\(")),
        ("magic_number", __import__("re").compile(r"\b\d{5,}\b")),
    ]

    def run(self, code_samples: dict[str, str]) -> BenchmarkRun:
        run = BenchmarkRun(kind=BenchmarkKind.CODE_QUALITY, timestamp=time.time())
        total = len(code_samples)
        clean = 0
        for name, code in code_samples.items():
            issues_found = [label for label, pat in self._ISSUES if pat.search(code)]
            if not issues_found:
                clean += 1
            run.samples.append(BenchmarkSample(
                name=name,
                value=1.0 if not issues_found else 0.0,
                unit="pass",
                metadata={"issues": issues_found},
            ))
        pass_rate = clean / total if total else 0.0
        run.summary = {"passRate": round(pass_rate, 3), "total": total, "clean": clean}
        run.passed = pass_rate >= 0.8
        return run


class GenerationSpeedBench:
    """Records generation speed from BrainResponse elapsed times."""

    def run(self, responses: list[dict]) -> BenchmarkRun:
        run = BenchmarkRun(kind=BenchmarkKind.GENERATION_SPEED, timestamp=time.time())
        elapsed_times: list[float] = []
        for resp in responses:
            elapsed = resp.get("elapsedSeconds", 0.0)
            length = len(resp.get("responseMarkdown", ""))
            chars_per_sec = length / elapsed if elapsed > 0 else 0
            run.samples.append(BenchmarkSample(
                name="response",
                value=elapsed,
                unit="seconds",
                metadata={"charsPerSec": round(chars_per_sec, 1), "responseLength": length},
            ))
            elapsed_times.append(elapsed)

        if elapsed_times:
            run.summary = {
                "meanElapsed": round(statistics.mean(elapsed_times), 3),
                "medianElapsed": round(statistics.median(elapsed_times), 3),
                "minElapsed": round(min(elapsed_times), 3),
                "maxElapsed": round(max(elapsed_times), 3),
            }
        run.passed = (run.summary.get("meanElapsed", 999) < 60)
        return run


class RepositoryUnderstandingBench:
    """Measures how completely the Brain understood an indexed repository."""

    def run(self, index_summary: dict) -> BenchmarkRun:
        run = BenchmarkRun(kind=BenchmarkKind.REPOSITORY_UNDERSTANDING, timestamp=time.time())
        file_count = index_summary.get("fileCount", 0)
        skipped = index_summary.get("skipped", 0)
        frameworks = index_summary.get("frameworks", [])
        languages = index_summary.get("languages", {})
        kg = index_summary.get("knowledgeGraph", {})

        coverage = (file_count / max(1, file_count + skipped))
        run.samples.append(BenchmarkSample("file_coverage", coverage, "ratio"))
        run.samples.append(BenchmarkSample("frameworks_detected", len(frameworks), "count"))
        run.samples.append(BenchmarkSample("languages_detected", len(languages), "count"))
        run.samples.append(BenchmarkSample("symbols_indexed", kg.get("symbolCount", 0), "count"))

        run.summary = {
            "fileCoverage": round(coverage, 3),
            "frameworksDetected": len(frameworks),
            "languagesDetected": len(languages),
            "symbolsIndexed": kg.get("symbolCount", 0),
        }
        run.passed = coverage >= 0.9
        return run


class AccuracyBench:
    """Measures intent classification accuracy against labelled examples."""

    _EXAMPLES = [
        ("fix the null pointer exception in auth.py", "fix_bug"),
        ("add OAuth2 login support", "add_feature"),
        ("clean up the database module", "refactor"),
        ("write unit tests for the payment service", "write_tests"),
        ("check for SQL injection vulnerabilities", "security_review"),
        ("generate a README for the project", "document"),
        ("explain how the caching layer works", "explain"),
    ]

    def run(self, classify_fn: Callable[[str], str]) -> BenchmarkRun:
        run = BenchmarkRun(kind=BenchmarkKind.ACCURACY, timestamp=time.time())
        correct = 0
        for request, expected in self._EXAMPLES:
            predicted = classify_fn(request)
            match = predicted == expected
            if match:
                correct += 1
            run.samples.append(BenchmarkSample(
                name=request[:40],
                value=1.0 if match else 0.0,
                unit="correct",
                metadata={"expected": expected, "predicted": predicted},
            ))
        accuracy = correct / len(self._EXAMPLES)
        run.summary = {"accuracy": round(accuracy, 3), "correct": correct, "total": len(self._EXAMPLES)}
        run.passed = accuracy >= 0.7
        return run


class ValidationSuccessBench:
    """Measures what fraction of generated files pass structural validation."""

    def run(self, validation_results: list[dict]) -> BenchmarkRun:
        run = BenchmarkRun(kind=BenchmarkKind.VALIDATION_SUCCESS, timestamp=time.time())
        total = len(validation_results)
        passed_count = sum(1 for r in validation_results if r.get("valid", False))
        for r in validation_results:
            run.samples.append(BenchmarkSample(
                name=r.get("file", "unknown"),
                value=1.0 if r.get("valid") else 0.0,
                unit="valid",
                metadata={"errors": r.get("errors", [])},
            ))
        rate = passed_count / total if total else 0.0
        run.summary = {"passRate": round(rate, 3), "total": total, "passed": passed_count}
        run.passed = rate >= 0.9
        return run


class ToolPerformanceBench:
    """Times individual Brain tool calls."""

    def run(self, timings: dict[str, list[float]]) -> BenchmarkRun:
        run = BenchmarkRun(kind=BenchmarkKind.TOOL_PERFORMANCE, timestamp=time.time())
        for tool_name, times in timings.items():
            if not times:
                continue
            mean_ms = statistics.mean(times) * 1000
            run.samples.append(BenchmarkSample(
                name=tool_name,
                value=mean_ms,
                unit="ms",
                metadata={"calls": len(times), "maxMs": round(max(times) * 1000, 2)},
            ))
        run.summary = {"toolsProfiled": len(timings)}
        run.passed = all(
            s.value < 5000 for s in run.samples  # warn if any tool > 5s average
        )
        return run


class BrainPerformanceBench:
    """End-to-end Brain request latency benchmark."""

    def run(self, request_timings: list[float]) -> BenchmarkRun:
        run = BenchmarkRun(kind=BenchmarkKind.BRAIN_PERFORMANCE, timestamp=time.time())
        for t in request_timings:
            run.samples.append(BenchmarkSample(name="request", value=t, unit="seconds"))
        if request_timings:
            run.summary = {
                "mean": round(statistics.mean(request_timings), 3),
                "p50": round(statistics.median(request_timings), 3),
                "p95": round(sorted(request_timings)[int(len(request_timings) * 0.95)], 3) if len(request_timings) >= 2 else round(max(request_timings), 3),
                "max": round(max(request_timings), 3),
            }
        run.passed = run.summary.get("mean", 999) < 120
        return run


# ---------------------------------------------------------------------------
# BenchmarkSuite -- orchestrates all benchmarks and persists reports
# ---------------------------------------------------------------------------

class BenchmarkSuite:
    """
    Runs all benchmark types and generates a unified report.
    Reports are written to data/benchmarks/<timestamp>.json.
    """

    def __init__(self, report_dir: str = "data/benchmarks") -> None:
        self.report_dir = report_dir
        self._timings: dict[str, list[float]] = {}

    def record_timing(self, tool_name: str, elapsed: float) -> None:
        self._timings.setdefault(tool_name, []).append(elapsed)

    def run_code_quality(self, code_samples: dict[str, str]) -> BenchmarkRun:
        return CodeQualityBench().run(code_samples)

    def run_generation_speed(self, responses: list[dict]) -> BenchmarkRun:
        return GenerationSpeedBench().run(responses)

    def run_repository_understanding(self, index_summary: dict) -> BenchmarkRun:
        return RepositoryUnderstandingBench().run(index_summary)

    def run_accuracy(self, classify_fn: Callable[[str], str]) -> BenchmarkRun:
        return AccuracyBench().run(classify_fn)

    def run_validation_success(self, validation_results: list[dict]) -> BenchmarkRun:
        return ValidationSuccessBench().run(validation_results)

    def run_tool_performance(self) -> BenchmarkRun:
        return ToolPerformanceBench().run(self._timings)

    def run_brain_performance(self, request_timings: list[float]) -> BenchmarkRun:
        return BrainPerformanceBench().run(request_timings)

    def full_report(
        self,
        code_samples: dict[str, str] | None = None,
        responses: list[dict] | None = None,
        index_summary: dict | None = None,
        classify_fn: Callable[[str], str] | None = None,
        validation_results: list[dict] | None = None,
        request_timings: list[float] | None = None,
    ) -> BenchmarkReport:
        report = BenchmarkReport(generated_at=time.time())

        if code_samples:
            report.runs.append(self.run_code_quality(code_samples))
        if responses:
            report.runs.append(self.run_generation_speed(responses))
        if index_summary:
            report.runs.append(self.run_repository_understanding(index_summary))
        if classify_fn:
            report.runs.append(self.run_accuracy(classify_fn))
        if validation_results:
            report.runs.append(self.run_validation_success(validation_results))
        if self._timings:
            report.runs.append(self.run_tool_performance())
        if request_timings:
            report.runs.append(self.run_brain_performance(request_timings))

        passed_runs = [r for r in report.runs if r.passed]
        report.overall_score = len(passed_runs) / max(1, len(report.runs))

        self._save(report)
        return report

    def _save(self, report: BenchmarkReport) -> None:
        os.makedirs(self.report_dir, exist_ok=True)
        fname = os.path.join(self.report_dir, f"{int(report.generated_at)}.json")
        with open(fname, "w", encoding="utf-8") as fh:
            json.dump(report.as_dict(), fh, indent=2)

    def list_reports(self) -> list[str]:
        if not os.path.isdir(self.report_dir):
            return []
        return sorted(
            [f for f in os.listdir(self.report_dir) if f.endswith(".json")],
            reverse=True,
        )

    def load_report(self, filename: str) -> dict:
        path = os.path.join(self.report_dir, filename)
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
