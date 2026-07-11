"""
Code Graph Engine -- builds dependency graphs, call graphs, import graphs,
and relationship graphs from AST analysis.

Uses tree-sitter-graph when available, otherwise derives graphs from the
tree-sitter symbol extraction and import analysis.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class GraphEdge:
    source: str      # file or symbol
    target: str
    kind: str        # imports | calls | extends | implements | uses
    line: int = 0

    def as_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "kind": self.kind, "line": self.line}


@dataclass
class CodeGraph:
    nodes: list[str]
    edges: list[GraphEdge]
    kind: str        # import | call | dependency | full

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "nodeCount": len(self.nodes),
            "edgeCount": len(self.edges),
            "nodes": self.nodes[:500],
            "edges": [e.as_dict() for e in self.edges[:2000]],
        }

    def find_dependents(self, target: str) -> list[str]:
        return [e.source for e in self.edges if e.target == target or target in e.target]

    def find_dependencies(self, source: str) -> list[str]:
        return [e.target for e in self.edges if e.source == source or source in e.source]


_IMPORT_PATTERNS: dict[str, re.Pattern] = {
    "python":     re.compile(r"^(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", re.M),
    "typescript": re.compile(r"""^import\s+.*?from\s+['"]([^'"]+)['"]""", re.M),
    "javascript": re.compile(r"""(?:^import\s+.*?from\s+|require\()['"](\.?[^'"]+)['"]""", re.M),
    "rust":       re.compile(r"^use\s+([\w:]+)", re.M),
    "go":         re.compile(r'"(\.?[\w/\.]+)"', re.M),
}

_CALL_PATTERNS: dict[str, re.Pattern] = {
    "python":     re.compile(r"\b(\w+)\s*\("),
    "typescript": re.compile(r"\b(\w+)\s*[<(]"),
    "javascript": re.compile(r"\b(\w+)\s*\("),
    "rust":       re.compile(r"\b(\w+)\s*[!(<]"),
    "go":         re.compile(r"\b(\w+)\s*\("),
}

_EXTEND_PATTERNS: dict[str, list[tuple[re.Pattern, str]]] = {
    "python": [
        (re.compile(r"class\s+\w+\(([^)]+)\)"), "extends"),
    ],
    "typescript": [
        (re.compile(r"class\s+\w+\s+extends\s+(\w+)"), "extends"),
        (re.compile(r"class\s+\w+[^{]*implements\s+([\w,\s]+)"), "implements"),
    ],
    "java": [
        (re.compile(r"class\s+\w+\s+extends\s+(\w+)"), "extends"),
        (re.compile(r"class\s+\w+[^{]*implements\s+([\w,\s]+)"), "implements"),
    ],
}


class GraphEngine:
    """Derives import, call, and dependency graphs from file contents."""

    def build_import_graph(self, files: dict[str, tuple[str, str]]) -> CodeGraph:
        """files: {path -> (language, content)}"""
        nodes = list(files.keys())
        edges: list[GraphEdge] = []

        for path, (lang, content) in files.items():
            pat = _IMPORT_PATTERNS.get(lang)
            if not pat:
                continue
            for m in pat.finditer(content):
                target = (m.group(1) or m.group(2) or "").strip()
                if not target:
                    continue
                # Resolve relative imports to actual files
                resolved = self._resolve(path, target, nodes)
                line = content[:m.start()].count("\n") + 1
                edges.append(GraphEdge(source=path, target=resolved or target, kind="imports", line=line))

        return CodeGraph(nodes=nodes, edges=edges, kind="import")

    def build_call_graph(self, file_path: str, language: str, content: str,
                         known_symbols: set[str]) -> CodeGraph:
        """Build call graph for a single file against a set of known symbol names."""
        edges: list[GraphEdge] = []
        pat = _CALL_PATTERNS.get(language)
        if not pat:
            return CodeGraph(nodes=[file_path], edges=[], kind="call")

        for m in pat.finditer(content):
            callee = m.group(1)
            if callee in known_symbols and callee not in ("if", "for", "while", "return"):
                line = content[:m.start()].count("\n") + 1
                edges.append(GraphEdge(source=file_path, target=callee, kind="calls", line=line))

        return CodeGraph(nodes=[file_path] + list({e.target for e in edges}), edges=edges, kind="call")

    def build_inheritance_graph(self, files: dict[str, tuple[str, str]]) -> CodeGraph:
        nodes: list[str] = []
        edges: list[GraphEdge] = []
        for path, (lang, content) in files.items():
            for pat, kind in _EXTEND_PATTERNS.get(lang, []):
                for m in pat.finditer(content):
                    parents = [p.strip() for p in m.group(1).split(",")]
                    cls_m = re.search(r"class\s+(\w+)", content[:m.start()])
                    cls_name = cls_m.group(1) if cls_m else path
                    if cls_name not in nodes:
                        nodes.append(cls_name)
                    for parent in parents:
                        if parent not in nodes:
                            nodes.append(parent)
                        line = content[:m.start()].count("\n") + 1
                        edges.append(GraphEdge(source=cls_name, target=parent, kind=kind, line=line))

        return CodeGraph(nodes=nodes, edges=edges, kind="inheritance")

    def full_graph(self, files: dict[str, tuple[str, str]]) -> CodeGraph:
        import_graph = self.build_import_graph(files)
        inherit_graph = self.build_inheritance_graph(files)
        all_nodes = list(dict.fromkeys(import_graph.nodes + inherit_graph.nodes))
        all_edges = import_graph.edges + inherit_graph.edges
        return CodeGraph(nodes=all_nodes, edges=all_edges, kind="full")

    @staticmethod
    def _resolve(source_path: str, target: str, all_paths: list[str]) -> str | None:
        if not target.startswith("."):
            return None
        base = "/".join(source_path.split("/")[:-1])
        resolved = f"{base}/{target.lstrip('./')}"
        for path in all_paths:
            stem = path.rsplit(".", 1)[0]
            if stem.endswith(resolved.replace("./", "")) or path == resolved:
                return path
        return None
