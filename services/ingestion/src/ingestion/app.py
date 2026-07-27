"""Durable REST, MCP, and Squid-rules surfaces for SquidWard ingestion."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from . import store

SCHEMA_VERSION = "1.0"
DB_PATH = os.environ.get("INGESTION_DB_PATH", os.environ.get("INGESTION_DB", "data/exfilguard.db"))
conn = store.connect(DB_PATH)
ActionType = Literal["deny_destination"]


def envelope(**values: Any) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, **values}


class EventIn(BaseModel):
    model_config = {"extra": "allow"}

    schema_version: str | None = None
    event_id: str | None = None
    timestamp: str | None = None
    source_type: str | None = None
    actor: str | None = None
    action: str | None = None
    destination: str | None = None
    request_bytes: int | None = None
    attributes: dict[str, Any] | None = None
    ts: float | None = None
    src: str | None = None
    uri: str | None = None
    method: str | None = None
    req_bytes: int | None = None
    resp_bytes: int | None = None


class FindingIn(BaseModel):
    model_config = {"extra": "allow"}

    schema_version: Literal["1.0"]
    finding_id: str
    event_ids: list[str]
    risk_score: float = Field(ge=0, le=100)
    severity: Literal["low", "medium", "high", "critical"]
    detectors: list[str] = Field(default_factory=list)
    summary: str = ""
    model_version: str | None = None


class RecommendationIn(BaseModel):
    schema_version: Literal["1.0"]
    recommendation_id: str
    finding_id: str
    action_type: ActionType
    target: str
    scope: str
    reason: str | None = None
    expires_at: str | None = None


class EnforcementResultIn(BaseModel):
    model_config = {"extra": "allow"}

    schema_version: Literal["1.0"]
    enforcement_result_id: str
    recommendation_id: str
    status: str


mcp = FastMCP("squidward-ingestion")


@mcp.tool
def query_events(
    limit: int = 50, destination: str | None = None, src: str | None = None
) -> dict[str, Any]:
    """Recent canonical egress events. Side-effect free."""
    return {"events": store.list_events(conn, limit=limit, destination=destination, src=src)}


@mcp.tool
def get_evidence(finding_id: str) -> dict[str, Any]:
    """A finding and the canonical events behind it. Side-effect free."""
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
    """Record a correlated finding over persisted events."""
    return {"finding_id": store.add_finding(conn, summary, risk_score, event_ids)}


@mcp.tool
def recommend_policy(
    action_type: ActionType,
    destination: str,
    rationale: str,
    finding_id: str | None = None,
) -> dict[str, Any]:
    """Recommend a constrained action; enforcement still requires approval."""
    recommendation_id = store.add_recommendation(
        conn, action_type, destination, rationale, finding_id
    )
    return {"recommendation_id": recommendation_id, "status": "pending"}


mcp_app = mcp.http_app(path="/")
app = FastAPI(title="squidward-ingestion", lifespan=mcp_app.lifespan)
app.mount("/mcp", mcp_app)


@app.get("/health")
def health() -> dict[str, Any]:
    ok = store.healthy(conn)
    return envelope(status="ok" if ok else "degraded", database=ok)


@app.post("/v1/events", status_code=201)
def post_events(events: list[EventIn] | EventIn) -> dict[str, Any]:
    batch = events if isinstance(events, list) else [events]
    records = [event.model_dump(exclude_none=False) for event in batch]
    for record in records:
        version = record.get("schema_version")
        if version not in {None, SCHEMA_VERSION}:
            raise HTTPException(400, "schema_version must be 1.0")
    ids = [store.add_event(conn, record) for record in records]
    return envelope(accepted=len(ids), event_ids=ids)


@app.get("/v1/events")
def get_events(
    limit: int = 1000,
    destination: str | None = None,
    src: str | None = None,
    after_id: str | None = None,
) -> dict[str, Any]:
    events = store.list_events(conn, limit, destination, src)
    events.reverse()
    if after_id:
        ids = [event.get("event_id") for event in events]
        if after_id not in ids:
            raise HTTPException(400, f"unknown after_id: {after_id}")
        events = events[ids.index(after_id) + 1 :]
    findings = store.list_findings(conn)
    for event in events:
        for finding in findings:
            if event.get("event_id") in finding["event_ids"]:
                event["finding_id"] = finding["finding_id"]
                event["risk_score"] = finding["risk_score"]
                break
    return envelope(count=len(events), events=events)


@app.delete("/v1/demo-data")
def delete_demo_data() -> dict[str, Any]:
    """Remove synthetic demo records without touching captured production data."""
    return envelope(removed=store.clear_demo_data(conn))


@app.post("/v1/findings", status_code=201)
def post_finding(finding: FindingIn) -> dict[str, Any]:
    finding_id = store.put_finding(conn, finding.model_dump(exclude_none=True))
    return envelope(finding_id=finding_id, accepted=True)


@app.get("/v1/findings")
def get_findings() -> dict[str, Any]:
    findings = [_finding_view(item) for item in store.list_findings(conn)]
    return envelope(count=len(findings), findings=findings)


@app.get("/v1/findings/{finding_id}")
def get_finding(finding_id: str) -> dict[str, Any]:
    finding = store.get_finding(conn, finding_id)
    if finding is None:
        raise HTTPException(404, "no such finding")
    return envelope(finding=_finding_view(finding))


@app.post("/v1/findings/{finding_id}/labels", status_code=201)
def post_label(finding_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_version(payload)
    if store.get_finding(conn, finding_id) is None:
        raise HTTPException(404, "no such finding")
    store.add_label(conn, finding_id, payload)
    return envelope(finding_id=finding_id, accepted=True)


@app.post("/v1/findings/{finding_id}/investigate", status_code=503)
def investigate(finding_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_version(payload)
    if store.get_finding(conn, finding_id) is None:
        raise HTTPException(404, "no such finding")
    return envelope(
        error={"code": "inference_unconfigured", "message": "Use processing inference"},
        investigation={
            "schema_version": SCHEMA_VERSION,
            "status": "unavailable",
            "summary": None,
            "served_model": None,
            "route": None,
        },
    )


@app.post("/v1/recommendations", status_code=201)
def post_recommendation(recommendation: RecommendationIn) -> dict[str, Any]:
    recommendation_id = store.put_recommendation(conn, recommendation.model_dump())
    return envelope(recommendation_id=recommendation_id, accepted=True)


@app.get("/v1/recommendations")
def get_recommendations(status: str | None = None) -> dict[str, Any]:
    recommendations = store.list_recommendations(conn, status)
    return envelope(count=len(recommendations), recommendations=recommendations)


@app.post("/v1/recommendations/{recommendation_id}/decision")
def post_decision(recommendation_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    _require_version(decision, optional=True)
    if "decision" in decision:
        value = decision["decision"]
        if value not in {"approved", "rejected"}:
            raise HTTPException(400, "decision must be approved or rejected")
        approve = value == "approved"
        actor = str(decision.get("analyst") or decision.get("actor") or "demo-analyst")
    else:
        if not isinstance(decision.get("approve"), bool):
            raise HTTPException(400, "decision or approve is required")
        approve = decision["approve"]
        actor = str(decision.get("actor") or "demo-analyst")
    recommendation = store.decide(conn, recommendation_id, approve, actor)
    if recommendation is None:
        raise HTTPException(404, "no such recommendation")
    return envelope(
        recommendation=recommendation,
        decision={
            "schema_version": SCHEMA_VERSION,
            "recommendation_id": recommendation_id,
            "decision": "approved" if approve else "rejected",
            "analyst": actor,
        },
    )


@app.get("/v1/policies/approved")
def get_approved_policies(after_id: str | None = None) -> dict[str, Any]:
    policies = store.approved_policies(conn, after_id)
    return envelope(count=len(policies), policies=policies)


@app.post("/v1/enforcement-results", status_code=201)
def post_enforcement_result(result: EnforcementResultIn) -> dict[str, Any]:
    result_id = store.put_enforcement_result(conn, result.model_dump())
    return envelope(enforcement_result_id=result_id, accepted=True)


@app.get("/v1/enforcement-results")
def get_enforcement_results(finding_id: str | None = None) -> dict[str, Any]:
    results = store.list_enforcement_results(conn)
    if finding_id:
        recommendation_ids = {
            recommendation["recommendation_id"]
            for recommendation in store.list_recommendations(conn)
            if recommendation.get("finding_id") == finding_id
        }
        results = [
            result for result in results if result["recommendation_id"] in recommendation_ids
        ]
    return envelope(count=len(results), enforcement_results=results)


@app.post("/v1/snapshots", status_code=201)
def post_snapshot() -> dict[str, Any]:
    snapshot_id, _ = store.create_snapshot(conn, DB_PATH)
    return envelope(snapshot_id=snapshot_id, status="completed")


@app.get("/v1/snapshots/{snapshot_id}", response_class=FileResponse)
def get_snapshot(snapshot_id: str) -> FileResponse:
    path = Path(DB_PATH).parent / "snapshots" / f"{snapshot_id}.sqlite"
    if not path.is_file():
        raise HTTPException(404, "no such snapshot")
    return FileResponse(path, filename=path.name)


@app.get("/v1/metrics/summary")
def metrics_summary(range: str | None = Query(None)) -> dict[str, Any]:  # noqa: A002
    counts = store.counts(conn)
    findings = store.list_findings(conn)
    suspicious_ids = {event_id for finding in findings for event_id in finding["event_ids"]}
    return envelope(
        total_events=counts["events"],
        normal_events=max(0, counts["events"] - len(suspicious_ids)),
        suspicious_events=len(suspicious_ids),
        findings=counts["findings"],
        pending_recommendations=len(store.list_recommendations(conn, "pending")),
        enforcement_results=counts["enforcement_results"],
        metrics=[
            {
                "key": "events_processed",
                "label": "Events processed",
                "value": counts["events"],
                "delta": 0,
                "tone": "neutral",
            },
            {
                "key": "active_alerts",
                "label": "Active alerts",
                "value": counts["findings"],
                "delta": 0,
                "tone": "negative",
            },
        ],
    )


@app.get("/v1/system-status")
def system_status() -> dict[str, Any]:
    return envelope(
        status="operational",
        appliance={
            "name": "local-ingestion",
            "model": "development",
            "mode": "observe",
            "address": "127.0.0.1",
            "egress": "Local only",
            "gpu": {"status": "unavailable"},
        },
        ingestion={"events_per_second": 0, "queue_depth": 0},
        model={"active_version": None},
        components=[{"name": "event_ingestion", "status": "operational"}],
    )


@app.get("/v1/rules")
def get_rules_json() -> dict[str, Any]:
    return envelope(rules=store.list_rules(conn))


@app.get("/v1/rules.txt")
def get_rules_txt() -> Response:
    body = "".join(f"{rule['destination']}\n" for rule in store.list_rules(conn))
    return Response(content=body, media_type="text/plain")


@app.get("/v1/rules/check")
def check_rule(dst: str) -> dict[str, Any]:
    return envelope(destination=dst, denied=store.is_denied(conn, dst))


def _require_version(payload: dict[str, Any], optional: bool = False) -> None:
    version = payload.get("schema_version")
    if version is None and optional:
        return
    if version != SCHEMA_VERSION:
        raise HTTPException(400, "schema_version must be 1.0")


def _finding_view(finding: dict[str, Any]) -> dict[str, Any]:
    events_by_id = {event["event_id"]: event for event in store.list_events(conn, 1000)}
    related = [
        events_by_id[event_id] for event_id in finding["event_ids"] if event_id in events_by_id
    ]
    recommendations = [
        recommendation
        for recommendation in store.list_recommendations(conn)
        if recommendation.get("finding_id") == finding["finding_id"]
    ]
    raw_evidence = finding.get("evidence", [])
    view = dict(finding)
    view.update(
        {
            "title": "Suspicious correlated activity",
            "status": "completed",
            "investigation_status": "unavailable",
            "actor": related[0].get("actor") if related else "business-agent",
            "destination": recommendations[0].get("target") if recommendations else None,
            "first_seen": related[0].get("timestamp") if related else None,
            "last_seen": related[-1].get("timestamp") if related else None,
            "timeline": [
                {
                    "schema_version": SCHEMA_VERSION,
                    "event_id": event["event_id"],
                    "timestamp": event.get("timestamp"),
                    "source_type": event.get("source_type"),
                    "action": event.get("action"),
                    "destination": event.get("destination", "local"),
                    "request_bytes": event.get("request_bytes", 0),
                }
                for event in related
            ],
            "evidence": [
                {
                    "code": item.get("detector", item.get("code", "evidence")),
                    "label": item.get("description", item.get("label", "Evidence")),
                    "score_contribution": item.get("points", item.get("score_contribution", 0)),
                    "event_ids": item.get("event_ids", finding["event_ids"]),
                }
                for item in raw_evidence
            ],
            "investigation": {
                "schema_version": SCHEMA_VERSION,
                "status": "unavailable",
                "summary": None,
                "served_model": None,
                "route": None,
            },
            "recommendation_ids": [
                recommendation["recommendation_id"] for recommendation in recommendations
            ],
        }
    )
    return view
