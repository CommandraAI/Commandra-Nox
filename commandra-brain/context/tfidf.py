"""
Minimal, dependency-free TF-IDF implementation used for semantic-ish code
retrieval. Commandra stays fully offline and does not download embedding
models, so ranking is done with classic term-frequency statistics over
identifier-aware tokenization. This is intentionally simple and fast enough
for large repositories; it is the retrieval layer the Context Engine calls.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


def tokenize(text: str) -> list[str]:
    """Tokenize source/prose text, splitting camelCase and snake_case."""
    raw_tokens = _TOKEN_RE.findall(text)
    tokens: list[str] = []
    for tok in raw_tokens:
        parts = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", tok).split("_")
        tokens.extend(p.lower() for p in parts if p)
        tokens.append(tok.lower())
    return tokens


@dataclass
class Document:
    doc_id: str
    tokens: list[str]


class TfidfIndex:
    """A small in-memory TF-IDF index over a set of documents (chunks)."""

    def __init__(self) -> None:
        self._docs: dict[str, Counter] = {}
        self._doc_len: dict[str, int] = {}
        self._df: Counter = Counter()

    def add_document(self, doc_id: str, text: str) -> None:
        tokens = tokenize(text)
        if not tokens:
            return
        counts = Counter(tokens)
        self._docs[doc_id] = counts
        self._doc_len[doc_id] = len(tokens)
        for term in counts:
            self._df[term] += 1

    def _idf(self, term: str) -> float:
        n = len(self._docs) or 1
        df = self._df.get(term, 0)
        return math.log((n + 1) / (df + 1)) + 1.0

    def query(self, text: str, top_k: int = 10) -> list[tuple[str, float]]:
        query_tokens = Counter(tokenize(text))
        if not query_tokens or not self._docs:
            return []

        scores: dict[str, float] = {}
        for doc_id, counts in self._docs.items():
            score = 0.0
            length = self._doc_len[doc_id] or 1
            for term, q_count in query_tokens.items():
                tf = counts.get(term, 0) / length
                if tf == 0:
                    continue
                score += tf * self._idf(term) * q_count
            if score > 0:
                scores[doc_id] = score

        return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
