"""Minimal FastAPI app for the processing service.

Scaffold only (dxnvh-332.7): the one endpoint every component in
docs/modular-implementation-plan.md §4 exposes. The live scoring loop and the
offline batch runner (dxnvh-0e6) will mount their own routes onto an app built
the same way once that logic lands.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app(name: str = "processing", version: str = "0.1.0") -> FastAPI:
    """Build the processing service's FastAPI app."""
    app = FastAPI(title=name, version=version)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": name}

    return app


app = create_app()
