"""
Architecture Engine -- picks a sensible software architecture pattern for a
request (or an explicit project type / complexity), and describes it well
enough that the Planner/Coding agents can build against it.

This module has no external dependencies: it works from keyword heuristics
over the request text, plus optional explicit hints from the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArchitectureBlueprint:
    pattern: str
    description: str
    layers: list[str] = field(default_factory=list)
    recommended_stack: list[str] = field(default_factory=list)
    folder_structure: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "description": self.description,
            "layers": self.layers,
            "recommendedStack": self.recommended_stack,
            "folderStructure": self.folder_structure,
            "notes": self.notes,
        }


_PATTERNS: dict[str, ArchitectureBlueprint] = {
    "layered": ArchitectureBlueprint(
        pattern="layered",
        description="Classic layered architecture: presentation, application/service, "
                     "domain, and data access layers, each depending only on the layer below it.",
        layers=["presentation", "application", "domain", "data-access"],
        recommended_stack=["REST or GraphQL API", "service layer", "ORM/repository layer"],
        folder_structure=["api/", "services/", "domain/", "repositories/", "models/"],
        notes=["Good default for CRUD-heavy apps and small-to-medium teams."],
    ),
    "hexagonal": ArchitectureBlueprint(
        pattern="hexagonal",
        description="Ports & adapters: a framework-independent core domain surrounded by "
                     "adapters for HTTP, database, queues, and third-party APIs.",
        layers=["domain core", "ports (interfaces)", "adapters (inbound/outbound)"],
        recommended_stack=["dependency injection", "interface-driven domain", "adapter modules per integration"],
        folder_structure=["domain/", "ports/", "adapters/http/", "adapters/persistence/", "adapters/external/"],
        notes=["Best when the domain logic needs to outlive specific frameworks or providers."],
    ),
    "microservices": ArchitectureBlueprint(
        pattern="microservices",
        description="Independently deployable services, each owning its own data store, "
                     "communicating over well-defined APIs or async events.",
        layers=["service boundary", "API gateway", "per-service data store", "event bus"],
        recommended_stack=["API gateway", "service discovery", "message broker", "per-service CI/CD"],
        folder_structure=["services/<service-name>/", "gateway/", "shared/contracts/"],
        notes=["Only worth the operational overhead once a single deployable becomes a real bottleneck."],
    ),
    "event_driven": ArchitectureBlueprint(
        pattern="event_driven",
        description="Producers publish events; consumers react asynchronously through a "
                     "broker or event bus, decoupling components in time and space.",
        layers=["event producers", "event bus/broker", "event consumers", "read models"],
        recommended_stack=["message broker (Kafka/Redis Streams/etc.)", "event schemas", "idempotent consumers"],
        folder_structure=["events/", "producers/", "consumers/", "handlers/"],
        notes=["Good fit for workflows with retries, fan-out, or long-running async steps."],
    ),
    "monolith_modular": ArchitectureBlueprint(
        pattern="modular_monolith",
        description="A single deployable split into clearly bounded internal modules with "
                     "enforced boundaries, giving most microservice benefits without the ops cost.",
        layers=["module boundary", "shared kernel", "composition root"],
        recommended_stack=["single deploy target", "internal module contracts", "shared database with per-module schemas"],
        folder_structure=["modules/<module-name>/", "shared/", "app/"],
        notes=["Usually the right starting point before microservices are justified."],
    ),
    "component_based": ArchitectureBlueprint(
        pattern="component_based",
        description="Frontend architecture built from small, composable, reusable UI components "
                     "with unidirectional data flow.",
        layers=["components", "hooks/composables", "state management", "API client"],
        recommended_stack=["component library", "state store", "typed API client"],
        folder_structure=["components/", "hooks/", "store/", "api/"],
        notes=["Default choice for React/Vue/Svelte single-page apps."],
    ),
    "mvc": ArchitectureBlueprint(
        pattern="mvc",
        description="Model-View-Controller: controllers handle input, models hold state and "
                     "business rules, views render output.",
        layers=["controllers", "models", "views"],
        recommended_stack=["server-rendered templates or a thin API layer", "ORM models"],
        folder_structure=["controllers/", "models/", "views/"],
        notes=["Simple and well understood; good for small server-rendered apps and prototypes."],
    ),
}

_DEFAULT_PATTERN = "layered"

_KEYWORD_HINTS: list[tuple[str, str]] = [
    ("microservice", "microservices"),
    ("micro-service", "microservices"),
    ("event driven", "event_driven"),
    ("event-driven", "event_driven"),
    ("message queue", "event_driven"),
    ("kafka", "event_driven"),
    ("hexagonal", "hexagonal"),
    ("ports and adapters", "hexagonal"),
    ("clean architecture", "hexagonal"),
    ("modular monolith", "monolith_modular"),
    ("dashboard", "component_based"),
    ("react", "component_based"),
    ("vue", "component_based"),
    ("frontend", "component_based"),
    ("ui", "component_based"),
    ("mvc", "mvc"),
    ("crud", "layered"),
    ("rest api", "layered"),
]

_PROJECT_TYPE_HINTS: dict[str, str] = {
    "api": "layered",
    "rest_api": "layered",
    "frontend": "component_based",
    "dashboard": "component_based",
    "microservice": "microservices",
    "cli": "layered",
    "game": "monolith_modular",
    "mobile": "component_based",
}


def available_patterns() -> list[dict]:
    return [bp.as_dict() for bp in _PATTERNS.values()]


def select_architecture(
    request: str,
    project_type: str | None = None,
    complexity: str | None = None,
) -> ArchitectureBlueprint:
    """Pick the best-fit architecture blueprint for a request.

    Priority: explicit project_type hint > keyword match in request text >
    complexity-based fallback > default (layered).
    """
    if project_type:
        pattern_key = _PROJECT_TYPE_HINTS.get(project_type.lower())
        if pattern_key:
            return _PATTERNS[pattern_key]

    lowered = request.lower()
    for keyword, pattern_key in _KEYWORD_HINTS:
        if keyword in lowered:
            return _PATTERNS[pattern_key]

    if complexity and complexity.lower() in ("complex", "large"):
        return _PATTERNS["monolith_modular"]

    return _PATTERNS[_DEFAULT_PATTERN]
