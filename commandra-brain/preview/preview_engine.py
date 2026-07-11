"""
Live UI Preview Engine -- generates instant, self-contained HTML previews
for interface code produced by the Brain.

Supports:
- Raw HTML / CSS            (passthrough with sanitisation)
- Tailwind CSS              (injects CDN link, renders immediately)
- React (JSX/TSX)           (Babel standalone transform, React CDN)
- Next.js                   (extracts JSX component, renders via React CDN)
- Vue 3                     (Vue CDN, renders <template> / <script setup>)
- Flutter Web               (generates a placeholder preview scaffold)

Each preview is a self-contained HTML page that can be served as-is or
embedded in an iframe.  No build step, no node_modules, no bundler.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from enum import Enum


class PreviewLanguage(str, Enum):
    HTML = "html"
    CSS = "css"
    TAILWIND = "tailwind"
    REACT = "react"
    NEXTJS = "nextjs"
    VUE = "vue"
    FLUTTER = "flutter"


@dataclass
class PreviewResult:
    language: PreviewLanguage
    html: str                       # self-contained HTML page
    preview_id: str
    generated_at: float
    warnings: list[str]

    def as_dict(self) -> dict:
        return {
            "language": self.language.value,
            "html": self.html,
            "previewId": self.preview_id,
            "generatedAt": self.generated_at,
            "warnings": self.warnings,
            "sizeBytes": len(self.html.encode("utf-8")),
        }


# ---------------------------------------------------------------------------
# HTML sanitisation (remove truly dangerous constructs only)
# ---------------------------------------------------------------------------

_DANGEROUS_ATTRS = re.compile(
    r'\b(on\w+)\s*=',
    re.I,
)
_SCRIPT_SRCS = re.compile(
    r'<script[^>]+src=["\'](?!https://cdn\.jsdelivr\.net|https://unpkg\.com|https://cdnjs\.cloudflare\.com|https://cdn\.tailwindcss\.com)',
    re.I,
)


def _sanitise_html(html: str) -> tuple[str, list[str]]:
    """Remove dangerous inline event handlers and non-CDN script srcs."""
    warnings: list[str] = []
    cleaned = html

    if _DANGEROUS_ATTRS.search(cleaned):
        cleaned = _DANGEROUS_ATTRS.sub(r'data-\1=', cleaned)
        warnings.append("Inline event handlers (onclick, onerror, …) were neutralised for safety.")

    if _SCRIPT_SRCS.search(cleaned):
        cleaned = _SCRIPT_SRCS.sub('<script src="about:blank"', cleaned)
        warnings.append("External script sources from non-CDN origins were blocked.")

    return cleaned, warnings


# ---------------------------------------------------------------------------
# CDN links
# ---------------------------------------------------------------------------

_TAILWIND_CDN = '<script src="https://cdn.tailwindcss.com"></script>'
_REACT_CDN = (
    '<script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>\n'
    '<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>\n'
    '<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>'
)
_VUE_CDN = '<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>'


# ---------------------------------------------------------------------------
# Renderers per language
# ---------------------------------------------------------------------------

def _wrap_html(title: str, head_extra: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 0; }}
</style>
{head_extra}
</head>
<body>
{body}
</body>
</html>"""


class _HtmlRenderer:
    def render(self, code: str, warnings: list[str]) -> str:
        code, w = _sanitise_html(code)
        warnings.extend(w)
        # If it's a fragment (no <html> tag), wrap it
        if "<html" not in code.lower():
            return _wrap_html("HTML Preview", "", code)
        return code


class _CssRenderer:
    def render(self, code: str, warnings: list[str]) -> str:
        body = f"""<div id="preview-root" class="preview">
  <p style="font-style:italic;color:#666;">CSS Preview — apply these styles to your HTML elements.</p>
  <div class="example">Example element</div>
</div>"""
        return _wrap_html("CSS Preview", f"<style>\n{code}\n</style>", body)


class _TailwindRenderer:
    def render(self, code: str, warnings: list[str]) -> str:
        code, w = _sanitise_html(code)
        warnings.extend(w)
        if "<html" in code.lower():
            # Already a full page — inject Tailwind CDN if not present
            if "tailwindcss" not in code:
                code = code.replace("</head>", f"{_TAILWIND_CDN}\n</head>", 1)
            return code
        return _wrap_html("Tailwind Preview", _TAILWIND_CDN, code)


class _ReactRenderer:
    def render(self, code: str, warnings: list[str]) -> str:
        # Extract the component name
        m = re.search(r"(?:export\s+default\s+function|function)\s+(\w+)", code)
        comp_name = m.group(1) if m else "App"

        # Strip imports/exports that Babel standalone doesn't handle
        cleaned = re.sub(r"^import\s.*;\n?", "", code, flags=re.MULTILINE)
        cleaned = re.sub(r"^export\s+default\s+", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^export\s+", "", cleaned, flags=re.MULTILINE)

        # Append render call
        render_call = f"\nconst root = ReactDOM.createRoot(document.getElementById('root'));\nroot.render(React.createElement({comp_name}));"

        script_block = f"""<script type="text/babel">
{cleaned}
{render_call}
</script>"""

        body = '<div id="root" style="padding:16px"></div>\n' + script_block
        return _wrap_html(f"React Preview — {comp_name}", _REACT_CDN, body)


class _NextJsRenderer:
    """Next.js: extract the default export component and render it like React."""

    def render(self, code: str, warnings: list[str]) -> str:
        warnings.append("Next.js preview renders the page component only — routing, server components, and data fetching are not available in preview mode.")
        return _ReactRenderer().render(code, warnings)


class _VueRenderer:
    def render(self, code: str, warnings: list[str]) -> str:
        # Extract <template> and <script setup> blocks
        template_m = re.search(r"<template>(.*?)</template>", code, re.DOTALL)
        script_m = re.search(r"<script[^>]*>(.*?)</script>", code, re.DOTALL)

        template_html = template_m.group(1).strip() if template_m else "<div>No template found</div>"
        script_code = script_m.group(1).strip() if script_m else ""

        # Strip import statements
        script_code = re.sub(r"^import\s.*;\n?", "", script_code, flags=re.MULTILINE)

        vue_app = f"""<div id="app">{template_html}</div>
<script>
{_VUE_CDN.replace('<script ', '').replace('></script>', '')}
</script>
{_VUE_CDN}
<script>
const {{ createApp, ref, reactive, computed, onMounted }} = Vue;
createApp({{
  setup() {{
    {script_code}
    return {{}};
  }}
}}).mount('#app');
</script>"""
        return _wrap_html("Vue Preview", "", f'<div id="app">{template_html}</div>\n' + _VUE_CDN +
                          f'\n<script>\nconst {{ createApp, ref, reactive, computed, onMounted }} = Vue;\n'
                          f'createApp({{\n  setup() {{\n    {script_code}\n    return {{}};\n  }}\n}}).mount("#app");\n</script>')


class _FlutterRenderer:
    def render(self, code: str, warnings: list[str]) -> str:
        warnings.append(
            "Flutter Web preview is a scaffold only — actual Flutter compilation requires the Flutter SDK. "
            "Use the Flutter Web DevTools for full rendering."
        )
        # Extract widget class names for display
        widgets = re.findall(r"class\s+(\w+)\s+extends\s+(?:State(?:less|ful)Widget)", code)
        widget_list = ", ".join(widgets) if widgets else "No widgets detected"
        body = f"""<div style="padding:32px;font-family:system-ui">
  <h2 style="color:#0175C2">Flutter Web Preview</h2>
  <p>Detected widgets: <strong>{widget_list}</strong></p>
  <p style="color:#666">Full Flutter compilation requires the Flutter SDK. This is a structural preview.</p>
  <pre style="background:#f5f5f5;padding:16px;border-radius:8px;overflow:auto;font-size:13px">{code[:1000]}{'...' if len(code) > 1000 else ''}</pre>
</div>"""
        return _wrap_html("Flutter Preview", "", body)


_RENDERERS = {
    PreviewLanguage.HTML: _HtmlRenderer(),
    PreviewLanguage.CSS: _CssRenderer(),
    PreviewLanguage.TAILWIND: _TailwindRenderer(),
    PreviewLanguage.REACT: _ReactRenderer(),
    PreviewLanguage.NEXTJS: _NextJsRenderer(),
    PreviewLanguage.VUE: _VueRenderer(),
    PreviewLanguage.FLUTTER: _FlutterRenderer(),
}


def _detect_language(code: str, hint: str | None = None) -> PreviewLanguage:
    """Auto-detect the framework from code content."""
    if hint:
        try:
            return PreviewLanguage(hint.lower())
        except ValueError:
            pass
    if "flutter" in code.lower() or "extends StatelessWidget" in code:
        return PreviewLanguage.FLUTTER
    if "next/image" in code or "getServerSideProps" in code or "getStaticProps" in code:
        return PreviewLanguage.NEXTJS
    if "createApp" in code or "<template>" in code or "defineComponent" in code:
        return PreviewLanguage.VUE
    if "React" in code or "JSX" in code or ".tsx" in code or "useState" in code:
        return PreviewLanguage.REACT
    if "tw-" in code or "className=" in code or re.search(r'class="[a-z]+-[a-z]', code):
        return PreviewLanguage.TAILWIND
    if "<style" in code or code.strip().startswith("{") or re.match(r"\w[\w-]*\s*\{", code.strip()):
        return PreviewLanguage.CSS
    return PreviewLanguage.HTML


# ---------------------------------------------------------------------------
# PreviewEngine -- public API
# ---------------------------------------------------------------------------

class PreviewEngine:
    """
    Generates self-contained HTML previews for any supported UI framework.

    Usage:
        engine = PreviewEngine()
        result = engine.generate(jsx_code, language="react")
        # result.html is a standalone HTML page ready to serve or embed
    """

    def generate(self, code: str, language: str | None = None) -> PreviewResult:
        lang = _detect_language(code, language)
        renderer = _RENDERERS.get(lang, _RENDERERS[PreviewLanguage.HTML])
        warnings: list[str] = []
        html = renderer.render(code, warnings)
        preview_id = hashlib.sha1(html.encode()).hexdigest()[:12]
        return PreviewResult(
            language=lang,
            html=html,
            preview_id=preview_id,
            generated_at=time.time(),
            warnings=warnings,
        )

    def refresh(self, code: str, previous_html: str, language: str | None = None) -> PreviewResult:
        """Re-generate a preview after code changes. Returns a fresh PreviewResult."""
        return self.generate(code, language)

    @staticmethod
    def supported_languages() -> list[str]:
        return [lang.value for lang in PreviewLanguage]
