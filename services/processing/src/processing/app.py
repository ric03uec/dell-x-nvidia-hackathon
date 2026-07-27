"""FastAPI health surface and lifecycle for the live processing scorer."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import FastAPI

from processing.live import LiveScorer


def create_app(name: str = "processing", version: str = "0.1.0") -> FastAPI:
    ingestion_url = os.environ.get("INGESTION_URL")
    stop_event = Event()
    worker: Thread | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal worker
        if ingestion_url:
            scorer = LiveScorer(ingestion_url)
            worker = Thread(
                target=scorer.run,
                kwargs={"stop_event": stop_event},
                name="squidward-live-scorer",
                daemon=True,
            )
            worker.start()
        yield
        stop_event.set()
        if worker:
            worker.join(timeout=5)

    app = FastAPI(title=name, version=version, lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        if ingestion_url and (worker is None or not worker.is_alive()):
            return {"status": "degraded", "service": name, "scorer": "stopped"}
        return {
            "status": "ok",
            "service": name,
            "scorer": "running" if ingestion_url else "disabled",
        }

    return app


app = create_app()
