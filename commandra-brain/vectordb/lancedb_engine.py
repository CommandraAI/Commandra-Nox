"""
LanceDB Engine -- high-performance local vector database with zero infrastructure.
Data is stored as Lance files on disk (no server required).

Install: pip install lancedb
"""
from __future__ import annotations
import hashlib
import os
from dataclasses import dataclass, field

_LANCEDB_AVAILABLE = False
try:
    import lancedb  # type: ignore
    import pyarrow as pa  # type: ignore
    _LANCEDB_AVAILABLE = True
except ImportError:
    pass


def _simple_embed(text: str, dim: int = 64) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    floats = [(b / 255.0) for b in h]
    while len(floats) < dim:
        floats += floats
    return floats[:dim]


@dataclass
class LanceHit:
    doc_id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"docId": self.doc_id, "text": self.text[:400], "score": round(self.score, 4), "metadata": self.metadata}


@dataclass
class LanceResult:
    query: str
    hits: list[LanceHit]
    table: str
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "hits": [h.as_dict() for h in self.hits],
            "hitCount": len(self.hits),
            "table": self.table,
            "available": self.available,
            "error": self.error,
        }


class LanceDBEngine:
    """Local vector storage via LanceDB (no server required)."""

    VECTOR_DIM = 64

    def __init__(self, path: str = "data/lancedb") -> None:
        self.path = path
        self._db = None
        if _LANCEDB_AVAILABLE:
            try:
                os.makedirs(path, exist_ok=True)
                self._db = lancedb.connect(path)
            except Exception:
                pass

    def available(self) -> bool:
        return _LANCEDB_AVAILABLE and self._db is not None

    def add_documents(self, table_name: str, documents: list[dict]) -> dict:
        if not self.available():
            return {"added": 0, "available": False, "error": "lancedb not installed. Run: pip install lancedb pyarrow"}

        rows = []
        for d in documents:
            rows.append({
                "doc_id": d.get("id", hashlib.md5(d["text"].encode()).hexdigest()),
                "text": d["text"][:2000],
                "vector": _simple_embed(d["text"], self.VECTOR_DIM),
                **{k: str(v)[:200] for k, v in d.get("metadata", {}).items()},
            })

        try:
            if table_name in self._db.table_names():
                tbl = self._db.open_table(table_name)
                tbl.add(rows)
            else:
                self._db.create_table(table_name, data=rows)
            return {"added": len(rows), "available": True}
        except Exception as exc:
            return {"added": 0, "available": True, "error": str(exc)}

    def search(self, table_name: str, query: str, top_k: int = 10) -> LanceResult:
        if not self.available():
            return LanceResult(query=query, hits=[], table=table_name, available=False,
                               error="lancedb not installed")
        try:
            if table_name not in self._db.table_names():
                return LanceResult(query=query, hits=[], table=table_name, available=True,
                                   error=f"Table '{table_name}' not found")
            tbl = self._db.open_table(table_name)
            query_vec = _simple_embed(query, self.VECTOR_DIM)
            results = tbl.search(query_vec).limit(top_k).to_list()
            hits = [
                LanceHit(
                    doc_id=r.get("doc_id", ""),
                    text=r.get("text", ""),
                    score=1.0 - r.get("_distance", 0.0),
                    metadata={k: v for k, v in r.items() if k not in ("doc_id", "text", "vector", "_distance")},
                )
                for r in results
            ]
            return LanceResult(query=query, hits=hits, table=table_name, available=True)
        except Exception as exc:
            return LanceResult(query=query, hits=[], table=table_name, available=True, error=str(exc))

    def list_tables(self) -> list[str]:
        if not self.available():
            return []
        try:
            return self._db.table_names()
        except Exception:
            return []
