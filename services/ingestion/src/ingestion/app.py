"""Ingestion: one process, three surfaces.

  REST  /v1/*       — the collector posts events, the dashboard reads
  RULES /v1/rules{,.txt,/check} — what Squid asks for enforcement
  MCP   /mcp        — the tool surface the OpenClaw security agent calls

All three go through services.ingestion.store, so there is one implementation
of every operation and the surfaces cannot disagree (dxnvh-2jb.7).

Port 8100 per docs/ports.md — that file is the table of record, not this.

Routes are /v1/*, NOT /api/v1/*. services/dashboard/vite.config.ts proxies /api
to this service and rewrites ^/api away, so the dashboard's /api/v1/events
arrives here as /v1/events. Re-adding the /api prefix silently 404s the whole
dashboard.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Response
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from . import store

SCHEMA_VERSION = "1.0"
DB_PATH = os.environ.get("INGESTION_DB", "/var/lib/ingestion/events.db")

conn = store.connect(DB_PATH)

# The action a recommendation may propose. Constraining it here means an
# invalid action is rejected at the protocol boundary — before handler code,
# and before the model can talk anyone into it (dxnvh-2jb.7).
ActionType = Literal["block_destination", "alert_only", "raise_risk"]


def envelope(**values: Any) -> dict[str, Any]:
    """Every response carries schema_version — services/dashboard/src/api/client.js
    rejects any payload without it."""
    return {"schema_version": SCHEMA_VERSION, **values}


# --- MCP surface --------------------------------------------------------

mcp = FastMCP("squidward-ingestion")


@mcp.tool
def query_events(
    limit: int = 50, destination: str | None = None, src: str | None = None
) -> dict[str, Any]:
    """Recent proxied egress events, newest first. Filter by destination or source.

    Side-effect free.
    """
    return {"events": store.list_events(conn, limit=limit, destination=destination, src=src)}


@mcp.tool
def get_evidence(finding_id: str) -> dict[str, Any]:
    """The finding and the full events behind it, for explaining a verdict.

    Side-effect free.
    """
    finding = store.get_finding(conn, finding_id)
    if finding is None:
        return {"error": f"no such finding: {finding_id}"}
    return {"finding": finding, "events": store.events_by_ids(conn, finding["event_ids"])}


@mcp.tool
def get_rules() -> dict[str, Any]:
    """Destinations currently denied at the proxy. Side-effect free."""
    return {"rules": store.list_rules(conn)}


@mcp.tool
def submit_finding(summary: str, risk_score: int, event_ids: list[str]) -> dict[str, Any]:
    """Record a correlated finding over events the agent believes are related."""
    finding_id = store.add_finding(conn, summary, risk_score, event_ids)
    return {"finding_id": finding_id}


@mcp.tool
def recommend_policy(
    action_type: ActionType,
    destination: str,
    rationale: str,
    finding_id: str | None = None,
) -> dict[str, Any]:
    """Propose a policy action. This RECOMMENDS only — it never enforces.

    Nothing here reaches Squid. A recommendation becomes a rule only when a
    human approves it via POST /v1/recommendations/{id}/decision.
    """
    recommendation_id = store.add_recommendation(
        conn, action_type, destination, rationale, finding_id
    )
    return {"recommendation_id": recommendation_id, "status": "pending"}


mcp_app = mcp.http_app(path="/")

# --- REST surface -------------------------------------------------------

# lifespan=mcp_app.lifespan is REQUIRED. Drop it and FastMCP's session manager
# never initialises: the MCP endpoint mounts, accepts connections, and then
# fails on session state — with no startup error pointing at the cause. This
# is the documented failure mode, so it is asserted in the tests.
app = FastAPI(title="squidward-ingestion", lifespan=mcp_app.lifespan)
app.mount("/mcp", mcp_app)


class EventIn(BaseModel):
    # Deliberately permissive: the exfilguard field set is provisional until
    # dxnvh-332.2 freezes it, so unknown keys are kept in `raw` rather than
    # rejected. Tighten when the contract freezes.
    model_config = {"extra": "allow"}

    ts: float | None = None
    src: str | None = None
    uri: str | None = None
    method: str | None = None
    req_bytes: int | None = None
    resp_bytes: int | None = None


class Decision(BaseModel):
    approve: bool
    actor: Annotated[str, Field(min_length=1)]


@app.get("/health")
def health() -> dict[str, Any]:
    ok = store.healthy(conn)
    return envelope(status="ok" if ok else "degraded", database=ok)


@app.post("/v1/events", status_code=201)
def post_events(events: list[EventIn] | EventIn) -> dict[str, Any]:
    batch = events if isinstance(events, list) else [events]
    ids = [store.add_event(conn, e.model_dump(exclude_none=False)) for e in batch]
    return envelope(accepted=len(ids), event_ids=ids)


@app.get("/v1/events")
def get_events(
    limit: int = 100, destination: str | None = None, src: str | None = None
) -> dict[str, Any]:
    return envelope(events=store.list_events(conn, limit, destination, src))


@app.get("/v1/recommendations")
def get_recommendations(status: str | None = None) -> dict[str, Any]:
    return envelope(recommendations=store.list_recommendations(conn, status))


@app.post("/v1/recommendations/{recommendation_id}/decision")
def post_decision(recommendation_id: str, decision: Decision) -> dict[str, Any]:
    rec = store.decide(conn, recommendation_id, decision.approve, decision.actor)
    if rec is None:
        raise HTTPException(status_code=404, detail="no such recommendation")
    return envelope(recommendation=rec)


# --- the rules surface Squid consumes -----------------------------------


@app.get("/v1/rules")
def get_rules_json() -> dict[str, Any]:
    return envelope(rules=store.list_rules(conn))


@app.get("/v1/rules.txt")
def get_rules_txt() -> Response:
    """One destination per line — squid's `dstdomain "file"` format directly.

    This is the MVP enforcement path from architecture §7: fetch to a file,
    then `squid -k reconfigure`. No envelope: squid parses this, not the
    dashboard.
    """
    body = "".join(f"{r['destination']}\n" for r in store.list_rules(conn))
    return Response(content=body, media_type="text/plain")


@app.get("/v1/rules/check")
def check_rule(dst: str) -> dict[str, Any]:
    """Point query for the external_acl helper. `denied` true means deny."""
    return envelope(destination=dst, denied=store.is_denied(conn, dst))
