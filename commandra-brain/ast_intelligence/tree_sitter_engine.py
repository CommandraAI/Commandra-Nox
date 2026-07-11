"""
Tree-sitter Engine -- multi-language AST parsing, syntax tree generation,
symbol extraction, and function/class analysis.

Wraps the tree-sitter Python package (pip install tree-sitter).
Language grammars are loaded on demand from installed tree-sitter-* packages.
Gracefully degrades to regex-based extraction when tree-sitter is not installed.
"""
from __future__ import annotations
import re
import shutil
from dataclasses import dataclass, field
from typing import Any

_TS_AVAILABLE = False
try:
    import tree_sitter  # type: ignore
    _TS_AVAILABLE = True
except ImportError:
    pass

LANGUAGE_PACKAGES = {
    "python":     "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "rust":       "tree_sitter_rust",
    "go":         "tree_sitter_go",
    "c":          "tree_sitter_c",
    "cpp":        "tree_sitter_cpp",
    "java":       "tree_sitter_java",
    "ruby":       "tree_sitter_ruby",
    "bash":       "tree_sitter_bash",
    "json":       "tree_sitter_json",
    "yaml":       "tree_sitter_yaml",
    "toml":       "tree_sitter_toml",
}

_LANG_CACHE: dict[str, Any] = {}


def _load_language(lang: str) -> Any | None:
    if not _TS_AVAILABLE:
        return None
    if lang in _LANG_CACHE:
        return _LANG_CACHE[lang]
    pkg = LANGUAGE_PACKAGES.get(lang)
    if not pkg:
        return None
    try:
        mod = __import__(pkg)
        from tree_sitter import Language  # type: ignore
        lang_obj = Language(mod.language())
        _LANG_CACHE[lang] = lang_obj
        return lang_obj
    except Exception:
        _LANG_CACHE[lang] = None
        return None


@dataclass
class ASTNode:
    type: str
    text: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    children: list["ASTNode"] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "type": self.type,
            "text": self.text[:200],
            "startLine": self.start_line,
            "endLine": self.end_line,
            "startCol": self.start_col,
            "endCol": self.end_col,
            "children": [c.as_dict() for c in self.children[:8]],
        }


@dataclass
class ExtractedSymbol:
    name: str
    kind: str          # function | class | method | variable | import | interface | enum
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""
    modifiers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "startLine": self.start_line,
            "endLine": self.end_line,
            "signature": self.signature,
            "docstring": self.docstring,
            "modifiers": self.modifiers,
        }


@dataclass
class ParseResult:
    language: str
    symbols: list[ExtractedSymbol]
    imports: list[str]
    ast_available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "symbols": [s.as_dict() for s in self.symbols],
            "imports": self.imports,
            "astAvailable": self.ast_available,
            "symbolCount": len(self.symbols),
            "error": self.error,
        }


# Regex fallback patterns per language
_REGEX_SYMBOLS: dict[str, list[tuple[re.Pattern, str]]] = {
    "python": [
        (re.compile(r"^(?P<mod>(?:async\s+)?def)\s+(?P<name>\w+)\s*\(", re.M), "function"),
        (re.compile(r"^class\s+(?P<name>\w+)", re.M), "class"),
    ],
    "typescript": [
        (re.compile(r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)", re.M), "function"),
        (re.compile(r"(?:export\s+)?class\s+(?P<name>\w+)", re.M), "class"),
        (re.compile(r"(?:export\s+)?interface\s+(?P<name>\w+)", re.M), "interface"),
        (re.compile(r"(?:export\s+)?enum\s+(?P<name>\w+)", re.M), "enum"),
        (re.compile(r"(?:export\s+)?const\s+(?P<name>\w+)\s*=\s*(?:async\s+)?\(", re.M), "function"),
    ],
    "javascript": [
        (re.compile(r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)", re.M), "function"),
        (re.compile(r"(?:export\s+)?class\s+(?P<name>\w+)", re.M), "class"),
        (re.compile(r"const\s+(?P<name>\w+)\s*=\s*(?:async\s+)?\(", re.M), "function"),
    ],
    "rust": [
        (re.compile(r"(?:pub\s+)?(?:async\s+)?fn\s+(?P<name>\w+)", re.M), "function"),
        (re.compile(r"(?:pub\s+)?struct\s+(?P<name>\w+)", re.M), "class"),
        (re.compile(r"(?:pub\s+)?enum\s+(?P<name>\w+)", re.M), "enum"),
        (re.compile(r"(?:pub\s+)?trait\s+(?P<name>\w+)", re.M), "interface"),
    ],
    "go": [
        (re.compile(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(?P<name>\w+)", re.M), "function"),
        (re.compile(r"type\s+(?P<name>\w+)\s+struct", re.M), "class"),
        (re.compile(r"type\s+(?P<name>\w+)\s+interface", re.M), "interface"),
    ],
}

_IMPORT_PATTERNS: dict[str, re.Pattern] = {
    "python": re.compile(r"^(?:import|from)\s+([\w\.]+)", re.M),
    "typescript": re.compile(r"^import\s+.*?from\s+['\"]([^'\"]+)['\"]", re.M),
    "javascript": re.compile(r"^(?:import\s+.*?from\s+|require\()['\"]([^'\"]+)['\"]", re.M),
    "rust": re.compile(r"^use\s+([\w:]+)", re.M),
    "go": re.compile(r'"([\w/\.]+)"', re.M),
}


def _regex_parse(language: str, content: str) -> ParseResult:
    symbols: list[ExtractedSymbol] = []
    lines = content.splitlines()
    for pat, kind in _REGEX_SYMBOLS.get(language, []):
        for m in pat.finditer(content):
            name = m.group("name") if "name" in m.groupdict() else ""
            if not name:
                continue
            line_no = content[:m.start()].count("\n") + 1
            symbols.append(ExtractedSymbol(name=name, kind=kind, start_line=line_no, end_line=line_no))

    imports: list[str] = []
    imp_pat = _IMPORT_PATTERNS.get(language)
    if imp_pat:
        imports = [m.group(1) for m in imp_pat.finditer(content)]

    return ParseResult(language=language, symbols=symbols, imports=imports, ast_available=False)


def _ts_node_to_ast(node: Any) -> ASTNode:
    children = [_ts_node_to_ast(c) for c in node.children if c.is_named]
    return ASTNode(
        type=node.type,
        text=node.text.decode("utf-8", errors="replace") if hasattr(node, "text") else "",
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        start_col=node.start_point[1],
        end_col=node.end_point[1],
        children=children,
    )


class TreeSitterEngine:
    """
    Wraps tree-sitter for real multi-language AST parsing.
    Falls back to regex-based extraction when tree-sitter is unavailable.
    """

    @staticmethod
    def available() -> bool:
        return _TS_AVAILABLE

    @staticmethod
    def available_languages() -> list[str]:
        if not _TS_AVAILABLE:
            return list(_REGEX_SYMBOLS.keys())
        available = []
        for lang in LANGUAGE_PACKAGES:
            if _load_language(lang) is not None:
                available.append(lang)
        return available

    def parse(self, language: str, content: str) -> ParseResult:
        if not _TS_AVAILABLE:
            return _regex_parse(language, content)

        lang_obj = _load_language(language)
        if lang_obj is None:
            return _regex_parse(language, content)

        try:
            from tree_sitter import Parser  # type: ignore
            parser = Parser(lang_obj)
            tree = parser.parse(content.encode("utf-8"))
            symbols = self._extract_symbols(tree.root_node, language, content)
            imports = self._extract_imports(tree.root_node, language)
            return ParseResult(language=language, symbols=symbols, imports=imports, ast_available=True)
        except Exception as exc:
            result = _regex_parse(language, content)
            result.error = str(exc)
            return result

    def get_ast(self, language: str, content: str) -> dict:
        if not _TS_AVAILABLE:
            return {"error": "tree-sitter not installed", "fallback": "regex"}
        lang_obj = _load_language(language)
        if lang_obj is None:
            return {"error": f"Language grammar for '{language}' not installed"}
        try:
            from tree_sitter import Parser  # type: ignore
            parser = Parser(lang_obj)
            tree = parser.parse(content.encode("utf-8"))
            return _ts_node_to_ast(tree.root_node).as_dict()
        except Exception as exc:
            return {"error": str(exc)}

    def _extract_symbols(self, root: Any, language: str, content: str) -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        self._walk(root, language, content, symbols)
        return symbols

    _SYMBOL_TYPES: dict[str, dict[str, str]] = {
        "python": {
            "function_definition": "function",
            "async_function_definition": "function",
            "class_definition": "class",
        },
        "typescript": {
            "function_declaration": "function",
            "method_definition": "method",
            "class_declaration": "class",
            "interface_declaration": "interface",
            "enum_declaration": "enum",
            "lexical_declaration": "variable",
        },
        "javascript": {
            "function_declaration": "function",
            "method_definition": "method",
            "class_declaration": "class",
            "lexical_declaration": "variable",
        },
        "rust": {
            "function_item": "function",
            "struct_item": "class",
            "enum_item": "enum",
            "trait_item": "interface",
            "impl_item": "method",
        },
        "go": {
            "function_declaration": "function",
            "method_declaration": "method",
            "type_declaration": "class",
        },
    }

    def _walk(self, node: Any, language: str, content: str, out: list[ExtractedSymbol]) -> None:
        kind_map = self._SYMBOL_TYPES.get(language, {})
        kind = kind_map.get(node.type)
        if kind:
            name = ""
            for child in node.children:
                if child.type == "identifier" or child.type == "name":
                    name = child.text.decode("utf-8", errors="replace")
                    break
            if name:
                text = node.text.decode("utf-8", errors="replace") if hasattr(node, "text") else ""
                out.append(ExtractedSymbol(
                    name=name,
                    kind=kind,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=text.splitlines()[0][:200] if text else "",
                ))
        for child in node.children:
            self._walk(child, language, content, out)

    def _extract_imports(self, root: Any, language: str) -> list[str]:
        imports: list[str] = []
        import_types = {
            "python": ["import_statement", "import_from_statement"],
            "typescript": ["import_declaration"],
            "javascript": ["import_declaration", "call_expression"],
            "rust": ["use_declaration"],
            "go": ["import_declaration"],
        }
        types = import_types.get(language, [])

        def walk(node: Any) -> None:
            if node.type in types:
                text = node.text.decode("utf-8", errors="replace") if hasattr(node, "text") else ""
                if text:
                    imports.append(text.splitlines()[0][:200])
            for child in node.children:
                walk(child)

        walk(root)
        return imports
