"""Always-on security agent support code: correlate findings across the live
and offline paths, explain them, and produce one constrained policy
recommendation for analyst approval.

An investigator, not an orchestrator — deterministic evidence from `live` is
never a fallback for this package's output, only an enhancement to it.
Scaffold only (dxnvh-332.7) — no correlation/recommendation logic yet; that
lands in epic dxnvh-0e6 (`.8`).
"""

__all__: list[str] = []
