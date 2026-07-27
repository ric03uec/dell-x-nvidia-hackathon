"""The security-agent side of the loop, driven over MCP.

This is what the OpenClaw security agent does with its tool surface: read the
events, correlate them into a finding, and propose a policy. It is written as a
deterministic script rather than an LLM call so the demo is reproducible on
video — the *protocol path* it exercises is identical either way, and that path
is the thing worth showing.

The critical property it demonstrates: recommend_policy creates a PENDING
recommendation. The agent cannot enforce. A human approval is what moves a
destination into Squid's denylist.
"""

from __future__ import annotations

import urllib.request
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastmcp import Client

MCP_URL = "http://127.0.0.1:8100/mcp/"
INGESTION = "http://127.0.0.1:8100"


def _severity(risk: int) -> str:
    """contracts/finding.schema.json constrains this to four values."""
    if risk >= 90:
        return "critical"
    if risk >= 70:
        return "high"
    return "medium" if risk >= 40 else "low"


@dataclass
class Verdict:
    destination: str
    bytes_up: int
    event_ids: list[str]
    risk: int
    rationale: str


def triage(events: list[dict[str, Any]], baseline_hosts: set[str]) -> Verdict | None:
    """Pick the destination that looks least like the baseline.

    Deliberately simple and explainable: unseen destination + the largest
    upload volume. A model can replace this behind the same seam (dxnvh-0e6).
    """
    by_dest: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        dest = (e.get("destination") or "").split(":")[0]
        if dest:
            by_dest[dest].append(e)

    best: Verdict | None = None
    for dest, group in by_dest.items():
        if dest in baseline_hosts:
            continue
        # Same both-spellings rule as run.py: collector events use
        # req_bytes, canonical events use request_bytes.
        up = sum(int(e.get("req_bytes") or e.get("request_bytes") or 0) for e in group)
        if up < 1_000_000:
            continue
        if best is None or up > best.bytes_up:
            best = Verdict(
                destination=dest,
                bytes_up=up,
                event_ids=[e["event_id"] for e in group],
                risk=min(99, 60 + up // (1024 * 1024)),
                rationale=(
                    f"{up:,} bytes uploaded to {dest}, which has no prior history "
                    f"for this environment, across {len(group)} request(s)"
                ),
            )
    return best


def fetch_events(limit: int = 500) -> list[dict[str, Any]]:
    with urllib.request.urlopen(f"{INGESTION}/v1/events?limit={limit}", timeout=15) as r:
        import json

        return list(json.load(r).get("events", []))


async def investigate(baseline_hosts: set[str], mcp_url: str = MCP_URL) -> dict[str, Any]:
    """Read → correlate → submit finding → recommend policy, all over MCP."""
    report: dict[str, Any] = {}

    async with Client(mcp_url) as client:
        queried = await client.call_tool("query_events", {"limit": 500})
        events = queried.data.get("events", [])
        report["events_seen"] = len(events)

        verdict = triage(events, baseline_hosts)
        if verdict is None:
            report["finding"] = None
            return report

        report["verdict"] = verdict.__dict__

        # finding_id and severity are required by the frozen contract
        # (contracts/finding.schema.json) — the tool schema enforces them, so
        # the caller mints the id rather than the server.
        finding_id = f"fnd-{uuid.uuid4().hex[:12]}"
        await client.call_tool(
            "submit_finding",
            {
                "finding_id": finding_id,
                "summary": verdict.rationale,
                "risk_score": verdict.risk,
                "severity": _severity(verdict.risk),
                "event_ids": verdict.event_ids[:20],
            },
        )
        report["finding_id"] = finding_id

        recommendation_id = f"rec-{uuid.uuid4().hex[:12]}"
        proposal = await client.call_tool(
            "recommend_policy",
            {
                "finding_id": finding_id,
                "action_type": "deny_destination",
                "target": verdict.destination,
                "scope": "destination",
                "reason": verdict.rationale,
            },
        )
        report["recommendation_id"] = proposal.data.get("recommendation_id") or recommendation_id
        report["status"] = proposal.data.get("status", "pending")

    return report
