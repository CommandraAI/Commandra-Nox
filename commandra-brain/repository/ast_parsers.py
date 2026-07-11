"""
AST Intelligence -- structural understanding of code, not just text/regex
symbol scraping. Python gets a real AST (stdlib `ast`) walk producing
classes, methods, functions, variables, imports, inheritance, and call
edges. Every other supported language (TypeScript, JavaScript, Rust, Java,
C#, Go, PHP) gets a dependency-free structural parser built from balanced-
brace block scanning + per-construct regexes -- not a full grammar, but
enough to recover the same node kinds without pulling in a compiler
front-end for each language.

The output feeds `repository/knowledge_graph.py`, turning "a pile of
indexed files" into "classes, functions, and how they relate".
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

SUPPORTED_AST_LANGUAGES = [
    "python", "typescript", "javascript", "rust", "java", "csharp", "go", "php",
]


@dataclass
class AstNode:
    kind: str  # class | interface | function | method | variable | import | export
    name: str
    line: int
    end_line: int = 0
    parent: str | None = None  # enclosing class/interface name, if any
    bases: list[str] = field(default_factory=list)  # inheritance
    calls: list[str] = field(default_factory=list)  # names this node calls
    exported: bool = False
    signature: str = ""


@dataclass
class FileAst:
    path: str
    language: str
    nodes: list[AstNode] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)

    def classes(self) -> list[AstNode]:
        return [n for n in self.nodes if n.kind in ("class", "interface")]

    def functions(self) -> list[AstNode]:
        return [n for n in self.nodes if n.kind in ("function", "method")]


# -- Python: real AST -------------------------------------------------------

def _parse_python(source: str) -> FileAst:
    file_ast = FileAst(path="", language="python")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return file_ast

    class _CallCollector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def visit_Call(self, node: ast.Call) -> None:
            fn = node.func
            if isinstance(fn, ast.Name):
                self.calls.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                self.calls.append(fn.attr)
            self.generic_visit(node)

    def collect_calls(node: ast.AST) -> list[str]:
        collector = _CallCollector()
        collector.visit(node)
        return collector.calls

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [b.id if isinstance(b, ast.Name) else getattr(b, "attr", "?") for b in node.bases]
            file_ast.nodes.append(
                AstNode(kind="class", name=node.name, line=node.lineno, end_line=getattr(node, "end_lineno", node.lineno), bases=bases)
            )
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    file_ast.nodes.append(
                        AstNode(
                            kind="method", name=item.name, line=item.lineno,
                            end_line=getattr(item, "end_lineno", item.lineno), parent=node.name,
                            calls=collect_calls(item),
                            signature=f"{item.name}({', '.join(a.arg for a in item.args.args)})",
                        )
                    )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not isinstance(
            getattr(node, "parent", None), ast.ClassDef
        ):
            # top-level functions only (methods are handled via ClassDef above)
            pass

    # top-level functions: those whose direct parent in the module body is Module
    for item in tree.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            file_ast.nodes.append(
                AstNode(
                    kind="function", name=item.name, line=item.lineno,
                    end_line=getattr(item, "end_lineno", item.lineno),
                    calls=collect_calls(item),
                    signature=f"{item.name}({', '.join(a.arg for a in item.args.args)})",
                )
            )
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    file_ast.nodes.append(AstNode(kind="variable", name=target.id, line=item.lineno))
        elif isinstance(item, ast.Import):
            file_ast.imports.extend(alias.name for alias in item.names)
        elif isinstance(item, ast.ImportFrom) and item.module:
            file_ast.imports.append(item.module)

    file_ast.exports = [n.name for n in file_ast.nodes if n.kind in ("class", "function") and not n.name.startswith("_")]
    return file_ast


# -- Structural (regex/brace-based) parser for C-family/TS/JS/Go/Rust/PHP --

_CLASS_RE = {
    "typescript": re.compile(r"^\s*(export\s+)?(abstract\s+)?class\s+([A-Za-z0-9_$]+)(?:<[^>]*>)?(?:\s+extends\s+([A-Za-z0-9_$.]+))?(?:\s+implements\s+([A-Za-z0-9_$.,\s]+))?"),
    "javascript": re.compile(r"^\s*(export\s+)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$.]+))?"),
    "java": re.compile(r"^\s*(public\s+|private\s+)?(abstract\s+)?class\s+([A-Za-z0-9_$]+)(?:<[^>]*>)?(?:\s+extends\s+([A-Za-z0-9_$.]+))?(?:\s+implements\s+([A-Za-z0-9_$.,\s]+))?"),
    "csharp": re.compile(r"^\s*(public\s+|private\s+|internal\s+)?(abstract\s+)?class\s+([A-Za-z0-9_$]+)(?:<[^>]*>)?(?:\s*:\s*([A-Za-z0-9_$.,\s]+))?"),
    "go": re.compile(r"^\s*type\s+([A-Za-z0-9_$]+)\s+struct\b"),
    "rust": re.compile(r"^\s*(pub\s+)?struct\s+([A-Za-z0-9_$]+)"),
    "php": re.compile(r"^\s*(abstract\s+)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$\\]+))?(?:\s+implements\s+([A-Za-z0-9_$\\,\s]+))?"),
}

_INTERFACE_RE = {
    "typescript": re.compile(r"^\s*(export\s+)?interface\s+([A-Za-z0-9_$]+)(?:<[^>]*>)?(?:\s+extends\s+([A-Za-z0-9_$.,\s]+))?"),
    "java": re.compile(r"^\s*(public\s+)?interface\s+([A-Za-z0-9_$]+)(?:<[^>]*>)?(?:\s+extends\s+([A-Za-z0-9_$.,\s]+))?"),
    "csharp": re.compile(r"^\s*(public\s+)?interface\s+([A-Za-z0-9_$]+)(?:<[^>]*>)?(?:\s*:\s*([A-Za-z0-9_$.,\s]+))?"),
    "go": re.compile(r"^\s*type\s+([A-Za-z0-9_$]+)\s+interface\b"),
    "rust": re.compile(r"^\s*(pub\s+)?trait\s+([A-Za-z0-9_$]+)"),
    "php": re.compile(r"^\s*interface\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$\\,\s]+))?"),
}

_FUNCTION_RE = {
    "typescript": re.compile(r"^\s*(export\s+)?(default\s+)?(async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)"),
    "javascript": re.compile(r"^\s*(export\s+)?(default\s+)?(async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)"),
    "java": re.compile(r"^\s*(public|private|protected)\s+(static\s+)?[\w<>\[\],\s]+\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)\s*\{"),
    "csharp": re.compile(r"^\s*(public|private|protected|internal)\s+(static\s+)?[\w<>\[\],\s]+\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)"),
    "go": re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z0-9_$]+)\s*\(([^)]*)\)"),
    "rust": re.compile(r"^\s*(pub\s+)?(async\s+)?fn\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)"),
    "php": re.compile(r"^\s*(public\s+|private\s+|protected\s+)?(static\s+)?function\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)"),
}

_METHOD_RE = {
    "typescript": re.compile(r"^\s*(public\s+|private\s+|protected\s+)?(static\s+)?(async\s+)?([A-Za-z0-9_$]+)\s*\(([^)]*)\)\s*[:{]"),
}

_IMPORT_RE = {
    "typescript": re.compile(r"""^\s*import\s+.*?from\s+['"](.+?)['"]"""),
    "javascript": re.compile(r"""^\s*import\s+.*?from\s+['"](.+?)['"]"""),
    "java": re.compile(r"^\s*import\s+([\w.]+);"),
    "csharp": re.compile(r"^\s*using\s+([\w.]+);"),
    "go": re.compile(r"""^\s*"([\w./-]+)"\s*$"""),
    "rust": re.compile(r"^\s*use\s+([\w:]+)"),
    "php": re.compile(r"^\s*use\s+([\w\\]+);"),
}

_EXPORT_RE = re.compile(r"^\s*export\s+(?:default\s+)?(?:const|function|class|interface|type)\s+([A-Za-z0-9_$]+)")

_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _split_names(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [n.strip() for n in re.split(r"[,\s]+", raw.strip()) if n.strip() and n.strip() != "implements"]


def _collect_calls_in_block(lines: list[str], start: int, end: int) -> list[str]:
    calls: set[str] = set()
    for line in lines[start:end]:
        for m in _CALL_RE.finditer(line):
            name = m.group(1)
            if name not in {"if", "for", "while", "switch", "catch", "function"}:
                calls.add(name)
    return sorted(calls)[:20]


def _find_block_end(lines: list[str], start_idx: int) -> int:
    """Find the closing brace line for a block starting at `start_idx`
    (0-based), using simple brace-depth counting from that line onward."""
    depth = 0
    started = False
    for i in range(start_idx, min(len(lines), start_idx + 500)):
        depth += lines[i].count("{") - lines[i].count("}")
        if "{" in lines[i]:
            started = True
        if started and depth <= 0:
            return i
    return min(start_idx + 40, len(lines) - 1)


def _parse_structural(source: str, language: str) -> FileAst:
    file_ast = FileAst(path="", language=language)
    lines = source.splitlines()

    class_re = _CLASS_RE.get(language)
    interface_re = _INTERFACE_RE.get(language)
    function_re = _FUNCTION_RE.get(language)
    import_re = _IMPORT_RE.get(language)

    current_class: str | None = None
    current_class_end = -1

    for idx, line in enumerate(lines):
        lineno = idx + 1

        if current_class and idx > current_class_end:
            current_class = None

        if import_re and (m := import_re.match(line)):
            file_ast.imports.append(m.group(1))

        if (m := _EXPORT_RE.match(line)):
            file_ast.exports.append(m.group(1))

        if class_re and (m := class_re.match(line)):
            groups = [g for g in m.groups() if g]
            name = next((g for g in groups if re.match(r"^[A-Za-z0-9_$]+$", g or "")), None)
            if name:
                end = _find_block_end(lines, idx)
                bases = []
                if language in {"typescript", "javascript", "java", "php"} and len(m.groups()) >= 3:
                    bases = _split_names(m.group(len(m.groups()) - 1)) if m.groups()[-1] else []
                file_ast.nodes.append(AstNode(kind="class", name=name, line=lineno, end_line=end + 1, bases=bases))
                current_class, current_class_end = name, end

        if interface_re and (m := interface_re.match(line)):
            groups = [g for g in m.groups() if g]
            name = next((g for g in groups if re.match(r"^[A-Za-z0-9_$]+$", g or "")), None)
            if name:
                end = _find_block_end(lines, idx)
                file_ast.nodes.append(AstNode(kind="interface", name=name, line=lineno, end_line=end + 1))

        if function_re and (m := function_re.match(line)):
            name = None
            params = ""
            for g in m.groups():
                if g and re.match(r"^[A-Za-z0-9_$]+$", g):
                    name = g
                elif g is not None:
                    params = g
            if name:
                end = _find_block_end(lines, idx)
                kind = "method" if current_class else "function"
                file_ast.nodes.append(
                    AstNode(
                        kind=kind, name=name, line=lineno, end_line=end + 1, parent=current_class,
                        signature=f"{name}({params})",
                        calls=_collect_calls_in_block(lines, idx, end + 1),
                        exported=name in file_ast.exports,
                    )
                )

    return file_ast


_PARSERS = {"python": _parse_python}


def parse_file_ast(path: str, language: str, source: str) -> FileAst:
    """Entry point: dispatch to the Python AST parser or the structural
    parser for every other supported language. Unsupported languages get an
    empty FileAst rather than raising -- AST intelligence is additive."""
    parser = _PARSERS.get(language)
    file_ast = parser(source) if parser else _parse_structural(source, language)
    file_ast.path = path
    file_ast.language = language
    return file_ast
