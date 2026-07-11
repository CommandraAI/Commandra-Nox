"""
Project Generator -- turns a free-text request ("build me a REST API for a
todo app with auth") into a structured `ProjectPlan`: a project type,
suggested stack, and an ordered file scaffold. This is a planning artifact,
not code generation -- actual file contents still come from the agent
pipeline in `CommandraBrain.handle_request`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScaffoldFile:
    path: str
    purpose: str

    def as_dict(self) -> dict:
        return {"path": self.path, "purpose": self.purpose}


@dataclass
class ProjectPlan:
    request: str
    project_type: str
    summary: str
    stack: list[str] = field(default_factory=list)
    scaffold: list[ScaffoldFile] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "request": self.request,
            "projectType": self.project_type,
            "summary": self.summary,
            "stack": self.stack,
            "scaffold": [f.as_dict() for f in self.scaffold],
            "notes": self.notes,
        }


_PROJECT_TEMPLATES: dict[str, dict] = {
    "rest_api": {
        "keywords": ["rest api", "api", "backend", "endpoint", "endpoints"],
        "summary": "A REST API service with routing, request validation, and a data layer.",
        "stack": ["FastAPI or Express", "SQL or NoSQL database", "JWT auth"],
        "scaffold": [
            ("app/main.py", "Application entrypoint and route registration"),
            ("app/routes/", "HTTP route handlers grouped by resource"),
            ("app/services/", "Business logic, independent of the HTTP layer"),
            ("app/models/", "Data models / ORM schema"),
            ("app/schemas/", "Request/response validation schemas"),
            ("tests/", "Unit and integration tests"),
        ],
    },
    "frontend": {
        "keywords": ["dashboard", "frontend", "react", "vue", "ui", "web app", "webapp"],
        "summary": "A component-based single-page frontend application.",
        "stack": ["React or Vue", "Component library", "State management", "Typed API client"],
        "scaffold": [
            ("src/App", "Root application shell and routing"),
            ("src/components/", "Reusable UI components"),
            ("src/pages/", "Route-level page components"),
            ("src/store/", "Application state management"),
            ("src/api/", "Typed API client"),
        ],
    },
    "cli": {
        "keywords": ["cli", "command line", "terminal tool", "script"],
        "summary": "A command-line tool with subcommands and structured output.",
        "stack": ["argparse/click/typer", "structured logging"],
        "scaffold": [
            ("cli/main.py", "Entrypoint and subcommand registration"),
            ("cli/commands/", "One module per subcommand"),
            ("tests/", "CLI behavior tests"),
        ],
    },
    "game": {
        "keywords": ["game", "grand strategy", "rpg", "simulation"],
        "summary": "A game with a core simulation loop, state management, and a rendering layer.",
        "stack": ["Game loop", "State/entity management", "Rendering layer (canvas/SVG/engine)"],
        "scaffold": [
            ("game/state.py", "Core simulation state"),
            ("game/loop.py", "Main update/render loop"),
            ("game/entities/", "Game entities and behaviors"),
            ("game/ui/", "Player-facing UI"),
        ],
    },
    "mobile": {
        "keywords": ["mobile app", "android", "ios", "react native"],
        "summary": "A cross-platform mobile application.",
        "stack": ["React Native or native SDK", "Local storage", "REST/GraphQL client"],
        "scaffold": [
            ("app/screens/", "Screen-level components"),
            ("app/components/", "Reusable UI components"),
            ("app/services/", "API and storage services"),
        ],
    },
    "general": {
        "keywords": [],
        "summary": "A general-purpose software project scaffold.",
        "stack": ["To be determined from repository context"],
        "scaffold": [
            ("src/", "Application source"),
            ("tests/", "Tests"),
            ("README.md", "Project overview and setup instructions"),
        ],
    },
}


def _classify_project_type(request: str) -> str:
    lowered = request.lower()
    for project_type, template in _PROJECT_TEMPLATES.items():
        if project_type == "general":
            continue
        if any(keyword in lowered for keyword in template["keywords"]):
            return project_type
    return "general"


def generate_project_plan(request: str) -> ProjectPlan:
    project_type = _classify_project_type(request)
    template = _PROJECT_TEMPLATES[project_type]

    scaffold = [ScaffoldFile(path=path, purpose=purpose) for path, purpose in template["scaffold"]]

    return ProjectPlan(
        request=request,
        project_type=project_type,
        summary=template["summary"],
        stack=list(template["stack"]),
        scaffold=scaffold,
        notes=[],
    )
