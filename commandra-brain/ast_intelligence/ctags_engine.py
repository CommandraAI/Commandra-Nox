"""
Universal Ctags Engine -- symbol indexing for functions, classes, variables,
interfaces, enums, and repository navigation.

Wraps the `ctags` CLI (universal-ctags preferred, exuberant-ctags fallback).
Install: apt install universal-ctags  OR  brew install universal-ctags
"""
from __future__ import annotations
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class CtagsSymbol:
    name: str
    file: str
    line: int
    kind: str      # f=function, c=class, v=variable, m=method, i=interface, g=enum
    language: str
    signature: str = ""
    scope: str = ""
    access: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "kind": self.kind,
            "language": self.language,
            "signature": self.signature,
            "scope": self.scope,
            "access": self.access,
        }


@dataclass
class CtagsResult:
    root: str
    symbols: list[CtagsSymbol]
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "root": self.root,
            "symbols": [s.as_dict() for s in self.symbols],
            "symbolCount": len(self.symbols),
            "available": self.available,
            "error": self.error,
        }


_KIND_NAMES = {
    "f": "function", "c": "class", "m": "method", "v": "variable",
    "i": "interface", "g": "enum", "s": "struct", "t": "type",
    "d": "define", "e": "enum-member", "p": "prototype", "x": "extern",
}


class CtagsEngine:
    """Symbol extraction via universal-ctags."""

    BINARY = "ctags"

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.BINARY) is not None

    def index_repository(self, root: str, languages: list[str] | None = None, max_symbols: int = 10000) -> CtagsResult:
        if not self.available():
            return CtagsResult(root=root, symbols=[], available=False,
                               error="ctags not installed. Run: apt install universal-ctags")

        lang_flag = []
        if languages:
            lang_list = ",".join(l.capitalize() for l in languages)
            lang_flag = [f"--languages={lang_list}"]

        try:
            cmd = [
                self.BINARY,
                "--output-format=json",
                "--fields=+nisSaf",
                "-R",
                *lang_flag,
                "--extras=+q",
                "-f", "-",  # stdout
                root,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0 and not proc.stdout:
                return CtagsResult(root=root, symbols=[], available=True, error=proc.stderr[:500])

            symbols: list[CtagsSymbol] = []
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    kind_raw = obj.get("kind", "v")
                    symbols.append(CtagsSymbol(
                        name=obj.get("name", ""),
                        file=obj.get("path", ""),
                        line=obj.get("line", 0),
                        kind=_KIND_NAMES.get(kind_raw[0] if kind_raw else "v", kind_raw),
                        language=obj.get("language", ""),
                        signature=obj.get("signature", ""),
                        scope=obj.get("scope", ""),
                        access=obj.get("access", ""),
                    ))
                    if len(symbols) >= max_symbols:
                        break
                except (json.JSONDecodeError, KeyError):
                    continue

            return CtagsResult(root=root, symbols=symbols, available=True)
        except subprocess.TimeoutExpired:
            return CtagsResult(root=root, symbols=[], available=True, error="ctags timed out")
        except Exception as exc:
            return CtagsResult(root=root, symbols=[], available=True, error=str(exc))

    def search_symbol(self, root: str, name: str) -> list[CtagsSymbol]:
        result = self.index_repository(root)
        name_lower = name.lower()
        return [s for s in result.symbols if name_lower in s.name.lower()]
