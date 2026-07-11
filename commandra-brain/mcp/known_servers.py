"""
Known MCP Servers -- pre-configured connection recipes for the official
MCP server implementations from modelcontextprotocol/servers.

Provides one-call setup for:
  - filesystem   (local file access)
  - git          (git repository operations)
  - github       (GitHub API via MCP)
  - postgres     (PostgreSQL database access)
  - sqlite       (SQLite database access)
  - brave-search (web search via Brave)
  - puppeteer    (browser automation)
  - fetch        (URL fetching)
  - memory       (knowledge graph persistence)
  - everything   (reference/test server)

All servers are run via `npx -y @modelcontextprotocol/server-<name>`.
Node.js must be installed.
"""
from __future__ import annotations
import os
import shutil
from dataclasses import dataclass, field


@dataclass
class KnownServer:
    server_id: str
    name: str
    description: str
    npx_package: str
    required_env: list[str] = field(default_factory=list)
    optional_env: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)

    def command(self, extra_args: list[str] | None = None) -> list[str]:
        cmd = ["npx", "-y", self.npx_package, *self.args]
        if extra_args:
            cmd += extra_args
        return cmd

    def env_from_os(self) -> dict[str, str]:
        """Pull configured env vars from the current process environment."""
        env: dict[str, str] = {}
        for key in self.required_env + self.optional_env:
            val = os.environ.get(key)
            if val:
                env[key] = val
        return env

    def is_ready(self) -> bool:
        """Returns True if all required env vars are set and npx is available."""
        if not shutil.which("npx"):
            return False
        return all(os.environ.get(k) for k in self.required_env)

    def as_dict(self) -> dict:
        return {
            "serverId": self.server_id,
            "name": self.name,
            "description": self.description,
            "npxPackage": self.npx_package,
            "requiredEnv": self.required_env,
            "optionalEnv": self.optional_env,
            "ready": self.is_ready(),
        }


KNOWN_SERVERS: dict[str, KnownServer] = {
    "filesystem": KnownServer(
        server_id="filesystem",
        name="MCP Filesystem",
        description="Local file system access — read, write, list, move files",
        npx_package="@modelcontextprotocol/server-filesystem",
        required_env=[],
        args=[],                    # pass root path at connect time
    ),
    "git": KnownServer(
        server_id="git",
        name="MCP Git",
        description="Git repository operations — log, diff, blame, commit, branch",
        npx_package="@modelcontextprotocol/server-git",
        required_env=[],
        args=[],
    ),
    "github": KnownServer(
        server_id="github",
        name="MCP GitHub",
        description="GitHub API — search repos, issues, PRs, code, file contents",
        npx_package="@modelcontextprotocol/server-github",
        required_env=["GITHUB_PERSONAL_ACCESS_TOKEN"],
    ),
    "postgres": KnownServer(
        server_id="postgres",
        name="MCP PostgreSQL",
        description="PostgreSQL read-only access — schema inspection and query execution",
        npx_package="@modelcontextprotocol/server-postgres",
        required_env=["POSTGRES_CONNECTION_STRING"],
    ),
    "sqlite": KnownServer(
        server_id="sqlite",
        name="MCP SQLite",
        description="SQLite database access — schema inspection and queries",
        npx_package="@modelcontextprotocol/server-sqlite",
        required_env=[],
        args=["--db-path"],         # pass DB path at connect time
    ),
    "brave-search": KnownServer(
        server_id="brave-search",
        name="MCP Brave Search",
        description="Web and local search via the Brave Search API",
        npx_package="@modelcontextprotocol/server-brave-search",
        required_env=["BRAVE_API_KEY"],
    ),
    "puppeteer": KnownServer(
        server_id="puppeteer",
        name="MCP Puppeteer",
        description="Browser automation — screenshots, web scraping, navigation",
        npx_package="@modelcontextprotocol/server-puppeteer",
        required_env=[],
    ),
    "fetch": KnownServer(
        server_id="fetch",
        name="MCP Fetch",
        description="Fetch URL content and convert to Markdown",
        npx_package="@modelcontextprotocol/server-fetch",
        required_env=[],
    ),
    "memory": KnownServer(
        server_id="memory",
        name="MCP Memory",
        description="Persistent knowledge graph memory across sessions",
        npx_package="@modelcontextprotocol/server-memory",
        required_env=[],
    ),
    "everything": KnownServer(
        server_id="everything",
        name="MCP Everything",
        description="Reference MCP server with all capability examples (testing)",
        npx_package="@modelcontextprotocol/server-everything",
        required_env=[],
    ),
    "slack": KnownServer(
        server_id="slack",
        name="MCP Slack",
        description="Slack workspace access — channels, messages, users",
        npx_package="@modelcontextprotocol/server-slack",
        required_env=["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    ),
    "google-drive": KnownServer(
        server_id="google-drive",
        name="MCP Google Drive",
        description="Read and search files in Google Drive",
        npx_package="@modelcontextprotocol/server-gdrive",
        required_env=["GDRIVE_CREDENTIALS_FILE"],
    ),
    "google-maps": KnownServer(
        server_id="google-maps",
        name="MCP Google Maps",
        description="Location data, directions, place search",
        npx_package="@modelcontextprotocol/server-google-maps",
        required_env=["GOOGLE_MAPS_API_KEY"],
    ),
    "sentry": KnownServer(
        server_id="sentry",
        name="MCP Sentry",
        description="Sentry error tracking — issues, events, performance",
        npx_package="@modelcontextprotocol/server-sentry",
        required_env=["SENTRY_AUTH_TOKEN"],
        optional_env=["SENTRY_ORG", "SENTRY_PROJECT"],
    ),
    "aws-kb": KnownServer(
        server_id="aws-kb",
        name="MCP AWS Knowledge Base",
        description="Amazon Bedrock Knowledge Base retrieval",
        npx_package="@modelcontextprotocol/server-aws-kb-retrieval",
        required_env=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"],
    ),
}


def list_known_servers() -> list[dict]:
    return [s.as_dict() for s in KNOWN_SERVERS.values()]


def get_known_server(server_id: str) -> KnownServer | None:
    return KNOWN_SERVERS.get(server_id)


def ready_servers() -> list[dict]:
    """Return only servers whose required env vars are set and npx is available."""
    return [s.as_dict() for s in KNOWN_SERVERS.values() if s.is_ready()]
