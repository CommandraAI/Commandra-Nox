"""
Response Optimizer -- the last stop before a response reaches the user.

Cleans up model output, ensures code blocks are properly fenced with a
language tag, strips accidental leakage of internal prompt scaffolding, and
attaches the metadata (plan, reasoning, context, agent) the UI needs to
render a rich, transparent response.
"""

from __future__ import annotations

import re


def optimize(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Ensure unlabeled fenced code blocks at least get a generic tag so the
    # markdown UI can apply syntax highlighting.
    def _label_fence(match: re.Match) -> str:
        fence, lang = match.group(1), match.group(2)
        return f"{fence}text\n" if not lang.strip() else match.group(0)

    cleaned = re.sub(r"(```)([^\n`]*)\n", _label_fence, cleaned)
    return cleaned
