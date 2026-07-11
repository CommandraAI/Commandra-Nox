"""
Repository Intelligence -- builds and maintains an internal semantic map of
a repository: file list, per-file symbols/imports, a naive dependency
graph, and detected project facts (frameworks, config files, languages
present). This is the source of truth the Context Engine ranks against.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from context.semantic_search import SemanticIndex
from repository.architecture import ArchitectureSummary, summarize_architecture
from repository.ast_parsers import SUPPORTED_AST_LANGUAGES
from repository.cache import save_index
from repository.dependency_graph import DependencyGraph, build_dependency_graph
from repository.knowledge_graph import KnowledgeGraph
from repository.package_managers import PackageManagerInfo, detect_package_managers
from repository.scanner import RepoFile, scan_repository
from repository.symbols import FileSymbols, extract_symbols

FRAMEWORK_SIGNALS = {
    "package.json": "Node.js project",
    "requirements.txt": "Python (pip) project",
    "pyproject.toml": "Python (pyproject) project",
    "Cargo.toml": "Rust project",
    "go.mod": "Go project",
    "pom.xml": "Java (Maven) project",
    "build.gradle": "Java/Kotlin (Gradle) project",
    "Gemfile": "Ruby project",
    "composer.json": "PHP (Composer) project",
    "pubspec.yaml": "Dart/Flutter project",
    "next.config.js": "Next.js app",
    "next.config.ts": "Next.js app",
    "vite.config.ts": "Vite app",
    "angular.json": "Angular app",
    "tailwind.config.js": "Tailwind CSS",
    "tailwind.config.ts": "Tailwind CSS",
    "docker-compose.yml": "Docker Compose",
    "Dockerfile": "Docker",
}


@dataclass
class IndexedFile:
    path: str
    language: str
    size: int
    content: str
    symbols: FileSymbols


@dataclass
class RepositoryIndex:
    repo_id: str
    root: str
    indexed_at: float
    files: dict[str, IndexedFile] = field(default_factory=dict)
    languages: dict[str, int] = field(default_factory=dict)
    frameworks: list[str] = field(default_factory=list)
    skipped: int = 0
    package_managers: list[PackageManagerInfo] = field(default_factory=list)
    dependency_graph: DependencyGraph = field(default_factory=DependencyGraph)
    architecture: ArchitectureSummary | None = None
    knowledge_graph: KnowledgeGraph = field(default_factory=KnowledgeGraph)
    semantic_index: SemanticIndex = field(default_factory=SemanticIndex)

    @property
    def file_count(self) -> int:
        return len(self.files)

    def rebuild_derived(self) -> None:
        """Recompute the dependency graph and architecture summary from the
        current `files` map. Called after a full build or an incremental
        update so downstream consumers never see a stale graph."""
        self.dependency_graph = build_dependency_graph(self.files)
        self.architecture = summarize_architecture(self, self.dependency_graph)

    def summary(self) -> dict:
        return {
            "repoId": self.repo_id,
            "root": self.root,
            "indexedAt": self.indexed_at,
            "fileCount": self.file_count,
            "skipped": self.skipped,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "packageManagers": [pm.__dict__ for pm in self.package_managers],
            "dependencyGraph": self.dependency_graph.summary(),
            "architecture": self.architecture.as_dict() if self.architecture else None,
            "knowledgeGraph": self.knowledge_graph.summary(),
        }

    def file_list(self) -> list[dict]:
        return [
            {
                "path": f.path,
                "language": f.language,
                "size": f.size,
                "symbolCount": len(f.symbols.symbols),
            }
            for f in sorted(self.files.values(), key=lambda x: x.path)
        ]


def _detect_frameworks(files: list[RepoFile]) -> list[str]:
    names = {f.path.split("/")[-1] for f in files}
    return sorted({label for filename, label in FRAMEWORK_SIGNALS.items() if filename in names})


class RepositoryIndexer:
    """Builds a RepositoryIndex from a directory on disk."""

    def build(self, repo_id: str, root: str) -> RepositoryIndex:
        scan = scan_repository(root)
        index = RepositoryIndex(
            repo_id=repo_id,
            root=root,
            indexed_at=time.time(),
            skipped=scan.skipped,
        )

        for repo_file in scan.files:
            symbols = extract_symbols(repo_file.path, repo_file.language, repo_file.content)
            index.files[repo_file.path] = IndexedFile(
                path=repo_file.path,
                language=repo_file.language,
                size=repo_file.size,
                content=repo_file.content,
                symbols=symbols,
            )
            index.languages[repo_file.language] = index.languages.get(repo_file.language, 0) + 1
            index.semantic_index.add_document(repo_file.path, repo_file.content)
            if repo_file.language in SUPPORTED_AST_LANGUAGES:
                index.knowledge_graph.index_file(repo_file.path, repo_file.language, repo_file.content)

        index.frameworks = _detect_frameworks(scan.files)
        index.package_managers = detect_package_managers(scan.files)
        index.rebuild_derived()
        save_index(index)
        return index

    def update_file(self, index: RepositoryIndex, path: str, content: str) -> None:
        """Incremental update -- re-index a single changed file in place and
        rebuild only the derived graph/architecture (not a full repo rescan)."""
        from repository.scanner import detect_language

        was_present = path in index.files
        old_language = index.files[path].language if was_present else None

        language = detect_language(path)
        symbols = extract_symbols(path, language, content)
        index.files[path] = IndexedFile(
            path=path,
            language=language,
            size=len(content.encode("utf-8")),
            content=content,
            symbols=symbols,
        )

        if was_present and old_language:
            index.languages[old_language] = max(0, index.languages.get(old_language, 1) - 1)
        index.languages[language] = index.languages.get(language, 0) + 1

        index.semantic_index.add_document(path, content)
        if language in SUPPORTED_AST_LANGUAGES:
            index.knowledge_graph.index_file(path, language, content)
        else:
            index.knowledge_graph.remove_file(path)

        index.rebuild_derived()
        save_index(index)

    def remove_file(self, index: RepositoryIndex, path: str) -> None:
        removed = index.files.pop(path, None)
        if removed is not None:
            index.languages[removed.language] = max(0, index.languages.get(removed.language, 1) - 1)
            index.semantic_index.remove_document(path)
            index.knowledge_graph.remove_file(path)
            index.rebuild_derived()
            save_index(index)
