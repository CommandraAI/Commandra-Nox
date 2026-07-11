"""
SearXNG Client -- privacy-focused internet search for documentation,
GitHub, Stack Overflow and engineering references.

Connects to a locally-running SearXNG instance (default: http://localhost:8888).
Self-host: docker run -d -p 8888:8080 searxng/searxng
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    engine: str
    score: float = 0.0

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "engine": self.engine,
            "score": round(self.score, 4),
        }


@dataclass
class SearXNGResponse:
    query: str
    results: list[SearchResult]
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.as_dict() for r in self.results],
            "resultCount": len(self.results),
            "available": self.available,
            "error": self.error,
        }


class SearXNGClient:
    """
    Queries a SearXNG instance for documentation and code search.
    Falls back to returning an informative error when unavailable.
    """

    def __init__(self, base_url: str = "http://localhost:8888") -> None:
        self.base_url = base_url.rstrip("/")

    def _is_available(self) -> bool:
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/healthz", timeout=2.0)
            return r.status_code < 500
        except Exception:
            return False

    def search(
        self,
        query: str,
        categories: list[str] | None = None,
        engines: list[str] | None = None,
        top_k: int = 10,
    ) -> SearXNGResponse:
        if not self._is_available():
            return SearXNGResponse(
                query=query, results=[], available=False,
                error=f"SearXNG not running at {self.base_url}. "
                      "Self-host: docker run -d -p 8888:8080 searxng/searxng",
            )
        try:
            import httpx
            params = {
                "q": query,
                "format": "json",
                "pageno": 1,
            }
            if categories:
                params["categories"] = ",".join(categories)
            if engines:
                params["engines"] = ",".join(engines)

            resp = httpx.get(f"{self.base_url}/search", params=params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", "")[:500],
                    engine=r.get("engine", ""),
                    score=r.get("score", 0.0),
                )
                for r in data.get("results", [])[:top_k]
            ]
            return SearXNGResponse(query=query, results=results, available=True)
        except Exception as exc:
            return SearXNGResponse(query=query, results=[], available=True, error=str(exc))

    def search_docs(self, query: str) -> SearXNGResponse:
        return self.search(query, categories=["it"], engines=["github", "stackoverflow"])

    def search_github(self, query: str) -> SearXNGResponse:
        return self.search(f"site:github.com {query}", engines=["duckduckgo", "bing"])
