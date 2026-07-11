"""
LSP Server Adapters -- connects the Brain to real Language Server Protocol
implementations for Pyright (Python), TypeScript Language Server, rust-analyzer,
and clangd.

Each adapter manages a persistent language server process, speaks the LSP
JSON-RPC protocol, and exposes the same interface as the Brain's built-in
LSPEngine -- so callers never need to know which backend is active.

Installation:
  Pyright:               pip install pyright   OR  npm install -g pyright
  TypeScript LS:         npm install -g typescript-language-server typescript
  rust-analyzer:         rustup component add rust-analyzer
  clangd:                apt install clangd  OR  brew install llvm
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("commandra.lsp.adapters")


# ---------------------------------------------------------------------------
# LSP JSON-RPC transport (shared with mcp_client pattern)
# ---------------------------------------------------------------------------

class _LSPTransport:
    """stdin/stdout JSON-RPC transport for LSP servers."""

    def __init__(self, cmd: list[str], env: dict | None = None) -> None:
        merged = {**os.environ, **(env or {})}
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged,
        )
        self._lock = threading.Lock()
        self._pending: dict[int, dict | None] = {}
        self._seq = 0
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self._proc.stdout
        while True:
            try:
                header = b""
                while not header.endswith(b"\r\n\r\n"):
                    ch = self._proc.stdout.read(1)
                    if not ch:
                        return
                    header += ch
                content_length = 0
                for line in header.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        content_length = int(line.split(b":")[1].strip())
                if content_length == 0:
                    continue
                body = self._proc.stdout.read(content_length)
                msg = json.loads(body)
                msg_id = msg.get("id")
                if msg_id is not None and msg_id in self._pending:
                    with self._lock:
                        self._pending[msg_id] = msg
            except Exception:
                return

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        with self._lock:
            assert self._proc.stdin
            self._proc.stdin.write(header + body)
            self._proc.stdin.flush()

    def request(self, method: str, params: Any, timeout: float = 10.0) -> dict:
        with self._lock:
            self._seq += 1
            msg_id = self._seq
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        with self._lock:
            self._pending[msg_id] = None
        self._send(payload)
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                r = self._pending.get(msg_id)
            if r is not None:
                with self._lock:
                    del self._pending[msg_id]
                return r
            time.sleep(0.02)
        with self._lock:
            self._pending.pop(msg_id, None)
        raise TimeoutError(f"LSP request '{method}' timed out")

    def notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def close(self) -> None:
        try:
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:
            self._proc.kill()


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------

class _BaseAdapter:
    NAME = "base"
    BINARY: str | None = None
    COMMAND: list[str] = []

    def __init__(self) -> None:
        self._transport: _LSPTransport | None = None
        self._initialized = False
        self._workspace_uri: str | None = None

    @classmethod
    def available(cls) -> bool:
        if cls.BINARY:
            return shutil.which(cls.BINARY) is not None
        if cls.COMMAND:
            return shutil.which(cls.COMMAND[0]) is not None
        return False

    def start(self, workspace_root: str) -> bool:
        if self._initialized:
            return True
        cmd = self.COMMAND or ([self.BINARY] if self.BINARY else [])
        if not cmd or not shutil.which(cmd[0]):
            return False
        try:
            self._workspace_uri = f"file://{os.path.abspath(workspace_root)}"
            self._transport = _LSPTransport(cmd)
            resp = self._transport.request("initialize", {
                "processId": os.getpid(),
                "rootUri": self._workspace_uri,
                "capabilities": {
                    "textDocument": {
                        "hover": {"contentFormat": ["markdown", "plaintext"]},
                        "definition": {},
                        "references": {},
                        "documentSymbol": {},
                        "publishDiagnostics": {},
                        "completion": {},
                        "signatureHelp": {},
                        "rename": {},
                        "codeAction": {},
                        "semanticTokens": {"requests": {"full": True}},
                    },
                    "workspace": {"symbol": {}},
                },
                "initializationOptions": {},
            }, timeout=15.0)
            if "error" in resp:
                logger.warning("%s init error: %s", self.NAME, resp["error"])
                return False
            self._transport.notify("initialized", {})
            self._initialized = True
            logger.info("%s language server started", self.NAME)
            return True
        except Exception as exc:
            logger.warning("Failed to start %s: %s", self.NAME, exc)
            return False

    def _uri(self, path: str) -> str:
        return f"file://{os.path.abspath(path)}"

    def open_file(self, path: str, content: str, language_id: str) -> None:
        if not self._transport:
            return
        self._transport.notify("textDocument/didOpen", {
            "textDocument": {
                "uri": self._uri(path),
                "languageId": language_id,
                "version": 1,
                "text": content,
            }
        })

    def hover(self, path: str, line: int, character: int) -> dict | None:
        if not self._transport:
            return None
        try:
            resp = self._transport.request("textDocument/hover", {
                "textDocument": {"uri": self._uri(path)},
                "position": {"line": line, "character": character},
            })
            return resp.get("result")
        except Exception:
            return None

    def definition(self, path: str, line: int, character: int) -> list[dict]:
        if not self._transport:
            return []
        try:
            resp = self._transport.request("textDocument/definition", {
                "textDocument": {"uri": self._uri(path)},
                "position": {"line": line, "character": character},
            })
            result = resp.get("result") or []
            return result if isinstance(result, list) else [result]
        except Exception:
            return []

    def references(self, path: str, line: int, character: int) -> list[dict]:
        if not self._transport:
            return []
        try:
            resp = self._transport.request("textDocument/references", {
                "textDocument": {"uri": self._uri(path)},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": True},
            })
            return resp.get("result") or []
        except Exception:
            return []

    def rename(self, path: str, line: int, character: int, new_name: str) -> dict:
        if not self._transport:
            return {}
        try:
            resp = self._transport.request("textDocument/rename", {
                "textDocument": {"uri": self._uri(path)},
                "position": {"line": line, "character": character},
                "newName": new_name,
            })
            return resp.get("result") or {}
        except Exception:
            return {}

    def document_symbols(self, path: str) -> list[dict]:
        if not self._transport:
            return []
        try:
            resp = self._transport.request("textDocument/documentSymbol", {
                "textDocument": {"uri": self._uri(path)},
            })
            return resp.get("result") or []
        except Exception:
            return []

    def workspace_symbols(self, query: str) -> list[dict]:
        if not self._transport:
            return []
        try:
            resp = self._transport.request("workspace/symbol", {"query": query})
            return resp.get("result") or []
        except Exception:
            return []

    def code_actions(self, path: str, line: int, character: int) -> list[dict]:
        if not self._transport:
            return []
        try:
            r = Range(line, character, line, character + 1)
            resp = self._transport.request("textDocument/codeAction", {
                "textDocument": {"uri": self._uri(path)},
                "range": {"start": {"line": line, "character": character},
                          "end": {"line": line, "character": character + 1}},
                "context": {"diagnostics": []},
            })
            return resp.get("result") or []
        except Exception:
            return []

    def close(self) -> None:
        if self._transport:
            try:
                self._transport.request("shutdown", None, timeout=3.0)
                self._transport.notify("exit", None)
            except Exception:
                pass
            self._transport.close()
            self._transport = None
        self._initialized = False


class Range:
    def __init__(self, sl, sc, el, ec):
        self.sl, self.sc, self.el, self.ec = sl, sc, el, ec


# ---------------------------------------------------------------------------
# Concrete adapters
# ---------------------------------------------------------------------------

class PyrightAdapter(_BaseAdapter):
    """Python language analysis via Pyright."""
    NAME = "pyright"
    COMMAND = ["pyright-langserver", "--stdio"]
    LANGUAGE_ID = "python"

    @classmethod
    def available(cls) -> bool:
        return shutil.which("pyright-langserver") is not None or shutil.which("pyright") is not None

    def get_command(self) -> list[str]:
        if shutil.which("pyright-langserver"):
            return ["pyright-langserver", "--stdio"]
        return ["pyright", "--outputjson"]  # fallback

    def start(self, workspace_root: str) -> bool:
        self.COMMAND = self.get_command()
        return super().start(workspace_root)


class TypeScriptAdapter(_BaseAdapter):
    """TypeScript/JavaScript via typescript-language-server."""
    NAME = "typescript-language-server"
    COMMAND = ["typescript-language-server", "--stdio"]
    LANGUAGE_ID = "typescript"

    @classmethod
    def available(cls) -> bool:
        return shutil.which("typescript-language-server") is not None


class RustAnalyzerAdapter(_BaseAdapter):
    """Rust via rust-analyzer."""
    NAME = "rust-analyzer"
    COMMAND = ["rust-analyzer"]
    LANGUAGE_ID = "rust"

    @classmethod
    def available(cls) -> bool:
        return shutil.which("rust-analyzer") is not None


class ClangdAdapter(_BaseAdapter):
    """C/C++ via clangd."""
    NAME = "clangd"
    COMMAND = ["clangd", "--background-index"]
    LANGUAGE_ID = "cpp"

    @classmethod
    def available(cls) -> bool:
        return shutil.which("clangd") is not None


# ---------------------------------------------------------------------------
# LSPServerManager -- routes requests to the right adapter
# ---------------------------------------------------------------------------

_LANG_ADAPTERS: dict[str, type[_BaseAdapter]] = {
    "python":      PyrightAdapter,
    "typescript":  TypeScriptAdapter,
    "javascript":  TypeScriptAdapter,
    "rust":        RustAnalyzerAdapter,
    "c":           ClangdAdapter,
    "cpp":         ClangdAdapter,
}


class LSPServerManager:
    """
    Manages per-language LSP server connections.
    Falls back to the Brain's built-in LSPEngine when no server is available.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, _BaseAdapter] = {}

    def available_servers(self) -> dict[str, bool]:
        return {lang: cls.available() for lang, cls in _LANG_ADAPTERS.items()}

    def start_server(self, language: str, workspace_root: str) -> bool:
        if language in self._adapters and self._adapters[language]._initialized:
            return True
        cls = _LANG_ADAPTERS.get(language)
        if cls is None or not cls.available():
            return False
        adapter = cls()
        started = adapter.start(workspace_root)
        if started:
            self._adapters[language] = adapter
        return started

    def _get(self, language: str) -> _BaseAdapter | None:
        return self._adapters.get(language)

    def hover(self, language: str, path: str, content: str, line: int, character: int) -> dict | None:
        adapter = self._get(language)
        if adapter:
            adapter.open_file(path, content, language)
            return adapter.hover(path, line, character)
        return None

    def definition(self, language: str, path: str, content: str, line: int, character: int) -> list[dict]:
        adapter = self._get(language)
        if adapter:
            adapter.open_file(path, content, language)
            return adapter.definition(path, line, character)
        return []

    def references(self, language: str, path: str, content: str, line: int, character: int) -> list[dict]:
        adapter = self._get(language)
        if adapter:
            adapter.open_file(path, content, language)
            return adapter.references(path, line, character)
        return []

    def rename(self, language: str, path: str, content: str, line: int, character: int, new_name: str) -> dict:
        adapter = self._get(language)
        if adapter:
            adapter.open_file(path, content, language)
            return adapter.rename(path, line, character, new_name)
        return {}

    def document_symbols(self, language: str, path: str, content: str) -> list[dict]:
        adapter = self._get(language)
        if adapter:
            adapter.open_file(path, content, language)
            return adapter.document_symbols(path)
        return []

    def workspace_symbols(self, language: str, query: str) -> list[dict]:
        adapter = self._get(language)
        if adapter:
            return adapter.workspace_symbols(query)
        return []

    def code_actions(self, language: str, path: str, content: str, line: int, character: int) -> list[dict]:
        adapter = self._get(language)
        if adapter:
            adapter.open_file(path, content, language)
            return adapter.code_actions(path, line, character)
        return []

    def stop_all(self) -> None:
        for adapter in self._adapters.values():
            try:
                adapter.close()
            except Exception:
                pass
        self._adapters.clear()
