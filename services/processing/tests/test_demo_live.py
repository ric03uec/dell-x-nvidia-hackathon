from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from processing import demo_live
from processing.pipeline import detect_window


def test_demo_events_are_safe_unique_and_produce_real_rule_findings() -> None:
    start = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    normal = demo_live.normal_events(session_id="session", cycle=1, start=start, count=8, seed=7)
    suspicious = demo_live.suspicious_events(session_id="session", cycle=2, start=start)

    events = normal + suspicious
    assert len({event["event_id"] for event in events}) == len(events)
    assert all(event["schema_version"] == "1.0" for event in events)
    assert all(event["attributes"]["body_stored"] is False for event in events)
    assert all(event["attributes"]["openshell_run_id"] == demo_live.DEMO_RUN_ID for event in events)
    assert detect_window(normal, known_destinations=demo_live.KNOWN_DESTINATIONS).finding is None

    detection = detect_window(suspicious, known_destinations=demo_live.KNOWN_DESTINATIONS)
    assert detection.finding is not None
    assert detection.finding["severity"] == "critical"
    assert detection.risk_score == 100


def test_run_demo_posts_events_and_active_finding(monkeypatch: Any) -> None:
    posted: dict[str, list[dict[str, Any]]] = {
        "events": [],
        "findings": [],
        "recommendations": [],
    }

    class FakeClient:
        def __init__(self, ingestion_url: str) -> None:
            assert ingestion_url == "http://ingestion.test"

        def post_event(self, event: dict[str, Any]) -> None:
            posted["events"].append(event)

        def post_finding(self, finding: dict[str, Any]) -> None:
            posted["findings"].append(finding)

        def post_recommendation(self, recommendation: dict[str, Any]) -> None:
            posted["recommendations"].append(recommendation)

    monkeypatch.setattr(demo_live, "IngestionClient", FakeClient)
    demo_live.run_demo(
        "http://ingestion.test",
        interval=0,
        cycle_pause=0,
        normal_per_cycle=2,
        suspicious_every=2,
        cycles=3,
        sleep=lambda _: None,
    )

    assert len(posted["events"]) == 10
    assert len(posted["findings"]) == 1
    assert len(posted["recommendations"]) == 1
    assert posted["recommendations"][0]["action_type"] == "deny_destination"
    assert posted["recommendations"][0]["finding_id"] == posted["findings"][0]["finding_id"]
