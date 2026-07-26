#!/usr/bin/env python3
"""Validate fixtures/expected/*.json against contracts/event.schema.json.

Every canonical event in `fixtures/expected/` must be a schema-valid Canonical
Event (see contracts/event.schema.json), and the fixtures must stay
deterministic: stable, unique `event_id`s and UTC `timestamp`s hardcoded in
the file (never generated at load time), so replaying a fixture twice yields
byte-identical canonical events.

Run directly:

    uv run --with jsonschema python3 fixtures/validate.py

Wired into `just check` via `just fixtures-check`.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import jsonschema

FIXTURES_DIR = Path(__file__).resolve().parent
EXPECTED_DIR = FIXTURES_DIR / "expected"
EVENT_SCHEMA_PATH = FIXTURES_DIR.parent / "contracts" / "event.schema.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def check_timestamp_is_utc(event_id: str, timestamp: str) -> str | None:
    """Return an error string unless `timestamp` is an explicit UTC instant."""
    if not timestamp.endswith("Z"):
        return f"{event_id}: timestamp {timestamp!r} is not UTC (must end in 'Z')"
    try:
        dt.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        return f"{event_id}: timestamp {timestamp!r} is not a valid UTC instant ({exc})"
    return None


def check_fixture_file(path: Path, schema: dict) -> list[str]:
    """Validate one fixtures/expected/*.json file. Returns a list of errors."""
    rel = path.relative_to(FIXTURES_DIR)
    events = load_json(path)

    if not isinstance(events, list) or not events:
        return [f"{rel}: expected a non-empty JSON array of canonical events"]

    errors: list[str] = []
    seen_ids: set[str] = set()

    for index, event in enumerate(events):
        label = f"{rel}[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{label}: expected a JSON object")
            continue

        try:
            jsonschema.validate(event, schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{label}: {str(exc).splitlines()[0]}")
            continue

        event_id = event["event_id"]
        label = f"{rel}[{index}] ({event_id})"

        if event_id in seen_ids:
            errors.append(f"{label}: duplicate event_id within {rel}")
        seen_ids.add(event_id)

        if (error := check_timestamp_is_utc(label, event["timestamp"])) is not None:
            errors.append(error)

    if not errors:
        print(f"OK   {rel}: {len(events)} canonical event(s) validated")

    return errors


def main() -> int:
    if not EVENT_SCHEMA_PATH.is_file():
        print(f"FAILED:\n  - missing schema: {EVENT_SCHEMA_PATH}", file=sys.stderr)
        return 1

    schema = load_json(EVENT_SCHEMA_PATH)
    if not isinstance(schema, dict):
        print(
            f"FAILED:\n  - schema is not a JSON object: {EVENT_SCHEMA_PATH}",
            file=sys.stderr,
        )
        return 1

    fixture_files = sorted(EXPECTED_DIR.glob("*.json"))

    if not fixture_files:
        print(f"FAILED:\n  - no fixtures found under {EXPECTED_DIR}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for path in fixture_files:
        failures += check_fixture_file(path, schema)

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"\n{len(fixture_files)} fixture file(s) validated OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
