#!/usr/bin/env python3
"""Local stdlib-only mock API for the SquidWard dashboard."""

from __future__ import annotations

import importlib.util
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlsplit


SCHEMA_VERSION = "1.0"
FINDING_ID = "fnd-synthetic-001"
RECOMMENDATION_ID = "rec-synthetic-001"


def _load_dummy_events() -> list[dict[str, Any]]:
    """Load the canonical event generator without relying on the current directory."""
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        generator_path = parent / "scripts" / "generate_dummy_events.py"
        if generator_path.is_file():
            spec = importlib.util.spec_from_file_location(
                "squidward_generate_dummy_events", generator_path
            )
            if spec is None or spec.loader is None:
                break
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.generate_events()
    raise RuntimeError("could not locate scripts/generate_dummy_events.py from mock API")


ALL_DUMMY_EVENTS = _load_dummy_events()
EVENTS_BY_ID = {event["event_id"]: event for event in ALL_DUMMY_EVENTS}
SOURCE_EVENTS = tuple(ALL_DUMMY_EVENTS[:22])
GENERATED_AT = SOURCE_EVENTS[-1]["timestamp"]
SUSPICIOUS_RISK = {
    "evt-016": 45,
    "evt-017": 58,
    "evt-018": 61,
    "evt-019": 67,
    "evt-020": 73,
    "evt-021": 84,
    "evt-022": 92,
}


def _response(**values: Any) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, **values}


def _error(code: str, message: str) -> dict[str, Any]:
    return _response(error={"code": code, "message": message})


def _evidence(event: dict[str, Any]) -> dict[str, Any]:
    attributes = event["attributes"]
    detail_by_action = {
        "file_read": "Customer-record data was read before staging activity.",
        "archive_create": "A 25 MB archive was created in local staging.",
        "http_get": "The agent contacted a previously unseen receiver with GET.",
        "http_put": "The agent contacted a previously unseen receiver with PUT.",
        "http_patch": "The agent contacted a previously unseen receiver with PATCH.",
        "http_delete": "The agent contacted a previously unseen receiver with DELETE.",
        "http_post": "A 25 MB POST containing a sensitive field name was sent.",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": event["event_id"],
        "timestamp": event["timestamp"],
        "source_type": event["source_type"],
        "action": event["action"],
        "destination": event["destination"],
        "request_bytes": event["request_bytes"],
        "detail": detail_by_action[event["action"]],
        "flow_id": attributes["flow_id"],
    }


class MockApi:
    """Pure response/state model shared by the HTTP handler and unit tests."""

    def __init__(self) -> None:
        self._decision: dict[str, Any] | None = None
        self._lock = Lock()

    def _recommendation(self) -> dict[str, Any]:
        status = self._decision["decision"] if self._decision else "pending"
        recommendation = {
            "schema_version": SCHEMA_VERSION,
            "recommendation_id": RECOMMENDATION_ID,
            "finding_id": FINDING_ID,
            "status": status,
            "action_type": "deny_destination",
            "destination": "new-receiver.demo.local",
            "reason": "Prevent repeat transfer to the destination identified in the finding.",
            "created_at": EVENTS_BY_ID["evt-022"]["timestamp"],
            "constraints": {
                "destination": "new-receiver.demo.local",
                "actor": "business-agent",
                "scope": "network_egress",
            },
        }
        if self._decision:
            recommendation["decision"] = dict(self._decision)
        return recommendation

    def _finding(self) -> dict[str, Any]:
        suspicious_events = SOURCE_EVENTS[15:22]
        return {
            "schema_version": SCHEMA_VERSION,
            "finding_id": FINDING_ID,
            "title": "Sensitive archive transferred to a new destination",
            "severity": "critical",
            "risk_score": 92,
            "status": "completed",
            "investigation_status": "completed",
            "actor": "business-agent",
            "destination": "new-receiver.demo.local",
            "first_seen": suspicious_events[0]["timestamp"],
            "last_seen": suspicious_events[-1]["timestamp"],
            "summary": "A sensitive-data read and archive creation preceded a 25 MB upload.",
            "event_ids": [event["event_id"] for event in suspicious_events],
            "timeline": [_evidence(event) for event in suspicious_events],
            "evidence": [
                {
                    "code": "sensitive_read",
                    "label": "Sensitive customer records were read",
                    "score_contribution": 22,
                    "event_ids": ["evt-016"],
                },
                {
                    "code": "archive_staging",
                    "label": "A 25 MB archive was staged",
                    "score_contribution": 18,
                    "event_ids": ["evt-017"],
                },
                {
                    "code": "new_destination",
                    "label": "Transfer targeted a previously unseen destination",
                    "score_contribution": 20,
                    "event_ids": ["evt-018", "evt-019", "evt-020", "evt-021", "evt-022"],
                },
                {
                    "code": "large_transfer",
                    "label": "A 25 MB transfer followed the staging sequence",
                    "score_contribution": 32,
                    "event_ids": ["evt-022"],
                },
            ],
            "investigation": {
                "status": "completed",
                "summary": "The local security agent correlated a sensitive read, archive staging, and a large transfer to a new receiver.",
                "served_model": "Qwen3.6-27B-FP8",
                "route": "nemoclaw-local",
            },
            "recommendation_ids": [RECOMMENDATION_ID],
        }

    def _source_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for event in SOURCE_EVENTS:
            projection = dict(event)
            risk_score = SUSPICIOUS_RISK.get(event["event_id"])
            if risk_score is not None:
                projection["risk_score"] = risk_score
                projection["finding_id"] = FINDING_ID
            events.append(projection)
        return events

    def _enforcement_results(self) -> list[dict[str, Any]]:
        if not self._decision or self._decision["decision"] != "approved":
            return []
        return [
            {
                "schema_version": SCHEMA_VERSION,
                "enforcement_result_id": "enf-synthetic-001",
                "recommendation_id": RECOMMENDATION_ID,
                "status": "applied",
                "event_id": "evt-025",
                "observed_at": EVENTS_BY_ID["evt-025"]["timestamp"],
                "destination": "new-receiver.demo.local",
            },
            {
                "schema_version": SCHEMA_VERSION,
                "enforcement_result_id": "enf-synthetic-002",
                "recommendation_id": RECOMMENDATION_ID,
                "status": "block_observed",
                "event_id": "evt-026",
                "observed_at": EVENTS_BY_ID["evt-026"]["timestamp"],
                "destination": "new-receiver.demo.local",
            },
        ]

    def get(self, path: str, query: dict[str, list[str]] | None = None) -> tuple[int, dict[str, Any]]:
        query = query or {}
        if path == "/health":
            return 200, _response(status="ok", generated_at=GENERATED_AT)
        if path == "/v1/system-status":
            return 200, _response(
                generated_at=GENERATED_AT,
                status="operational",
                appliance={
                    "name": "gb10-demo",
                    "model": "GB10",
                    "mode": "observe",
                    "address": "127.0.0.1",
                    "egress": "Verified blocked",
                    "gpu": {
                        "utilization_percent": 62,
                        "memory_used_bytes": 24_100_000_000,
                        "memory_total_bytes": 119_700_000_000,
                    },
                },
                ingestion={"events_per_second": 7.3, "queue_depth": 0},
                model={
                    "active_version": "Qwen3.6-27B-FP8",
                    "advertised_model": "Qwen3.6-27B-FP8",
                    "loaded_model": "Qwen3.6-27B-FP8",
                    "route_match": True,
                },
                components=[
                    {"name": "event_ingestion", "status": "operational"},
                    {"name": "investigation", "status": "operational"},
                    {"name": "policy_enforcement", "status": "operational"},
                ],
            )
        if path == "/v1/metrics/summary":
            return 200, _response(
                generated_at=GENERATED_AT,
                total_events=22,
                normal_events=15,
                suspicious_events=7,
                findings=1,
                pending_recommendations=0 if self._decision else 1,
                enforcement_results=len(self._enforcement_results()),
                metrics=[
                    {"key": "events_processed", "label": "Events processed", "value": 22, "delta": 7, "tone": "neutral"},
                    {"key": "active_alerts", "label": "Active alerts", "value": 1, "delta": 1, "tone": "negative"},
                    {"key": "avg_risk_score", "label": "Avg. risk score", "value": 68.6, "delta": -3.1, "tone": "positive"},
                    {"key": "services_online", "label": "Services online", "value": 3, "delta": 0, "tone": "neutral"},
                ],
            )
        if path == "/v1/events":
            return 200, _response(
                generated_at=GENERATED_AT,
                count=len(SOURCE_EVENTS),
                events=self._source_events(),
            )
        if path == "/v1/findings":
            return 200, _response(generated_at=GENERATED_AT, count=1, findings=[self._finding()])
        if path == f"/v1/findings/{FINDING_ID}":
            return 200, _response(generated_at=GENERATED_AT, finding=self._finding())
        if path == "/v1/recommendations":
            recommendations = [self._recommendation()]
            requested_status = query.get("status", [None])[0]
            if requested_status is not None:
                recommendations = [
                    item for item in recommendations if item["status"] == requested_status
                ]
            return 200, _response(
                generated_at=GENERATED_AT,
                count=len(recommendations),
                recommendations=recommendations,
            )
        if path == "/v1/enforcement-results":
            results = self._enforcement_results()
            generated_at = results[-1]["observed_at"] if results else GENERATED_AT
            return 200, _response(
                generated_at=generated_at,
                count=len(results),
                enforcement_results=results,
            )
        return 404, _error("not_found", f"no mock resource exists at {path}")

    def decide(self, payload: Any) -> tuple[int, dict[str, Any]]:
        if not isinstance(payload, dict):
            return 400, _error("invalid_request", "request body must be a JSON object")
        if payload.get("schema_version") != SCHEMA_VERSION:
            return 400, _error("invalid_schema_version", "schema_version must be 1.0")
        decision = payload.get("decision")
        if decision not in {"approved", "rejected"}:
            return 400, _error("invalid_decision", "decision must be approved or rejected")

        with self._lock:
            if self._decision and self._decision["decision"] != decision:
                return 409, _response(
                    error={
                        "code": "decision_conflict",
                        "message": "recommendation already has a conflicting decision",
                    },
                    decision=dict(self._decision),
                )
            if self._decision is None:
                self._decision = {
                    "schema_version": SCHEMA_VERSION,
                    "recommendation_id": RECOMMENDATION_ID,
                    "decision": decision,
                    "decided_at": EVENTS_BY_ID["evt-024"]["timestamp"],
                }
            return 200, _response(decision=dict(self._decision))


class MockRequestHandler(BaseHTTPRequestHandler):
    api = MockApi()

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        status, payload = self.api.get(request.path, parse_qs(request.query))
        self._write_json(status, payload)

    def do_POST(self) -> None:
        request = urlsplit(self.path)
        expected_path = f"/v1/recommendations/{RECOMMENDATION_ID}/decision"
        if request.path != expected_path:
            self._write_json(404, _error("not_found", f"no mock resource exists at {request.path}"))
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(400, _error("invalid_content_length", "Content-Length must be an integer"))
            return
        if content_length <= 0 or content_length > 1_000_000:
            self._write_json(400, _error("invalid_body", "request body must contain at most 1000000 bytes"))
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._write_json(400, _error("invalid_json", "request body must be valid JSON"))
            return
        status, response = self.api.decide(payload)
        self._write_json(status, response)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()


def main() -> None:
    host = os.environ.get("MOCK_API_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("MOCK_API_PORT", "8100"))
    except ValueError as error:
        raise SystemExit("MOCK_API_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise SystemExit("MOCK_API_PORT must be between 1 and 65535")
    server = ThreadingHTTPServer((host, port), MockRequestHandler)
    print(f"SquidWard mock API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
