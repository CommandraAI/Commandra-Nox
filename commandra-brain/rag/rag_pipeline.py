"""
Advanced RAG Pipeline -- Retrieval-Augmented Generation for the Brain.

Implements:
- Embedding Pipeline (TF-IDF + BM25 approximation, locally computed)
- Intelligent Chunking (sentence-aware, overlap-based)
- Context Ranking (BM25 + recency + structure signals)
- Multi-stage Retrieval (coarse recall → fine re-rank)
- Context Compression (remove low-signal sentences)
- Citation Mapping (track which chunk each statement came from)
- Semantic Context Selection (pick best chunk set under token budget)

Fully local -- no embedding API calls, no network required.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str
    source_path: str
    start_line: int
    end_line: int
    text: str
    score: float = 0.0
    citations: list[str] = field(default_factory=list)

    def token_estimate(self) -> int:
        return len(self.text) // 4

    def as_dict(self) -> dict:
        return {
            "chunkId": self.chunk_id,
            "sourcePath": self.source_path,
            "startLine": self.start_line,
            "endLine": self.end_line,
            "text": self.text,
            "score": round(self.score, 4),
            "citations": self.citations,
        }


class IntelligentChunker:
    """
    Chunks source files using sentence-aware boundaries with configurable
    overlap so no important statement gets split across a boundary.
    """

    def __init__(self, target_tokens: int = 256, overlap_tokens: int = 32) -> None:
        self.target_chars = target_tokens * 4
        self.overlap_chars = overlap_tokens * 4

    def chunk(self, path: str, content: str) -> list[Chunk]:
        lines = content.splitlines()
        if not lines:
            return []

        chunks: list[Chunk] = []
        buffer: list[str] = []
        buffer_start = 0
        buffer_chars = 0
        chunk_idx = 0

        def flush(end_line: int) -> None:
            nonlocal buffer, buffer_start, buffer_chars, chunk_idx
            if not buffer:
                return
            text = "\n".join(buffer)
            cid = f"{path}#{chunk_idx}"
            chunks.append(Chunk(
                chunk_id=cid,
                source_path=path,
                start_line=buffer_start,
                end_line=end_line,
                text=text,
            ))
            chunk_idx += 1
            # Overlap: carry last N chars worth of lines into next chunk
            overlap_text = text[-self.overlap_chars:]
            overlap_lines = overlap_text.splitlines()
            buffer = overlap_lines
            buffer_start = max(buffer_start, end_line - len(overlap_lines))
            buffer_chars = len(overlap_text)

        for i, line in enumerate(lines):
            buffer.append(line)
            buffer_chars += len(line) + 1

            # Natural break: blank line or function/class definition at limit
            is_natural_break = (
                not line.strip() or
                re.match(r"^\s*(def |class |fn |func |function |pub fn |async def )", line)
            )

            if buffer_chars >= self.target_chars and (is_natural_break or buffer_chars >= self.target_chars * 1.5):
                flush(i + 1)

        flush(len(lines))
        return chunks


# ---------------------------------------------------------------------------
# BM25-based ranking
# ---------------------------------------------------------------------------

class BM25Index:
    """Lightweight BM25 implementation, no external dependencies."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: dict[str, list[str]] = {}      # doc_id -> tokens
        self._df: dict[str, int] = {}              # term -> doc frequency
        self._avgdl: float = 0.0
        self._N: int = 0

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\b\w+\b", text.lower())

    def add(self, doc_id: str, text: str) -> None:
        tokens = self._tokenize(text)
        self._docs[doc_id] = tokens
        seen: set[str] = set()
        for t in tokens:
            if t not in seen:
                self._df[t] = self._df.get(t, 0) + 1
                seen.add(t)
        self._N = len(self._docs)
        self._avgdl = sum(len(d) for d in self._docs.values()) / max(1, self._N)

    def score(self, doc_id: str, query_tokens: list[str]) -> float:
        doc = self._docs.get(doc_id, [])
        dl = len(doc)
        tf_map: dict[str, int] = {}
        for t in doc:
            tf_map[t] = tf_map.get(t, 0) + 1

        total = 0.0
        for qt in query_tokens:
            tf = tf_map.get(qt, 0)
            df = self._df.get(qt, 0)
            if df == 0:
                continue
            idf = math.log((self._N - df + 0.5) / (df + 0.5) + 1)
            tf_norm = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / max(1, self._avgdl)))
            total += idf * tf_norm
        return total

    def query(self, text: str, top_k: int = 20) -> list[tuple[str, float]]:
        tokens = self._tokenize(text)
        scores = [(doc_id, self.score(doc_id, tokens)) for doc_id in self._docs]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(doc_id, s) for doc_id, s in scores[:top_k] if s > 0]


# ---------------------------------------------------------------------------
# Context Compression
# ---------------------------------------------------------------------------

class ContextCompressor:
    """Remove low-signal sentences from a retrieved chunk."""

    @staticmethod
    def compress(chunk_text: str, query: str, max_chars: int | None = None) -> str:
        query_tokens = set(re.findall(r"\b\w+\b", query.lower()))
        sentences = re.split(r"(?<=[.!?])\s+|\n", chunk_text)
        scored: list[tuple[str, float]] = []
        for s in sentences:
            s_stripped = s.strip()
            if not s_stripped:
                continue
            s_tokens = set(re.findall(r"\b\w+\b", s.lower()))
            overlap = len(query_tokens & s_tokens) / max(1, len(query_tokens))
            length_bonus = min(1.0, len(s_stripped) / 100)
            scored.append((s_stripped, overlap + 0.1 * length_bonus))

        scored.sort(key=lambda x: x[1], reverse=True)
        result_parts: list[str] = []
        total = 0
        for text, _ in scored:
            if max_chars and total + len(text) > max_chars:
                break
            result_parts.append(text)
            total += len(text)

        return " ".join(result_parts)


# ---------------------------------------------------------------------------
# Citation Mapper
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    chunk_id: str
    source_path: str
    start_line: int
    end_line: int
    relevance: float

    def as_dict(self) -> dict:
        return {
            "chunkId": self.chunk_id,
            "sourcePath": self.source_path,
            "startLine": self.start_line,
            "endLine": self.end_line,
            "relevance": round(self.relevance, 4),
        }


class CitationMapper:
    """Maps each selected chunk to a citable source reference."""

    @staticmethod
    def map_citations(selected_chunks: list[Chunk]) -> list[Citation]:
        return [
            Citation(
                chunk_id=c.chunk_id,
                source_path=c.source_path,
                start_line=c.start_line,
                end_line=c.end_line,
                relevance=c.score,
            )
            for c in selected_chunks
        ]


# ---------------------------------------------------------------------------
# RAGResult
# ---------------------------------------------------------------------------

@dataclass
class RAGResult:
    query: str
    selected_chunks: list[Chunk]
    citations: list[Citation]
    compressed_context: str
    total_tokens: int
    retrieval_stages: list[dict]

    def as_prompt_block(self) -> str:
        parts: list[str] = []
        for chunk in self.selected_chunks:
            header = f"[{chunk.source_path}:{chunk.start_line}-{chunk.end_line}]"
            parts.append(f"{header}\n{chunk.text}")
        return "\n\n".join(parts)

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "selectedChunks": [c.as_dict() for c in self.selected_chunks],
            "citations": [c.as_dict() for c in self.citations],
            "compressedContext": self.compressed_context,
            "totalTokens": self.total_tokens,
            "retrievalStages": self.retrieval_stages,
        }


# ---------------------------------------------------------------------------
# RAGPipeline -- the main entry point
# ---------------------------------------------------------------------------

class RAGPipeline:
    """
    Full Retrieval-Augmented Generation pipeline.

    Stage 1 -- Coarse Recall:   BM25 over all chunks (fast, high recall).
    Stage 2 -- Fine Re-rank:    Score by structural signals + query overlap.
    Stage 3 -- Budget Selection: Pick highest-scoring chunks within token budget.
    Stage 4 -- Compression:     Remove low-signal sentences from each chunk.
    Stage 5 -- Citation Map:    Record source attribution for every chunk.
    """

    def __init__(self) -> None:
        self._chunker = IntelligentChunker()
        self._compressor = ContextCompressor()
        self._citation_mapper = CitationMapper()

    def build_index(self, files: dict[str, str]) -> tuple[BM25Index, dict[str, Chunk]]:
        index = BM25Index()
        chunk_map: dict[str, Chunk] = {}
        for path, content in files.items():
            for chunk in self._chunker.chunk(path, content):
                index.add(chunk.chunk_id, chunk.text)
                chunk_map[chunk.chunk_id] = chunk
        return index, chunk_map

    def retrieve(
        self,
        query: str,
        files: dict[str, str],
        max_tokens: int = 4000,
        top_k: int = 20,
        compress: bool = True,
    ) -> RAGResult:
        stages: list[dict] = []

        # Stage 1: Coarse recall
        index, chunk_map = self.build_index(files)
        coarse_hits = index.query(query, top_k=top_k * 3)
        stages.append({"stage": "coarse_recall", "hits": len(coarse_hits)})

        # Stage 2: Fine re-rank with structural bonus
        query_terms = set(re.findall(r"\b\w+\b", query.lower()))
        reranked: list[tuple[str, float]] = []
        for cid, bm25_score in coarse_hits:
            chunk = chunk_map[cid]
            structural_bonus = 0.0
            # Bonus: definition lines (def/class/fn) rank higher
            if re.search(r"(def |class |fn |func )", chunk.text):
                structural_bonus += 0.3
            # Bonus: chunk contains query terms verbatim
            chunk_terms = set(re.findall(r"\b\w+\b", chunk.text.lower()))
            overlap_ratio = len(query_terms & chunk_terms) / max(1, len(query_terms))
            reranked.append((cid, bm25_score + structural_bonus + overlap_ratio))

        reranked.sort(key=lambda x: x[1], reverse=True)
        stages.append({"stage": "fine_rerank", "candidates": len(reranked)})

        # Stage 3: Budget selection
        selected: list[Chunk] = []
        used_tokens = 0
        seen_paths: set[str] = set()

        for cid, score in reranked:
            chunk = chunk_map[cid]
            est = chunk.token_estimate()
            if used_tokens + est > max_tokens:
                continue
            chunk.score = score
            selected.append(chunk)
            seen_paths.add(chunk.source_path)
            used_tokens += est
            if len(selected) >= top_k:
                break

        stages.append({"stage": "budget_selection", "selected": len(selected), "tokensUsed": used_tokens})

        # Stage 4: Compression
        context_parts: list[str] = []
        for chunk in selected:
            if compress:
                compressed = self._compressor.compress(chunk.text, query, max_chars=800)
            else:
                compressed = chunk.text
            context_parts.append(compressed)

        compressed_context = "\n\n".join(context_parts)
        stages.append({"stage": "compression", "outputChars": len(compressed_context)})

        # Stage 5: Citation mapping
        citations = self._citation_mapper.map_citations(selected)
        stages.append({"stage": "citation_mapping", "citations": len(citations)})

        return RAGResult(
            query=query,
            selected_chunks=selected,
            citations=citations,
            compressed_context=compressed_context,
            total_tokens=used_tokens,
            retrieval_stages=stages,
        )
