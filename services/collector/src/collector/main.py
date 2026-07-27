"""Squid access.log -> ingestion.

Two modes, one parser:

    collector                       # follow the live log, post as lines arrive
    collector --replay FILE         # parse a file to jsonl on stdout (fixtures)

The live source is a shell command whose stdout we read, defaulting to a
`docker exec` tail. That keeps it out of the volume-permissions problem
entirely — squid writes as uid 13 into the named `hack-squid-logs` volume, and
reading through the container needs no chowned host bind mount — while staying
trivially testable, since a test can pass `--source "cat fixture.log"`.

ponytail: PROTOTYPE SCOPE (dxnvh-dwj.4). No file-position memory, no bounded
buffer, no rotation handling — a restart loses whatever arrived while it was
down, and an ingestion outage drops records with a loud stderr line rather
than retrying. That is dxnvh-0f2.5's job. What is NOT cut is query-string
redaction, because a leaked credential is not a prototype-grade problem.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from .parse import parse_line

DEFAULT_SOURCE = "docker exec hack-squid tail -n 0 -F /var/log/squid/access.log"
DEFAULT_INGESTION = "http://127.0.0.1:8100"
RETRY_SECONDS = 3


def post_event(ingestion_url: str, record: dict[str, Any], timeout: float = 5.0) -> bool:
    """POST one record. Returns False on failure instead of raising — a dead
    ingestion must not kill the tail."""
    body = json.dumps([record]).encode()
    request = urllib.request.Request(
        f"{ingestion_url}/v1/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return bool(200 <= response.status < 300)
    except (urllib.error.URLError, OSError) as exc:
        print(f"collector: post failed ({exc}); dropping record", file=sys.stderr, flush=True)
        return False


def follow(source: str) -> Iterator[str]:
    """Yield lines from the source command's stdout until it exits."""
    process = subprocess.Popen(  # noqa: S602
        source, shell=True, stdout=subprocess.PIPE, text=True, bufsize=1
    )
    assert process.stdout is not None
    try:
        yield from process.stdout
    finally:
        process.terminate()


def run(source: str, ingestion_url: str, retry: bool = True) -> int:
    """Follow the source, reattaching if it ends.

    The default source is `docker exec ... tail -F`, and that exec dies
    whenever the squid container is recreated — which happens on any compose
    change. Without the retry the collector exits silently at that moment and
    events stop arriving with nothing in its log to say why. Observed exactly
    that; the tail surviving log ROTATION is not the same as surviving the
    container going away.
    """
    posted = dropped = 0
    while True:
        for line in follow(source):
            record = parse_line(line)
            if not record:
                continue
            if post_event(ingestion_url, record):
                posted += 1
            else:
                dropped += 1

        if not retry:
            break
        print(
            f"collector: source ended (posted={posted} dropped={dropped}); "
            f"reattaching in {RETRY_SECONDS}s",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(RETRY_SECONDS)

    print(f"collector: stopped. posted={posted} dropped={dropped}", file=sys.stderr)
    return 0 if dropped == 0 else 1


def replay(path: str) -> int:
    """Parse a log file to jsonl on stdout — how fixtures/squid/*.jsonl is made."""
    with open(path) as handle:
        for line in handle:
            record = parse_line(line)
            if record:
                print(json.dumps(record, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", metavar="FILE", help="parse a file to jsonl and exit")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="command producing log lines")
    parser.add_argument("--ingestion-url", default=DEFAULT_INGESTION)
    parser.add_argument(
        "--no-retry", action="store_true", help="exit when the source ends instead of reattaching"
    )
    args = parser.parse_args(argv)

    if args.replay:
        return replay(args.replay)
    return run(args.source, args.ingestion_url, retry=not args.no_retry)


if __name__ == "__main__":
    raise SystemExit(main())
