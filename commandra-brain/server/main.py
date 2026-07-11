"""
Commandra Nox Brain -- HTTP server entry point.

Every request from the UI passes through this API into `CommandraBrain`
(brain/orchestrator.py). Ollama (or the MockProvider) is only ever reached
from inside the Brain, never directly from a route handler.

Run with: `python -m server.main` or `uvicorn server.main:app`.
The port is read from $PORT (falls back to 8765 for standalone local runs).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from brain.orchestrator import CommandraBrain
from repository import workspace
from server.schemas import (
    AnalyzeUiRequest,
    ArchitectureSelectRequest,
    BenchmarkRunRequest,
    ChatRequest,
    CreateSessionRequest,
    GenerateDocsRequest,
    GenerateProjectRequest,
    IndexRepoResponse,
    IndexRepoRequest,
    KBAddEntryRequest,
    KBSearchRequest,
    LSPFileRequest,
    LSPPositionRequest,
    LSPRenameRequest,
    MCPCallToolRequest,
    MCPConnectRequest,
    MCPDisconnectRequest,
    MCPGetPromptRequest,
    MCPReadResourceRequest,
    PatchPreviewRequest,
    PluginInvokeRequest,
    PreviewGenerateRequest,
    PreviewRefreshRequest,
    ProviderConfig,
    RAGRetrieveRequest,
    ReflectRequest,
    SandboxExecuteRequest,
    ScanFilesRequest,
    SearchRequest,
    SymbolSearchRequest,
    TaskQueueRequest,
    ValidateFilesRequest,
)
from server.settings import get_provider, set_provider
from providers.ollama_provider import build_ollama_provider
from providers.mock_provider import MockProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("commandra.server")

app = FastAPI(title="Commandra Nox Brain", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

brain = CommandraBrain(provider=get_provider())


# ===========================================================================
# Core endpoints (unchanged from v0.1)
# ===========================================================================

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": brain.provider.describe()}


@app.get("/agents")
def list_agents() -> dict:
    from agents.registry import available_agents
    return {"agents": available_agents()}


@app.get("/provider")
def get_provider_status() -> dict:
    return brain.provider.describe()


@app.post("/provider")
def update_provider(config: ProviderConfig) -> dict:
    if config.provider == "mock":
        provider = MockProvider()
    elif config.provider == "ollama":
        provider = build_ollama_provider(base_url=config.baseUrl, model=config.model)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {config.provider}")
    set_provider(provider)
    brain.set_provider(provider)
    return provider.describe()


@app.post("/repository/index", response_model=IndexRepoResponse)
def index_repository_by_path(body: IndexRepoRequest) -> IndexRepoResponse:
    try:
        root = workspace.register_local_path(body.path)
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repo_id = workspace.new_repo_id()
    index = brain.index_repository(repo_id, root)
    return IndexRepoResponse(repoId=repo_id, root=root, **_index_summary(index))


@app.post("/repository/upload", response_model=IndexRepoResponse)
async def index_repository_upload(file: UploadFile = File(...)) -> IndexRepoResponse:
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported")
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        repo_id, root = workspace.extract_zip_upload(tmp_path)
    finally:
        os.unlink(tmp_path)
    index = brain.index_repository(repo_id, root)
    return IndexRepoResponse(repoId=repo_id, root=root, **_index_summary(index))


@app.get("/repository/{repo_id}")
def get_repository(repo_id: str) -> dict:
    index = brain.get_index(repo_id)
    if index is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    return index.summary()


@app.get("/repository/{repo_id}/files")
def get_repository_files(repo_id: str) -> dict:
    index = brain.get_index(repo_id)
    if index is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    return {"files": index.file_list()}


@app.get("/repository/{repo_id}/file")
def get_repository_file(repo_id: str, path: str) -> dict:
    index = brain.get_index(repo_id)
    if index is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    file = index.files.get(path)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found in index")
    return {
        "path": file.path,
        "language": file.language,
        "content": file.content,
        "symbols": [s.__dict__ for s in file.symbols.symbols],
        "imports": file.symbols.imports,
    }


@app.get("/memory/{repo_id}")
def get_memory(repo_id: str) -> dict:
    return {"entries": brain.memory_engine.long_term.all_for(repo_id)}


@app.post("/chat")
def chat(body: ChatRequest) -> dict:
    if body.repoId and brain.get_index(body.repoId) is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    response = brain.handle_request(body.repoId, body.message)
    return response.as_dict()


@app.post("/generator/project")
def generate_project(body: GenerateProjectRequest) -> dict:
    return brain.generate_project(body.request).as_dict()


@app.post("/validation/files")
def validate_files(body: ValidateFilesRequest) -> dict:
    return brain.validate_files(body.files, body.expectedPaths).as_dict()


@app.post("/security/scan")
def scan_security(body: ScanFilesRequest) -> dict:
    return brain.scan_security(body.files).as_dict()


@app.post("/performance/scan")
def scan_performance(body: ScanFilesRequest) -> dict:
    return brain.scan_performance(body.files).as_dict()


@app.post("/ui/analyze")
def analyze_ui(body: AnalyzeUiRequest) -> dict:
    return brain.analyze_ui(body.path, body.content).as_dict()


@app.get("/repository/{repo_id}/testing")
def recommend_testing(repo_id: str) -> dict:
    if brain.get_index(repo_id) is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    return brain.recommend_testing(repo_id).as_dict()


@app.post("/repository/{repo_id}/docs")
def generate_docs(repo_id: str, body: GenerateDocsRequest) -> dict:
    if brain.get_index(repo_id) is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    return {"kind": body.kind, "content": brain.generate_docs(repo_id, body.kind)}


@app.get("/tools")
def list_tools() -> dict:
    from tools.registry import available_tools
    return {"tools": available_tools()}


@app.post("/repository/{repo_id}/search")
def search_repository(repo_id: str, body: SearchRequest) -> dict:
    if brain.get_index(repo_id) is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    return {"results": brain.search_repository(repo_id, body.query, body.mode, body.topK)}


@app.post("/repository/{repo_id}/search/symbol")
def search_symbol(repo_id: str, body: SymbolSearchRequest) -> dict:
    if brain.get_index(repo_id) is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    return {"results": brain.search_symbol(repo_id, body.name)}


@app.post("/repository/{repo_id}/search/references")
def search_references(repo_id: str, body: SymbolSearchRequest) -> dict:
    if brain.get_index(repo_id) is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    return {"results": brain.search_references(repo_id, body.name)}


@app.get("/repository/{repo_id}/style")
def get_style_profile(repo_id: str) -> dict:
    if brain.get_index(repo_id) is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")
    profile = brain.get_style_profile(repo_id)
    return profile.as_dict() if profile else {}


@app.post("/architecture/select")
def select_architecture(body: ArchitectureSelectRequest) -> dict:
    return brain.select_architecture(body.request, body.projectType, body.complexity).as_dict()


@app.get("/architecture/patterns")
def list_architecture_patterns() -> dict:
    from architecture.architecture_engine import available_patterns
    return {"patterns": available_patterns()}


@app.post("/diff/preview")
def diff_preview(body: PatchPreviewRequest) -> dict:
    return brain.preview_patch(body.path, body.original, body.updated)


@app.post("/tasks/queue")
def build_task_queue(body: TaskQueueRequest) -> dict:
    queue = brain.build_task_queue(body.goal, body.stages)
    return {"steps": [s.__dict__ for s in queue.steps]}


@app.get("/plugins")
def list_plugins() -> dict:
    return {"plugins": brain.plugin_registry.list_plugins()}


@app.post("/plugins/{plugin_name}/invoke")
def invoke_plugin(plugin_name: str, body: PluginInvokeRequest) -> dict:
    try:
        result = brain.plugin_registry.invoke(plugin_name, body.action, **body.args)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.as_dict()


@app.post("/sessions")
def create_session(body: CreateSessionRequest) -> dict:
    session = brain.session_manager.create(body.repoId)
    return session.as_dict()


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        return brain.session_manager.resume_summary(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/workspace/{repo_id}")
def get_workspace(repo_id: str) -> dict:
    state = brain.workspace_engine.get(repo_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Workspace not opened for this repository")
    return state.as_dict()


# ===========================================================================
# 1. MCP — Model Context Protocol
# ===========================================================================

@app.post("/mcp/connect")
def mcp_connect(body: MCPConnectRequest) -> dict:
    """Connect to an external MCP server and discover its tools/resources/prompts."""
    return brain.mcp_connect(body.command, body.env, body.serverId)


@app.post("/mcp/disconnect")
def mcp_disconnect(body: MCPDisconnectRequest) -> dict:
    ok = brain.mcp_disconnect(body.serverId)
    return {"disconnected": ok, "serverId": body.serverId}


@app.get("/mcp/servers")
def mcp_list_servers() -> dict:
    return {"servers": brain.mcp_list_servers()}


@app.get("/mcp/tools")
def mcp_all_tools() -> dict:
    return {"tools": brain.mcp_all_tools()}


@app.get("/mcp/resources")
def mcp_all_resources() -> dict:
    return {"resources": brain.mcp_all_resources()}


@app.get("/mcp/prompts")
def mcp_all_prompts() -> dict:
    return {"prompts": brain.mcp_all_prompts()}


@app.get("/mcp/capabilities")
def mcp_capabilities() -> dict:
    return {"capabilities": brain.mcp_capabilities()}


@app.post("/mcp/tools/call")
def mcp_call_tool(body: MCPCallToolRequest) -> dict:
    try:
        return brain.mcp_call_tool(body.toolName, body.arguments, body.serverId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/mcp/resources/read")
def mcp_read_resource(body: MCPReadResourceRequest) -> dict:
    try:
        return brain.mcp_read_resource(body.uri, body.serverId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/mcp/prompts/get")
def mcp_get_prompt(body: MCPGetPromptRequest) -> dict:
    try:
        return brain.mcp_get_prompt(body.name, body.arguments, body.serverId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ===========================================================================
# 2. LSP — Language Server Protocol
# ===========================================================================

@app.post("/repository/{repo_id}/lsp/definition")
def lsp_definition(repo_id: str, body: LSPPositionRequest) -> dict:
    _require_repo(repo_id)
    return {"locations": brain.lsp_go_to_definition(repo_id, body.filePath, body.line, body.character)}


@app.post("/repository/{repo_id}/lsp/references")
def lsp_references(repo_id: str, body: LSPPositionRequest) -> dict:
    _require_repo(repo_id)
    return {"locations": brain.lsp_find_references(repo_id, body.filePath, body.line, body.character)}


@app.post("/repository/{repo_id}/lsp/rename")
def lsp_rename(repo_id: str, body: LSPRenameRequest) -> dict:
    _require_repo(repo_id)
    return {"workspaceEdit": brain.lsp_rename_symbol(repo_id, body.filePath, body.line, body.character, body.newName)}


@app.post("/repository/{repo_id}/lsp/hover")
def lsp_hover(repo_id: str, body: LSPPositionRequest) -> dict:
    _require_repo(repo_id)
    result = brain.lsp_hover(repo_id, body.filePath, body.line, body.character)
    return {"hover": result}


@app.post("/repository/{repo_id}/lsp/diagnostics")
def lsp_diagnostics(repo_id: str, body: LSPFileRequest) -> dict:
    _require_repo(repo_id)
    return {"diagnostics": brain.lsp_diagnostics(repo_id, body.filePath)}


@app.post("/repository/{repo_id}/lsp/semanticTokens")
def lsp_semantic_tokens(repo_id: str, body: LSPFileRequest) -> dict:
    _require_repo(repo_id)
    return {"tokens": brain.lsp_semantic_tokens(repo_id, body.filePath)}


@app.post("/repository/{repo_id}/lsp/documentSymbols")
def lsp_document_symbols(repo_id: str, body: LSPFileRequest) -> dict:
    _require_repo(repo_id)
    return {"symbols": brain.lsp_document_symbols(repo_id, body.filePath)}


@app.post("/repository/{repo_id}/lsp/workspaceSymbols")
def lsp_workspace_symbols(repo_id: str, body: SymbolSearchRequest) -> dict:
    _require_repo(repo_id)
    return {"symbols": brain.lsp_workspace_symbols(repo_id, body.name)}


@app.post("/repository/{repo_id}/lsp/codeActions")
def lsp_code_actions(repo_id: str, body: LSPPositionRequest) -> dict:
    _require_repo(repo_id)
    return {"actions": brain.lsp_code_actions(repo_id, body.filePath, body.line, body.character)}


# ===========================================================================
# 3. Advanced RAG Pipeline
# ===========================================================================

@app.post("/repository/{repo_id}/rag/retrieve")
def rag_retrieve(repo_id: str, body: RAGRetrieveRequest) -> dict:
    _require_repo(repo_id)
    return brain.rag_retrieve(repo_id, body.query, body.maxTokens, body.topK)


# ===========================================================================
# 4. Secure Code Execution Sandbox
# ===========================================================================

@app.post("/sandbox/execute")
def sandbox_execute(body: SandboxExecuteRequest) -> dict:
    return brain.sandbox_execute(body.language, body.code, body.timeoutSeconds, body.stdinData)


@app.get("/sandbox/runtimes")
def sandbox_runtimes() -> dict:
    return {"runtimes": brain.sandbox_runtimes()}


# ===========================================================================
# 5. Self-Reflection Engine
# ===========================================================================

@app.post("/reflect")
def reflect_response(body: ReflectRequest) -> dict:
    return brain.reflect_response(body.response, body.contextFiles)


# ===========================================================================
# 6. Benchmark Suite
# ===========================================================================

@app.post("/benchmarks/run")
def run_benchmarks(body: BenchmarkRunRequest) -> dict:
    return brain.run_benchmarks(
        code_samples=body.codeSamples,
        index_summary=body.indexSummary,
    )


@app.get("/benchmarks/reports")
def list_benchmark_reports() -> dict:
    return {"reports": brain.list_benchmark_reports()}


@app.get("/benchmarks/reports/{filename}")
def load_benchmark_report(filename: str) -> dict:
    try:
        return brain.load_benchmark_report(filename)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ===========================================================================
# 7. AI Planning Timeline
# ===========================================================================

@app.get("/timeline/{task_id}")
def get_timeline(task_id: str) -> dict:
    try:
        return brain.get_timeline(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/timelines")
def list_timelines(active: bool = False) -> dict:
    return {"timelines": brain.list_timelines(active_only=active)}


# ===========================================================================
# 8. Local Knowledge Base
# ===========================================================================

@app.post("/knowledge/search")
def kb_search(body: KBSearchRequest) -> dict:
    return {"entries": brain.kb_search(body.query, body.topK, body.category)}


@app.get("/knowledge/{entry_id}")
def kb_get(entry_id: str) -> dict:
    entry = brain.kb_get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Knowledge entry '{entry_id}' not found")
    return entry


@app.get("/knowledge/category/{category}")
def kb_by_category(category: str) -> dict:
    return {"entries": brain.kb_by_category(category)}


@app.post("/knowledge")
def kb_add_entry(body: KBAddEntryRequest) -> dict:
    return brain.kb_add_entry(body.model_dump(by_alias=False))


# ===========================================================================
# 9. Live UI Preview Engine
# ===========================================================================

@app.post("/preview/generate")
def preview_generate(body: PreviewGenerateRequest) -> dict:
    return brain.preview_generate(body.code, body.language)


@app.post("/preview/refresh")
def preview_refresh(body: PreviewRefreshRequest) -> dict:
    return brain.preview_refresh(body.code, body.previousHtml, body.language)


@app.get("/preview/languages")
def preview_languages() -> dict:
    return {"languages": brain.preview_languages()}


# ===========================================================================
# Helpers
# ===========================================================================

def _require_repo(repo_id: str) -> None:
    if brain.get_index(repo_id) is None:
        raise HTTPException(status_code=404, detail="Repository not indexed")


def _index_summary(index) -> dict:
    return {
        "fileCount": index.file_count,
        "skipped": index.skipped,
        "languages": index.languages,
        "frameworks": index.frameworks,
        "packageManagers": [pm.__dict__ for pm in index.package_managers],
        "dependencyGraph": index.dependency_graph.summary(),
        "architecture": index.architecture.as_dict() if index.architecture else None,
        "knowledgeGraph": index.knowledge_graph.summary(),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)


# ===========================================================================
# 10. AST Intelligence (tree-sitter, ast-grep, ctags, code graphs)
# ===========================================================================

@app.post("/ast/parse")
def ast_parse(language: str, content: str) -> dict:
    return brain.ast_parse(language, content)


@app.post("/ast/tree")
def ast_tree(language: str, content: str) -> dict:
    return brain.ast_get_tree(language, content)


@app.get("/ast/languages")
def ast_languages() -> dict:
    return {"languages": brain.ast_available_languages()}


@app.post("/ast/grep/search")
def ast_grep_search(pattern: str, language: str, root: str, topK: int = 50) -> dict:
    return brain.ast_grep_search(pattern, language, root, top_k=topK)


@app.post("/ast/grep/rewrite")
def ast_grep_rewrite(pattern: str, rewrite: str, language: str, root: str, dryRun: bool = True) -> dict:
    return brain.ast_grep_rewrite(pattern, rewrite, language, root, dry_run=dryRun)


@app.post("/ast/ctags/index")
def ctags_index(root: str, languages: str | None = None) -> dict:
    lang_list = [l.strip() for l in languages.split(",")] if languages else None
    return brain.ctags_index(root, lang_list)


@app.post("/ast/ctags/search")
def ctags_search(root: str, name: str) -> dict:
    return {"symbols": brain.ctags_search(root, name)}


@app.get("/repository/{repo_id}/graph/imports")
def graph_imports(repo_id: str) -> dict:
    _require_repo(repo_id)
    return brain.build_import_graph(repo_id)


@app.get("/repository/{repo_id}/graph/inheritance")
def graph_inheritance(repo_id: str) -> dict:
    _require_repo(repo_id)
    return brain.build_inheritance_graph(repo_id)


@app.get("/repository/{repo_id}/graph/full")
def graph_full(repo_id: str) -> dict:
    _require_repo(repo_id)
    return brain.build_full_graph(repo_id)


# ===========================================================================
# 11. Search & Discovery (ripgrep, fd, searxng, firecrawl, markitdown)
# ===========================================================================

@app.post("/search/ripgrep")
def ripgrep_search(query: str, root: str, caseSensitive: bool = False,
                   glob: str | None = None, maxResults: int = 200, context: int = 0) -> dict:
    return brain.ripgrep_search(query, root, caseSensitive, glob, maxResults, context)


@app.post("/search/fd")
def fd_find(root: str, pattern: str = "", extensions: str | None = None,
            hidden: bool = False, maxResults: int = 1000) -> dict:
    ext_list = [e.strip() for e in extensions.split(",")] if extensions else None
    return brain.fd_find(root, pattern, ext_list, hidden, maxResults)


@app.post("/search/web")
def searxng_search(query: str, categories: str | None = None, topK: int = 10,
                   baseUrl: str = "http://localhost:8888") -> dict:
    cats = [c.strip() for c in categories.split(",")] if categories else None
    return brain.searxng_search(query, cats, topK, baseUrl)


@app.post("/search/scrape")
def firecrawl_scrape(url: str, apiKey: str | None = None) -> dict:
    return brain.firecrawl_scrape(url, apiKey)


@app.post("/search/crawl")
def firecrawl_crawl(url: str, maxPages: int = 10, apiKey: str | None = None) -> dict:
    return brain.firecrawl_crawl(url, maxPages, apiKey)


@app.post("/docs/convert")
def markitdown_convert(filePath: str) -> dict:
    return brain.markitdown_convert(filePath)


@app.post("/docs/convert-url")
def markitdown_convert_url(url: str) -> dict:
    return brain.markitdown_convert_url(url)


# ===========================================================================
# 12. Vector Databases (Chroma, Qdrant, LanceDB)
# ===========================================================================

class VectorDocumentRequest(BaseModel):
    documents: list[dict]  # [{id, text, metadata}]


class VectorSearchRequest(BaseModel):
    query: str
    topK: int = 10


class _VectorDocs(BaseModel):
    documents: list[dict]

class _VectorQuery(BaseModel):
    query: str
    topK: int = 10


@app.post("/vectordb/chroma/{collection}/add")
def chroma_add(collection: str, body: _VectorDocs) -> dict:
    return brain.chroma_add(collection, body.documents)


@app.post("/vectordb/chroma/{collection}/search")
def chroma_search(collection: str, body: _VectorQuery) -> dict:
    return brain.chroma_search(collection, body.query, body.topK)


@app.get("/vectordb/chroma/collections")
def chroma_collections() -> dict:
    return {"collections": brain.chroma_collections()}


@app.post("/vectordb/qdrant/{collection}/upsert")
def qdrant_upsert(collection: str, body: _VectorDocs) -> dict:
    return brain.qdrant_upsert(collection, body.documents)


@app.post("/vectordb/qdrant/{collection}/search")
def qdrant_search(collection: str, body: _VectorQuery) -> dict:
    return brain.qdrant_search(collection, body.query, body.topK)


@app.post("/vectordb/lancedb/{table}/add")
def lancedb_add(table: str, body: _VectorDocs) -> dict:
    return brain.lancedb_add(table, body.documents)


@app.post("/vectordb/lancedb/{table}/search")
def lancedb_search(table: str, body: _VectorQuery) -> dict:
    return brain.lancedb_search(table, body.query, body.topK)


@app.get("/vectordb/lancedb/tables")
def lancedb_tables() -> dict:
    return {"tables": brain.lancedb_tables()}


# ===========================================================================
# 13. Enhanced Security (Semgrep, OSV Scanner, Gitleaks)
# ===========================================================================

class SemgrepConfigRequest(BaseModel):
    configs: list[str] | None = None


@app.post("/security/semgrep/{repo_id}")
def semgrep_scan_repo(repo_id: str, body: SemgrepConfigRequest = SemgrepConfigRequest()) -> dict:
    _require_repo(repo_id)
    return brain.semgrep_scan_repo(repo_id, body.configs)


@app.post("/security/semgrep/files")
def semgrep_scan_files(body: ScanFilesRequest) -> dict:
    return brain.semgrep_scan_files(body.files)


@app.get("/security/osv/{repo_id}")
def osv_scan(repo_id: str) -> dict:
    _require_repo(repo_id)
    return brain.osv_scan(repo_id)


@app.get("/security/gitleaks/{repo_id}")
def gitleaks_scan(repo_id: str, history: bool = False) -> dict:
    _require_repo(repo_id)
    return brain.gitleaks_scan(repo_id, history)


# ===========================================================================
# 14. Git Engine (GitPython)
# ===========================================================================

@app.get("/repository/{repo_id}/git/info")
def git_info(repo_id: str) -> dict:
    _require_repo(repo_id)
    return brain.git_info(repo_id)


@app.get("/repository/{repo_id}/git/log")
def git_log(repo_id: str, max: int = 20, file: str | None = None) -> dict:
    _require_repo(repo_id)
    return {"commits": brain.git_log(repo_id, max, file)}


@app.get("/repository/{repo_id}/git/diff")
def git_diff(repo_id: str, a: str = "HEAD~1", b: str = "HEAD", file: str | None = None) -> dict:
    _require_repo(repo_id)
    return {"diffs": brain.git_diff(repo_id, a, b, file)}


@app.get("/repository/{repo_id}/git/branches")
def git_branches(repo_id: str) -> dict:
    _require_repo(repo_id)
    return {"branches": brain.git_branches(repo_id)}


@app.get("/repository/{repo_id}/git/blame")
def git_blame(repo_id: str, file: str) -> dict:
    _require_repo(repo_id)
    return {"blame": brain.git_blame(repo_id, file)}


@app.get("/repository/{repo_id}/git/history")
def git_file_history(repo_id: str, file: str, max: int = 10) -> dict:
    _require_repo(repo_id)
    return {"commits": brain.git_file_history(repo_id, file, max)}


# ===========================================================================
# 15. Real LSP Servers (Pyright, TypeScript LS, rust-analyzer, clangd)
# ===========================================================================

@app.get("/lsp/servers")
def lsp_servers() -> dict:
    return brain.lsp_available_servers()


@app.post("/repository/{repo_id}/lsp/server/start")
def lsp_server_start(repo_id: str, language: str) -> dict:
    _require_repo(repo_id)
    return brain.lsp_start_server(language, repo_id)


@app.post("/repository/{repo_id}/lsp/server/hover")
def lsp_server_hover(repo_id: str, language: str, body: LSPPositionRequest) -> dict:
    _require_repo(repo_id)
    result = brain.lsp_server_hover(language, repo_id, body.filePath, body.line, body.character)
    return {"hover": result}


@app.post("/repository/{repo_id}/lsp/server/definition")
def lsp_server_definition(repo_id: str, language: str, body: LSPPositionRequest) -> dict:
    _require_repo(repo_id)
    return {"locations": brain.lsp_server_definition(language, repo_id, body.filePath, body.line, body.character)}


@app.post("/repository/{repo_id}/lsp/server/references")
def lsp_server_references(repo_id: str, language: str, body: LSPPositionRequest) -> dict:
    _require_repo(repo_id)
    return {"locations": brain.lsp_server_references(language, repo_id, body.filePath, body.line, body.character)}


@app.post("/repository/{repo_id}/lsp/server/rename")
def lsp_server_rename(repo_id: str, language: str, body: LSPRenameRequest) -> dict:
    _require_repo(repo_id)
    return {"edit": brain.lsp_server_rename(language, repo_id, body.filePath, body.line, body.character, body.newName)}


@app.post("/repository/{repo_id}/lsp/server/symbols")
def lsp_server_symbols(repo_id: str, language: str, body: LSPFileRequest) -> dict:
    _require_repo(repo_id)
    return {"symbols": brain.lsp_server_symbols(language, repo_id, body.filePath)}


# ===========================================================================
# 16. Docker Sandbox
# ===========================================================================

@app.post("/sandbox/docker/execute")
def docker_execute(body: SandboxExecuteRequest) -> dict:
    return brain.docker_execute(body.language, body.code, body.timeoutSeconds)


@app.get("/sandbox/docker/images")
def docker_images() -> dict:
    return brain.docker_available_images()


@app.post("/sandbox/docker/pull")
def docker_pull(language: str) -> dict:
    return brain.docker_pull_image(language)


# ===========================================================================
# 17. MCP Known Servers
# ===========================================================================

@app.get("/mcp/known")
def mcp_known_servers() -> dict:
    return {"servers": brain.mcp_known_servers()}


@app.get("/mcp/known/ready")
def mcp_ready_servers() -> dict:
    return {"servers": brain.mcp_ready_servers()}


@app.post("/mcp/known/{server_id}/connect")
def mcp_connect_known(server_id: str, extraArgs: list[str] | None = None) -> dict:
    try:
        return brain.mcp_connect_known(server_id, extraArgs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ===========================================================================
# 18. Integrations Registry
# ===========================================================================

@app.get("/integrations")
def list_integrations(category: str | None = None) -> dict:
    return {"integrations": brain.integrations_list(category)}


@app.get("/integrations/status")
def integrations_status() -> dict:
    return brain.integrations_status()


@app.get("/integrations/available")
def integrations_available() -> dict:
    return {"integrations": brain.integrations_available()}


@app.get("/integrations/unavailable")
def integrations_unavailable() -> dict:
    return {"integrations": brain.integrations_unavailable()}


@app.get("/integrations/{integration_id}")
def get_integration(integration_id: str) -> dict:
    result = brain.integration_get(integration_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    return result


# ===========================================================================
# 19. Streaming SSE chat endpoint  (Monster Edition)
# ===========================================================================

import asyncio as _asyncio
import json as _json

from fastapi.responses import StreamingResponse


@app.get("/chat/stream")
async def chat_stream(
    message: str,
    repoId: Optional[str] = None,
    sessionId: Optional[str] = None,
) -> StreamingResponse:
    """Stream a chat response token-by-token via Server-Sent Events.

    Emitted event payloads (each line is: data: <JSON>\\n\\n):
      { type: "plan",      data: { intent, complexity, steps } }
      { type: "context",   files: ["path/a", ...] }
      { type: "reasoning", data: { requirementAnalysis, approach, ... } }
      { type: "agent",     name: "coding_agent" }
      { type: "token",     token: "..." }   ← one per generated chunk
      { type: "done",      response: "<full text>" }
      { type: "error",     error: "..." }
    """

    async def event_generator():  # noqa: C901
        try:
            # ── 1. Plan ───────────────────────────────────────────────────
            plan = brain.planning_engine.create_plan(message)
            yield f"data: {_json.dumps({'type': 'plan', 'data': plan.as_dict()})}\n\n"

            # ── 2. Context ────────────────────────────────────────────────
            if repoId and repoId in brain._indexes:
                idx = brain._indexes[repoId]
                context = brain.context_engine.select(idx, message)
            else:
                from context.context_engine import ContextSelection
                context = ContextSelection(query=message)

            yield f"data: {_json.dumps({'type': 'context', 'files': context.file_paths()})}\n\n"

            # ── 3. Memory block ───────────────────────────────────────────
            try:
                recent = brain.memory_engine.short_term.recent(5)
                memory_block = "\n".join(
                    f"[{t.role}] {t.content[:300]}" for t in recent
                )
            except Exception:
                memory_block = ""

            # ── 4. Reasoning ──────────────────────────────────────────────
            reasoning = brain.reasoning_engine.reason(plan, context, memory_block)
            yield f"data: {_json.dumps({'type': 'reasoning', 'data': reasoning.as_dict()})}\n\n"

            # ── 5. Agent selection ────────────────────────────────────────
            agent_name = (
                plan.steps[-1].agent if plan.steps else "coding_agent"
            )
            agent = brain.agents.get(agent_name) or brain.agents.get("coding_agent")
            yield f"data: {_json.dumps({'type': 'agent', 'name': agent.name})}\n\n"

            # ── 6. Build prompt ───────────────────────────────────────────
            from agents.base import AgentInput
            from providers.ai_provider import GenerationRequest

            agent_input = AgentInput(
                request=message,
                plan=plan,
                reasoning=reasoning,
                context=context,
                memory_block=memory_block,
            )
            prompt = agent.build_prompt(agent_input)

            gen_request = GenerationRequest(
                prompt=prompt,
                system=agent.system_prompt,
                temperature=0.2,
                max_tokens=2048,
            )

            # ── 7. Stream tokens ──────────────────────────────────────────
            full_response = ""
            for token in brain.provider.stream(gen_request):
                full_response += token
                yield f"data: {_json.dumps({'type': 'token', 'token': token})}\n\n"
                await _asyncio.sleep(0)  # yield control to event loop

            # ── 8. Record conversation turn ───────────────────────────────
            try:
                brain.memory_engine.short_term.remember_turn("user", message)
                brain.memory_engine.short_term.remember_turn("assistant", full_response[:600])
            except Exception:
                pass

            yield f"data: {_json.dumps({'type': 'done', 'response': full_response})}\n\n"

        except Exception as exc:
            logger.exception("SSE stream error")
            yield f"data: {_json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/models")
def list_models() -> dict:
    """List available models from the configured Ollama provider."""
    try:
        models = brain.provider.list_models()
        return {"models": models}
    except Exception:
        return {"models": []}
