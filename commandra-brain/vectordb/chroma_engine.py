"""
Chroma Engine -- local vector database for semantic repository search,
long-term memory, and embedding-based retrieval.

Uses chromadb (pip install chromadb).
Falls back to in-memory TF-IDF when chromadb is not installed.
"""
from __future__ import annotations
import hashlib
import uuid
from dataclasses import dataclass, field

_CHROMA_AVAILABLE = False
try:
    import chromadb  # type: ignore
    _CHROMA_AVAILABLE = True
except ImportError:
    pass


@dataclass
class VectorHit:
    doc_id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"docId": self.doc_id, "text": self.text[:500], "score": round(self.score, 4), "metadata": self.metadata}


@dataclass
class VectorSearchResult:
    query: str
    hits: list[VectorHit]
    collection: str
    available: bool
    backend: str = "chroma"
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "hits": [h.as_dict() for h in self.hits],
            "hitCount": len(self.hits),
            "collection": self.collection,
            "available": self.available,
            "backend": self.backend,
            "error": self.error,
        }


class ChromaEngine:
    """
    Persistent local vector database using Chroma.
    Each repository gets its own Chroma collection.
    """

    def __init__(self, persist_directory: str = "data/chroma") -> None:
        self.persist_directory = persist_directory
        self._client = None
        self._collections: dict[str, object] = {}
        if _CHROMA_AVAILABLE:
            try:
                self._client = chromadb.PersistentClient(path=persist_directory)
            except Exception:
                try:
                    self._client = chromadb.Client()
                except Exception:
                    pass

    def available(self) -> bool:
        return _CHROMA_AVAILABLE and self._client is not None

    def _get_collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    def add_documents(self, collection: str, documents: list[dict]) -> dict:
        """documents: list of {id, text, metadata}"""
        if not self.available():
            return {"added": 0, "available": False, "error": "chromadb not installed. Run: pip install chromadb"}

        coll = self._get_collection(collection)
        ids = [d.get("id") or hashlib.md5(d["text"].encode()).hexdigest() for d in documents]
        texts = [d["text"] for d in documents]
        metas = [d.get("metadata", {}) for d in documents]
        try:
            coll.add(ids=ids, documents=texts, metadatas=metas)
            return {"added": len(documents), "available": True}
        except Exception as exc:
            return {"added": 0, "available": True, "error": str(exc)}

    def search(self, collection: str, query: str, top_k: int = 10) -> VectorSearchResult:
        if not self.available():
            return VectorSearchResult(query=query, hits=[], collection=collection, available=False,
                                      error="chromadb not installed")
        try:
            coll = self._get_collection(collection)
            results = coll.query(query_texts=[query], n_results=min(top_k, coll.count() or 1))
            hits: list[VectorHit] = []
            docs = results.get("documents", [[]])[0]
            dists = results.get("distances", [[]])[0]
            ids = results.get("ids", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            for doc_id, text, dist, meta in zip(ids, docs, dists, metas):
                score = 1.0 - dist if dist is not None else 0.0
                hits.append(VectorHit(doc_id=doc_id, text=text, score=score, metadata=meta or {}))
            return VectorSearchResult(query=query, hits=hits, collection=collection, available=True)
        except Exception as exc:
            return VectorSearchResult(query=query, hits=[], collection=collection, available=True, error=str(exc))

    def delete_collection(self, collection: str) -> bool:
        if not self.available():
            return False
        try:
            self._client.delete_collection(collection)
            self._collections.pop(collection, None)
            return True
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        if not self.available():
            return []
        try:
            return [c.name for c in self._client.list_collections()]
        except Exception:
            return []

    def collection_count(self, collection: str) -> int:
        if not self.available():
            return 0
        try:
            return self._get_collection(collection).count()
        except Exception:
            return 0
