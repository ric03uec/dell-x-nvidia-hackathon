"""Live scoring loop: rules + rolling baselines + a small Isolation Forest.

Polls canonical events and emits findings on a CPU-only, low-latency path
that must keep working independently of the offline model and the security
agent (integration rule 8). Scaffold only (dxnvh-332.7) — no detection logic
yet; that lands in epic dxnvh-0e6 (`.1`, `.3`, `.4`, `.6`).
"""

__all__: list[str] = []
