"""Continuous privacy-safe demo traffic and finding generation."""

from __future__ import annotations

import random
import time
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from processing.client import IngestionClient
from processing.pipeline import detect_window, recommend_policy

DEMO_RUN_ID = "run-synthetic-001"
KNOWN_DESTINATIONS = {"approved-api.demo.local", "packages.demo.local"}
ACTORS = ("finance-agent", "support-agent", "build-agent")


class DemoInvestigator:
    """Deterministic prose for a demo; no inference call is implied."""

    def investigate(self, evidence: Mapping[str, Any]) -> Mapping[str, str]:
        return {
            "summary": "Sensitive access, staging, and a large transfer were correlated.",
            "reason": "Deterministic evidence exceeded the review threshold.",
        }


def _event(
    event_id: str,
    timestamp: datetime,
    *,
    actor: str,
    source_type: str,
    action: str,
    destination: str,
    request_bytes: int = 0,
    attributes: dict[str, Any] | None = None,
    session_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "timestamp": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_type": source_type,
        "actor": actor,
        "action": action,
        "destination": destination,
        "request_bytes": request_bytes,
        "attributes": {
            "openshell_run_id": DEMO_RUN_ID,
            "demo_session_id": session_id,
            "body_stored": False,
            **(attributes or {}),
        },
    }


def normal_events(
    *, session_id: str, cycle: int, start: datetime, count: int, seed: int
) -> list[dict[str, Any]]:
    randomizer = random.Random((seed * 1_000_003) + cycle)
    events = []
    for index in range(count):
        actor = randomizer.choice(ACTORS)
        destination = randomizer.choice(tuple(sorted(KNOWN_DESTINATIONS)))
        method = randomizer.choice(("GET", "GET", "POST", "PUT"))
        events.append(
            _event(
                f"demo-{session_id}-{cycle:04d}-normal-{index:03d}",
                start + timedelta(seconds=index),
                actor=actor,
                source_type="mitmproxy",
                action=f"http_{method.lower()}",
                destination=destination,
                request_bytes=0 if method == "GET" else randomizer.randint(128, 16_384),
                attributes={
                    "method": method,
                    "response_status": randomizer.choice((200, 200, 201, 204)),
                    "response_bytes": randomizer.randint(256, 65_536),
                    "duration_ms": randomizer.randint(12, 240),
                    "json_field_names": ["record_id", "status"] if method != "GET" else [],
                },
                session_id=session_id,
            )
        )
    return events


def suspicious_events(*, session_id: str, cycle: int, start: datetime) -> list[dict[str, Any]]:
    actor = ACTORS[cycle % len(ACTORS)]
    destination = f"dropzone-{cycle % 7}.demo.invalid"
    prefix = f"demo-{session_id}-{cycle:04d}-risk"
    critical = cycle % 2 == 0
    common = {"correlation_id": f"corr-{session_id}-{cycle:04d}"}
    return [
        _event(
            f"{prefix}-001",
            start,
            actor=actor,
            source_type="openshell",
            action="sensitive_file_read",
            destination="local-customer-records",
            attributes={**common, "sensitive": True, "resource_class": "customer-records"},
            session_id=session_id,
        ),
        _event(
            f"{prefix}-002",
            start + timedelta(seconds=1),
            actor=actor,
            source_type="openshell",
            action="archive_create",
            destination="local-staging",
            request_bytes=24_000_000,
            attributes={**common, "archive_format": "zip"},
            session_id=session_id,
        ),
        _event(
            f"{prefix}-003",
            start + timedelta(seconds=2),
            actor=actor,
            source_type="mitmproxy",
            action="network_connect",
            destination=destination,
            request_bytes=512,
            attributes={**common, "method": "CONNECT", "response_status": 200},
            session_id=session_id,
        ),
        _event(
            f"{prefix}-004",
            start + timedelta(seconds=3),
            actor=actor,
            source_type="mitmproxy",
            action="http_post",
            destination=destination,
            request_bytes=24_000_000,
            attributes={
                **common,
                "method": "POST",
                "response_status": 202,
                "json_field_names": ["record_id", "authorization"] if critical else ["record_id"],
                "outside_work_hours": critical,
            },
            session_id=session_id,
        ),
    ]


def run_demo(
    ingestion_url: str,
    *,
    interval: float = 1.0,
    cycle_pause: float = 3.0,
    normal_per_cycle: int = 5,
    suspicious_every: int = 3,
    cycles: int | None = None,
    seed: int = 42,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    if interval < 0 or cycle_pause < 0:
        raise ValueError("intervals must not be negative")
    if normal_per_cycle < 1 or suspicious_every < 1:
        raise ValueError("normal_per_cycle and suspicious_every must be positive")
    client = IngestionClient(ingestion_url)
    session_id = uuid.uuid4().hex[:10]
    cycle = 1
    while cycles is None or cycle <= cycles:
        started = datetime.now(timezone.utc)
        normal = normal_events(
            session_id=session_id,
            cycle=cycle,
            start=started,
            count=normal_per_cycle,
            seed=seed,
        )
        for event in normal:
            client.post_event(event)
            print(f"normal event {event['event_id']} -> {event['destination']}", flush=True)
            sleep(interval)

        if cycle % suspicious_every == 0:
            risk_events = suspicious_events(
                session_id=session_id,
                cycle=cycle,
                start=datetime.now(timezone.utc),
            )
            for event in risk_events:
                client.post_event(event)
                print(f"risk event {event['event_id']} -> {event['destination']}", flush=True)
                sleep(interval)
            detection = detect_window(risk_events, known_destinations=KNOWN_DESTINATIONS)
            if detection.finding is None:
                raise RuntimeError("synthetic risk scenario did not produce a finding")
            finding, recommendation = recommend_policy(detection, DemoInvestigator())
            client.post_finding(finding)
            client.post_recommendation(recommendation)
            print(
                f"active finding {finding['finding_id']} risk={finding['risk_score']} "
                f"recommendation={recommendation['recommendation_id']}",
                flush=True,
            )
        cycle += 1
        if cycles is None or cycle <= cycles:
            sleep(cycle_pause)
