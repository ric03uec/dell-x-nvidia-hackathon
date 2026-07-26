"""services/ingestion's HTTP surface.

Scaffold only: a bare FastAPI app with a single `/health` endpoint. The
schema, adapters, and the real REST/MCP API surface (docs/ports.md's
`hack-ingestion`, port 8100) land in epic 2 — nothing here talks to SQLite
or anything else yet.
"""

from fastapi import FastAPI

app = FastAPI(title="ingestion", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. The only endpoint this scaffold defines."""
    return {"status": "ok"}
