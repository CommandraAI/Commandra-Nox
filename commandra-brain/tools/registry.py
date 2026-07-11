"""
Tools Registry -- a discovery surface listing every capability the brain
exposes, grouped by category. This is read-only metadata for clients (e.g.
a UI wanting to show "what can Commandra Nox do") -- it does not invoke
anything itself.
"""

from __future__ import annotations

_TOOLS: list[dict] = [
    # -- Repository intelligence --------------------------------------------
    {"id": "repository.index", "category": "repository", "description": "Index a repository into files, symbols, dependency graph, and knowledge graph."},
    {"id": "repository.search", "category": "repository", "description": "Hybrid keyword/vector search across an indexed repository."},
    {"id": "repository.search_symbol", "category": "repository", "description": "Find a symbol definition by name via the knowledge graph."},
    {"id": "repository.search_references", "category": "repository", "description": "Find references to a symbol across the repository."},
    {"id": "repository.style_profile", "category": "repository", "description": "Infer the repository's indentation, quoting, and naming conventions."},

    # -- Planning & architecture ---------------------------------------------
    {"id": "planning.create_plan", "category": "planning", "description": "Classify intent/complexity and break a request into ordered steps."},
    {"id": "planning.task_queue", "category": "planning", "description": "Build a resumable, trackable task queue for a goal."},
    {"id": "architecture.select", "category": "architecture", "description": "Select an architecture pattern (layered, hexagonal, microservices, ...) for a request."},
    {"id": "generator.project", "category": "generator", "description": "Generate a structured project scaffold plan from a free-text request."},

    # -- Code intelligence ----------------------------------------------------
    {"id": "lsp.hover", "category": "lsp", "description": "Hover information for a symbol at a file position."},
    {"id": "lsp.definition", "category": "lsp", "description": "Go-to-definition for a symbol."},
    {"id": "lsp.references", "category": "lsp", "description": "Find all references to a symbol."},
    {"id": "lsp.rename", "category": "lsp", "description": "Rename a symbol across the workspace."},
    {"id": "ast.tree_sitter", "category": "ast", "description": "Tree-sitter based structural parsing."},
    {"id": "ast.grep", "category": "ast", "description": "AST-aware structural search/replace."},

    # -- Validation, security, performance --------------------------------------
    {"id": "validation.files", "category": "validation", "description": "Validate generated files against expected paths/conventions."},
    {"id": "security.scan", "category": "security", "description": "Static security scan of project files."},
    {"id": "security.semgrep", "category": "security", "description": "Semgrep-based rule scanning."},
    {"id": "security.osv", "category": "security", "description": "OSV vulnerability database dependency scan."},
    {"id": "security.gitleaks", "category": "security", "description": "Secret scanning across files or git history."},
    {"id": "performance.scan", "category": "performance", "description": "Static performance heuristics scan of project files."},

    # -- Execution --------------------------------------------------------------
    {"id": "sandbox.execute", "category": "sandbox", "description": "Run code in an isolated in-process sandbox."},
    {"id": "sandbox.docker_execute", "category": "sandbox", "description": "Run code in an isolated Docker container."},

    # -- Diffing, git, workspace --------------------------------------------------
    {"id": "diff.preview", "category": "diffing", "description": "Preview a unified diff between original and updated file content."},
    {"id": "diff.apply", "category": "diffing", "description": "Record an applied patch for later rollback."},
    {"id": "git.log", "category": "git", "description": "Read commit history for the repository or a file."},
    {"id": "git.diff", "category": "git", "description": "Diff between two git refs."},
    {"id": "git.blame", "category": "git", "description": "Blame annotations for a file."},
    {"id": "workspace.state", "category": "workspace", "description": "Current open-workspace state for a repository."},

    # -- Testing & documentation --------------------------------------------------
    {"id": "testing.recommend", "category": "testing", "description": "Detect and recommend a test framework for the repository."},
    {"id": "documentation.generate", "category": "documentation", "description": "Generate README, architecture, or installation docs."},

    # -- Memory, knowledge, RAG -----------------------------------------------------
    {"id": "memory.long_term", "category": "memory", "description": "Persistent per-project architecture notes and decisions."},
    {"id": "knowledge.search", "category": "knowledge", "description": "Search the internal engineering knowledge base."},
    {"id": "rag.retrieve", "category": "rag", "description": "Retrieval-augmented context selection over repository content."},

    # -- External integrations --------------------------------------------------
    {"id": "mcp.connect", "category": "mcp", "description": "Connect to an external MCP server and expose its tools/resources."},
    {"id": "plugins.invoke", "category": "plugins", "description": "Invoke a registered plugin action."},

    # -- Preview & UI intelligence --------------------------------------------------
    {"id": "ui.analyze", "category": "ui", "description": "Analyze HTML/CSS for layout, typography, and design-token opportunities."},
    {"id": "preview.render", "category": "preview", "description": "Live preview for HTML/CSS/React/Vue/Tailwind/Flutter."},
]


def available_tools() -> list[dict]:
    return list(_TOOLS)


def tools_by_category(category: str) -> list[dict]:
    return [t for t in _TOOLS if t["category"] == category]
