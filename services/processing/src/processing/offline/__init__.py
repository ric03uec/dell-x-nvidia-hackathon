"""Offline batch runner: a PyTorch sequence/autoencoder model over a safe
SQLite snapshot, triggered manually or nightly.

Requests its snapshot through the ingestion API rather than opening the live
database directly. Scaffold only (dxnvh-332.7) — no model logic yet; that
lands in epic dxnvh-0e6 (`.2`, `.5`, `.7`). Needs the ``ml`` extra
(``uv sync --package processing --extra ml``) once it does.
"""

__all__: list[str] = []
