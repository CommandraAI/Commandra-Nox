"""
Proxy-aware ASGI entry point.

This Replit project serves every service behind a shared reverse proxy that
does NOT strip path prefixes -- a request for the Brain's `/health` route
arrives at this process as `/brain/health`. Starlette's `Mount` handles that
prefix stripping (and Swagger UI's relative asset/openapi URLs) for us, so
external tooling (uvicorn, `python -m server.mounted`) should import `app`
from this module instead of `server.main` directly.

Run with: `python -m server.mounted` (reads $PORT, same as server/main.py).
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from server.main import app as brain_app

app = FastAPI()
app.mount("/brain", brain_app)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)
