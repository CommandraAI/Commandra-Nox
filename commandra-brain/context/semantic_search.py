"""
Semantic Repository Search -- goes beyond plain TF-IDF keyword matching.

Commandra stays fully local/offline (no downloaded embedding models), so
"embeddings" here are a dependency-free hashed bag-of-words vector (a
standard "feature hashing" trick): tokens are hashed into a fixed-size
float vector, giving a cosine-comparable representation that captures
co-occurring vocabulary without needing a neural encoder. It is not a
learned embedding, but it is meaning-oriented (near-synonymous identifiers
sharing tokens land closer together) and gives the Hybrid/Vector/Semantic
search modes a real, distinct signal from raw TF-IDF term weighting.

Modes:
  - embedding_search / vector_search -- hashed-vector cosine similarity
  - hybrid_search                    -- TF-IDF + vector, blended
  - symbol_search                    -- exact/fuzzy lookup against the
                                         Knowledge Graph's symbol table
  - reference_search                 -- every call site of a symbol
  - semantic_search                  -- convenience: hybrid + symbol boost
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from context.tfidf import TfidfIndex, tokenize

VECTOR_DIM = 256


def _hash_token(token: str) -> int:
    return hash(token) % VECTOR_DIM


def embed(text: str) -> list[float]:
    """Deterministic hashed bag-of-words vector, L2-normalized."""
    vector = [0.0] * VECTOR_DIM
    for token in tokenize(text):
        vector[_hash_token(token)] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class SearchHit:
    doc_id: str
    score: float
    mode: str


@dataclass
class SemanticIndex:
    tfidf: TfidfIndex = field(default_factory=TfidfIndex)
    _vectors: dict[str, list[float]] = field(default_factory=dict)
    _texts: dict[str, str] = field(default_factory=dict)

    def add_document(self, doc_id: str, text: str) -> None:
        self.tfidf.add_document(doc_id, text)
        self._vectors[doc_id] = embed(text)
        self._texts[doc_id] = text

    def remove_document(self, doc_id: str) -> None:
        self._vectors.pop(doc_id, None)
        self._texts.pop(doc_id, None)

    # -- Search modes -----------------------------------------------------

    def vector_search(self, query: str, top_k: int = 10) -> list[SearchHit]:
        query_vec = embed(query)
        scored = [(doc_id, cosine_similarity(query_vec, vec)) for doc_id, vec in self._vectors.items()]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [SearchHit(doc_id, score, "vector") for doc_id, score in scored[:top_k] if score > 0]

    # embedding_search is an alias -- same hashed-vector representation
    embedding_search = vector_search

    def keyword_search(self, query: str, top_k: int = 10) -> list[SearchHit]:
        return [SearchHit(doc_id, score, "tfidf") for doc_id, score in self.tfidf.query(query, top_k)]

    def hybrid_search(self, query: str, top_k: int = 10, tfidf_weight: float = 0.6) -> list[SearchHit]:
        tfidf_hits = {h.doc_id: h.score for h in self.keyword_search(query, top_k=top_k * 3)}
        vector_hits = {h.doc_id: h.score for h in self.vector_search(query, top_k=top_k * 3)}
        all_ids = set(tfidf_hits) | set(vector_hits)

        def _normalize(hits: dict[str, float]) -> dict[str, float]:
            max_score = max(hits.values(), default=1.0) or 1.0
            return {k: v / max_score for k, v in hits.items()}

        tfidf_norm, vector_norm = _normalize(tfidf_hits), _normalize(vector_hits)
        blended = [
            (doc_id, tfidf_weight * tfidf_norm.get(doc_id, 0.0) + (1 - tfidf_weight) * vector_norm.get(doc_id, 0.0))
            for doc_id in all_ids
        ]
        blended.sort(key=lambda pair: pair[1], reverse=True)
        return [SearchHit(doc_id, score, "hybrid") for doc_id, score in blended[:top_k] if score > 0]

    semantic_search = hybrid_search


def symbol_search(knowledge_graph, name: str, fuzzy: bool = True) -> list[dict]:
    """Exact match first; falls back to substring/case-insensitive fuzzy
    matching against the Knowledge Graph's symbol table."""
    exact = knowledge_graph.find_symbol(name)
    if exact:
        return [{"path": r.path, "name": r.node.name, "kind": r.node.kind, "line": r.node.line, "match": "exact"} for r in exact]
    if not fuzzy:
        return []
    lowered = name.lower()
    hits = []
    for symbol_name, refs in knowledge_graph.symbols_by_name.items():
        if lowered in symbol_name.lower():
            hits.extend({"path": r.path, "name": r.node.name, "kind": r.node.kind, "line": r.node.line, "match": "fuzzy"} for r in refs)
    return hits


def reference_search(knowledge_graph, name: str) -> list[dict]:
    return knowledge_graph.find_references(name)
