"""
MarkItDown Engine -- convert PDF, DOCX, PPTX, HTML, and other documents
to Markdown for repository knowledge ingestion.

Uses microsoft/markitdown (pip install markitdown).
Falls back to plain text extraction for common formats.
"""
from __future__ import annotations
import os
from dataclasses import dataclass

_MARKITDOWN_AVAILABLE = False
try:
    from markitdown import MarkItDown  # type: ignore
    _MARKITDOWN_AVAILABLE = True
except ImportError:
    pass


@dataclass
class ConvertResult:
    source_path: str
    markdown: str
    title: str
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "sourcePath": self.source_path,
            "markdown": self.markdown[:20000],
            "title": self.title,
            "available": self.available,
            "error": self.error,
            "wordCount": len(self.markdown.split()),
        }


class MarkItDownEngine:
    """Convert documents to Markdown for AI knowledge ingestion."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".txt", ".md", ".rst"}

    def __init__(self) -> None:
        self._converter = MarkItDown() if _MARKITDOWN_AVAILABLE else None

    @staticmethod
    def available() -> bool:
        return _MARKITDOWN_AVAILABLE

    def convert(self, file_path: str) -> ConvertResult:
        ext = os.path.splitext(file_path)[1].lower()
        title = os.path.basename(file_path)

        if not _MARKITDOWN_AVAILABLE:
            # Fallback: read as plain text for txt/md/rst
            if ext in (".txt", ".md", ".rst"):
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                    return ConvertResult(source_path=file_path, markdown=content, title=title, available=False)
                except Exception as exc:
                    return ConvertResult(source_path=file_path, markdown="", title=title, available=False, error=str(exc))
            return ConvertResult(
                source_path=file_path, markdown="", title=title, available=False,
                error="markitdown not installed. Run: pip install markitdown"
            )

        try:
            result = self._converter.convert(file_path)
            return ConvertResult(
                source_path=file_path,
                markdown=result.text_content or "",
                title=result.title or title,
                available=True,
            )
        except Exception as exc:
            return ConvertResult(source_path=file_path, markdown="", title=title, available=True, error=str(exc))

    def convert_url(self, url: str) -> ConvertResult:
        if not _MARKITDOWN_AVAILABLE:
            return ConvertResult(source_path=url, markdown="", title=url, available=False,
                                 error="markitdown not installed")
        try:
            result = self._converter.convert_url(url)
            return ConvertResult(source_path=url, markdown=result.text_content or "",
                                 title=result.title or url, available=True)
        except Exception as exc:
            return ConvertResult(source_path=url, markdown="", title=url, available=True, error=str(exc))
