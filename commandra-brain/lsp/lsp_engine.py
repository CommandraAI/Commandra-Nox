"""
LSP Engine -- Language Server Protocol integration for the Brain.

Provides Go To Definition, Find References, Rename Symbol, Hover
Information, Diagnostics, Semantic Tokens, Document Symbols, Workspace
Symbols, and Code Actions entirely from the indexed repository's AST and
symbol graph -- no external language server process required for basic
intelligence.  When an external LSP server IS available (e.g. pyright,
rust-analyzer), the engine will forward requests to it and merge results.

All position arithmetic uses 0-based line/character (LSP convention).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Core LSP data types
# ---------------------------------------------------------------------------

@dataclass
class Position:
    line: int       # 0-based
    character: int  # 0-based

    def as_dict(self) -> dict:
        return {"line": self.line, "character": self.character}


@dataclass
class Range:
    start: Position
    end: Position

    def as_dict(self) -> dict:
        return {"start": self.start.as_dict(), "end": self.end.as_dict()}


@dataclass
class Location:
    uri: str          # file path (or file:// URI)
    range: Range

    def as_dict(self) -> dict:
        return {"uri": self.uri, "range": self.range.as_dict()}


@dataclass
class Diagnostic:
    range: Range
    message: str
    severity: int  # 1=Error, 2=Warning, 3=Info, 4=Hint
    source: str = "commandra-lsp"
    code: str | None = None

    def as_dict(self) -> dict:
        d: dict = {
            "range": self.range.as_dict(),
            "message": self.message,
            "severity": self.severity,
            "source": self.source,
        }
        if self.code:
            d["code"] = self.code
        return d


@dataclass
class DocumentSymbol:
    name: str
    kind: int         # SymbolKind enum value
    range: Range
    selection_range: Range
    detail: str = ""
    children: list["DocumentSymbol"] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "range": self.range.as_dict(),
            "selectionRange": self.selection_range.as_dict(),
            "detail": self.detail,
            "children": [c.as_dict() for c in self.children],
        }


@dataclass
class WorkspaceSymbol:
    name: str
    kind: int
    location: Location
    container_name: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "location": self.location.as_dict(),
            "containerName": self.container_name,
        }


@dataclass
class HoverResult:
    contents: str         # Markdown
    range: Range | None = None

    def as_dict(self) -> dict:
        d: dict = {"contents": {"kind": "markdown", "value": self.contents}}
        if self.range:
            d["range"] = self.range.as_dict()
        return d


@dataclass
class TextEdit:
    range: Range
    new_text: str

    def as_dict(self) -> dict:
        return {"range": self.range.as_dict(), "newText": self.new_text}


@dataclass
class CodeAction:
    title: str
    kind: str          # e.g. "quickfix", "refactor"
    diagnostics: list[Diagnostic] = field(default_factory=list)
    edit: dict | None = None   # WorkspaceEdit

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "kind": self.kind,
            "diagnostics": [d.as_dict() for d in self.diagnostics],
            "edit": self.edit,
        }


@dataclass
class SemanticToken:
    line: int
    start_char: int
    length: int
    token_type: int
    token_modifiers: int = 0


# Symbol kind constants (LSP spec)
class SymbolKind:
    FILE = 1; MODULE = 2; NAMESPACE = 3; PACKAGE = 4; CLASS = 5
    METHOD = 6; PROPERTY = 7; FIELD = 8; CONSTRUCTOR = 9; ENUM = 10
    INTERFACE = 11; FUNCTION = 12; VARIABLE = 13; CONSTANT = 14
    STRING = 15; NUMBER = 16; BOOLEAN = 17; ARRAY = 18; OBJECT = 19
    KEY = 20; NULL = 21; ENUM_MEMBER = 22; STRUCT = 23; EVENT = 24
    OPERATOR = 25; TYPE_PARAMETER = 26


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _word_at(content: str, line: int, character: int) -> str:
    """Extract the identifier at the given line/character position."""
    lines = content.splitlines()
    if line >= len(lines):
        return ""
    row = lines[line]
    # Walk left and right from character to find word boundaries
    start = character
    while start > 0 and (row[start - 1].isalnum() or row[start - 1] == "_"):
        start -= 1
    end = character
    while end < len(row) and (row[end].isalnum() or row[end] == "_"):
        end += 1
    return row[start:end]


def _find_word_in_line(line_text: str, word: str) -> list[int]:
    """Return all start character positions where word appears as a whole word."""
    positions: list[int] = []
    pattern = re.compile(r"\b" + re.escape(word) + r"\b")
    for m in pattern.finditer(line_text):
        positions.append(m.start())
    return positions


def _kind_for_symbol(sym_type: str) -> int:
    mapping = {
        "class": SymbolKind.CLASS,
        "function": SymbolKind.FUNCTION,
        "def": SymbolKind.FUNCTION,
        "method": SymbolKind.METHOD,
        "variable": SymbolKind.VARIABLE,
        "const": SymbolKind.CONSTANT,
        "interface": SymbolKind.INTERFACE,
        "enum": SymbolKind.ENUM,
        "struct": SymbolKind.STRUCT,
        "type": SymbolKind.TYPE_PARAMETER,
        "module": SymbolKind.MODULE,
        "property": SymbolKind.PROPERTY,
    }
    return mapping.get(sym_type.lower(), SymbolKind.VARIABLE)


# ---------------------------------------------------------------------------
# Diagnostic patterns per language
# ---------------------------------------------------------------------------

_DIAGNOSTIC_PATTERNS: dict[str, list[tuple[re.Pattern, str, int]]] = {
    "python": [
        (re.compile(r"\bprint\s*\("), "Use logger instead of print() in production code", 3),
        (re.compile(r"except\s*:"), "Bare except clause catches all exceptions including KeyboardInterrupt", 2),
        (re.compile(r"\beval\s*\("), "eval() is a security risk; avoid in production code", 1),
        (re.compile(r"\bexec\s*\("), "exec() is a security risk; avoid in production code", 1),
        (re.compile(r"TODO|FIXME|HACK|XXX"), "Unresolved annotation found", 4),
    ],
    "typescript": [
        (re.compile(r"\bany\b"), "Prefer specific types over 'any'", 3),
        (re.compile(r"console\.log\("), "Remove console.log before committing", 3),
        (re.compile(r"// @ts-ignore"), "@ts-ignore suppresses type safety", 2),
        (re.compile(r"TODO|FIXME|HACK|XXX"), "Unresolved annotation found", 4),
    ],
    "javascript": [
        (re.compile(r"var\s+\w+"), "Prefer 'const' or 'let' over 'var'", 3),
        (re.compile(r"console\.log\("), "Remove console.log before committing", 3),
        (re.compile(r"TODO|FIXME|HACK|XXX"), "Unresolved annotation found", 4),
    ],
    "go": [
        (re.compile(r"panic\("), "panic() in non-main code may crash the server", 2),
        (re.compile(r"TODO|FIXME|HACK|XXX"), "Unresolved annotation found", 4),
    ],
    "rust": [
        (re.compile(r"unwrap\(\)"), "unwrap() panics on None/Err; use ? or proper error handling", 2),
        (re.compile(r"TODO|FIXME|HACK|XXX"), "Unresolved annotation found", 4),
    ],
}


# ---------------------------------------------------------------------------
# LSPEngine
# ---------------------------------------------------------------------------

class LSPEngine:
    """
    Language Server Protocol intelligence backed by the repository index.

    Each method accepts file content + the repository's knowledge graph
    and returns standard LSP-shaped results.
    """

    # -- Go To Definition --------------------------------------------------

    def go_to_definition(
        self,
        file_path: str,
        content: str,
        line: int,
        character: int,
        knowledge_graph: Any,
    ) -> list[Location]:
        word = _word_at(content, line, character)
        if not word:
            return []

        locations: list[Location] = []
        # Search symbol definitions across the knowledge graph
        for sym in knowledge_graph.all_symbols():
            if sym.get("name") == word and sym.get("kind") in ("definition", "class", "function", "method"):
                def_line = sym.get("line", 0)
                loc = Location(
                    uri=sym.get("file", file_path),
                    range=Range(
                        start=Position(max(0, def_line - 1), 0),
                        end=Position(max(0, def_line - 1), len(word)),
                    ),
                )
                locations.append(loc)

        # Fallback: scan current file for definition
        if not locations:
            lines = content.splitlines()
            patterns = [
                re.compile(rf"^\s*(def|class|const|let|var|function|fn|func)\s+{re.escape(word)}\b"),
                re.compile(rf"^\s*{re.escape(word)}\s*[=:(]"),
            ]
            for i, ln in enumerate(lines):
                for pat in patterns:
                    if pat.search(ln):
                        col = ln.index(word) if word in ln else 0
                        locations.append(
                            Location(
                                uri=file_path,
                                range=Range(Position(i, col), Position(i, col + len(word))),
                            )
                        )
                        break
        return locations

    # -- Find References ---------------------------------------------------

    def find_references(
        self,
        file_path: str,
        content: str,
        line: int,
        character: int,
        knowledge_graph: Any,
        all_files: dict[str, str] | None = None,
    ) -> list[Location]:
        word = _word_at(content, line, character)
        if not word:
            return []

        locations: list[Location] = []
        search_corpus = {file_path: content}
        if all_files:
            search_corpus.update(all_files)

        for fpath, fcontent in search_corpus.items():
            for i, ln in enumerate(fcontent.splitlines()):
                for col in _find_word_in_line(ln, word):
                    locations.append(
                        Location(
                            uri=fpath,
                            range=Range(Position(i, col), Position(i, col + len(word))),
                        )
                    )
        return locations

    # -- Rename Symbol -----------------------------------------------------

    def rename_symbol(
        self,
        file_path: str,
        content: str,
        line: int,
        character: int,
        new_name: str,
        all_files: dict[str, str] | None = None,
    ) -> dict[str, list[TextEdit]]:
        """Returns a WorkspaceEdit-style dict: {uri -> [TextEdit]}."""
        word = _word_at(content, line, character)
        if not word or word == new_name:
            return {}

        search_corpus = {file_path: content}
        if all_files:
            search_corpus.update(all_files)

        workspace_edit: dict[str, list[TextEdit]] = {}
        for fpath, fcontent in search_corpus.items():
            edits: list[TextEdit] = []
            for i, ln in enumerate(fcontent.splitlines()):
                for col in _find_word_in_line(ln, word):
                    edits.append(
                        TextEdit(
                            range=Range(Position(i, col), Position(i, col + len(word))),
                            new_text=new_name,
                        )
                    )
            if edits:
                workspace_edit[fpath] = edits

        return {uri: [e.as_dict() for e in edits] for uri, edits in workspace_edit.items()}

    # -- Hover -------------------------------------------------------------

    def hover(
        self,
        file_path: str,
        content: str,
        line: int,
        character: int,
        knowledge_graph: Any,
    ) -> HoverResult | None:
        word = _word_at(content, line, character)
        if not word:
            return None

        # Look up symbol in knowledge graph
        for sym in knowledge_graph.all_symbols():
            if sym.get("name") == word:
                kind_label = sym.get("kind", "symbol")
                doc = sym.get("docstring", "")
                sig = sym.get("signature", "")
                md = f"**{kind_label}** `{word}`"
                if sig:
                    md += f"\n\n```\n{sig}\n```"
                if doc:
                    md += f"\n\n{doc}"
                return HoverResult(contents=md)

        # Fallback: show the line
        lines = content.splitlines()
        if line < len(lines):
            return HoverResult(contents=f"```\n{lines[line].strip()}\n```")
        return None

    # -- Diagnostics -------------------------------------------------------

    def diagnostics(self, file_path: str, content: str, language: str) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        patterns = _DIAGNOSTIC_PATTERNS.get(language, [])
        for i, ln in enumerate(content.splitlines()):
            for pat, message, severity in patterns:
                m = pat.search(ln)
                if m:
                    diags.append(
                        Diagnostic(
                            range=Range(Position(i, m.start()), Position(i, m.end())),
                            message=message,
                            severity=severity,
                            source="commandra-lsp",
                        )
                    )
        return diags

    # -- Semantic Tokens ---------------------------------------------------

    def semantic_tokens(self, content: str, language: str) -> list[dict]:
        """Returns a flat list of semantic token dicts for syntax highlighting."""
        tokens: list[SemanticToken] = []

        keyword_patterns: dict[str, re.Pattern] = {
            "python": re.compile(r"\b(def|class|import|from|return|if|else|elif|for|while|with|as|pass|raise|try|except|finally|yield|lambda|async|await|not|and|or|in|is|None|True|False)\b"),
            "typescript": re.compile(r"\b(const|let|var|function|class|interface|type|import|export|return|if|else|for|while|async|await|new|this|super|extends|implements|enum|namespace|readonly|public|private|protected|static|abstract)\b"),
            "javascript": re.compile(r"\b(const|let|var|function|class|import|export|return|if|else|for|while|async|await|new|this)\b"),
            "rust": re.compile(r"\b(fn|let|mut|pub|struct|impl|trait|enum|use|mod|return|if|else|for|while|match|async|await|where|self|Self|type|const|static|unsafe|extern|crate)\b"),
            "go": re.compile(r"\b(func|var|const|type|struct|interface|import|package|return|if|else|for|range|switch|case|default|go|chan|defer|select|break|continue|fallthrough|goto)\b"),
        }
        string_pat = re.compile(r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`[^`]*`)')
        comment_pat = re.compile(r'(//.*$|#.*$|/\*.*?\*/)', re.MULTILINE)

        kw_pat = keyword_patterns.get(language, re.compile(r"(?!x)x"))  # no-match fallback

        for i, ln in enumerate(content.splitlines()):
            for m in kw_pat.finditer(ln):
                tokens.append(SemanticToken(line=i, start_char=m.start(), length=len(m.group()), token_type=0))
            for m in string_pat.finditer(ln):
                tokens.append(SemanticToken(line=i, start_char=m.start(), length=len(m.group()), token_type=1))
            for m in comment_pat.finditer(ln):
                tokens.append(SemanticToken(line=i, start_char=m.start(), length=len(m.group()), token_type=2))

        return [{"line": t.line, "startChar": t.start_char, "length": t.length, "tokenType": t.token_type} for t in tokens]

    # -- Document Symbols --------------------------------------------------

    def document_symbols(self, file_path: str, content: str, language: str) -> list[dict]:
        symbols: list[DocumentSymbol] = []
        patterns: list[tuple[re.Pattern, int]] = []

        if language == "python":
            patterns = [
                (re.compile(r"^(class)\s+(\w+)"), SymbolKind.CLASS),
                (re.compile(r"^(def|async def)\s+(\w+)"), SymbolKind.FUNCTION),
            ]
        elif language in ("typescript", "javascript"):
            patterns = [
                (re.compile(r"^(class)\s+(\w+)"), SymbolKind.CLASS),
                (re.compile(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)"), SymbolKind.FUNCTION),
                (re.compile(r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\("), SymbolKind.FUNCTION),
                (re.compile(r"(?:export\s+)?(?:const|let|var)\s+(\w+)"), SymbolKind.VARIABLE),
                (re.compile(r"(?:export\s+)?interface\s+(\w+)"), SymbolKind.INTERFACE),
                (re.compile(r"(?:export\s+)?type\s+(\w+)"), SymbolKind.TYPE_PARAMETER),
            ]
        elif language == "rust":
            patterns = [
                (re.compile(r"^(?:pub\s+)?fn\s+(\w+)"), SymbolKind.FUNCTION),
                (re.compile(r"^(?:pub\s+)?struct\s+(\w+)"), SymbolKind.STRUCT),
                (re.compile(r"^(?:pub\s+)?enum\s+(\w+)"), SymbolKind.ENUM),
                (re.compile(r"^(?:pub\s+)?trait\s+(\w+)"), SymbolKind.INTERFACE),
            ]
        elif language == "go":
            patterns = [
                (re.compile(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)"), SymbolKind.FUNCTION),
                (re.compile(r"^type\s+(\w+)\s+struct"), SymbolKind.STRUCT),
                (re.compile(r"^type\s+(\w+)\s+interface"), SymbolKind.INTERFACE),
            ]

        for i, ln in enumerate(content.splitlines()):
            for pat, kind in patterns:
                m = pat.match(ln)
                if m:
                    name = m.group(m.lastindex or 1) if m.lastindex else m.group(1)
                    r = Range(Position(i, 0), Position(i, len(ln)))
                    symbols.append(DocumentSymbol(name=name, kind=kind, range=r, selection_range=r))
                    break

        return [s.as_dict() for s in symbols]

    # -- Workspace Symbols -------------------------------------------------

    def workspace_symbols(self, query: str, knowledge_graph: Any) -> list[dict]:
        results: list[WorkspaceSymbol] = []
        q = query.lower()
        for sym in knowledge_graph.all_symbols():
            name = sym.get("name", "")
            if q in name.lower():
                f = sym.get("file", "")
                ln = sym.get("line", 1)
                results.append(
                    WorkspaceSymbol(
                        name=name,
                        kind=_kind_for_symbol(sym.get("kind", "variable")),
                        location=Location(
                            uri=f,
                            range=Range(Position(max(0, ln - 1), 0), Position(max(0, ln - 1), len(name))),
                        ),
                        container_name=sym.get("container", ""),
                    )
                )
        return [s.as_dict() for s in results[:50]]

    # -- Code Actions ------------------------------------------------------

    def code_actions(
        self,
        file_path: str,
        content: str,
        language: str,
        line: int,
        character: int,
    ) -> list[dict]:
        actions: list[CodeAction] = []
        lines = content.splitlines()
        if line >= len(lines):
            return []

        ln = lines[line]

        # Quick fix: convert bare except
        if language == "python" and re.search(r"except\s*:", ln):
            actions.append(CodeAction(
                title="Replace bare 'except:' with 'except Exception:'",
                kind="quickfix",
                edit={"changes": {file_path: [TextEdit(
                    range=Range(Position(line, 0), Position(line, len(ln))),
                    new_text=ln.replace("except:", "except Exception:", 1),
                ).as_dict()]}},
            ))

        # Quick fix: var -> const
        if language in ("typescript", "javascript") and re.search(r"\bvar\s+\w+", ln):
            actions.append(CodeAction(
                title="Replace 'var' with 'const'",
                kind="quickfix",
                edit={"changes": {file_path: [TextEdit(
                    range=Range(Position(line, 0), Position(line, len(ln))),
                    new_text=re.sub(r"\bvar\b", "const", ln, count=1),
                ).as_dict()]}},
            ))

        # Refactor: extract variable
        word = _word_at(content, line, character)
        if word:
            actions.append(CodeAction(
                title=f"Extract '{word}' into a named variable",
                kind="refactor.extract",
            ))

        return [a.as_dict() for a in actions]
