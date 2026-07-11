"""
Firecrawl Client -- crawl documentation websites and convert them to
AI-friendly Markdown for the Brain's knowledge pipeline.

Uses firecrawl-py (pip install firecrawl-py) or the self-hosted Firecrawl API.
Without an API key, falls back to httpx + basic HTML→Markdown extraction.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

_FIRECRAWL_AVAILABLE = False
try:
    from firecrawl import FirecrawlApp  # type: ignore
    _FIRECRAWL_AVAILABLE = True
except ImportError:
    pass


@dataclass
class CrawledPage:
    url: str
    title: str
    markdown: str
    links: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "markdown": self.markdown[:8000],
            "links": self.links[:50],
            "metadata": self.metadata,
        }


@dataclass
class CrawlResult:
    url: str
    pages: list[CrawledPage]
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "pages": [p.as_dict() for p in self.pages],
            "pageCount": len(self.pages),
            "available": self.available,
            "error": self.error,
        }


def _html_to_markdown(html: str) -> str:
    """Minimal HTML→Markdown conversion (no external dependency)."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<h([1-6])[^>]*>(.*?)</h\1>", lambda m: "#" * int(m.group(1)) + " " + m.group(2) + "\n", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<(b|strong)[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<(i|em)[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<pre[^>]*>(.*?)</pre>", r"```\n\1\n```", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", r"[\2](\1)", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class FirecrawlClient:
    """Crawls documentation URLs and converts them to clean Markdown."""

    def __init__(self, api_key: str | None = None, base_url: str = "http://localhost:3002") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self._app = None
        if _FIRECRAWL_AVAILABLE and api_key:
            try:
                self._app = FirecrawlApp(api_key=api_key)
            except Exception:
                pass

    def scrape(self, url: str) -> CrawledPage:
        if self._app:
            try:
                result = self._app.scrape_url(url, params={"formats": ["markdown"]})
                return CrawledPage(
                    url=url,
                    title=result.get("metadata", {}).get("title", ""),
                    markdown=result.get("markdown", ""),
                    links=result.get("links", []),
                    metadata=result.get("metadata", {}),
                )
            except Exception as exc:
                pass  # fall through to httpx fallback

        try:
            import httpx
            resp = httpx.get(url, timeout=15.0, follow_redirects=True,
                             headers={"User-Agent": "CommandraBot/0.2 (documentation-scraper)"})
            resp.raise_for_status()
            title_m = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.I | re.DOTALL)
            title = title_m.group(1).strip() if title_m else url
            markdown = _html_to_markdown(resp.text)
            links = re.findall(r'href=[\'"]([^\'"#][^\'"]*)[\'"]', resp.text)
            return CrawledPage(url=url, title=title, markdown=markdown, links=links[:50])
        except Exception as exc:
            return CrawledPage(url=url, title="", markdown=f"Failed to fetch: {exc}", links=[])

    def crawl(self, url: str, max_pages: int = 10) -> CrawlResult:
        if self._app:
            try:
                result = self._app.crawl_url(url, params={"limit": max_pages, "scrapeOptions": {"formats": ["markdown"]}})
                pages = [
                    CrawledPage(
                        url=p.get("url", ""),
                        title=p.get("metadata", {}).get("title", ""),
                        markdown=p.get("markdown", ""),
                        links=p.get("links", []),
                    )
                    for p in result.get("data", [])
                ]
                return CrawlResult(url=url, pages=pages, available=True)
            except Exception as exc:
                return CrawlResult(url=url, pages=[self.scrape(url)], available=True, error=str(exc))

        # Fallback: scrape only the given URL
        page = self.scrape(url)
        return CrawlResult(url=url, pages=[page], available=_FIRECRAWL_AVAILABLE or True)
