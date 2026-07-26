#!/usr/bin/env python3
"""Turn squid's exfilguard access.log into jsonl fixtures.

The exfilguard logformat is key=value, so the event contract IS the field set —
no mapping table to drift. This is deliberate: dxnvh-dwj.2 derives the contract
from real traffic instead of freezing it up front (dxnvh-332.2 freezes it later
by observing what consumers actually used).

    docker exec hack-squid cat /var/log/squid/access.log | ./log2jsonl.py > out.jsonl

ponytail: query strings are stripped here as well as in the collector. Belt and
braces on credential leakage is the one redundancy worth paying for.
"""

import json
import sys

# Numeric fields, so consumers do not each re-guess which strings are numbers.
NUMERIC = {"ts", "status", "req_bytes", "resp_bytes"}


def parse(line):
    record = {}
    for token in line.split():
        key, _, value = token.partition("=")
        if not _:
            continue
        if key == "uri":
            value = value.split("?", 1)[0]  # never persist query strings
        if key in NUMERIC:
            try:
                value = float(value) if key == "ts" else int(value)
            except ValueError:
                pass
        record[key] = None if value == "-" else value
    return record


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        record = parse(line)
        if record:
            print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
