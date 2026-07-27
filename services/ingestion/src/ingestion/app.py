"""Durable REST, MCP, and Squid-rules surfaces for SquidWard ingestion."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastmcp import FastMCP
from pydantic import BaseModel, Field, StringConstraints

from . import store
from .openclaw import OpenClawClient, OpenClawError
from .runtime import GpuTelemetryCollector, inference_status, observed_at
from .vulnerabilities import CisaKevFeed, VulnerabilityFeedError

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


class EventAssessmentIn(BaseModel):
    schema_version: Literal["1.0"]
    event_id: str
    risk_score: float = Field(ge=0, le=100)
    model_version: str


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
    enforcement_result_id: str | None = None
    recommendation_id: str
    status: Literal["applied", "failed"]
    enforcement_point: str
    policy_version: str | None = None


class ApprovalIn(BaseModel):
    model_config = {"extra": "allow"}

    schema_version: Literal["1.0"]
    recommendation_id: str
    decision: Literal["approved", "rejected"]
    analyst: str = Field(min_length=1)
    timestamp: str


class VulnerabilityPolicyIn(BaseModel):
    schema_version: Literal["1.0"]
    cve_id: str
    disposition: Literal["rejected"]
    analyst: str = Field(min_length=1)


class RecommendationNoteIn(BaseModel):
    schema_version: Literal["1.0"]
    # Stripped before the length check so whitespace cannot become a blank audit entry.
    analyst: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


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
def submit_finding(
    finding_id: str,
    event_ids: list[str],
    risk_score: float,
    severity: Literal["low", "medium", "high", "critical"],
    summary: str = "",
    detectors: list[str] | None = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    """Record a canonical detector finding over persisted events."""
    store.put_finding(
        conn,
        {
            "schema_version": SCHEMA_VERSION,
            "finding_id": finding_id,
            "event_ids": event_ids,
            "risk_score": risk_score,
            "severity": severity,
            "detectors": detectors or [],
            "summary": summary,
            "model_version": model_version,
        },
    )
    return {"finding_id": finding_id}


@mcp.tool
def submit_investigation(
    finding_id: str,
    status: Literal["completed", "failed"],
    summary: str | None = None,
    served_model: str | None = None,
) -> dict[str, Any]:
    """Persist the local security agent's analysis for a finding."""
    investigation = store.put_investigation(
        conn, finding_id, status, summary=summary, served_model=served_model
    )
    return (
        {"investigation": investigation}
        if investigation
        else {"error": f"no such finding: {finding_id}"}
    )


@mcp.tool
def recommend_policy(
    finding_id: str,
    target: str,
    scope: str,
    reason: str,
    expires_at: str | None = None,
    action_type: ActionType = "deny_destination",
) -> dict[str, Any]:
    """Recommend a constrained action; enforcement still requires approval."""
    recommendation_id = f"rec-{uuid.uuid4().hex[:12]}"
    store.put_recommendation(
        conn,
        {
            "schema_version": SCHEMA_VERSION,
            "recommendation_id": recommendation_id,
            "finding_id": finding_id,
            "action_type": action_type,
            "target": target,
            "scope": scope,
            "reason": reason,
            "expires_at": expires_at,
        },
    )
    return {"recommendation_id": recommendation_id, "status": "pending"}


mcp_app = mcp.http_app(path="/")
app = FastAPI(title="squidward-ingestion", lifespan=mcp_app.lifespan)
app.mount("/mcp", mcp_app)
app.state.gpu_collector = GpuTelemetryCollector()
app.state.openclaw = OpenClawClient.from_env()
app.state.vulnerability_feed = CisaKevFeed()


@app.get("/health")
def health() -> dict[str, Any]:
    ok = store.healthy(conn)
    return envelope(status="ok" if ok else "degraded", database=ok)


@app.post("/v1/events", status_code=201)
def post_events(events: list[EventIn] | EventIn) -> dict[str, Any]:
    batch = events if isinstance(events, list) else [events]
    records = [event.model_dump(exclude_none=True) for event in batch]
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
    assessments = store.event_assessments(conn, [str(event["event_id"]) for event in events])
    for event in events:
        assessment = assessments.get(str(event["event_id"]))
        if assessment:
            event.update(assessment)
    findings = store.list_findings(conn)
    for event in events:
        for finding in findings:
            if event.get("event_id") in finding["event_ids"]:
                event["finding_id"] = finding["finding_id"]
                event.setdefault("risk_score", finding["risk_score"])
                break
    return envelope(count=len(events), events=events)


@app.get("/v1/vulnerabilities")
def get_vulnerabilities(
    request: Request, limit: int = Query(default=25, ge=1, le=100)
) -> dict[str, Any]:
    try:
        catalog = request.app.state.vulnerability_feed.get(limit)
    except VulnerabilityFeedError as error:
        raise HTTPException(503, str(error)) from error
    return envelope(**catalog, policies=store.list_vulnerability_policies(conn))


@app.post("/v1/vulnerability-policies/{cve_id}", status_code=201)
def post_vulnerability_policy(cve_id: str, policy: VulnerabilityPolicyIn) -> dict[str, Any]:
    if policy.cve_id != cve_id:
        raise HTTPException(400, "cve_id does not match path")
    if not re.fullmatch(r"CVE-\d{4}-\d{4,}", cve_id):
        raise HTTPException(400, "cve_id must be a valid CVE identifier")
    persisted = store.put_vulnerability_policy(conn, cve_id, policy.analyst)
    return envelope(policy=persisted)


@app.delete("/v1/vulnerability-policies/{cve_id}")
def delete_vulnerability_policy(cve_id: str) -> dict[str, Any]:
    return envelope(cve_id=cve_id, removed=store.delete_vulnerability_policy(conn, cve_id))


@app.post("/v1/event-assessments", status_code=201)
def post_event_assessments(
    assessments: list[EventAssessmentIn] | EventAssessmentIn,
) -> dict[str, Any]:
    batch = assessments if isinstance(assessments, list) else [assessments]
    accepted = store.put_event_assessments(conn, [assessment.model_dump() for assessment in batch])
    return envelope(accepted=accepted)


@app.delete("/v1/demo-data")
def delete_demo_data() -> dict[str, Any]:
    """Remove synthetic demo records without touching captured production data."""
    return envelope(removed=store.clear_demo_data(conn))


@app.post("/v1/findings", status_code=201)
def post_finding(
    finding: FindingIn, request: Request, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    finding_id = store.put_finding(conn, finding.model_dump(exclude_none=True))
    investigation_status = None
    client: OpenClawClient | None = request.app.state.openclaw
    current = store.get_investigation(conn, finding_id)
    if (
        finding.severity in {"high", "critical"}
        and client is not None
        and (current is None or current["status"] == "failed")
    ):
        store.put_investigation(conn, finding_id, "running")
        background_tasks.add_task(_run_investigation, finding_id, client)
        investigation_status = "running"
    elif current is not None:
        investigation_status = current["status"]
    return envelope(
        finding_id=finding_id,
        accepted=True,
        investigation_status=investigation_status,
    )


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


@app.post("/v1/findings/{finding_id}/investigate", response_model=None)
def investigate(
    finding_id: str, payload: dict[str, Any], request: Request
) -> Response | dict[str, Any]:
    _require_version(payload)
    if store.get_finding(conn, finding_id) is None:
        raise HTTPException(404, "no such finding")
    current = store.get_investigation(conn, finding_id)
    if current and current["status"] in {"running", "completed"}:
        return envelope(investigation=current)
    client: OpenClawClient | None = request.app.state.openclaw
    if client is None:
        failed = store.put_investigation(
            conn, finding_id, "failed", error="OpenClaw gateway is not configured"
        )
        return JSONResponse(
            status_code=503,
            content=envelope(
                error={"code": "openclaw_unconfigured", "message": "OpenClaw is unavailable"},
                investigation=failed,
            ),
        )
    store.put_investigation(conn, finding_id, "running")
    result, error_code = _run_investigation(finding_id, client)
    if error_code:
        return JSONResponse(
            status_code=502,
            content=envelope(
                error={"code": error_code, "message": result["error"]},
                investigation=result,
            ),
        )
    return envelope(investigation=result)


@app.post("/v1/recommendations", status_code=201)
def post_recommendation(recommendation: RecommendationIn) -> dict[str, Any]:
    recommendation_id = store.put_recommendation(conn, recommendation.model_dump())
    return envelope(recommendation_id=recommendation_id, accepted=True)


@app.get("/v1/recommendations")
def get_recommendations(status: str | None = None) -> dict[str, Any]:
    recommendations = store.list_recommendations(conn, status)
    notes = store.notes_for_recommendations(
        conn, [str(item["recommendation_id"]) for item in recommendations]
    )
    for recommendation in recommendations:
        decision = store.get_decision(conn, recommendation["recommendation_id"])
        if decision:
            recommendation["decision"] = decision
        recommendation["notes"] = notes.get(str(recommendation["recommendation_id"]), [])
    return envelope(count=len(recommendations), recommendations=recommendations)


@app.post("/v1/recommendations/{recommendation_id}/decision")
def post_decision(recommendation_id: str, decision: ApprovalIn) -> dict[str, Any]:
    if decision.recommendation_id != recommendation_id:
        raise HTTPException(400, "recommendation_id does not match path")
    payload = decision.model_dump()
    try:
        recommendation = store.decide(
            conn,
            recommendation_id,
            decision.decision == "approved",
            decision.analyst,
            payload,
        )
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    if recommendation is None:
        raise HTTPException(404, "no such recommendation")
    recommendation["decision"] = payload
    return envelope(recommendation=recommendation, decision=payload)


@app.post("/v1/recommendations/{recommendation_id}/notes", status_code=201)
def post_recommendation_note(
    recommendation_id: str, payload: RecommendationNoteIn
) -> dict[str, Any]:
    if store.get_recommendation(conn, recommendation_id) is None:
        raise HTTPException(404, "no such recommendation")
    note = store.add_recommendation_note(conn, recommendation_id, payload.analyst, payload.note)
    return envelope(note=note)


@app.get("/v1/policies/approved")
def get_approved_policies(after_id: str | None = None) -> dict[str, Any]:
    policies = store.approved_policies(conn, after_id)
    return envelope(count=len(policies), policies=policies)


@app.post("/v1/enforcement-results", status_code=201)
def post_enforcement_result(result: EnforcementResultIn) -> dict[str, Any]:
    payload = result.model_dump(exclude_none=True)
    payload["enforcement_result_id"] = result.enforcement_result_id or (
        f"enf-{uuid.uuid4().hex[:12]}"
    )
    result_id = store.put_enforcement_result(conn, payload)
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
                "tone": "neutral",
            },
            {
                "key": "active_alerts",
                "label": "Active alerts",
                "value": counts["findings"],
                "tone": "negative",
            },
            {
                "key": "suspicious_events",
                "label": "Suspicious events",
                "value": len(suspicious_ids),
                "tone": "negative",
            },
            {
                "key": "pending_recommendations",
                "label": "Pending recommendations",
                "value": len(store.list_recommendations(conn, "pending")),
                "tone": "neutral",
            },
        ],
    )


@app.get("/v1/system-status")
def system_status(request: Request) -> dict[str, Any]:
    database_ok = store.healthy(conn)
    gpu = request.app.state.gpu_collector.collect()
    model = inference_status()
    healthy = database_ok and gpu["status"] == "healthy" and model["status"] == "healthy"
    return envelope(
        generated_at=observed_at(),
        status="operational" if healthy else "degraded",
        appliance={
            "name": os.environ.get("APPLIANCE_NAME", "gb10"),
            "model": "GB10",
            "mode": os.environ.get("APPLIANCE_MODE", "observe"),
            "address": os.environ.get("MGMT_BIND_ADDR", "127.0.0.1"),
            "egress": os.environ.get("APPLIANCE_EGRESS_STATUS"),
            "gpu": gpu,
        },
        ingestion={"events_per_second": None, "queue_depth": None},
        model=model,
        components=[
            {"name": "event_ingestion", "status": "operational" if database_ok else "degraded"},
            {
                "name": "openclaw",
                "status": "configured" if request.app.state.openclaw else "unavailable",
            },
            {"name": "gpu", "status": gpu["status"]},
            {"name": "inference", "status": model["status"]},
        ],
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


def _run_investigation(
    finding_id: str, client: OpenClawClient
) -> tuple[dict[str, Any], str | None]:
    try:
        client.investigate(finding_id)
    except OpenClawError as error:
        failed = store.put_investigation(conn, finding_id, "failed", error=str(error))
        assert failed is not None
        return failed, "openclaw_failed"

    completed = store.get_investigation(conn, finding_id)
    if completed is None or completed["status"] != "completed":
        message = "OpenClaw did not persist an investigation"
        failed = store.put_investigation(conn, finding_id, "failed", error=message)
        assert failed is not None
        return failed, "investigation_not_persisted"
    return completed, None


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
    investigation = store.get_investigation(conn, finding["finding_id"])
    if investigation is None:
        investigation = {
            "schema_version": SCHEMA_VERSION,
            "status": "pending" if app.state.openclaw else "unavailable",
            "summary": None,
            "served_model": None,
            "route": "openclaw-local" if app.state.openclaw else None,
        }
    view.update(
        {
            "title": "Suspicious correlated activity",
            "status": "completed",
            "investigation_status": investigation["status"],
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
            "investigation": investigation,
            "recommendation_ids": [
                recommendation["recommendation_id"] for recommendation in recommendations
            ],
        }
    )
    return view
