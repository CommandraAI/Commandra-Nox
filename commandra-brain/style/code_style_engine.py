"""
Code Style Engine -- infers a lightweight per-repository style profile
(indentation, quote style, semicolons, naming convention, line length) from
a sample of file contents, so agents can match the existing project's
conventions instead of imposing their own.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class StyleProfile:
    indent_style: str = "spaces"
    indent_size: int = 4
    quote_style: str = "double"
    uses_semicolons: bool | None = None
    naming_convention: str = "snake_case"
    average_line_length: int = 80
    max_line_length_seen: int = 80
    sample_size: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "indentStyle": self.indent_style,
            "indentSize": self.indent_size,
            "quoteStyle": self.quote_style,
            "usesSemicolons": self.uses_semicolons,
            "namingConvention": self.naming_convention,
            "averageLineLength": self.average_line_length,
            "maxLineLengthSeen": self.max_line_length_seen,
            "sampleSize": self.sample_size,
            "notes": self.notes,
        }

    def as_prompt_block(self) -> str:
        parts = [
            f"Indentation: {self.indent_size} {self.indent_style}",
            f"Quote style: {self.quote_style}",
            f"Naming convention: {self.naming_convention}",
        ]
        if self.uses_semicolons is not None:
            parts.append("Uses semicolons" if self.uses_semicolons else "Omits semicolons")
        return "Detected project style -- " + "; ".join(parts) + "."


_SNAKE_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_CAMEL_RE = re.compile(r"\b[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+\b")
_TAB_RE = re.compile(r"^\t+", re.MULTILINE)
_SPACE_INDENT_RE = re.compile(r"^( {2,})\S", re.MULTILINE)


def analyze_style(files: dict[str, str]) -> StyleProfile:
    if not files:
        return StyleProfile(sample_size=0, notes=["No files sampled; using defaults."])

    tab_count = 0
    space_indent_sizes: Counter[int] = Counter()
    single_quotes = 0
    double_quotes = 0
    semicolon_lines = 0
    non_semicolon_eligible_lines = 0
    snake_hits = 0
    camel_hits = 0
    line_lengths: list[int] = []

    for content in files.values():
        if not content:
            continue

        tab_count += len(_TAB_RE.findall(content))
        for match in _SPACE_INDENT_RE.finditer(content):
            space_indent_sizes[len(match.group(1))] += 1

        single_quotes += content.count("'")
        double_quotes += content.count('"')

        snake_hits += len(_SNAKE_RE.findall(content))
        camel_hits += len(_CAMEL_RE.findall(content))

        for line in content.splitlines():
            stripped = line.strip()
            line_lengths.append(len(line))
            if stripped and not stripped.startswith(("#", "//", "*", "/*")):
                non_semicolon_eligible_lines += 1
                if stripped.endswith(";"):
                    semicolon_lines += 1

    indent_style = "tabs" if tab_count > sum(space_indent_sizes.values()) else "spaces"
    indent_size = space_indent_sizes.most_common(1)[0][0] if space_indent_sizes else 4
    if indent_size not in (2, 4, 8):
        # Snap to the nearest conventional size rather than reporting odd numbers.
        indent_size = min((2, 4, 8), key=lambda s: abs(s - indent_size))

    quote_style = "single" if single_quotes > double_quotes else "double"

    uses_semicolons: bool | None = None
    if non_semicolon_eligible_lines > 0:
        ratio = semicolon_lines / non_semicolon_eligible_lines
        if ratio > 0.5:
            uses_semicolons = True
        elif ratio < 0.1:
            uses_semicolons = False

    naming_convention = "camelCase" if camel_hits > snake_hits else "snake_case"

    avg_len = round(sum(line_lengths) / len(line_lengths)) if line_lengths else 80
    max_len = max(line_lengths) if line_lengths else 80

    return StyleProfile(
        indent_style=indent_style,
        indent_size=indent_size,
        quote_style=quote_style,
        uses_semicolons=uses_semicolons,
        naming_convention=naming_convention,
        average_line_length=avg_len,
        max_line_length_seen=max_len,
        sample_size=len(files),
    )
