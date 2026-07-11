"""
MCP (Model Context Protocol) Client -- connects the Brain to external MCP
servers and exposes their tools, resources, and prompts as native Brain
capabilities.

Implements:
- MCP Client
- MCP Server Discovery
- Tool Registration
- Resource Loading
- Prompt Registration
- Dynamic MCP Server Connections
- MCP Capability Detection

All communication uses JSON-RPC 2.0 over stdin/stdout (SSE for HTTP-based
servers). The Brain can discover and call MCP tools the same way it calls
internal tools.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("commandra.mcp")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict
    server_id: str

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "serverId": self.server_id,
        }


@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    mime_type: str
    server_id: str

    def as_dict(self) -> dict:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
            "serverId": self.server_id,
        }


@dataclass
class MCPPrompt:
    name: str
    description: str
    arguments: list[dict]
    server_id: str

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
            "serverId": self.server_id,
        }


@dataclass
class MCPCapabilities:
    tools: bool = False
    resources: bool = False
    prompts: bool = False
    logging: bool = False

    def as_dict(self) -> dict:
        return {
            "tools": self.tools,
            "resources": self.resources,
            "prompts": self.prompts,
            "logging": self.logging,
        }


@dataclass
class MCPServerInfo:
    server_id: str
    name: str
    version: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    capabilities: MCPCapabilities = field(default_factory=MCPCapabilities)
    tools: list[MCPTool] = field(default_factory=list)
    resources: list[MCPResource] = field(default_factory=list)
    prompts: list[MCPPrompt] = field(default_factory=list)
    connected: bool = False
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "serverId": self.server_id,
            "name": self.name,
            "version": self.version,
            "command": self.command,
            "capabilities": self.capabilities.as_dict(),
            "tools": [t.as_dict() for t in self.tools],
            "resources": [r.as_dict() for r in self.resources],
            "prompts": [p.as_dict() for p in self.prompts],
            "connected": self.connected,
            "error": self.error,
        }


@dataclass
class MCPToolCallResult:
    tool_name: str
    server_id: str
    content: list[dict]
    is_error: bool = False
    elapsed_ms: float = 0.0

    def as_dict(self) -> dict:
        return {
            "toolName": self.tool_name,
            "serverId": self.server_id,
            "content": self.content,
            "isError": self.is_error,
            "elapsedMs": round(self.elapsed_ms, 2),
        }


# ---------------------------------------------------------------------------
# Low-level JSON-RPC transport over subprocess stdio
# ---------------------------------------------------------------------------

class _StdioTransport:
    """Manages a subprocess MCP server and sends/receives JSON-RPC 2.0 messages."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        import os
        merged_env = {**os.environ, **(env or {})}
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()
        self._pending: dict[str, Any] = {}
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg_id = msg.get("id")
            if msg_id and msg_id in self._pending:
                self._pending[msg_id] = msg

    def request(self, method: str, params: dict | None = None, timeout: float = 10.0) -> dict:
        msg_id = str(uuid.uuid4())
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
        with self._lock:
            self._pending[msg_id] = None
            assert self._proc.stdin
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()

        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                result = self._pending.get(msg_id)
            if result is not None:
                with self._lock:
                    del self._pending[msg_id]
                return result
            time.sleep(0.02)

        with self._lock:
            self._pending.pop(msg_id, None)
        raise TimeoutError(f"MCP request '{method}' timed out after {timeout}s")

    def notify(self, method: str, params: dict | None = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        with self._lock:
            assert self._proc.stdin
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()

    def close(self) -> None:
        try:
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:
            self._proc.kill()


# ---------------------------------------------------------------------------
# Per-server connection
# ---------------------------------------------------------------------------

class _MCPConnection:
    """Maintains a live connection to a single MCP server."""

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, info: MCPServerInfo) -> None:
        self.info = info
        self._transport: _StdioTransport | None = None

    def connect(self) -> None:
        self._transport = _StdioTransport(self.info.command, self.info.env)
        resp = self._transport.request(
            "initialize",
            {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "clientInfo": {"name": "commandra-nox-brain", "version": "0.1.0"},
            },
        )
        if "error" in resp:
            raise RuntimeError(f"MCP init error: {resp['error']}")

        result = resp.get("result", {})
        caps = result.get("capabilities", {})
        self.info.capabilities = MCPCapabilities(
            tools="tools" in caps,
            resources="resources" in caps,
            prompts="prompts" in caps,
            logging="logging" in caps,
        )
        self.info.name = result.get("serverInfo", {}).get("name", self.info.name)
        self.info.version = result.get("serverInfo", {}).get("version", self.info.version)

        self._transport.notify("notifications/initialized")

        if self.info.capabilities.tools:
            self._load_tools()
        if self.info.capabilities.resources:
            self._load_resources()
        if self.info.capabilities.prompts:
            self._load_prompts()

        self.info.connected = True

    def _load_tools(self) -> None:
        assert self._transport
        resp = self._transport.request("tools/list")
        for t in resp.get("result", {}).get("tools", []):
            self.info.tools.append(
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    server_id=self.info.server_id,
                )
            )

    def _load_resources(self) -> None:
        assert self._transport
        resp = self._transport.request("resources/list")
        for r in resp.get("result", {}).get("resources", []):
            self.info.resources.append(
                MCPResource(
                    uri=r["uri"],
                    name=r.get("name", r["uri"]),
                    description=r.get("description", ""),
                    mime_type=r.get("mimeType", "text/plain"),
                    server_id=self.info.server_id,
                )
            )

    def _load_prompts(self) -> None:
        assert self._transport
        resp = self._transport.request("prompts/list")
        for p in resp.get("result", {}).get("prompts", []):
            self.info.prompts.append(
                MCPPrompt(
                    name=p["name"],
                    description=p.get("description", ""),
                    arguments=p.get("arguments", []),
                    server_id=self.info.server_id,
                )
            )

    def call_tool(self, tool_name: str, arguments: dict) -> MCPToolCallResult:
        assert self._transport, "Not connected"
        start = time.time()
        resp = self._transport.request("tools/call", {"name": tool_name, "arguments": arguments})
        elapsed_ms = (time.time() - start) * 1000
        result = resp.get("result", {})
        is_error = result.get("isError", False) or "error" in resp
        content = result.get("content", [{"type": "text", "text": str(resp.get("error", result))}])
        return MCPToolCallResult(
            tool_name=tool_name,
            server_id=self.info.server_id,
            content=content,
            is_error=is_error,
            elapsed_ms=elapsed_ms,
        )

    def read_resource(self, uri: str) -> dict:
        assert self._transport, "Not connected"
        resp = self._transport.request("resources/read", {"uri": uri})
        return resp.get("result", {})

    def get_prompt(self, name: str, arguments: dict | None = None) -> dict:
        assert self._transport, "Not connected"
        resp = self._transport.request("prompts/get", {"name": name, "arguments": arguments or {}})
        return resp.get("result", {})

    def disconnect(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None
        self.info.connected = False


# ---------------------------------------------------------------------------
# MCPClient -- the public API used by CommandraBrain
# ---------------------------------------------------------------------------

class MCPClient:
    """
    Central MCP client used by CommandraBrain.

    Manages a registry of MCP servers.  The Brain can connect to any number
    of external MCP servers; their tools are then available alongside native
    Brain tools in the tool registry.
    """

    def __init__(self) -> None:
        self._servers: dict[str, _MCPConnection] = {}

    # -- Server lifecycle --------------------------------------------------

    def connect_server(self, command: list[str], env: dict[str, str] | None = None, server_id: str | None = None) -> MCPServerInfo:
        sid = server_id or str(uuid.uuid4())[:8]
        info = MCPServerInfo(server_id=sid, name=sid, version="unknown", command=command, env=env or {})
        conn = _MCPConnection(info)
        try:
            conn.connect()
            self._servers[sid] = conn
            logger.info("Connected to MCP server %s (%s tools, %s resources, %s prompts)",
                        sid, len(info.tools), len(info.resources), len(info.prompts))
        except Exception as exc:
            info.error = str(exc)
            info.connected = False
            logger.warning("Failed to connect MCP server %s: %s", sid, exc)
        return info

    def disconnect_server(self, server_id: str) -> bool:
        conn = self._servers.pop(server_id, None)
        if conn:
            conn.disconnect()
            return True
        return False

    # -- Discovery ---------------------------------------------------------

    def list_servers(self) -> list[dict]:
        return [conn.info.as_dict() for conn in self._servers.values()]

    def all_tools(self) -> list[MCPTool]:
        tools: list[MCPTool] = []
        for conn in self._servers.values():
            if conn.info.connected:
                tools.extend(conn.info.tools)
        return tools

    def all_resources(self) -> list[MCPResource]:
        resources: list[MCPResource] = []
        for conn in self._servers.values():
            if conn.info.connected:
                resources.extend(conn.info.resources)
        return resources

    def all_prompts(self) -> list[MCPPrompt]:
        prompts: list[MCPPrompt] = []
        for conn in self._servers.values():
            if conn.info.connected:
                prompts.extend(conn.info.prompts)
        return prompts

    def capabilities(self) -> dict:
        return {
            sid: conn.info.capabilities.as_dict()
            for sid, conn in self._servers.items()
        }

    # -- Tool invocation ---------------------------------------------------

    def call_tool(self, tool_name: str, arguments: dict, server_id: str | None = None) -> MCPToolCallResult:
        if server_id:
            conn = self._servers.get(server_id)
            if not conn:
                raise KeyError(f"Unknown MCP server: {server_id}")
            return conn.call_tool(tool_name, arguments)

        # Auto-discover which server owns this tool
        for conn in self._servers.values():
            if conn.info.connected and any(t.name == tool_name for t in conn.info.tools):
                return conn.call_tool(tool_name, arguments)

        raise KeyError(f"Tool '{tool_name}' not found on any connected MCP server")

    def read_resource(self, uri: str, server_id: str | None = None) -> dict:
        if server_id:
            conn = self._servers.get(server_id)
            if not conn:
                raise KeyError(f"Unknown MCP server: {server_id}")
            return conn.read_resource(uri)

        for conn in self._servers.values():
            if conn.info.connected and any(r.uri == uri for r in conn.info.resources):
                return conn.read_resource(uri)

        raise KeyError(f"Resource '{uri}' not found on any connected MCP server")

    def get_prompt(self, name: str, arguments: dict | None = None, server_id: str | None = None) -> dict:
        if server_id:
            conn = self._servers.get(server_id)
            if not conn:
                raise KeyError(f"Unknown MCP server: {server_id}")
            return conn.get_prompt(name, arguments)

        for conn in self._servers.values():
            if conn.info.connected and any(p.name == name for p in conn.info.prompts):
                return conn.get_prompt(name, arguments)

        raise KeyError(f"Prompt '{name}' not found on any connected MCP server")

    def disconnect_all(self) -> None:
        for conn in list(self._servers.values()):
            try:
                conn.disconnect()
            except Exception:
                pass
        self._servers.clear()
