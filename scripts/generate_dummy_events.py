#!/usr/bin/env python3
"""Generate deterministic, privacy-safe demo events.

The sequence is inspired by a mitmproxy capture, but contains only synthetic
values. It includes varied ordinary HTTP activity followed by a suspicious
read/stage/upload sequence. Expected policy outcomes are kept separately.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

METHODS = ("GET", "PUT", "PATCH", "DELETE", "POST")
APPROVED_DESTINATIONS = (
    "approved-api.demo.local",
    "artifacts.demo.local",
    "packages.demo.local",
    "telemetry.demo.local",
    "wiki.demo.local",
)
IDENTITIES = (
    ("business-agent", "demo-analyst", "gb10-demo"),
    ("build-agent", "ci-runner", "build-node-01"),
    ("finance-agent", "finance-ops", "finance-node-02"),
    ("support-agent", "support-ops", "support-node-03"),
    ("research-agent", "research-ops", "research-node-04"),
)
BASE_TIME = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)


def _timestamp(index: int) -> str:
    return (BASE_TIME + timedelta(seconds=index * 3)).isoformat().replace("+00:00", "Z")


def _event(
    index: int,
    *,
    source_type: str,
    action: str,
    destination: str,
    request_bytes: int = 0,
    attributes: dict[str, Any] | None = None,
    actor: str = "business-agent",
    user: str = "demo-analyst",
    device: str = "gb10-demo",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "event_id": f"evt-{index:03d}",
        "timestamp": _timestamp(index),
        "source_type": source_type,
        "actor": actor,
        "user": user,
        "device": device,
        "action": action,
        "destination": destination,
        "request_bytes": request_bytes,
        "attributes": {
            "flow_id": f"flow-{index:03d}",
            "openshell_run_id": "run-synthetic-001",
            "openclaw_agent_id": actor,
            **(attributes or {}),
        },
    }


def generate_events() -> list[dict[str, Any]]:
    """Return 100 input events followed by four expected outcome events."""
    events: list[dict[str, Any]] = []

    # Ninety-three varied requests to approved internal destinations.
    for index in range(1, 94):
        method = METHODS[(index - 1) % len(METHODS)]
        actor, user, device = IDENTITIES[(index - 1) % len(IDENTITIES)]
        destination_index = ((index - 1) // len(METHODS)) % len(APPROVED_DESTINATIONS)
        destination = APPROVED_DESTINATIONS[destination_index]
        events.append(
            _event(
                index,
                source_type="mitmproxy",
                action=f"http_{method.lower()}",
                destination=destination,
                request_bytes=0 if method == "GET" else 128 + (index * 137) % 250_000,
                actor=actor,
                user=user,
                device=device,
                attributes={
                    "method": method,
                    "path_template": "/anything/{item_id}",
                    "query_key_names": ["page"] if method == "GET" else [],
                    "request_content_type": "application/json" if method != "GET" else None,
                    "response_content_type": "application/json",
                    "response_status": 200,
                    "response_bytes": 512,
                    "json_field_names": ["index", "random", "run"] if method != "GET" else [],
                    "duration_ms": 20 + index % 45,
                },
            )
        )

    # Cross-source activity provides the context that makes the upload suspicious.
    events.append(
        _event(
            94,
            source_type="openshell",
            action="file_read",
            destination="local-sensitive-data",
            attributes={"resource_class": "customer-records", "openshell_action_id": "action-094"},
        )
    )
    events.append(
        _event(
            95,
            source_type="openshell",
            action="archive_create",
            destination="local-staging",
            request_bytes=25_000_000,
            attributes={"resource_class": "staged-archive", "openshell_action_id": "action-095"},
        )
    )

    for index, method in enumerate(METHODS, start=96):
        is_upload = method == "POST"
        events.append(
            _event(
                index,
                source_type="mitmproxy",
                action=f"http_{method.lower()}",
                destination="new-receiver.demo.local",
                request_bytes=25_000_000 if is_upload else 256,
                attributes={
                    "method": method,
                    "path_template": "/ingest/{run_id}",
                    "query_key_names": [],
                    "request_content_type": "application/json",
                    "response_content_type": "application/json",
                    "response_status": 200,
                    "response_bytes": 384,
                    # Keep field names for detection; omit field values and bodies.
                    "json_field_names": (
                        ["index", "random", "run", "token"] if is_upload else ["index"]
                    ),
                    "sensitive_field_names": ["token"] if is_upload else [],
                    "body_stored": False,
                    "duration_ms": 35 + index,
                },
            )
        )

    events.append(
        _event(
            101,
            source_type="security-agent",
            action="policy_recommended",
            destination="new-receiver.demo.local",
            attributes={
                "action_type": "deny_destination",
                "recommendation_id": "rec-synthetic-001",
            },
        )
    )
    events.append(
        _event(
            102,
            source_type="dashboard",
            action="policy_approved",
            destination="new-receiver.demo.local",
            attributes={"recommendation_id": "rec-synthetic-001", "decision": "approved"},
        )
    )
    events.append(
        _event(
            103,
            source_type="mitmproxy",
            action="http_post",
            destination="new-receiver.demo.local",
            request_bytes=25_000_000,
            attributes={
                "method": "POST",
                "path_template": "/ingest/{run_id}",
                "response_status": 403,
                "json_field_names": ["index", "random", "run", "token"],
                "sensitive_field_names": ["token"],
                "body_stored": False,
                "blocked": True,
            },
        )
    )
    events.append(
        _event(
            104,
            source_type="openshell",
            action="network_denied",
            destination="new-receiver.demo.local",
            attributes={
                "openshell_action_id": "action-104",
                "recommendation_id": "rec-synthetic-001",
                "enforcement_point": "network_policy",
            },
        )
    )
    return events


def expected_outcomes() -> dict[str, Any]:
    """Return fixture truth separately so labels do not leak into input events."""
    return {
        "schema_version": "1.0",
        "normal_event_ids": [f"evt-{index:03d}" for index in range(1, 94)],
        "suspicious_event_ids": [f"evt-{index:03d}" for index in range(94, 101)],
        "recommendation_event_id": "evt-101",
        "approval_event_id": "evt-102",
        "blocked_event_ids": ["evt-103", "evt-104"],
        "expected_action_type": "deny_destination",
        "expected_destination": "new-receiver.demo.local",
    }


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events))


def _post_events(url: str, events: list[dict[str, Any]], timeout: float) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--post-to must be an absolute HTTP(S) URL")

    for position, event in enumerate(events, start=1):
        request = Request(
            url,
            data=json.dumps(event).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            # Deliberately do not print response bodies: an echo endpoint could
            # duplicate event data or future sensitive values.
            with urlopen(request, timeout=timeout) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"API returned HTTP {response.status}")
        except HTTPError as error:
            raise RuntimeError(
                f"failed to post {event['event_id']}: API returned HTTP {error.code}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"failed to post {event['event_id']}: {error.reason}") from error
        print(
            f"posted {position}/{len(events)} {event['event_id']}",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write events.jsonl and expected.json.",
    )
    parser.add_argument(
        "--post-to",
        metavar="URL",
        help=(
            "POST each event as JSON to an ingestion endpoint, such as "
            "http://localhost:8100/v1/events."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds (default: 10).",
    )
    parser.add_argument(
        "--event-count",
        type=int,
        help="Use only the first N generated input events.",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    events = generate_events()
    if args.event_count is not None:
        if not 1 <= args.event_count <= len(events):
            parser.error(f"--event-count must be between 1 and {len(events)}")
        events = events[: args.event_count]
    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(args.output_dir / "events.jsonl", events)
        (args.output_dir / "expected.json").write_text(
            json.dumps(expected_outcomes(), indent=2, sort_keys=True) + "\n"
        )

    if args.post_to is not None:
        try:
            _post_events(args.post_to, events, args.timeout)
        except (RuntimeError, ValueError) as error:
            parser.exit(1, f"error: {error}\n")

    if args.output_dir is None and args.post_to is None:
        for event in events:
            print(json.dumps(event, sort_keys=True))


if __name__ == "__main__":
    main()
