"""Minimal FastAPI factory shared by every agent project."""

from __future__ import annotations

import os

from fastapi import FastAPI

# ponytail: defaults to the managed vLLM the NemoClaw installer stands up on a
# DGX Spark. Override with OPENAI_BASE_URL per host (Ollama is :11434), not per
# agent — the route is a property of the box, not of the idea being prototyped.
DEFAULT_INFERENCE_URL = "http://127.0.0.1:8000/v1"


def inference_base_url() -> str:
    """The OpenAI-compatible endpoint this agent's service should talk to."""
    return os.environ.get("OPENAI_BASE_URL", DEFAULT_INFERENCE_URL)


def create_app(name: str, version: str = "0.1.0") -> FastAPI:
    """Build an agent service with the one endpoint every agent needs."""
    app = FastAPI(title=name, version=version)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "agent": name, "inference": inference_base_url()}

    return app
