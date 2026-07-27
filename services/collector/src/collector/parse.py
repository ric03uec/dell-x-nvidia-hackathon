"""The one place a Squid exfilguard log line becomes a record.

Single-sourced deliberately. Two copies of this parser — one in the collector
and one in a fixture script — is exactly the drift the ingestion beads warn
about: the fixtures every other component develops against would slowly stop
matching what the live path produces.
"""

from __future__ import annotations

from typing import Any

# Typed here so consumers do not each re-guess which strings are numbers.
NUMERIC = {"status", "req_bytes", "resp_bytes"}


def parse_line(line: str) -> dict[str, Any]:
    """Parse one `key=value key=value` exfilguard line. Returns {} if it is not one.

    Squid writes `-` for an absent field; that becomes None rather than the
    literal string, so downstream `if record["user"]` behaves.
    """
    record: dict[str, Any] = {}

    for token in line.split():
        key, sep, value = token.partition("=")
        if not sep:
            continue

        if key == "uri":
            # Never persist a query string. A credential in a demo log is a
            # real incident, and this is the cheapest place to stop it. The
            # collector strips again before posting — belt and braces.
            value = value.split("?", 1)[0]

        parsed: Any = value
        if key == "ts":
            try:
                parsed = float(value)
            except ValueError:
                pass
        elif key in NUMERIC:
            try:
                parsed = int(value)
            except ValueError:
                pass

        record[key] = None if parsed == "-" else parsed

    return record
