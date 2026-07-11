"""
Lightweight, dependency-free symbol extraction.

For Python we use the standard `ast` module for accurate function/class
extraction. For every other supported language we use conservative regexes
-- good enough for repository-map purposes (Repository Intelligence does
not need a full compiler front-end, it needs a useful semantic index).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class Symbol:
    kind: str  # "function" | "class" | "export" | "import"
    name: str
    line: int


@dataclass
class FileSymbols:
    path: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


_JS_FUNC_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)"
)
_JS_ARROW_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\("
)
_JS_CLASS_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_$]+)")
_JS_IMPORT_RE = re.compile(r"""^\s*import\s+.*?from\s+['"](.+?)['"]""")
_GENERIC_IMPORT_RES = {
    "python": re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))"),
    "go": re.compile(r"""^\s*"([\w./-]+)"\s*$"""),
    "rust": re.compile(r"^\s*use\s+([\w:]+)"),
    "java": re.compile(r"^\s*import\s+([\w.]+);"),
    "kotlin": re.compile(r"^\s*import\s+([\w.]+)"),
    "php": re.compile(r"^\s*use\s+([\w\\]+);"),
    "csharp": re.compile(r"^\s*using\s+([\w.]+);"),
    "dart": re.compile(r"""^\s*import\s+['"](.+?)['"]"""),
    "swift": re.compile(r"^\s*import\s+([\w.]+)"),
}


def _extract_python(source: str) -> tuple[list[Symbol], list[str]]:
    symbols: list[Symbol] = []
    imports: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return symbols, imports

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            symbols.append(Symbol("function", node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            symbols.append(Symbol("class", node.name, node.lineno))
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    return symbols, imports


def _extract_js_like(source: str) -> tuple[list[Symbol], list[str]]:
    symbols: list[Symbol] = []
    imports: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if m := _JS_FUNC_RE.match(line):
            symbols.append(Symbol("function", m.group(1), lineno))
        elif m := _JS_ARROW_RE.match(line):
            symbols.append(Symbol("function", m.group(1), lineno))
        elif m := _JS_CLASS_RE.match(line):
            symbols.append(Symbol("class", m.group(1), lineno))
        if m := _JS_IMPORT_RE.match(line):
            imports.append(m.group(1))
    return symbols, imports


def _extract_generic(source: str, language: str) -> tuple[list[Symbol], list[str]]:
    pattern = _GENERIC_IMPORT_RES.get(language)
    imports: list[str] = []
    if pattern:
        for line in source.splitlines():
            if m := pattern.match(line):
                imports.append(next(g for g in m.groups() if g))
    return [], imports


def extract_symbols(path: str, language: str, source: str) -> FileSymbols:
    if language == "python":
        symbols, imports = _extract_python(source)
    elif language in {"javascript", "typescript", "vue", "svelte"}:
        symbols, imports = _extract_js_like(source)
    else:
        symbols, imports = _extract_generic(source, language)

    return FileSymbols(path=path, language=language, symbols=symbols, imports=imports)
