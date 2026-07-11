"""Pydantic request/response models for the Commandra Brain HTTP API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class IndexRepoRequest(BaseModel):
    path: str = Field(..., description="Absolute or workspace-relative path to a local directory to index")


class IndexRepoResponse(BaseModel):
    repoId: str
    root: str
    fileCount: int
    skipped: int
    languages: dict[str, int]
    frameworks: list[str]
    packageManagers: list[dict] = Field(default_factory=list)
    dependencyGraph: dict = Field(default_factory=dict)
    architecture: Optional[dict] = None
    knowledgeGraph: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    repoId: Optional[str] = None
    message: str


class ProviderConfig(BaseModel):
    provider: str
    baseUrl: Optional[str] = None
    model: Optional[str] = None


class GenerateProjectRequest(BaseModel):
    request: str


class ValidateFilesRequest(BaseModel):
    files: dict[str, str]
    expectedPaths: Optional[list[str]] = None


class ScanFilesRequest(BaseModel):
    files: dict[str, str]


class AnalyzeUiRequest(BaseModel):
    path: str
    content: str


class GenerateDocsRequest(BaseModel):
    kind: str = "readme"


class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    topK: int = 10


class SymbolSearchRequest(BaseModel):
    name: str


class ArchitectureSelectRequest(BaseModel):
    request: str
    projectType: Optional[str] = None
    complexity: Optional[str] = None


class PatchPreviewRequest(BaseModel):
    path: str
    original: str
    updated: str


class TaskQueueRequest(BaseModel):
    goal: str
    stages: Optional[list[str]] = None


class PluginInvokeRequest(BaseModel):
    action: str
    args: dict = Field(default_factory=dict)


class CreateSessionRequest(BaseModel):
    repoId: Optional[str] = None


# -- MCP ------------------------------------------------------------------

class MCPConnectRequest(BaseModel):
    command: list[str]
    env: Optional[dict[str, str]] = None
    serverId: Optional[str] = None


class MCPDisconnectRequest(BaseModel):
    serverId: str


class MCPCallToolRequest(BaseModel):
    toolName: str
    arguments: dict = Field(default_factory=dict)
    serverId: Optional[str] = None


class MCPReadResourceRequest(BaseModel):
    uri: str
    serverId: Optional[str] = None


class MCPGetPromptRequest(BaseModel):
    name: str
    arguments: Optional[dict] = None
    serverId: Optional[str] = None


# -- LSP ------------------------------------------------------------------

class LSPPositionRequest(BaseModel):
    filePath: str
    line: int
    character: int


class LSPRenameRequest(BaseModel):
    filePath: str
    line: int
    character: int
    newName: str


class LSPFileRequest(BaseModel):
    filePath: str


# -- RAG ------------------------------------------------------------------

class RAGRetrieveRequest(BaseModel):
    query: str
    maxTokens: int = 4000
    topK: int = 20


# -- Sandbox --------------------------------------------------------------

class SandboxExecuteRequest(BaseModel):
    language: str
    code: str
    timeoutSeconds: float = 10.0
    stdinData: str = ""


# -- Reflection -----------------------------------------------------------

class ReflectRequest(BaseModel):
    response: str
    contextFiles: Optional[list[str]] = None


# -- Benchmarks -----------------------------------------------------------

class BenchmarkRunRequest(BaseModel):
    codeSamples: Optional[dict[str, str]] = None
    indexSummary: Optional[dict] = None


# -- Timeline -------------------------------------------------------------

class TimelineListRequest(BaseModel):
    activeOnly: bool = False


# -- Knowledge Base -------------------------------------------------------

class KBSearchRequest(BaseModel):
    query: str
    topK: int = 5
    category: Optional[str] = None


class KBAddEntryRequest(BaseModel):
    entryId: str
    category: str
    title: str
    summary: str
    detail: str = ""
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)


# -- Preview Engine -------------------------------------------------------

class PreviewGenerateRequest(BaseModel):
    code: str
    language: Optional[str] = None


class PreviewRefreshRequest(BaseModel):
    code: str
    previousHtml: str = ""
    language: Optional[str] = None
