"""
Dependency Graph & Import Graph -- turns the per-file import lists that the
symbol extractor produces into an actual graph the rest of the Brain can
reason over: "what does this file depend on", "what depends on this file",
and repo-wide fan-in/fan-out so the Context Engine and Refactoring Engine
can find hubs, cycles, and dead code candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DependencyGraph:
    # path -> set of resolved paths it imports
    edges: dict[str, set[str]] = field(default_factory=dict)
    # path -> set of resolved paths that import it
    reverse_edges: dict[str, set[str]] = field(default_factory=dict)
    # imports that could not be resolved to a file in the repo (external deps)
    unresolved: dict[str, set[str]] = field(default_factory=dict)

    def add_edge(self, source: str, target: str) -> None:
        self.edges.setdefault(source, set()).add(target)
        self.reverse_edges.setdefault(target, set()).add(source)

    def add_unresolved(self, source: str, module: str) -> None:
        self.unresolved.setdefault(source, set()).add(module)

    def dependents_of(self, path: str) -> list[str]:
        return sorted(self.reverse_edges.get(path, set()))

    def dependencies_of(self, path: str) -> list[str]:
        return sorted(self.edges.get(path, set()))

    def fan_in(self, path: str) -> int:
        return len(self.reverse_edges.get(path, set()))

    def fan_out(self, path: str) -> int:
        return len(self.edges.get(path, set()))

    def hubs(self, top_n: int = 10) -> list[dict]:
        """Files with the highest fan-in -- widely depended-on, high blast radius."""
        scored = [
            {"path": path, "fanIn": len(deps)}
            for path, deps in self.reverse_edges.items()
        ]
        return sorted(scored, key=lambda x: x["fanIn"], reverse=True)[:top_n]

    def orphans(self, all_paths: list[str]) -> list[str]:
        """Files nothing in the repo imports -- candidates for dead code, unless
        they are entry points (main/index/app files), which callers should filter."""
        return sorted(p for p in all_paths if p not in self.reverse_edges or not self.reverse_edges[p])

    def find_cycles(self) -> list[list[str]]:
        """Detect import cycles via DFS. Small repos only -- O(V+E) per start node."""
        cycles: list[list[str]] = []
        visited: set[str] = set()

        def dfs(node: str, stack: list[str]) -> None:
            if node in stack:
                cycle = stack[stack.index(node):] + [node]
                if sorted(cycle) not in [sorted(c) for c in cycles]:
                    cycles.append(cycle)
                return
            if node in visited:
                return
            visited.add(node)
            stack.append(node)
            for neighbor in self.edges.get(node, set()):
                dfs(neighbor, stack)
            stack.pop()

        for start in list(self.edges.keys()):
            dfs(start, [])

        return cycles

    def summary(self) -> dict:
        return {
            "fileCount": len(set(self.edges) | set(self.reverse_edges)),
            "edgeCount": sum(len(v) for v in self.edges.values()),
            "unresolvedImportCount": sum(len(v) for v in self.unresolved.values()),
            "hubs": self.hubs(),
            "cycles": self.find_cycles()[:10],
        }


def _resolve_import(all_paths: set[str], source_path: str, imported: str) -> str | None:
    """Best-effort match of an import string to a file path within the repo."""
    if imported.startswith("."):
        # relative import: resolve relative to the source file's directory
        base = "/".join(source_path.split("/")[:-1])
        candidate = "/".join(
            p for p in (base + "/" + imported).split("/") if p not in ("", ".")
        )
        candidate = _normalize_relative(base, imported)
        for suffix in ("", ".ts", ".tsx", ".js", ".jsx", ".py", "/index.ts", "/index.js", "/__init__.py"):
            if candidate + suffix in all_paths:
                return candidate + suffix
        return None

    normalized = imported.replace(".", "/").lstrip("/")
    for path in all_paths:
        stem = path.rsplit(".", 1)[0]
        if stem == normalized or stem.endswith("/" + normalized) or path.endswith(imported):
            return path
    return None


def _normalize_relative(base: str, imported: str) -> str:
    parts = base.split("/") if base else []
    for segment in imported.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return "/".join(parts)


def build_dependency_graph(files: dict[str, "object"]) -> DependencyGraph:
    """`files` is `RepositoryIndex.files` (path -> IndexedFile)."""
    graph = DependencyGraph()
    all_paths = set(files.keys())

    for path, indexed_file in files.items():
        for imported in indexed_file.symbols.imports:
            resolved = _resolve_import(all_paths, path, imported)
            if resolved and resolved != path:
                graph.add_edge(path, resolved)
            else:
                graph.add_unresolved(path, imported)

    return graph
