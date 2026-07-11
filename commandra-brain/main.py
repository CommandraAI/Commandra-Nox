"""
Commandra Nox Brain — production entry point.

Reads PORT from the environment (injected by the Replit artifact system)
and starts the proxy-aware ASGI app that mounts the Brain at /brain.
"""
from __future__ import annotations

import os
import uvicorn

from server.mounted import app  # noqa: F401 — re-exported so workers can import it


def main() -> None:
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(
        "server.mounted:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("RELOAD", "false").lower() == "true",
        log_level="info",
    )


if __name__ == "__main__":
    main()
