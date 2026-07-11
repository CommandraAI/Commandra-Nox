"""
Knowledge Graph -- aggregates per-file AST nodes (repository/ast_parsers.py)
into a repository-wide graph of classes, interfaces, functions/methods, and
their relationships (inheritance, calls, containment). This is what turns
Repository Intelligence from "a pile of indexed files" into something the
Brain can actually reason over structurally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from repository.ast_parsers import AstNode, FileAst, parse_file_ast


@dataclass
class SymbolRef:
    path: str
    node: AstNode

    def qualified_name(self) -> str:
        return f"{self.node.parent}.{self.node.name}" if self.node.parent else self.node.name


@dataclass
class KnowledgeGraph:
    file_asts: dict[str, FileAst] = field(default_factory=dict)
    # name -> list of (path, node) -- a name can be defined in multiple files
    symbols_by_name: dict[str, list[SymbolRef]] = field(default_factory=dict)

    def index_file(self, path: str, language: str, source: str) -> FileAst:
        file_ast = parse_file_ast(path, language, source)
        self.file_asts[path] = file_ast
        for node in file_ast.nodes:
            self.symbols_by_name.setdefault(node.name, []).append(SymbolRef(path=path, node=node))
        return file_ast

    def remove_file(self, path: str) -> None:
        self.file_asts.pop(path, None)
        for name in list(self.symbols_by_name):
            self.symbols_by_name[name] = [r for r in self.symbols_by_name[name] if r.path != path]
            if not self.symbols_by_name[name]:
                del self.symbols_by_name[name]

    # -- Queries --------------------------------------------------------

    def find_symbol(self, name: str) -> list[SymbolRef]:
        return self.symbols_by_name.get(name, [])

    def find_references(self, name: str) -> list[dict]:
        """Every node anywhere in the repo whose `calls` list mentions
        `name` -- i.e. every call site, not just the definition."""
        refs = []
        for path, file_ast in self.file_asts.items():
            for node in file_ast.nodes:
                if name in node.calls:
                    refs.append({"path": path, "caller": node.name, "line": node.line})
        return refs

    def class_hierarchy(self) -> dict[str, list[str]]:
        """class/interface name -> list of direct base names, across the repo."""
        hierarchy: dict[str, list[str]] = {}
        for file_ast in self.file_asts.values():
            for node in file_ast.classes():
                hierarchy[node.name] = node.bases
        return hierarchy

    def subclasses_of(self, base_name: str) -> list[str]:
        return [name for name, bases in self.class_hierarchy().items() if base_name in bases]

    def methods_of(self, class_name: str) -> list[AstNode]:
        methods = []
        for file_ast in self.file_asts.values():
            methods.extend(n for n in file_ast.functions() if n.parent == class_name)
        return methods

    def call_graph(self) -> dict[str, list[str]]:
        """function/method qualified name -> list of names it calls."""
        graph: dict[str, list[str]] = {}
        for file_ast in self.file_asts.values():
            for node in file_ast.functions():
                qualified = f"{node.parent}.{node.name}" if node.parent else node.name
                graph[qualified] = node.calls
        return graph

    def summary(self) -> dict:
        total_classes = sum(len(fa.classes()) for fa in self.file_asts.values())
        total_functions = sum(len(fa.functions()) for fa in self.file_asts.values())
        return {
            "filesParsed": len(self.file_asts),
            "classCount": total_classes,
            "functionCount": total_functions,
            "symbolCount": sum(len(v) for v in self.symbols_by_name.values()),
        }
