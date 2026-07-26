#!/usr/bin/env python3
"""Validate contracts/examples/* against their JSON Schemas.

Every positive fixture in `examples/` must validate against its schema.
Every fixture under `examples/invalid/` must be *rejected* by its schema
(currently used to prove policy-recommendation.schema.json's closed
action_type enum actually closes the hole).

Run directly:

    uv run --with jsonschema python3 contracts/validate.py

Wired into `just check`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

CONTRACTS_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = CONTRACTS_DIR / "examples"

# (example path relative to examples/, schema filename, expected to validate)
CASES: list[tuple[str, str, bool]] = [
    ("event.json", "event.schema.json", True),
    ("finding.json", "finding.schema.json", True),
    ("policy-recommendation.json", "policy-recommendation.schema.json", True),
    ("approval.json", "approval.schema.json", True),
    ("enforcement-result.json", "enforcement-result.schema.json", True),
    (
        "invalid/policy-recommendation-bad-action-type.json",
        "policy-recommendation.schema.json",
        False,
    ),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def check_case(example_name: str, schema_name: str, expect_valid: bool) -> str | None:
    """Return an error string if the case didn't behave as expected, else None."""
    example_path = EXAMPLES_DIR / example_name
    schema_path = CONTRACTS_DIR / schema_name

    if not example_path.is_file():
        return f"missing example: {example_path}"
    if not schema_path.is_file():
        return f"missing schema: {schema_path}"

    instance = load_json(example_path)
    schema = load_json(schema_path)

    try:
        jsonschema.validate(instance, schema)
        valid, error = True, None
    except jsonschema.ValidationError as exc:
        valid, error = False, str(exc).splitlines()[0]

    rel = example_path.relative_to(CONTRACTS_DIR)
    if valid == expect_valid:
        outcome = "validated" if valid else f"rejected ({error})"
        print(f"OK   {rel}: {outcome}")
        return None

    want = "to validate" if expect_valid else "to be rejected"
    got = "validated" if valid else f"was rejected ({error})"
    return f"{rel}: expected {want}, but {got}"


def find_uncovered_examples() -> list[str]:
    """Fail loudly if a top-level example file isn't wired into CASES."""
    covered = {EXAMPLES_DIR / name for name, _, _ in CASES}
    top_level = {p for p in EXAMPLES_DIR.glob("*.json") if p.is_file()}
    uncovered = sorted(top_level - covered)
    return [f"{p.relative_to(CONTRACTS_DIR)}: not covered by any validation case" for p in uncovered]


def main() -> int:
    failures = [error for case in CASES if (error := check_case(*case)) is not None]
    failures += find_uncovered_examples()

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"\n{len(CASES)} case(s) validated OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
