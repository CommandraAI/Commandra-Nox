"""
CommandraBrain -- the orchestration layer that ties every module together.

    User
      -> Planning Engine     (what needs to happen)
      -> Context Engine      (what files matter)
      -> Reasoning Engine    (think before generating)
      -> Memory Engine       (recall + record project knowledge)
      -> Agent(s)            (specialist prompt construction)
      -> AIProvider          (the only place text is actually generated)
      -> Response Optimizer  (clean up before returning)
      -> Reflection Engine   (self-review before returning to user)

New systems wired in (non-breaking extensions):
  MCP Client          -- external MCP server tools as native capabilities
  LSP Engine          -- Go To Definition, References, Hover, Diagnostics, ...
  RAG Pipeline        -- full Retrieval-Augmented Generation
  Execution Sandbox   -- isolated Python/Node/Rust/Go code execution
  Reflection Engine   -- self-review and refinement of every response
  Benchmark Suite     -- internal benchmarking and reporting
  Planning Timeline   -- per-task visual progress tracking
  Knowledge Base      -- searchable engineering knowledge
  Preview Engine      -- live UI preview for HTML/CSS/React/Vue/Tailwind/Flutter
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from agents.registry import build_agents
from architecture.architecture_engine import ArchitectureBlueprint, select_architecture
from brain.ollama_optimizer import OllamaOptimizer
from brain.prompt_compiler import PreviousAction
from brain.reasoning_engine import ReasoningEngine
from brain.response_optimizer import optimize
from context.context_engine import ContextEngine, ContextSelection
from diffing.diff_engine import DiffEngine
from memory.memory_engine import MemoryEngine
from planning.planning_engine import Complexity, Plan, PlanningEngine
from plugins.plugin_sdk import get_registry as get_plugin_registry
from providers.ai_provider import AIProvider
from repository.indexer import RepositoryIndex, RepositoryIndexer
from session.session_manager import SessionManager
from style.code_style_engine import StyleProfile, analyze_style
from workspace.workspace_engine import WorkspaceEngine

# New systems
from mcp.mcp_client import MCPClient
from lsp.lsp_engine import LSPEngine
from rag.rag_pipeline import RAGPipeline
from sandbox.execution_sandbox import ExecutionSandbox
from reflection.reflection_engine import ReflectionEngine
from benchmarks.benchmark_suite import BenchmarkSuite
from timeline.planning_timeline import PlanningTimeline, StageName, StageStatus
from knowledge.knowledge_base import KnowledgeBase
from preview.preview_engine import PreviewEngine

# Multi-agent coordinator pipeline for COMPLEX requests: each stage hands its
# output to the next as a "previous action" so later agents see what earlier
# ones already decided, instead of re-deriving it from scratch.
_COMPLEX_PIPELINE = ["planner_agent", "coding_agent", "review_agent", "testing_agent", "documentation_agent"]


@dataclass
class BrainResponse:
    plan: Plan
    reasoning: dict
    context_files: list[str]
    agent: str
    response_markdown: str
    provider: str
    model: str
    elapsed_seconds: float
    steps_trace: list[dict] = field(default_factory=list)
    reflection: dict | None = None
    timeline_id: str | None = None

    def as_dict(self) -> dict:
        d = {
            "plan": self.plan.as_dict(),
            "reasoning": self.reasoning,
            "contextFiles": self.context_files,
            "agent": self.agent,
            "responseMarkdown": self.response_markdown,
            "provider": self.provider,
            "model": self.model,
            "elapsedSeconds": self.elapsed_seconds,
            "stepsTrace": self.steps_trace,
        }
        if self.reflection is not None:
            d["reflection"] = self.reflection
        if self.timeline_id is not None:
            d["timelineId"] = self.timeline_id
        return d


class CommandraBrain:
    """Single entry point every user interaction passes through."""

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider
        self.planning_engine = PlanningEngine()
        self.context_engine = ContextEngine()
        self.reasoning_engine = ReasoningEngine()
        self.reasoning_engine.set_provider(provider)
        self.memory_engine = MemoryEngine()
        self.repository_indexer = RepositoryIndexer()
        self.agents = build_agents(provider)
        self._indexes: dict[str, RepositoryIndex] = {}

        # Original infrastructure
        self.ollama_optimizer = OllamaOptimizer()
        self.session_manager = SessionManager()
        self.workspace_engine = WorkspaceEngine()
        self.diff_engine = DiffEngine()
        self.plugin_registry = get_plugin_registry()
        self._style_profiles: dict[str, StyleProfile] = {}

        # New systems (all optional / gracefully degraded)
        self.mcp_client = MCPClient()
        self.lsp_engine = LSPEngine()
        self.rag_pipeline = RAGPipeline()
        self.execution_sandbox = ExecutionSandbox()
        self.reflection_engine = ReflectionEngine()
        self.benchmark_suite = BenchmarkSuite()
        self.planning_timeline = PlanningTimeline()
        self.knowledge_base = KnowledgeBase()
        self.preview_engine = PreviewEngine()

        # Runtime bookkeeping
        self._request_timings: list[float] = []

    # -- Repository lifecycle -------------------------------------------------

    def index_repository(self, repo_id: str, root: str) -> RepositoryIndex:
        index = self.repository_indexer.build(repo_id, root)
        self._indexes[repo_id] = index
        self.memory_engine.record_architecture_note(
            repo_id,
            f"Indexed {index.file_count} files. Detected frameworks: "
            f"{', '.join(index.frameworks) or 'none detected'}. "
            f"Languages: {', '.join(sorted(index.languages, key=index.languages.get, reverse=True)[:5])}."
            f" Knowledge graph: {index.knowledge_graph.summary()}.",
        )
        self.workspace_engine.open_workspace(repo_id, root)
        sample = dict(list((p, f.content) for p, f in index.files.items())[:50])
        self._style_profiles[repo_id] = analyze_style(sample)
        return index

    def get_style_profile(self, repo_id: str) -> StyleProfile | None:
        return self._style_profiles.get(repo_id)

    def get_index(self, repo_id: str) -> RepositoryIndex | None:
        return self._indexes.get(repo_id)

    def reindex_file(self, repo_id: str, path: str, content: str) -> None:
        index = self._indexes.get(repo_id)
        if index is None:
            raise KeyError(f"Unknown repository: {repo_id}")
        self.repository_indexer.update_file(index, path, content)

    # -- Chat / generation ------------------------------------------------------

    def set_provider(self, provider: AIProvider) -> None:
        self.provider = provider
        self.agents = build_agents(provider)
        self.reasoning_engine.set_provider(provider)

    def handle_request(self, repo_id: str | None, request: str) -> BrainResponse:
        start = time.time()
        steps_trace: list[dict] = []

        # Create a planning timeline for this request
        timeline = self.planning_timeline.create_timeline(request)
        self.planning_timeline.advance(timeline.task_id, StageName.PLANNING, StageStatus.IN_PROGRESS)

        index = self._indexes.get(repo_id) if repo_id else None

        # -- Repository Analysis stage
        self.planning_timeline.advance(timeline.task_id, StageName.REPOSITORY_ANALYSIS,
                                       StageStatus.IN_PROGRESS, f"repo_id={repo_id}")

        # -- Context Collection stage (RAG if index is available, else fallback)
        self.planning_timeline.advance(timeline.task_id, StageName.CONTEXT_COLLECTION, StageStatus.IN_PROGRESS)

        if index is not None:
            # Augment with RAG pipeline for richer context selection
            rag_files = {p: f.content for p, f in list(index.files.items())[:200]}
            rag_result = self.rag_pipeline.retrieve(request, rag_files, max_tokens=3500)
            steps_trace.append({
                "step": "rag_pipeline",
                "detail": f"retrieved {len(rag_result.selected_chunks)} chunks, {rag_result.total_tokens} tokens",
            })

            context = self.context_engine.select(index, request)
        else:
            context = ContextSelection(query=request)

        steps_trace.append({"step": "context_engine", "detail": f"selected {len(context.chunks)} chunk(s)"})

        self.planning_timeline.advance(timeline.task_id, StageName.CONTEXT_COLLECTION, StageStatus.COMPLETE)
        self.planning_timeline.advance(timeline.task_id, StageName.REPOSITORY_ANALYSIS, StageStatus.COMPLETE)

        plan = self.planning_engine.create_plan(request, files_considered=context.files_considered)
        steps_trace.append({"step": "planning_engine", "detail": f"intent={plan.intent.value}, complexity={plan.complexity.value}"})

        self.planning_timeline.advance(timeline.task_id, StageName.PLANNING, StageStatus.COMPLETE,
                                       f"intent={plan.intent.value}, complexity={plan.complexity.value}")

        memory_repo_key = repo_id or "default"
        memory_block = self.memory_engine.long_term.as_prompt_block(memory_repo_key)

        # Enrich memory_block with relevant knowledge base entries
        kb_block = self.knowledge_base.relevant_for_request(request, top_k=2)
        if kb_block:
            memory_block = memory_block + "\n\n" + kb_block

        reasoning = self.reasoning_engine.reason(plan, context, memory_block)
        steps_trace.append({"step": "reasoning_engine", "detail": "reasoning trace produced"})

        self.memory_engine.conversation_memory.remember_turn("user", request)

        from agents.base import AgentInput

        if plan.complexity == Complexity.COMPLEX:
            pipeline = _COMPLEX_PIPELINE
        else:
            final_agent_step = plan.steps[-1]
            pipeline = [self.agents.get(final_agent_step.agent, self.agents["coding_agent"]).name]

        # -- Code Generation stage
        self.planning_timeline.advance(timeline.task_id, StageName.CODE_GENERATION, StageStatus.IN_PROGRESS)

        previous_actions: list[PreviousAction] = []
        last_output = None
        last_agent_name = pipeline[0]

        for agent_name in pipeline:
            agent = self.agents.get(agent_name, self.agents["coding_agent"])
            agent_output = agent.run(
                AgentInput(
                    request=request,
                    plan=plan,
                    reasoning=reasoning,
                    context=context,
                    memory_block=memory_block,
                    previous_actions=list(previous_actions),
                )
            )
            steps_trace.append({"step": agent.name, "detail": "response generated"})
            previous_actions.append(PreviousAction(step=agent.name, detail=optimize(agent_output.text)[:500]))
            last_output = agent_output
            last_agent_name = agent.name

        raw_response = optimize(last_output.text)
        self.planning_timeline.advance(timeline.task_id, StageName.CODE_GENERATION, StageStatus.COMPLETE)

        # -- Validation stage (Self-Reflection Engine)
        self.planning_timeline.advance(timeline.task_id, StageName.VALIDATION, StageStatus.IN_PROGRESS,
                                       "Running self-reflection...")
        reflection_result = self.reflection_engine.reflect(
            raw_response,
            context_files=context.file_paths(),
        )
        steps_trace.append({
            "step": "reflection_engine",
            "detail": (
                f"score={reflection_result.score:.2f}, "
                f"issues={len(reflection_result.issues)}, "
                f"refined={reflection_result.refinement_applied}"
            ),
        })
        final_response = reflection_result.revised_response
        self.planning_timeline.advance(timeline.task_id, StageName.VALIDATION, StageStatus.COMPLETE,
                                       f"score={reflection_result.score:.2f}")

        self.memory_engine.conversation_memory.remember_turn("brain", final_response)

        for step in plan.steps:
            step.done = True

        # Skip Testing/Documentation stages for non-complex requests
        if plan.complexity != Complexity.COMPLEX:
            tl_obj = self.planning_timeline.get(timeline.task_id)
            for sn in (StageName.TESTING, StageName.DOCUMENTATION):
                s = tl_obj.get_stage(sn)
                if s:
                    s.skip("Not required for this complexity level")

        self.planning_timeline.advance(timeline.task_id, StageName.COMPLETION, StageStatus.COMPLETE)

        elapsed = time.time() - start
        self._request_timings.append(elapsed)
        self.benchmark_suite.record_timing("handle_request", elapsed)

        return BrainResponse(
            plan=plan,
            reasoning=reasoning.as_dict(),
            context_files=context.file_paths(),
            agent=last_agent_name,
            response_markdown=final_response,
            provider=self.provider.name,
            model=getattr(self.provider, "model", self.provider.name),
            elapsed_seconds=elapsed,
            steps_trace=steps_trace,
            reflection=reflection_result.as_dict(),
            timeline_id=timeline.task_id,
        )

    # -- Standalone engine access (used directly by server routes) ----------

    def generate_project(self, request: str):
        from generator.project_generator import generate_project_plan

        plan = generate_project_plan(request)
        plan.notes.append(f"Selected architecture: {self.select_architecture(request, plan.project_type).pattern}")
        return plan

    def select_architecture(self, request: str, project_type: str | None = None, complexity: str | None = None) -> ArchitectureBlueprint:
        return select_architecture(request, project_type=project_type, complexity=complexity)

    # -- Semantic / symbol / reference search --------------------------------

    def search_repository(self, repo_id: str, query: str, mode: str = "hybrid", top_k: int = 10) -> list[dict]:
        index = self._require_index(repo_id)
        hits = {
            "vector": index.semantic_index.vector_search,
            "keyword": index.semantic_index.keyword_search,
            "hybrid": index.semantic_index.hybrid_search,
        }.get(mode, index.semantic_index.hybrid_search)(query, top_k=top_k)
        return [{"path": h.doc_id, "score": round(h.score, 4), "mode": h.mode} for h in hits]

    def search_symbol(self, repo_id: str, name: str) -> list[dict]:
        from context.semantic_search import symbol_search

        index = self._require_index(repo_id)
        return symbol_search(index.knowledge_graph, name)

    def search_references(self, repo_id: str, name: str) -> list[dict]:
        index = self._require_index(repo_id)
        return index.knowledge_graph.find_references(name)

    def _require_index(self, repo_id: str) -> RepositoryIndex:
        index = self._indexes.get(repo_id)
        if index is None:
            raise KeyError(f"Unknown repository: {repo_id}")
        return index

    # -- Diffing ---------------------------------------------------------

    def preview_patch(self, path: str, original: str, updated: str) -> dict:
        from diffing.diff_engine import minimal_patch

        return minimal_patch(path, original, updated)

    def apply_patch(self, path: str, original: str, updated: str) -> str:
        record = self.diff_engine.record_patch(path, original, updated)
        return record.id

    def rollback_patch(self, patch_id: str) -> str:
        return self.diff_engine.rollback(patch_id)

    # -- Task queue --------------------------------------------------------

    def build_task_queue(self, goal: str, stages: list[str] | None = None):
        from tasks.task_queue import build_default_queue

        return build_default_queue(goal, stages)

    def validate_files(self, files: dict[str, str], expected_paths: list[str] | None = None):
        from validation.validation_engine import validate_generated_files

        return validate_generated_files(files, expected_paths)

    def scan_security(self, files: dict[str, str]):
        from security.security_engine import SecurityEngine

        return SecurityEngine().scan_project(files)

    def scan_performance(self, files: dict[str, str]):
        from performance.performance_engine import PerformanceEngine

        return PerformanceEngine().scan_project(files)

    def analyze_ui(self, path: str, content: str):
        from html_intelligence.analyzer import analyze

        return analyze(path, content)

    def recommend_testing(self, repo_id: str):
        from testing.test_engine import detect_frameworks

        index = self._indexes.get(repo_id)
        if index is None:
            raise KeyError(f"Unknown repository: {repo_id}")
        file_names = {p.split("/")[-1] for p in index.files}
        dependency_names: set[str] = set()
        for f in index.files.values():
            dependency_names.update(f.symbols.imports)
        return detect_frameworks(file_names, dependency_names)

    def generate_docs(self, repo_id: str, kind: str) -> str:
        from documentation.doc_generator import generate_architecture_doc, generate_installation_guide, generate_readme

        index = self._indexes.get(repo_id)
        if index is None:
            raise KeyError(f"Unknown repository: {repo_id}")
        arch = index.architecture.as_dict() if index.architecture else {"narrative": "No architecture summary available."}
        install_cmd = index.package_managers[0].install_command if index.package_managers else None

        if kind == "architecture":
            return generate_architecture_doc(arch)
        if kind == "installation":
            return generate_installation_guide([pm.__dict__ for pm in index.package_managers])
        return generate_readme(repo_id, arch.get("narrative", ""), install_cmd, None)

    # -- MCP ------------------------------------------------------------------

    def mcp_connect(self, command: list[str], env: dict[str, str] | None = None, server_id: str | None = None) -> dict:
        info = self.mcp_client.connect_server(command, env, server_id)
        return info.as_dict()

    def mcp_disconnect(self, server_id: str) -> bool:
        return self.mcp_client.disconnect_server(server_id)

    def mcp_list_servers(self) -> list[dict]:
        return self.mcp_client.list_servers()

    def mcp_all_tools(self) -> list[dict]:
        return [t.as_dict() for t in self.mcp_client.all_tools()]

    def mcp_all_resources(self) -> list[dict]:
        return [r.as_dict() for r in self.mcp_client.all_resources()]

    def mcp_all_prompts(self) -> list[dict]:
        return [p.as_dict() for p in self.mcp_client.all_prompts()]

    def mcp_call_tool(self, tool_name: str, arguments: dict, server_id: str | None = None) -> dict:
        result = self.mcp_client.call_tool(tool_name, arguments, server_id)
        return result.as_dict()

    def mcp_read_resource(self, uri: str, server_id: str | None = None) -> dict:
        return self.mcp_client.read_resource(uri, server_id)

    def mcp_get_prompt(self, name: str, arguments: dict | None = None, server_id: str | None = None) -> dict:
        return self.mcp_client.get_prompt(name, arguments, server_id)

    def mcp_capabilities(self) -> dict:
        return self.mcp_client.capabilities()

    # -- LSP ------------------------------------------------------------------

    def lsp_go_to_definition(self, repo_id: str, file_path: str, line: int, character: int) -> list[dict]:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        all_files = {p: f.content for p, f in index.files.items()}
        locs = self.lsp_engine.go_to_definition(file_path, file.content, line, character, index.knowledge_graph)
        return [l.as_dict() for l in locs]

    def lsp_find_references(self, repo_id: str, file_path: str, line: int, character: int) -> list[dict]:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        all_files = {p: f.content for p, f in index.files.items()}
        locs = self.lsp_engine.find_references(file_path, file.content, line, character, index.knowledge_graph, all_files)
        return [l.as_dict() for l in locs]

    def lsp_rename_symbol(self, repo_id: str, file_path: str, line: int, character: int, new_name: str) -> dict:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return {}
        all_files = {p: f.content for p, f in index.files.items()}
        return self.lsp_engine.rename_symbol(file_path, file.content, line, character, new_name, all_files)

    def lsp_hover(self, repo_id: str, file_path: str, line: int, character: int) -> dict | None:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return None
        result = self.lsp_engine.hover(file_path, file.content, line, character, index.knowledge_graph)
        return result.as_dict() if result else None

    def lsp_diagnostics(self, repo_id: str, file_path: str) -> list[dict]:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        diags = self.lsp_engine.diagnostics(file_path, file.content, file.language)
        return [d.as_dict() for d in diags]

    def lsp_semantic_tokens(self, repo_id: str, file_path: str) -> list[dict]:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        return self.lsp_engine.semantic_tokens(file.content, file.language)

    def lsp_document_symbols(self, repo_id: str, file_path: str) -> list[dict]:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        return self.lsp_engine.document_symbols(file_path, file.content, file.language)

    def lsp_workspace_symbols(self, repo_id: str, query: str) -> list[dict]:
        index = self._require_index(repo_id)
        return self.lsp_engine.workspace_symbols(query, index.knowledge_graph)

    def lsp_code_actions(self, repo_id: str, file_path: str, line: int, character: int) -> list[dict]:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        return self.lsp_engine.code_actions(file_path, file.content, file.language, line, character)

    # -- RAG ------------------------------------------------------------------

    def rag_retrieve(self, repo_id: str, query: str, max_tokens: int = 4000, top_k: int = 20) -> dict:
        index = self._require_index(repo_id)
        files = {p: f.content for p, f in index.files.items()}
        result = self.rag_pipeline.retrieve(query, files, max_tokens=max_tokens, top_k=top_k)
        return result.as_dict()

    # -- Sandbox --------------------------------------------------------------

    def sandbox_execute(self, language: str, code: str, timeout: float = 10.0, stdin_data: str = "") -> dict:
        from sandbox.execution_sandbox import ExecutionRequest, Language
        try:
            lang = Language(language.lower())
        except ValueError:
            return {"error": f"Unknown language: {language}", "success": False}
        from sandbox.execution_sandbox import ExecutionRequest
        req = ExecutionRequest(language=lang, code=code, timeout_seconds=timeout, stdin_data=stdin_data)
        result = self.execution_sandbox.execute(req)
        return result.as_dict()

    def sandbox_runtimes(self) -> dict:
        return self.execution_sandbox.available_runtimes()

    # -- Reflection -----------------------------------------------------------

    def reflect_response(self, response: str, context_files: list[str] | None = None) -> dict:
        result = self.reflection_engine.reflect(response, context_files)
        return result.as_dict()

    # -- Benchmarks -----------------------------------------------------------

    def run_benchmarks(
        self,
        code_samples: dict[str, str] | None = None,
        index_summary: dict | None = None,
    ) -> dict:
        from planning.planning_engine import _classify_intent
        classify_fn = lambda req: _classify_intent(req).value
        report = self.benchmark_suite.full_report(
            code_samples=code_samples,
            index_summary=index_summary,
            classify_fn=classify_fn,
            request_timings=list(self._request_timings),
        )
        return report.as_dict()

    def list_benchmark_reports(self) -> list[str]:
        return self.benchmark_suite.list_reports()

    def load_benchmark_report(self, filename: str) -> dict:
        return self.benchmark_suite.load_report(filename)

    # -- Planning Timeline ----------------------------------------------------

    def get_timeline(self, task_id: str) -> dict:
        return self.planning_timeline.get(task_id).as_dict()

    def list_timelines(self, active_only: bool = False) -> list[dict]:
        if active_only:
            return self.planning_timeline.list_active()
        return self.planning_timeline.list_all()

    # -- Knowledge Base -------------------------------------------------------

    def kb_search(self, query: str, top_k: int = 5, category: str | None = None) -> list[dict]:
        from knowledge.knowledge_base import KBCategory
        cat = None
        if category:
            try:
                cat = KBCategory(category)
            except ValueError:
                pass
        return [e.as_dict() for e in self.knowledge_base.search(query, top_k=top_k, category=cat)]

    def kb_get(self, entry_id: str) -> dict | None:
        entry = self.knowledge_base.get(entry_id)
        return entry.as_dict() if entry else None

    def kb_by_category(self, category: str) -> list[dict]:
        from knowledge.knowledge_base import KBCategory
        try:
            cat = KBCategory(category)
        except ValueError:
            return []
        return [e.as_dict() for e in self.knowledge_base.by_category(cat)]

    def kb_add_entry(self, entry_data: dict) -> dict:
        from knowledge.knowledge_base import KBEntry, KBCategory
        entry = KBEntry(
            entry_id=entry_data["entryId"],
            category=KBCategory(entry_data["category"]),
            title=entry_data["title"],
            summary=entry_data["summary"],
            detail=entry_data.get("detail", ""),
            tags=entry_data.get("tags", []),
            examples=entry_data.get("examples", []),
            related=entry_data.get("related", []),
        )
        self.knowledge_base.add_entry(entry)
        return entry.as_dict()

    # -- Preview Engine -------------------------------------------------------

    def preview_generate(self, code: str, language: str | None = None) -> dict:
        result = self.preview_engine.generate(code, language)
        return result.as_dict()

    def preview_refresh(self, code: str, previous_html: str = "", language: str | None = None) -> dict:
        result = self.preview_engine.refresh(code, previous_html, language)
        return result.as_dict()

    def preview_languages(self) -> list[str]:
        return self.preview_engine.supported_languages()


# ============================================================================
# Integration methods (added in v0.3.0)  -- AST, Search, VectorDB, Security,
# Git, LSP Servers, Docker, MCP Known Servers, Integration Registry
# ============================================================================

    # -- AST Intelligence --------------------------------------------------------

    def ast_parse(self, language: str, content: str) -> dict:
        from ast_intelligence.tree_sitter_engine import TreeSitterEngine
        engine = TreeSitterEngine()
        return engine.parse(language, content).as_dict()

    def ast_get_tree(self, language: str, content: str) -> dict:
        from ast_intelligence.tree_sitter_engine import TreeSitterEngine
        engine = TreeSitterEngine()
        return engine.get_ast(language, content)

    def ast_grep_search(self, pattern: str, language: str, root: str, top_k: int = 50) -> dict:
        from ast_intelligence.ast_grep_engine import AstGrepEngine
        return AstGrepEngine().search(pattern, language, root, top_k=top_k).as_dict()

    def ast_grep_rewrite(self, pattern: str, rewrite: str, language: str, root: str, dry_run: bool = True) -> dict:
        from ast_intelligence.ast_grep_engine import AstGrepEngine
        return AstGrepEngine().rewrite(pattern, rewrite, language, root, dry_run)

    def ctags_index(self, root: str, languages: list | None = None) -> dict:
        from ast_intelligence.ctags_engine import CtagsEngine
        return CtagsEngine().index_repository(root, languages).as_dict()

    def ctags_search(self, root: str, name: str) -> list:
        from ast_intelligence.ctags_engine import CtagsEngine
        return [s.as_dict() for s in CtagsEngine().search_symbol(root, name)]

    def build_import_graph(self, repo_id: str) -> dict:
        from ast_intelligence.graph_engine import GraphEngine
        index = self._require_index(repo_id)
        files = {p: (f.language, f.content) for p, f in index.files.items()}
        return GraphEngine().build_import_graph(files).as_dict()

    def build_inheritance_graph(self, repo_id: str) -> dict:
        from ast_intelligence.graph_engine import GraphEngine
        index = self._require_index(repo_id)
        files = {p: (f.language, f.content) for p, f in index.files.items()}
        return GraphEngine().build_inheritance_graph(files).as_dict()

    def build_full_graph(self, repo_id: str) -> dict:
        from ast_intelligence.graph_engine import GraphEngine
        index = self._require_index(repo_id)
        files = {p: (f.language, f.content) for p, f in index.files.items()}
        return GraphEngine().full_graph(files).as_dict()

    def ast_available_languages(self) -> list:
        from ast_intelligence.tree_sitter_engine import TreeSitterEngine
        return TreeSitterEngine.available_languages()

    # -- Search & Discovery -------------------------------------------------------

    def ripgrep_search(self, query: str, root: str, case_sensitive: bool = False,
                       file_glob: str | None = None, max_results: int = 200,
                       context_lines: int = 0) -> dict:
        from search.ripgrep_engine import RipgrepEngine
        return RipgrepEngine().search(query, root, case_sensitive, file_glob, max_results, context_lines).as_dict()

    def fd_find(self, root: str, pattern: str = "", extensions: list | None = None,
                hidden: bool = False, max_results: int = 1000) -> dict:
        from search.fd_engine import FdEngine
        return FdEngine().find(root, pattern, extensions, hidden, max_results).as_dict()

    def searxng_search(self, query: str, categories: list | None = None,
                       top_k: int = 10, base_url: str = "http://localhost:8888") -> dict:
        from search.searxng_client import SearXNGClient
        return SearXNGClient(base_url).search(query, categories, top_k=top_k).as_dict()

    def firecrawl_scrape(self, url: str, api_key: str | None = None) -> dict:
        from search.firecrawl_client import FirecrawlClient
        return FirecrawlClient(api_key).scrape(url).as_dict()

    def firecrawl_crawl(self, url: str, max_pages: int = 10, api_key: str | None = None) -> dict:
        from search.firecrawl_client import FirecrawlClient
        return FirecrawlClient(api_key).crawl(url, max_pages).as_dict()

    def markitdown_convert(self, file_path: str) -> dict:
        from search.markitdown_engine import MarkItDownEngine
        return MarkItDownEngine().convert(file_path).as_dict()

    def markitdown_convert_url(self, url: str) -> dict:
        from search.markitdown_engine import MarkItDownEngine
        return MarkItDownEngine().convert_url(url).as_dict()

    # -- Vector Databases ---------------------------------------------------------

    def chroma_add(self, collection: str, documents: list) -> dict:
        from vectordb.chroma_engine import ChromaEngine
        return ChromaEngine().add_documents(collection, documents)

    def chroma_search(self, collection: str, query: str, top_k: int = 10) -> dict:
        from vectordb.chroma_engine import ChromaEngine
        return ChromaEngine().search(collection, query, top_k).as_dict()

    def chroma_collections(self) -> list:
        from vectordb.chroma_engine import ChromaEngine
        return ChromaEngine().list_collections()

    def qdrant_upsert(self, collection: str, documents: list) -> dict:
        from vectordb.qdrant_engine import QdrantEngine
        return QdrantEngine().upsert(collection, documents)

    def qdrant_search(self, collection: str, query: str, top_k: int = 10) -> dict:
        from vectordb.qdrant_engine import QdrantEngine
        return QdrantEngine().search(collection, query, top_k).as_dict()

    def lancedb_add(self, table: str, documents: list) -> dict:
        from vectordb.lancedb_engine import LanceDBEngine
        return LanceDBEngine().add_documents(table, documents)

    def lancedb_search(self, table: str, query: str, top_k: int = 10) -> dict:
        from vectordb.lancedb_engine import LanceDBEngine
        return LanceDBEngine().search(table, query, top_k).as_dict()

    def lancedb_tables(self) -> list:
        from vectordb.lancedb_engine import LanceDBEngine
        return LanceDBEngine().list_tables()

    # -- Security -----------------------------------------------------------------

    def semgrep_scan_repo(self, repo_id: str, configs: list | None = None) -> dict:
        index = self._require_index(repo_id)
        from security.semgrep_engine import SemgrepEngine
        return SemgrepEngine().scan(index.root, configs).as_dict()

    def semgrep_scan_files(self, files: dict, configs: list | None = None) -> dict:
        from security.semgrep_engine import SemgrepEngine
        return SemgrepEngine().scan_files(files, configs).as_dict()

    def osv_scan(self, repo_id: str) -> dict:
        index = self._require_index(repo_id)
        from security.osv_scanner import OSVScanner
        return OSVScanner().scan(index.root).as_dict()

    def gitleaks_scan(self, repo_id: str, scan_history: bool = False) -> dict:
        index = self._require_index(repo_id)
        from security.gitleaks_engine import GitleaksEngine
        engine = GitleaksEngine()
        if scan_history:
            return engine.scan_git_history(index.root).as_dict()
        return engine.scan_directory(index.root).as_dict()

    # -- Git Engine ---------------------------------------------------------------

    def git_info(self, repo_id: str) -> dict:
        index = self._require_index(repo_id)
        from git.git_engine import GitEngine
        return GitEngine(index.root).info().as_dict()

    def git_log(self, repo_id: str, max_commits: int = 20, file_path: str | None = None) -> list:
        index = self._require_index(repo_id)
        from git.git_engine import GitEngine
        return [c.as_dict() for c in GitEngine(index.root).log(max_commits, file_path)]

    def git_diff(self, repo_id: str, ref_a: str = "HEAD~1", ref_b: str = "HEAD", file_path: str | None = None) -> list:
        index = self._require_index(repo_id)
        from git.git_engine import GitEngine
        return [d.as_dict() for d in GitEngine(index.root).diff(ref_a, ref_b, file_path)]

    def git_branches(self, repo_id: str) -> list:
        index = self._require_index(repo_id)
        from git.git_engine import GitEngine
        return [b.as_dict() for b in GitEngine(index.root).branches()]

    def git_blame(self, repo_id: str, file_path: str) -> list:
        index = self._require_index(repo_id)
        from git.git_engine import GitEngine
        return [e.as_dict() for e in GitEngine(index.root).blame(file_path)]

    def git_file_history(self, repo_id: str, file_path: str, max_commits: int = 10) -> list:
        index = self._require_index(repo_id)
        from git.git_engine import GitEngine
        return [c.as_dict() for c in GitEngine(index.root).file_history(file_path, max_commits)]

    # -- LSP Server Adapters ------------------------------------------------------

    def lsp_start_server(self, language: str, repo_id: str) -> dict:
        index = self._require_index(repo_id)
        from lsp.server_adapters import LSPServerManager
        if not hasattr(self, "_lsp_manager"):
            self._lsp_manager = LSPServerManager()
        started = self._lsp_manager.start_server(language, index.root)
        return {"language": language, "started": started, "repoId": repo_id}

    def lsp_available_servers(self) -> dict:
        from lsp.server_adapters import LSPServerManager
        if not hasattr(self, "_lsp_manager"):
            self._lsp_manager = LSPServerManager()
        return {"servers": self._lsp_manager.available_servers()}

    def lsp_server_hover(self, language: str, repo_id: str, file_path: str, line: int, character: int) -> dict | None:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return None
        from lsp.server_adapters import LSPServerManager
        if not hasattr(self, "_lsp_manager"):
            self._lsp_manager = LSPServerManager()
        return self._lsp_manager.hover(language, file_path, file.content, line, character)

    def lsp_server_definition(self, language: str, repo_id: str, file_path: str, line: int, character: int) -> list:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        from lsp.server_adapters import LSPServerManager
        if not hasattr(self, "_lsp_manager"):
            self._lsp_manager = LSPServerManager()
        return self._lsp_manager.definition(language, file_path, file.content, line, character)

    def lsp_server_references(self, language: str, repo_id: str, file_path: str, line: int, character: int) -> list:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        from lsp.server_adapters import LSPServerManager
        if not hasattr(self, "_lsp_manager"):
            self._lsp_manager = LSPServerManager()
        return self._lsp_manager.references(language, file_path, file.content, line, character)

    def lsp_server_rename(self, language: str, repo_id: str, file_path: str, line: int, character: int, new_name: str) -> dict:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return {}
        from lsp.server_adapters import LSPServerManager
        if not hasattr(self, "_lsp_manager"):
            self._lsp_manager = LSPServerManager()
        return self._lsp_manager.rename(language, file_path, file.content, line, character, new_name)

    def lsp_server_symbols(self, language: str, repo_id: str, file_path: str) -> list:
        index = self._require_index(repo_id)
        file = index.files.get(file_path)
        if file is None:
            return []
        from lsp.server_adapters import LSPServerManager
        if not hasattr(self, "_lsp_manager"):
            self._lsp_manager = LSPServerManager()
        return self._lsp_manager.document_symbols(language, file_path, file.content)

    # -- Docker Sandbox -----------------------------------------------------------

    def docker_execute(self, language: str, code: str, timeout: float = 15.0,
                       memory_mb: int = 256, network_disabled: bool = True) -> dict:
        from sandbox.docker_sandbox import DockerSandbox
        return DockerSandbox().execute(language, code, timeout, memory_mb,
                                       network_disabled=network_disabled).as_dict()

    def docker_available_images(self) -> dict:
        from sandbox.docker_sandbox import DockerSandbox
        sb = DockerSandbox()
        return {
            "available": sb.available(),
            "images": sb.available_images(),
            "pulled": sb.list_pulled_images(),
        }

    def docker_pull_image(self, language: str) -> dict:
        from sandbox.docker_sandbox import DockerSandbox
        return DockerSandbox().pull_image(language)

    # -- MCP Known Servers --------------------------------------------------------

    def mcp_known_servers(self) -> list:
        from mcp.known_servers import list_known_servers
        return list_known_servers()

    def mcp_ready_servers(self) -> list:
        from mcp.known_servers import ready_servers
        return ready_servers()

    def mcp_connect_known(self, server_id: str, extra_args: list | None = None) -> dict:
        from mcp.known_servers import get_known_server
        known = get_known_server(server_id)
        if not known:
            raise KeyError(f"Unknown MCP server: {server_id}")
        command = known.command(extra_args)
        env = known.env_from_os()
        return self.mcp_connect(command, env, server_id)

    # -- Integration Registry -----------------------------------------------------

    def integrations_list(self, category: str | None = None) -> list:
        from integrations.registry import list_integrations
        return list_integrations(category)

    def integrations_status(self) -> dict:
        from integrations.registry import integration_status
        return integration_status()

    def integrations_available(self) -> list:
        from integrations.registry import available_integrations
        return available_integrations()

    def integrations_unavailable(self) -> list:
        from integrations.registry import unavailable_integrations
        return unavailable_integrations()

    def integration_get(self, integration_id: str) -> dict | None:
        from integrations.registry import get_integration
        return get_integration(integration_id)
