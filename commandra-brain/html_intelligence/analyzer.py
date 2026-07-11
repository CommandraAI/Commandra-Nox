"""
HTML & UI Intelligence -- Commandra Nox is a coding model, and its most
common job is generating production-quality UI. This module encodes the
design/engineering judgment the Coding & Frontend agents should apply when
generating or reviewing HTML5/CSS3/Tailwind/React/Next.js/Vue markup:
spacing, typography, accessibility, color harmony, responsiveness,
component architecture, and animation.

It works two ways:
  1. `guidelines_for()` -- injected into the Prompt Compiler so generation
     is guided up front.
  2. `analyze()` -- a lightweight static pass that flags concrete misses in
     already-generated markup (missing alt text, no responsive classes,
     inline styles, etc.) for the Validation/Review agents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SUPPORTED_STACKS = ["html5", "css3", "tailwindcss", "react", "nextjs", "vue"]

_GUIDELINES = {
    "spacing": "Use a consistent spacing scale (e.g. 4/8px base or Tailwind's default scale) -- never arbitrary one-off pixel values.",
    "typography": "Establish a clear type scale (one display size, a few heading sizes, one body size) with deliberate font-weight and line-height pairing.",
    "accessibility": "Every interactive element needs a visible focus state, sufficient color contrast (WCAG AA, 4.5:1 for body text), semantic HTML elements over generic divs, and alt text on images.",
    "color_harmony": "Pick one dominant brand color, one accent, and neutral grays -- avoid more than 2-3 saturated hues fighting for attention.",
    "responsive_layouts": "Design mobile-first; every layout must reflow cleanly at common breakpoints (~375px, ~768px, ~1024px, ~1440px) without horizontal scroll or overlapping content.",
    "component_architecture": "Break UI into small, reusable, single-responsibility components with clear prop contracts -- avoid 300+ line monolithic components.",
    "animation": "Use subtle, purposeful motion (150-300ms ease-out transitions, staggered entrances) -- never animate for its own sake, and respect prefers-reduced-motion.",
    "dashboard_design": "Prioritize information density and scanability: consistent card/table patterns, clear data hierarchy, and status color-coding that stays consistent across the app.",
    "saas_ui": "Favor clarity over decoration: predictable navigation, consistent button/action placement, empty and loading states designed with the same care as the happy path.",
    "landing_pages": "Lead with a clear value proposition above the fold, strong visual hierarchy, and a single obvious primary call-to-action per section.",
    "admin_panels": "Optimize for speed of repeated tasks: dense tables, inline actions, keyboard-friendly forms, and predictable bulk-action patterns.",
}


def guidelines_for(stack: str, page_kind: str | None = None) -> str:
    """`stack` one of SUPPORTED_STACKS. `page_kind` optionally narrows to a
    specific pattern (dashboard_design, saas_ui, landing_pages, admin_panels)."""
    lines = [f"- {topic.replace('_', ' ').title()}: {text}" for topic, text in _GUIDELINES.items() if topic not in {"dashboard_design", "saas_ui", "landing_pages", "admin_panels"}]
    if page_kind and page_kind in _GUIDELINES:
        lines.append(f"- {page_kind.replace('_', ' ').title()}: {_GUIDELINES[page_kind]}")
    stack_note = {
        "tailwindcss": "Use Tailwind utility classes exclusively -- no inline `style=` attributes and no ad hoc custom CSS unless a utility genuinely doesn't exist.",
        "react": "Keep components function components with hooks; lift shared state no higher than necessary.",
        "nextjs": "Prefer server components for static/data-fetching concerns and client components only where interactivity requires it.",
        "vue": "Use the Composition API (`<script setup>`) and single-file components with scoped styles.",
    }.get(stack)
    if stack_note:
        lines.append(f"- {stack.title()} convention: {stack_note}")
    return "\n".join(lines)


@dataclass
class UiFinding:
    path: str
    line: int
    category: str
    message: str


@dataclass
class UiReport:
    findings: list[UiFinding] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"findingCount": len(self.findings), "findings": [f.__dict__ for f in self.findings]}


_IMG_NO_ALT_RE = re.compile(r"<img(?![^>]*\balt=)[^>]*>", re.I)
_INLINE_STYLE_RE = re.compile(r'style\s*=\s*["\'][^"\']+["\']')
_DIV_SOUP_RE = re.compile(r"<div[^>]*>\s*<div[^>]*>\s*<div", re.I)
_NO_RESPONSIVE_CLASS_RE = re.compile(r"\bclass(Name)?=[\"']w-\[\d+px\]|\bwidth:\s*\d+px")
_BUTTON_NO_TYPE_RE = re.compile(r"<button(?![^>]*\btype=)[^>]*>", re.I)


def analyze(path: str, content: str) -> UiReport:
    report = UiReport()
    if not path.endswith((".html", ".jsx", ".tsx", ".vue")):
        return report

    for lineno, line in enumerate(content.splitlines(), start=1):
        if _IMG_NO_ALT_RE.search(line):
            report.findings.append(UiFinding(path, lineno, "accessibility", "<img> without an alt attribute."))
        if _INLINE_STYLE_RE.search(line):
            report.findings.append(UiFinding(path, lineno, "maintainability", "Inline style attribute -- prefer utility classes or a stylesheet."))
        if _NO_RESPONSIVE_CLASS_RE.search(line):
            report.findings.append(UiFinding(path, lineno, "responsive_layouts", "Fixed pixel width detected -- verify this reflows on small screens."))
        if _BUTTON_NO_TYPE_RE.search(line):
            report.findings.append(UiFinding(path, lineno, "accessibility", "<button> without an explicit type -- defaults to submit inside forms and can cause accidental submits."))

    if _DIV_SOUP_RE.search(content):
        report.findings.append(UiFinding(path, 0, "component_architecture", "Deeply nested generic <div> wrappers detected -- consider semantic elements or extracting components."))

    return report
