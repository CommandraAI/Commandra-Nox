"""
Qdrant Engine -- high-performance local vector database via the Qdrant HTTP API.

Requires a running Qdrant server (default: http://localhost:6333).
Self-host: docker run -p 6333:6333 qdrant/qdrant
Or pip install qdrant-client for Python client.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field

_QDRANT_AVAILABLE = False
try:
    from qdrant_client import QdrantClient  # type: ignore
    from qdrant_client.models import Distance, VectorParams, PointStruct  # type: ignore
    _QDRANT_AVAILABLE = True
except ImportError:
    pass


@dataclass
class QdrantHit:
    doc_id: str
    score: float
    payload: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"docId": self.doc_id, "score": round(self.score, 4), "payload": self.payload}


@dataclass
class QdrantResult:
    query: str
    hits: list[QdrantHit]
    collection: str
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "hits": [h.as_dict() for h in self.hits],
            "hitCount": len(self.hits),
            "collection": self.collection,
            "available": self.available,
            "error": self.error,
        }


def _simple_embed(text: str, dim: int = 128) -> list[float]:
    """Deterministic, dimension-fixed embedding from text (no ML model needed for testing)."""
    import math
    h = hashlib.sha256(text.encode()).digest()
    floats = [((b / 255.0) * 2 - 1) for b in h]
    # Pad or truncate to dim
    while len(floats) < dim:
        floats += floats
    return floats[:dim]


class QdrantEngine:
    """
    Vector storage and retrieval via Qdrant.
    Uses a lightweight hash-based embedding when no ML model is installed.
    For production, replace _simple_embed with sentence-transformers or similar.
    """

    VECTOR_DIM = 128

    def __init__(self, host: str = "localhost", port: int = 6333) -> None:
        self.host = host
        self.port = port
        self._client = None
        if _QDRANT_AVAILABLE:
            try:
                self._client = QdrantClient(host=host, port=port, timeout=5.0)
            except Exception:
                pass

    def available(self) -> bool:
        if not _QDRANT_AVAILABLE or self._client is None:
            return False
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False

    def ensure_collection(self, name: str) -> bool:
        if not self.available():
            return False
        try:
            existing = [c.name for c in self._client.get_collections().collections]
            if name not in existing:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=self.VECTOR_DIM, distance=Distance.COSINE),
                )
            return True
        except Exception:
            return False

    def upsert(self, collection: str, documents: list[dict]) -> dict:
        """documents: list of {id, text, payload}"""
        if not self.available():
            return {"upserted": 0, "available": False, "error": "Qdrant not available"}
        self.ensure_collection(collection)
        try:
            points = [
                PointStruct(
                    id=abs(hash(d.get("id", d["text"][:50]))) % (2**63),
                    vector=_simple_embed(d["text"], self.VECTOR_DIM),
                    payload={**d.get("payload", {}), "text": d["text"], "doc_id": d.get("id", "")},
                )
                for d in documents
            ]
            self._client.upsert(collection_name=collection, points=points)
            return {"upserted": len(points), "available": True}
        except Exception as exc:
            return {"upserted": 0, "available": True, "error": str(exc)}

    def search(self, collection: str, query: str, top_k: int = 10) -> QdrantResult:
        if not self.available():
            return QdrantResult(query=query, hits=[], collection=collection, available=False,
                                error="Qdrant server not running at "
                                      f"{self.host}:{self.port}. Run: docker run -p 6333:6333 qdrant/qdrant")
        try:
            self.ensure_collection(collection)
            query_vec = _simple_embed(query, self.VECTOR_DIM)
            results = self._client.search(collection_name=collection, query_vector=query_vec, limit=top_k)
            hits = [
                QdrantHit(doc_id=str(r.payload.get("doc_id", r.id)), score=r.score, payload=r.payload)
                for r in results
            ]
            return QdrantResult(query=query, hits=hits, collection=collection, available=True)
        except Exception as exc:
            return QdrantResult(query=query, hits=[], collection=collection, available=True, error=str(exc))
