#!/usr/bin/env python3
"""Seed a review queue of policy recommendations for the Analyst Feedback page.

Recommendations normally come from the OpenClaw investigation, which is not
always running. This posts a deterministic, synthetic queue instead so the
review workflow (comment, approve, reject) has something to act on.

The values are synthetic. Destinations use reserved or clearly-fake names and
the analysts are role labels, not people.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1.0"
BASE_TIME = datetime(2026, 7, 26, 15, 0, tzinfo=timezone.utc)

# (target, scope, reason, decision, [(analyst, note), ...])
SEEDS: tuple[tuple[str, str, str, str | None, tuple[tuple[str, str], ...]], ...] = (
    (
        "pastebin.com:443",
        "business-agent",
        "Agent uploaded 4.1 MB to a paste service it has never contacted before, "
        "eight seconds after reading a credentials file.",
        None,
        (),
    ),
    (
        "anon-files.example:443",
        "business-agent",
        "Deterministic evidence exceeded the review threshold: unapproved "
        "destination, outbound volume 12x the agent's rolling median.",
        None,
        (
            ("soc-tier1", "Volume is real but this fired during the nightly backup window."),
            (
                "soc-tier2",
                "Backup targets artifacts.demo.local, not this host. Keeping it queued.",
            ),
        ),
    ),
    (
        "unknown-storage.example:443",
        "business-agent",
        "First contact with an unclassified object store, followed by a sustained "
        "PUT sequence totalling 38 MB.",
        "approved",
        (("soc-tier2", "Confirmed with the platform team that nothing should egress here."),),
    ),
    (
        "raw.githubusercontent.com:443",
        "build-agent",
        "Outbound transfer to a public content host outside the approved list.",
        "rejected",
        (
            ("soc-tier1", "This is the build agent pulling pinned action definitions."),
            ("soc-tier2", "Agreed, false positive. Should be on the approved list instead."),
        ),
    ),
    (
        "transfer.sh:443",
        "support-agent",
        "Single 22 MB request to a one-shot file transfer service, no prior history "
        "for this actor.",
        None,
        (
            (
                "soc-tier1",
                "Waiting on the support lead to confirm whether this was a customer export.",
            ),
        ),
    ),
    (
        "mega.example:443",
        "research-agent",
        "Repeated chunked uploads to a consumer file locker over a 90 second window.",
        "approved",
        (),
    ),
)


def _timestamp(index: int) -> str:
    return (BASE_TIME + timedelta(minutes=index * 7)).isoformat().replace("+00:00", "Z")


def _post(base: str, path: str, body: Any, timeout: float) -> dict[str, Any]:
    request = Request(
        f"{base}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or b"{}")
    except HTTPError as error:
        raise RuntimeError(
            f"POST {path} returned HTTP {error.code}: {error.read().decode()}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"POST {path} failed: {error.reason}") from error


def _finding_ids(base: str, timeout: float) -> list[str]:
    """Existing findings, so seeded recommendations point at real evidence."""
    try:
        with urlopen(f"{base}/v1/findings", timeout=timeout) as response:
            payload = json.loads(response.read() or b"{}")
    except (HTTPError, URLError):
        return []
    return [str(finding["finding_id"]) for finding in payload.get("findings", [])]


def seed(base: str, timeout: float) -> None:
    findings = _finding_ids(base, timeout)
    for index, (target, scope, reason, decision, notes) in enumerate(SEEDS):
        recommendation_id = f"rec-seed-{index:03d}"
        _post(
            base,
            "/v1/recommendations",
            {
                "schema_version": SCHEMA_VERSION,
                "recommendation_id": recommendation_id,
                "finding_id": findings[index % len(findings)]
                if findings
                else f"fnd-seed-{index:03d}",
                "action_type": "deny_destination",
                "target": target,
                "scope": scope,
                "reason": reason,
                "expires_at": (BASE_TIME + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
            },
            timeout,
        )
        for analyst, note in notes:
            _post(
                base,
                f"/v1/recommendations/{recommendation_id}/notes",
                {"schema_version": SCHEMA_VERSION, "analyst": analyst, "note": note},
                timeout,
            )
        if decision is not None:
            _post(
                base,
                f"/v1/recommendations/{recommendation_id}/decision",
                {
                    "schema_version": SCHEMA_VERSION,
                    "recommendation_id": recommendation_id,
                    "decision": decision,
                    "analyst": "soc-tier2",
                    "timestamp": _timestamp(index),
                },
                timeout,
            )
        print(
            f"seeded {recommendation_id} {target} ({decision or 'pending'}, {len(notes)} notes)",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default="http://localhost:8100",
        help="Ingestion base URL (default: http://localhost:8100).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds (default: 10).",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    base = args.api.rstrip("/")
    if urlparse(base).scheme not in {"http", "https"}:
        parser.error("--api must be an http or https URL")

    try:
        seed(base, args.timeout)
    except RuntimeError as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
