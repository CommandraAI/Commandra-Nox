"""
Local Knowledge Base -- a searchable engineering knowledge base that the
Brain consults during reasoning and planning.

Covers:
- Design Patterns         (GoF, enterprise, distributed systems)
- Software Architecture   (hexagonal, event-driven, CQRS, microservices, ...)
- Best Practices          (SOLID, DRY, YAGNI, twelve-factor, ...)
- Security Guidelines     (OWASP, least privilege, defence in depth, ...)
- Framework Knowledge     (React, FastAPI, Express, Django, Rails, ...)
- API Design              (REST, GraphQL, gRPC, versioning, pagination, ...)
- Database Design         (normalisation, indexing, sharding, CAP, ...)
- Coding Standards        (naming, module structure, documentation, ...)
- Performance Optimization(caching, lazy loading, async, connection pools, ...)

Entries are stored in-process for zero-latency lookup.  Full-text search is
provided by the same TF-IDF index used in the Context Engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class KBCategory(str, Enum):
    DESIGN_PATTERNS = "design_patterns"
    SOFTWARE_ARCHITECTURE = "software_architecture"
    BEST_PRACTICES = "best_practices"
    SECURITY = "security"
    FRAMEWORKS = "frameworks"
    API_DESIGN = "api_design"
    DATABASE_DESIGN = "database_design"
    CODING_STANDARDS = "coding_standards"
    PERFORMANCE = "performance"


@dataclass
class KBEntry:
    entry_id: str
    category: KBCategory
    title: str
    summary: str
    detail: str
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)   # entry_id references

    def as_dict(self) -> dict:
        return {
            "entryId": self.entry_id,
            "category": self.category.value,
            "title": self.title,
            "summary": self.summary,
            "detail": self.detail,
            "tags": self.tags,
            "examples": self.examples,
            "related": self.related,
        }

    def as_prompt_snippet(self) -> str:
        return f"**{self.title}** ({self.category.value}): {self.summary}"


# ---------------------------------------------------------------------------
# Built-in knowledge entries
# ---------------------------------------------------------------------------

_ENTRIES: list[KBEntry] = [
    # ---- Design Patterns --------------------------------------------------
    KBEntry("dp-singleton", KBCategory.DESIGN_PATTERNS, "Singleton Pattern",
        "Ensures a class has only one instance and provides a global access point.",
        "Use when exactly one object is needed to coordinate actions across the system. "
        "In Python, implement via module-level state or a metaclass. Avoid in tests — "
        "prefer dependency injection instead.",
        tags=["creational", "instance", "global"],
        examples=["Database connection pool", "Logger", "Configuration object"]),
    KBEntry("dp-factory", KBCategory.DESIGN_PATTERNS, "Factory Method Pattern",
        "Defines an interface for creating objects but lets subclasses decide which classes to instantiate.",
        "Use when the exact type of object to be created is unknown until runtime, or when you want "
        "to decouple object creation from usage. Common in plugin systems and provider architectures.",
        tags=["creational", "factory", "polymorphism"],
        examples=["Provider registry (MockProvider / OllamaProvider)", "Document export (PDF, Word, HTML)"]),
    KBEntry("dp-observer", KBCategory.DESIGN_PATTERNS, "Observer Pattern",
        "Defines a one-to-many dependency so that when one object changes state, all dependents are notified automatically.",
        "Use for event systems, pub/sub messaging, and reactive UIs. In Python, "
        "implement with callbacks, asyncio events, or a dedicated EventBus class.",
        tags=["behavioral", "events", "pub-sub"],
        examples=["UI state management", "Webhook delivery", "File-watcher notifications"]),
    KBEntry("dp-strategy", KBCategory.DESIGN_PATTERNS, "Strategy Pattern",
        "Defines a family of algorithms, encapsulates each one, and makes them interchangeable.",
        "Use when you need to swap algorithms at runtime without changing the client code. "
        "The AIProvider in Commandra is an example: OllamaProvider and MockProvider are strategies.",
        tags=["behavioral", "algorithm", "interchangeable"],
        examples=["Sorting strategies", "AI provider selection", "Compression algorithms"]),
    KBEntry("dp-decorator", KBCategory.DESIGN_PATTERNS, "Decorator Pattern",
        "Attaches additional responsibilities to an object dynamically, as a flexible alternative to subclassing.",
        "Python's @decorator syntax is a natural fit. Use for cross-cutting concerns: "
        "logging, caching, rate-limiting, retry logic, and authentication.",
        tags=["structural", "composition", "wrapping"],
        examples=["@lru_cache", "@retry", "@require_auth middleware"]),
    KBEntry("dp-command", KBCategory.DESIGN_PATTERNS, "Command Pattern",
        "Encapsulates a request as an object, allowing parameterization and queuing of requests.",
        "Use to implement undo/redo, task queues, and audit trails. "
        "Each command carries its own data and a reference to the receiver.",
        tags=["behavioral", "undo", "queue"],
        examples=["Text editor undo", "Brain task queue steps", "Database migrations"]),
    KBEntry("dp-repository", KBCategory.DESIGN_PATTERNS, "Repository Pattern",
        "Mediates between the domain and data mapping layers, acting like an in-memory collection of domain objects.",
        "Separates business logic from data access. The repository interface is defined in the domain "
        "layer; the concrete implementation (SQL, file, API) lives in the infrastructure layer. "
        "This makes the domain testable without a real database.",
        tags=["data-access", "domain", "ddd"],
        examples=["UserRepository with save/find/delete", "FileRepository for cached index data"]),

    # ---- Software Architecture --------------------------------------------
    KBEntry("arch-hexagonal", KBCategory.SOFTWARE_ARCHITECTURE, "Hexagonal Architecture (Ports & Adapters)",
        "Separates core business logic from external concerns via explicitly defined ports and adapters.",
        "The domain/application core defines ports (interfaces). Adapters implement those ports for "
        "specific technologies (HTTP, DB, message queue). This makes the core technology-agnostic "
        "and fully testable with stub adapters.",
        tags=["ports", "adapters", "clean-architecture"],
        examples=["FastAPI adapter → application service → database port", "Brain AIProvider as a port"]),
    KBEntry("arch-cqrs", KBCategory.SOFTWARE_ARCHITECTURE, "CQRS (Command Query Responsibility Segregation)",
        "Separates write operations (commands) from read operations (queries) into distinct models.",
        "Use when read and write workloads have very different scalability or complexity requirements. "
        "Often combined with Event Sourcing. Commands mutate state; queries return data without side effects.",
        tags=["commands", "queries", "event-sourcing"],
        examples=["Order write model + denormalised read model", "Chat commands vs. history queries"]),
    KBEntry("arch-event-driven", KBCategory.SOFTWARE_ARCHITECTURE, "Event-Driven Architecture",
        "Services communicate by producing and consuming events rather than direct calls.",
        "Decouples services, improves resilience, and enables async processing. "
        "Events are immutable facts. Use a message broker (Kafka, RabbitMQ, Redis Streams) "
        "for durability. Ensure idempotent consumers.",
        tags=["events", "async", "decoupled", "kafka"],
        examples=["Order placed → inventory reserved → shipping scheduled", "Code saved → lint triggered"]),
    KBEntry("arch-microservices", KBCategory.SOFTWARE_ARCHITECTURE, "Microservices",
        "Structures an application as a collection of small, independently deployable services.",
        "Each service owns its data, is deployed independently, and communicates over network APIs. "
        "Prefer microservices only when team scale and deployment velocity justify the operational overhead. "
        "A well-structured monolith is often better for small teams.",
        tags=["distributed", "deployment", "autonomy"],
        examples=["Auth service, Order service, Notification service"]),

    # ---- Best Practices ---------------------------------------------------
    KBEntry("bp-solid", KBCategory.BEST_PRACTICES, "SOLID Principles",
        "Five object-oriented design principles for maintainable, extensible software.",
        "S — Single Responsibility: a class has one reason to change.\n"
        "O — Open/Closed: open for extension, closed for modification.\n"
        "L — Liskov Substitution: subtypes must be substitutable for their base types.\n"
        "I — Interface Segregation: prefer small, focused interfaces.\n"
        "D — Dependency Inversion: depend on abstractions, not concretions.",
        tags=["oop", "design", "principles"]),
    KBEntry("bp-twelve-factor", KBCategory.BEST_PRACTICES, "Twelve-Factor App",
        "A methodology for building scalable, maintainable SaaS applications.",
        "Key factors: (1) one codebase, (2) explicit dependencies, (3) config in env vars, "
        "(4) backing services as attached resources, (5) strict build/release/run separation, "
        "(6) stateless processes, (7) port binding, (8) concurrency via process model, "
        "(9) fast startup/graceful shutdown, (10) dev/prod parity, (11) logs as streams, "
        "(12) admin tasks as one-off processes.",
        tags=["saas", "deployment", "config", "stateless"]),
    KBEntry("bp-dry", KBCategory.BEST_PRACTICES, "DRY — Don't Repeat Yourself",
        "Every piece of knowledge should have a single, unambiguous representation in the system.",
        "Eliminate duplication by extracting shared logic into functions, modules, or services. "
        "Watch for knowledge duplication, not just code duplication — two pieces of code that encode "
        "the same business rule are duplicates even if they look different.",
        tags=["duplication", "abstraction", "refactoring"]),

    # ---- Security ---------------------------------------------------------
    KBEntry("sec-owasp-top10", KBCategory.SECURITY, "OWASP Top 10",
        "The ten most critical web application security risks.",
        "A01 Broken Access Control · A02 Cryptographic Failures · A03 Injection · "
        "A04 Insecure Design · A05 Security Misconfiguration · A06 Vulnerable Components · "
        "A07 Auth Failures · A08 Software & Data Integrity · A09 Logging Failures · "
        "A10 SSRF. Always validate input server-side; parameterise queries; use short-lived tokens; "
        "enforce least privilege; keep dependencies updated.",
        tags=["owasp", "web", "injection", "auth", "csrf"]),
    KBEntry("sec-least-privilege", KBCategory.SECURITY, "Principle of Least Privilege",
        "Every component should have only the minimum permissions required to perform its function.",
        "Apply at every layer: OS users, database roles, API keys, OAuth scopes, IAM policies. "
        "Rotate credentials regularly. Audit access grants quarterly.",
        tags=["iam", "permissions", "zero-trust"]),
    KBEntry("sec-secrets", KBCategory.SECURITY, "Secret Management",
        "Secrets (API keys, passwords, tokens) must never appear in source code or logs.",
        "Use environment variables for runtime injection. Prefer a secrets manager (Vault, AWS SSM, "
        "Doppler) for production. Rotate secrets on suspected exposure immediately. "
        "Scan commits with tools like gitleaks or truffleHog.",
        tags=["secrets", "env-vars", "rotation"]),

    # ---- API Design -------------------------------------------------------
    KBEntry("api-rest", KBCategory.API_DESIGN, "RESTful API Design",
        "Stateless, resource-oriented HTTP APIs with predictable URL conventions.",
        "Resources are nouns (plural): /users, /orders. HTTP verbs carry semantics: "
        "GET (read), POST (create), PUT/PATCH (update), DELETE (remove). "
        "Use 2xx for success, 4xx for client errors, 5xx for server errors. "
        "Version via URL prefix (/v1/...) or Accept header. Paginate large collections.",
        tags=["rest", "http", "openapi", "versioning"]),
    KBEntry("api-graphql", KBCategory.API_DESIGN, "GraphQL",
        "A query language for APIs that lets clients request exactly the data they need.",
        "Use when clients have widely varying data requirements or bandwidth is constrained. "
        "Define a typed schema; use mutations for writes; subscriptions for real-time. "
        "Add query depth/complexity limits to prevent DoS. Use DataLoader to avoid N+1.",
        tags=["graphql", "schema", "subscriptions", "n+1"]),
    KBEntry("api-pagination", KBCategory.API_DESIGN, "API Pagination",
        "Strategies for returning large result sets in manageable pages.",
        "Offset-based (/items?offset=0&limit=20): simple but slow on large tables. "
        "Cursor-based (/items?after=<cursor>): stable and efficient for feeds. "
        "Keyset pagination: use the last row's indexed column as the next-page key. "
        "Always include total count and next/prev links in the envelope.",
        tags=["pagination", "cursor", "offset", "performance"]),

    # ---- Database Design --------------------------------------------------
    KBEntry("db-normalisation", KBCategory.DATABASE_DESIGN, "Database Normalisation",
        "Organises relational data to reduce redundancy and improve integrity.",
        "1NF: atomic values, no repeating groups. 2NF: no partial dependencies on composite keys. "
        "3NF: no transitive dependencies. BCNF: every determinant is a candidate key. "
        "Denormalise deliberately for read performance only when profiling proves it necessary.",
        tags=["sql", "normalisation", "integrity"]),
    KBEntry("db-indexing", KBCategory.DATABASE_DESIGN, "Database Indexing",
        "Indexes dramatically speed up read queries at the cost of write overhead and storage.",
        "Index columns used in WHERE, JOIN, and ORDER BY clauses. Composite indexes follow "
        "left-prefix matching. Partial indexes for sparse predicates. Cover frequently-queried "
        "column sets to avoid table scans. Monitor with EXPLAIN / EXPLAIN ANALYZE.",
        tags=["indexes", "query-planning", "explain"]),
    KBEntry("db-cap", KBCategory.DATABASE_DESIGN, "CAP Theorem",
        "A distributed system can guarantee at most two of: Consistency, Availability, Partition Tolerance.",
        "In practice, partition tolerance is required for any distributed system, so the real choice is "
        "between consistency (CP systems: HBase, Zookeeper) and availability (AP systems: Cassandra, CouchDB). "
        "Most SQL databases are CP. Choose based on your failure model.",
        tags=["distributed", "consistency", "availability"]),

    # ---- Performance Optimization -----------------------------------------
    KBEntry("perf-caching", KBCategory.PERFORMANCE, "Caching Strategies",
        "Caching reduces latency and backend load by serving repeated requests from fast storage.",
        "Cache-aside (lazy loading): populate on miss. Write-through: write to cache and DB together. "
        "Write-behind: write to cache, async flush to DB. TTL-based invalidation vs. event-driven. "
        "Use Redis for distributed cache, LRU for in-process cache. Cache at the lowest safe level.",
        tags=["redis", "ttl", "invalidation", "lru"]),
    KBEntry("perf-async", KBCategory.PERFORMANCE, "Async I/O",
        "Non-blocking I/O allows a single thread to handle thousands of concurrent connections.",
        "In Python, use asyncio + httpx/aiohttp/asyncpg. In Node, everything is async by default. "
        "Avoid mixing blocking calls (requests, psycopg2) with async code. "
        "Use connection pools to limit DB connections. Profile with py-spy or async_profiler.",
        tags=["asyncio", "non-blocking", "concurrency"]),
    KBEntry("perf-n-plus-one", KBCategory.PERFORMANCE, "N+1 Query Problem",
        "Loading a list of N items and then issuing one query per item results in N+1 total queries.",
        "Fix by: eager loading (JOIN or ORM selectinload), batch loading (DataLoader), "
        "or prefetching related data in a second bulk query. Always check query counts "
        "in development using a query logger.",
        tags=["n+1", "orm", "eager-loading", "performance"]),

    # ---- Frameworks -------------------------------------------------------
    KBEntry("fw-fastapi", KBCategory.FRAMEWORKS, "FastAPI",
        "Modern, fast Python web framework built on Starlette and Pydantic.",
        "Declare endpoints with type annotations; FastAPI generates OpenAPI docs automatically. "
        "Use Depends() for dependency injection. Background tasks via BackgroundTasks. "
        "Lifespan events for startup/shutdown. Prefer async route handlers for I/O-heavy routes. "
        "Validate all inputs with Pydantic models; never trust raw request data.",
        tags=["python", "async", "openapi", "pydantic"]),
    KBEntry("fw-react", KBCategory.FRAMEWORKS, "React",
        "A declarative JavaScript library for building component-based UIs.",
        "Prefer function components + hooks over class components. Use React Query for server state, "
        "useState/useReducer for local state, and Zustand/Jotai for shared client state. "
        "Memoize with useMemo/useCallback only when profiling shows it necessary. "
        "Keep components small and single-purpose.",
        tags=["javascript", "hooks", "components", "state"]),

    # ---- Coding Standards -------------------------------------------------
    KBEntry("cs-naming", KBCategory.CODING_STANDARDS, "Naming Conventions",
        "Consistent, descriptive names are the most powerful form of documentation.",
        "Variables and functions: describe what they hold/do, not how they work. "
        "Boolean names: use is_, has_, can_, should_ prefixes. "
        "Avoid abbreviations except for universally understood ones (url, id, db). "
        "Collection names should be plural. Constants should be UPPER_SNAKE_CASE. "
        "Class names should be PascalCase nouns.",
        tags=["naming", "readability", "conventions"]),
    KBEntry("cs-error-handling", KBCategory.CODING_STANDARDS, "Error Handling",
        "Errors should be explicit, informative, and handled at the right level.",
        "Never swallow exceptions silently. Log the full traceback. Return structured error responses "
        "from APIs (status code + machine-readable code + human message). "
        "Distinguish recoverable errors (retry) from unrecoverable ones (fail fast). "
        "Use typed exceptions / Result types over bare string errors.",
        tags=["exceptions", "logging", "result-types"]),
]


# ---------------------------------------------------------------------------
# Simple TF-IDF search over KB entries
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


class KnowledgeBase:
    """
    Searchable engineering knowledge base used by the Brain during reasoning.

    Usage:
        kb = KnowledgeBase()
        results = kb.search("SQL injection parameterised queries", top_k=3)
        for entry in results:
            print(entry.as_prompt_snippet())
    """

    def __init__(self, extra_entries: list[KBEntry] | None = None) -> None:
        self._entries: dict[str, KBEntry] = {}
        for e in _ENTRIES:
            self._entries[e.entry_id] = e
        if extra_entries:
            for e in extra_entries:
                self._entries[e.entry_id] = e

        # Build TF-IDF-style inverted index
        self._inv_index: dict[str, list[str]] = {}  # token -> [entry_id]
        for entry_id, entry in self._entries.items():
            doc = f"{entry.title} {entry.summary} {entry.detail} {' '.join(entry.tags)}"
            for token in set(_tokenize(doc)):
                self._inv_index.setdefault(token, []).append(entry_id)

    # -- Search ------------------------------------------------------------

    def search(self, query: str, top_k: int = 5, category: KBCategory | None = None) -> list[KBEntry]:
        tokens = _tokenize(query)
        scores: dict[str, float] = {}
        for token in tokens:
            for entry_id in self._inv_index.get(token, []):
                scores[entry_id] = scores.get(entry_id, 0.0) + 1.0

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results: list[KBEntry] = []
        for entry_id, _ in ranked:
            entry = self._entries[entry_id]
            if category and entry.category != category:
                continue
            results.append(entry)
            if len(results) >= top_k:
                break
        return results

    def get(self, entry_id: str) -> KBEntry | None:
        return self._entries.get(entry_id)

    def by_category(self, category: KBCategory) -> list[KBEntry]:
        return [e for e in self._entries.values() if e.category == category]

    def all_entries(self) -> list[KBEntry]:
        return list(self._entries.values())

    def add_entry(self, entry: KBEntry) -> None:
        self._entries[entry.entry_id] = entry
        doc = f"{entry.title} {entry.summary} {entry.detail} {' '.join(entry.tags)}"
        for token in set(_tokenize(doc)):
            self._inv_index.setdefault(token, []).append(entry.entry_id)

    # -- Reasoning integration --------------------------------------------

    def relevant_for_request(self, request: str, top_k: int = 3) -> str:
        """Return a markdown-formatted prompt block of the most relevant KB entries."""
        entries = self.search(request, top_k=top_k)
        if not entries:
            return ""
        lines = ["## Relevant Engineering Knowledge\n"]
        for entry in entries:
            lines.append(f"### {entry.title}")
            lines.append(entry.summary)
            if entry.detail:
                lines.append(f"\n{entry.detail[:400]}")
            lines.append("")
        return "\n".join(lines)
