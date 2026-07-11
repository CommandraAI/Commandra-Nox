"""
Context Engine -- decides exactly what the Brain sends to the model.

Repositories routinely exceed a model's context window, so this module:
  1. Chunks indexed files into manageable pieces.
  2. Ranks chunks against the current query with TF-IDF retrieval.
  3. Traverses import/dependency edges one hop out from top hits, so
     directly-related files are pulled in even if they don't match the
     query text.
  4. Selects a final set of chunks under a character/token budget.

This is what makes "the Brain decides what files to read before calling
Ollama" true, rather than just dumping the whole repo into the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from context.tfidf import TfidfIndex
from repository.indexer import RepositoryIndex

CHUNK_LINES = 120
CHARS_PER_TOKEN = 4


@dataclass
class ContextChunk:
    path: str
    start_line: int
    end_line: int
    content: str
    score: float = 0.0
    reason: str = "semantic-match"


@dataclass
class ContextSelection:
    query: str
    chunks: list[ContextChunk] = field(default_factory=list)
    files_considered: int = 0
    token_budget: int = 0
    tokens_used: int = 0

    def as_prompt_block(self) -> str:
        parts = []
        for chunk in self.chunks:
            parts.append(
                f"--- {chunk.path} (lines {chunk.start_line}-{chunk.end_line}) ---\n"
                f"{chunk.content}"
            )
        return "\n\n".join(parts)

    def file_paths(self) -> list[str]:
        seen: list[str] = []
        for chunk in self.chunks:
            if chunk.path not in seen:
                seen.append(chunk.path)
        return seen


def _chunk_file(path: str, content: str) -> list[ContextChunk]:
    lines = content.splitlines()
    if not lines:
        return []
    chunks = []
    for start in range(0, len(lines), CHUNK_LINES):
        end = min(start + CHUNK_LINES, len(lines))
        chunks.append(
            ContextChunk(
                path=path,
                start_line=start + 1,
                end_line=end,
                content="\n".join(lines[start:end]),
            )
        )
    return chunks


class ContextEngine:
    """Ranks and selects repository context under a token budget."""

    def build_index(self, index: RepositoryIndex) -> tuple[TfidfIndex, dict[str, ContextChunk]]:
        tfidf = TfidfIndex()
        chunk_map: dict[str, ContextChunk] = {}
        for file in index.files.values():
            for chunk in _chunk_file(file.path, file.content):
                chunk_id = f"{chunk.path}:{chunk.start_line}"
                chunk_map[chunk_id] = chunk
                tfidf.add_document(chunk_id, chunk.content)
        return tfidf, chunk_map

    def select(
        self,
        index: RepositoryIndex,
        query: str,
        max_tokens: int = 3000,
        max_chunks: int = 12,
    ) -> ContextSelection:
        tfidf, chunk_map = self.build_index(index)
        hits = tfidf.query(query, top_k=max_chunks * 2)

        selection = ContextSelection(
            query=query, files_considered=index.file_count, token_budget=max_tokens
        )

        used_paths: set[str] = set()
        budget_chars = max_tokens * CHARS_PER_TOKEN
        used_chars = 0

        for chunk_id, score in hits:
            chunk = chunk_map[chunk_id]
            if used_chars + len(chunk.content) > budget_chars:
                continue
            chunk.score = score
            selection.chunks.append(chunk)
            used_paths.add(chunk.path)
            used_chars += len(chunk.content)
            if len(selection.chunks) >= max_chunks:
                break

        # One-hop dependency traversal: pull in files imported by the
        # top-ranked hits, even if they didn't match the query text.
        for path in list(used_paths):
            file = index.files.get(path)
            if not file:
                continue
            for imported in file.symbols.imports[:5]:
                candidate = self._resolve_import(index, imported)
                if not candidate or candidate in used_paths:
                    continue
                content = index.files[candidate].content
                snippet = "\n".join(content.splitlines()[:CHUNK_LINES])
                if used_chars + len(snippet) > budget_chars:
                    continue
                selection.chunks.append(
                    ContextChunk(
                        path=candidate,
                        start_line=1,
                        end_line=min(CHUNK_LINES, len(content.splitlines())),
                        content=snippet,
                        score=0.0,
                        reason="dependency-of-selected-file",
                    )
                )
                used_paths.add(candidate)
                used_chars += len(snippet)

        selection.tokens_used = used_chars // CHARS_PER_TOKEN
        return selection

    @staticmethod
    def _resolve_import(index: RepositoryIndex, imported: str) -> str | None:
        """Best-effort match of an import string to an indexed file path."""
        normalized = imported.replace(".", "/").lstrip("/")
        for path in index.files:
            stem = path.rsplit(".", 1)[0]
            if stem.endswith(normalized) or path.endswith(imported):
                return path
        return None
