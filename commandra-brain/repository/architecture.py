"""
Architecture summarizer -- turns a RepositoryIndex + DependencyGraph into a
human-readable "this is what this project is" brief. This is what lets the
Brain understand a repository before it ever talks to Ollama, and it's what
gets injected into the Prompt Compiler and long-term memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_ARCHITECTURE_DIR_HINTS = {
    "controllers": "MVC-style controllers",
    "routes": "route handlers",
    "views": "server-rendered views",
    "models": "data models",
    "schemas": "data/validation schemas",
    "services": "service layer",
    "repositories": "repository/data-access layer",
    "components": "UI components",
    "pages": "page-level routes",
    "hooks": "reusable state/logic hooks",
    "agents": "agent modules",
    "tests": "automated tests",
    "test": "automated tests",
    "migrations": "database migrations",
    "middleware": "middleware",
    "middlewares": "middleware",
    "utils": "utilities/helpers",
    "lib": "shared libraries",
    "api": "API layer",
    "docker": "containerization config",
}


@dataclass
class ArchitectureSummary:
    project_type: str
    layers: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    top_level_dirs: list[str] = field(default_factory=list)
    notable_configs: list[str] = field(default_factory=list)
    narrative: str = ""

    def as_dict(self) -> dict:
        return {
            "projectType": self.project_type,
            "layers": self.layers,
            "entryPoints": self.entry_points,
            "topLevelDirs": self.top_level_dirs,
            "notableConfigs": self.notable_configs,
            "narrative": self.narrative,
        }


_ENTRY_POINT_NAMES = {
    "main.py", "app.py", "manage.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "main.js", "main.ts", "server.js", "server.ts",
    "App.tsx", "App.jsx", "main.rs", "main.go", "Main.java",
}


def _classify_project_type(frameworks: list[str], languages: dict[str, int]) -> str:
    joined = " ".join(frameworks).lower()
    if "next.js" in joined:
        return "Next.js full-stack web application"
    if "flutter" in joined or "dart" in languages:
        return "Flutter mobile application"
    if "vite" in joined and "typescript" in languages:
        return "TypeScript SPA (Vite)"
    if "django" in joined:
        return "Django web application"
    if not languages:
        return "Unknown / empty project"
    top_lang = max(languages, key=languages.get)
    if top_lang == "python" and "fastapi" in joined:
        return "FastAPI backend service"
    if top_lang == "python":
        return "Python application"
    if top_lang in {"javascript", "typescript"}:
        return "JavaScript/TypeScript application"
    return f"{top_lang.capitalize()} application"


def summarize_architecture(index: "object", graph: "object") -> ArchitectureSummary:
    top_dirs: dict[str, int] = {}
    entry_points: list[str] = []
    notable_configs: list[str] = []

    for path in index.files:
        parts = path.split("/")
        if len(parts) > 1:
            top_dirs[parts[0]] = top_dirs.get(parts[0], 0) + 1
        filename = parts[-1]
        if filename in _ENTRY_POINT_NAMES:
            entry_points.append(path)
        if filename in {
            "package.json", "pyproject.toml", "Dockerfile", "docker-compose.yml",
            "tsconfig.json", "next.config.js", "vite.config.ts", ".env.example",
        }:
            notable_configs.append(path)

    layers = sorted(
        {
            _ARCHITECTURE_DIR_HINTS[d]
            for d in top_dirs
            if d in _ARCHITECTURE_DIR_HINTS
        }
    )
    top_level = sorted(top_dirs, key=top_dirs.get, reverse=True)[:12]
    project_type = _classify_project_type(index.frameworks, index.languages)

    hub_note = ""
    hubs = graph.hubs(3) if hasattr(graph, "hubs") else []
    if hubs and hubs[0]["fanIn"] > 0:
        hub_names = ", ".join(h["path"] for h in hubs if h["fanIn"] > 0)
        if hub_names:
            hub_note = f" Most widely depended-on files: {hub_names}."

    narrative = (
        f"This appears to be a {project_type} with {index.file_count} indexed files "
        f"across {len(top_dirs)} top-level directories. "
        f"Detected layers: {', '.join(layers) or 'none clearly identified'}. "
        f"Entry points: {', '.join(entry_points) or 'none detected'}.{hub_note}"
    )

    return ArchitectureSummary(
        project_type=project_type,
        layers=layers,
        entry_points=entry_points,
        top_level_dirs=top_level,
        notable_configs=notable_configs,
        narrative=narrative,
    )
