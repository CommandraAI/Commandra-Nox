"""
Test Engine -- given the file names and dependency (import) names seen in a
repository, detects which test frameworks are already in use and
recommends sensible defaults where none are detected yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_FRAMEWORK_SIGNATURES: dict[str, dict[str, list[str]]] = {
    "pytest": {"deps": ["pytest"], "files": ["pytest.ini", "conftest.py"]},
    "unittest": {"deps": ["unittest"], "files": []},
    "jest": {"deps": ["jest"], "files": ["jest.config.js", "jest.config.ts"]},
    "vitest": {"deps": ["vitest"], "files": ["vitest.config.js", "vitest.config.ts"]},
    "mocha": {"deps": ["mocha"], "files": [".mocharc.json", ".mocharc.yml"]},
    "junit": {"deps": ["junit"], "files": ["pom.xml"]},
    "go_test": {"deps": [], "files": []},  # detected via *_test.go naming instead
    "rspec": {"deps": ["rspec"], "files": [".rspec"]},
}

_LANGUAGE_DEFAULTS: dict[str, str] = {
    "python": "pytest",
    "javascript": "vitest",
    "typescript": "vitest",
    "go": "go_test",
    "ruby": "rspec",
    "java": "junit",
}


@dataclass
class TestingRecommendation:
    detected_frameworks: list[str] = field(default_factory=list)
    recommended_framework: str | None = None
    reasoning: list[str] = field(default_factory=list)
    suggested_files: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "detectedFrameworks": self.detected_frameworks,
            "recommendedFramework": self.recommended_framework,
            "reasoning": self.reasoning,
            "suggestedFiles": self.suggested_files,
        }


def detect_frameworks(file_names: set[str], dependency_names: set[str]) -> TestingRecommendation:
    detected: list[str] = []
    reasoning: list[str] = []

    lowered_deps = {d.lower() for d in dependency_names}
    lowered_files = {f.lower() for f in file_names}

    for framework, sig in _FRAMEWORK_SIGNATURES.items():
        dep_hit = any(dep in lowered_deps for dep in sig["deps"])
        file_hit = any(f in lowered_files for f in sig["files"])
        if dep_hit or file_hit:
            detected.append(framework)
            if dep_hit:
                reasoning.append(f"Found dependency matching '{framework}'.")
            if file_hit:
                reasoning.append(f"Found config file matching '{framework}'.")

    if any(f.endswith("_test.go") for f in lowered_files):
        if "go_test" not in detected:
            detected.append("go_test")
        reasoning.append("Found *_test.go files, indicating Go's built-in testing package.")

    recommended = detected[0] if detected else None
    suggested_files: list[str] = []

    if recommended is None:
        # Infer primary language from extensions present and suggest a default.
        ext_to_lang = {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript", ".go": "go",
            ".rb": "ruby", ".java": "java",
        }
        lang_counts: dict[str, int] = {}
        for name in file_names:
            for ext, lang in ext_to_lang.items():
                if name.endswith(ext):
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if lang_counts:
            primary_lang = max(lang_counts, key=lang_counts.get)
            recommended = _LANGUAGE_DEFAULTS.get(primary_lang)
            if recommended:
                reasoning.append(
                    f"No test framework detected; recommending '{recommended}' as the "
                    f"standard choice for {primary_lang}."
                )

    if recommended == "pytest":
        suggested_files = ["tests/__init__.py", "tests/conftest.py", "pytest.ini"]
    elif recommended in ("jest", "vitest"):
        suggested_files = [f"{recommended}.config.ts", "tests/setup.ts"]
    elif recommended == "go_test":
        suggested_files = ["example_test.go"]
    elif recommended == "rspec":
        suggested_files = [".rspec", "spec/spec_helper.rb"]

    return TestingRecommendation(
        detected_frameworks=detected,
        recommended_framework=recommended,
        reasoning=reasoning,
        suggested_files=suggested_files,
    )
