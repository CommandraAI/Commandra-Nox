"""
Integration Registry -- central discovery and status hub for every external
tool and library wired into the Brain.

Every integration is registered with:
  - id           unique identifier
  - category     group (ast | search | vectordb | security | git | lsp | sandbox | docs | mcp)
  - name         human label
  - description  one-line purpose
  - available()  runtime probe function
  - install_hint how to install if not available
"""
from __future__ import annotations
import shutil
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Integration:
    id: str
    category: str
    name: str
    description: str
    check: Callable[[], bool]
    install_hint: str
    homepage: str = ""

    def available(self) -> bool:
        try:
            return self.check()
        except Exception:
            return False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "available": self.available(),
            "installHint": self.install_hint,
            "homepage": self.homepage,
        }


def _can_import(module: str) -> Callable[[], bool]:
    def check() -> bool:
        try:
            __import__(module)
            return True
        except ImportError:
            return False
    return check


def _has_binary(*names: str) -> Callable[[], bool]:
    def check() -> bool:
        return any(shutil.which(n) is not None for n in names)
    return check


def _docker_available() -> bool:
    try:
        import docker  # type: ignore
        docker.from_env(timeout=3).ping()
        return True
    except Exception:
        return False


_ALL: list[Integration] = [
    # ── AST Intelligence ──────────────────────────────────────────────────
    Integration(
        id="tree-sitter", category="ast",
        name="tree-sitter",
        description="Multi-language AST parsing, syntax tree generation, symbol extraction",
        check=_can_import("tree_sitter"),
        install_hint="pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-typescript",
        homepage="https://github.com/tree-sitter/tree-sitter",
    ),
    Integration(
        id="ast-grep", category="ast",
        name="ast-grep (sg)",
        description="Structural code search, pattern matching, and AST-level refactoring",
        check=_has_binary("sg"),
        install_hint="cargo install ast-grep  OR  npm install -g @ast-grep/cli",
        homepage="https://github.com/ast-grep/ast-grep",
    ),
    Integration(
        id="ctags", category="ast",
        name="Universal Ctags",
        description="Symbol indexing: functions, classes, variables, interfaces, enums",
        check=_has_binary("ctags"),
        install_hint="apt install universal-ctags  OR  brew install universal-ctags",
        homepage="https://github.com/universal-ctags/ctags",
    ),

    # ── Search & Discovery ────────────────────────────────────────────────
    Integration(
        id="ripgrep", category="search",
        name="ripgrep (rg)",
        description="Extremely fast repository text search before semantic analysis",
        check=_has_binary("rg"),
        install_hint="cargo install ripgrep  OR  apt install ripgrep  OR  brew install ripgrep",
        homepage="https://github.com/BurntSushi/ripgrep",
    ),
    Integration(
        id="fd", category="search",
        name="fd",
        description="Extremely fast file discovery and repository scanning",
        check=_has_binary("fd", "fdfind"),
        install_hint="cargo install fd-find  OR  apt install fd-find  OR  brew install fd",
        homepage="https://github.com/sharkdp/fd",
    ),
    Integration(
        id="fzf", category="search",
        name="fzf",
        description="Fuzzy file search and interactive repository navigation",
        check=_has_binary("fzf"),
        install_hint="apt install fzf  OR  brew install fzf",
        homepage="https://github.com/junegunn/fzf",
    ),
    Integration(
        id="searxng", category="search",
        name="SearXNG",
        description="Privacy-focused internet search for documentation and Stack Overflow",
        check=lambda: False,  # server-based; probe in client
        install_hint="docker run -d -p 8888:8080 searxng/searxng",
        homepage="https://github.com/searxng/searxng",
    ),
    Integration(
        id="firecrawl", category="search",
        name="Firecrawl",
        description="Crawl and convert documentation websites to AI-friendly Markdown",
        check=_can_import("firecrawl"),
        install_hint="pip install firecrawl-py  OR  self-host: docker run -p 3002:3002 firecrawl/firecrawl",
        homepage="https://github.com/firecrawl/firecrawl",
    ),
    Integration(
        id="markitdown", category="search",
        name="MarkItDown",
        description="Convert PDF, DOCX, PPTX, HTML documents to Markdown",
        check=_can_import("markitdown"),
        install_hint="pip install markitdown",
        homepage="https://github.com/microsoft/markitdown",
    ),
    Integration(
        id="bat", category="search",
        name="bat",
        description="Syntax-highlighted file preview for repository exploration",
        check=_has_binary("bat"),
        install_hint="apt install bat  OR  brew install bat",
        homepage="https://github.com/sharkdp/bat",
    ),

    # ── Vector Databases ──────────────────────────────────────────────────
    Integration(
        id="chroma", category="vectordb",
        name="Chroma",
        description="Local vector database for semantic search and long-term memory",
        check=_can_import("chromadb"),
        install_hint="pip install chromadb",
        homepage="https://github.com/chroma-core/chroma",
    ),
    Integration(
        id="qdrant", category="vectordb",
        name="Qdrant",
        description="High-performance local vector database via HTTP API",
        check=_can_import("qdrant_client"),
        install_hint="pip install qdrant-client  AND  docker run -p 6333:6333 qdrant/qdrant",
        homepage="https://github.com/qdrant/qdrant",
    ),
    Integration(
        id="lancedb", category="vectordb",
        name="LanceDB",
        description="Zero-infrastructure local vector database (Lance files on disk)",
        check=_can_import("lancedb"),
        install_hint="pip install lancedb pyarrow",
        homepage="https://github.com/lancedb/lancedb",
    ),

    # ── Security & Quality ────────────────────────────────────────────────
    Integration(
        id="semgrep", category="security",
        name="Semgrep",
        description="Static analysis, bug detection, security scanning, OWASP rules",
        check=_has_binary("semgrep"),
        install_hint="pip install semgrep",
        homepage="https://github.com/semgrep/semgrep",
    ),
    Integration(
        id="osv-scanner", category="security",
        name="OSV Scanner",
        description="Dependency vulnerability scanning via Google OSV database",
        check=_has_binary("osv-scanner"),
        install_hint="go install github.com/google/osv-scanner/cmd/osv-scanner@latest",
        homepage="https://github.com/google/osv-scanner",
    ),
    Integration(
        id="gitleaks", category="security",
        name="Gitleaks",
        description="Detect leaked API keys, passwords, tokens and secrets in repos",
        check=_has_binary("gitleaks"),
        install_hint="brew install gitleaks  OR  go install github.com/zricethezav/gitleaks/v8@latest",
        homepage="https://github.com/gitleaks/gitleaks",
    ),

    # ── Git ───────────────────────────────────────────────────────────────
    Integration(
        id="gitpython", category="git",
        name="GitPython",
        description="Full git integration: commits, branches, diffs, blame, log",
        check=_can_import("git"),
        install_hint="pip install gitpython",
        homepage="https://github.com/gitpython-developers/GitPython",
    ),

    # ── LSP Servers ───────────────────────────────────────────────────────
    Integration(
        id="pyright", category="lsp",
        name="Pyright",
        description="Python language analysis, diagnostics, type checking",
        check=_has_binary("pyright-langserver", "pyright"),
        install_hint="pip install pyright  OR  npm install -g pyright",
        homepage="https://github.com/microsoft/pyright",
    ),
    Integration(
        id="typescript-language-server", category="lsp",
        name="TypeScript Language Server",
        description="TypeScript/JavaScript LSP: hover, definitions, refactoring",
        check=_has_binary("typescript-language-server"),
        install_hint="npm install -g typescript-language-server typescript",
        homepage="https://github.com/typescript-language-server/typescript-language-server",
    ),
    Integration(
        id="rust-analyzer", category="lsp",
        name="rust-analyzer",
        description="Rust language analysis and intelligent code navigation",
        check=_has_binary("rust-analyzer"),
        install_hint="rustup component add rust-analyzer",
        homepage="https://github.com/rust-lang/rust-analyzer",
    ),
    Integration(
        id="clangd", category="lsp",
        name="clangd",
        description="C/C++ language intelligence and repository understanding",
        check=_has_binary("clangd"),
        install_hint="apt install clangd  OR  brew install llvm",
        homepage="https://github.com/clangd/clangd",
    ),

    # ── Code Execution ────────────────────────────────────────────────────
    Integration(
        id="docker", category="sandbox",
        name="Docker",
        description="Isolated code execution inside Docker containers with resource limits",
        check=_docker_available,
        install_hint="Install Docker Desktop or Docker Engine, then pip install docker",
        homepage="https://github.com/docker/docker-py",
    ),

    # ── MCP ───────────────────────────────────────────────────────────────
    Integration(
        id="mcp-servers", category="mcp",
        name="Official MCP Servers",
        description="Filesystem, Git, GitHub, Postgres, SQLite, Search and more via npx",
        check=_has_binary("npx"),
        install_hint="Install Node.js: https://nodejs.org",
        homepage="https://github.com/modelcontextprotocol/servers",
    ),
]

_INDEX: dict[str, Integration] = {i.id: i for i in _ALL}


def list_integrations(category: str | None = None) -> list[dict]:
    ints = _ALL if category is None else [i for i in _ALL if i.category == category]
    return [i.as_dict() for i in ints]


def get_integration(integration_id: str) -> dict | None:
    i = _INDEX.get(integration_id)
    return i.as_dict() if i else None


def available_integrations() -> list[dict]:
    return [i.as_dict() for i in _ALL if i.available()]


def unavailable_integrations() -> list[dict]:
    return [i.as_dict() for i in _ALL if not i.available()]


def integration_status() -> dict:
    available = [i for i in _ALL if i.available()]
    unavailable = [i for i in _ALL if not i.available()]
    by_category: dict[str, dict] = {}
    for i in _ALL:
        cat = i.category
        if cat not in by_category:
            by_category[cat] = {"available": 0, "total": 0}
        by_category[cat]["total"] += 1
        if i.available():
            by_category[cat]["available"] += 1
    return {
        "totalIntegrations": len(_ALL),
        "available": len(available),
        "unavailable": len(unavailable),
        "byCategory": by_category,
        "availableIds": [i.id for i in available],
    }
