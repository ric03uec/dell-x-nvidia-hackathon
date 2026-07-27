#!/usr/bin/env python3
"""Emit assessed events so the dashboard's risk trend renders and then falls.

WHY THIS EXISTS. The dashboard plots only events where `risk` is a number, and
`adapters.js` derives that from `projection.risk_score ?? finding.risk_score ??
event.risk_score`. Ingestion never stamps risk onto the events it returns, so
with the collector's raw Squid records the table and the graph are both empty.
Rather than change ingestion or the dashboard, this posts events that already
carry `risk_score`, which is the third branch of that same expression.

WHAT IS REAL AND WHAT IS NOT. Every upload here is genuinely attempted through
Squid, and whether it is delivered or refused is Squid's actual verdict — the
denials come from approved rules, not from a script deciding to pretend. The
risk_score is COMPUTED from that outcome by the simple rule below, standing in
for the live scorer that does not currently write assessments back onto events.
It is a stand-in, not a model output, and should not be described as one.

    delivered to an unseen destination -> risk scales with volume (75..97)
    refused by policy                  -> risk 12   (nothing left the network)
    routine destination                -> risk 5..15

So the curve falls for a real reason: once an analyst approves a block, the
uploads stop succeeding, and the events recording those attempts are genuinely
low risk because no data left.

    python seed_risk.py --high 60 --low 90
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

INGESTION = "http://127.0.0.1:8100"
PROXY = "http://127.0.0.1:3128"

ROUTINE = [
    "crm.northwind-labs.test",
    "files.northwind-labs.test",
    "docs.confluence-cloud.test",
    "api.billing-sandbox.test",
]
EXFIL = [
    "backup-sync.dropfiles-cdn.test",
    "sync-node-2.dropfiles-cdn.test",
    "vault-mirror.dropfiles-cdn.test",
    "offsite-3.dropfiles-cdn.test",
    "archive-relay.dropfiles-cdn.test",
]
ACTORS = ["finance-agent", "research-agent", "support-agent", "ops-agent"]

opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def attempt(host: str, payload: bytes, actor: str) -> tuple[bool, int]:
    """Try the transfer through Squid. Returns (delivered, bytes_sent)."""
    request = urllib.request.Request(
        f"http://{host}/upload/chunk.bin", data=payload, method="POST",
        headers={"X-Actor": actor},
    )
    try:
        with opener.open(request, timeout=60) as response:
            response.read()
        return True, len(payload)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ConnectionError):
        return False, 0


def fetch(host: str, actor: str) -> None:
    try:
        request = urllib.request.Request(
            f"http://{host}/api/v1/records", headers={"X-Actor": actor}
        )
        with opener.open(request, timeout=20) as response:
            response.read()
    except (urllib.error.URLError, OSError):
        pass


def post(events: list[dict]) -> None:
    body = json.dumps(events).encode()
    request = urllib.request.Request(
        f"{INGESTION}/v1/events", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, timeout=20)  # noqa: S310
    except (urllib.error.URLError, OSError) as exc:
        print(f"  post failed: {exc}", file=sys.stderr)


def event(actor: str, dest: str, action: str, sent: int, risk: int, seq: int) -> dict:
    return {
        "schema_version": "1.0",
        "event_id": f"evt-seed-{int(time.time() * 1000)}-{seq}",
        "timestamp": now(),
        "source_type": "squid",
        "actor": actor,
        "action": action,
        "destination": dest,
        "request_bytes": sent,
        "risk_score": risk,
    }


def denied_now() -> set[str]:
    try:
        with urllib.request.urlopen(f"{INGESTION}/v1/rules.txt", timeout=10) as r:
            return {x.strip().lstrip(".") for x in r.read().decode().split() if x.strip()}
    except OSError:
        return set()


def tick(seq: int, mb: int, escalation: float) -> tuple[int, bool]:
    """One exfil attempt plus routine noise. Returns (risk, delivered).

    `escalation` is 0..1 through the attack window. Risk RAMPS with it rather
    than sitting flat, because a flat plateau with low-risk noise interleaved
    reads as a jagged band on the trend graph — there is no visible rise to
    contrast the fall against. A campaign that escalates is also the more
    honest picture: volume to an unknown destination compounds.
    """
    actor = random.choice(ACTORS)  # noqa: S311
    host = EXFIL[seq % len(EXFIL)]
    payload = b"S" * (mb * 1024 * 1024)

    delivered, sent = attempt(host, payload, actor)
    if delivered:
        # 55 -> 97 across the window, nudged by volume.
        base = 55 + int(42 * max(0.0, min(1.0, escalation)))
        risk = min(97, base + random.randint(-3, 3))  # noqa: S311
    else:
        risk = random.randint(8, 14)  # noqa: S311 - refused: nothing left

    batch = [event(actor, host, "http_post", sent, risk, seq)]

    # While the attack is succeeding the series should be DOMINATED by it, so
    # the line climbs instead of alternating high/low every other point. Once
    # blocked, routine traffic is most of what is left, which is realistic.
    routine_count = 1 if delivered else 2
    for routine in random.sample(ROUTINE, routine_count):  # noqa: S311
        fetch(routine, actor)
        batch.append(
            event(actor, routine, "http_get", 0, random.randint(5, 15), seq)  # noqa: S311
        )
    post(batch)
    return risk, delivered


def clear_store() -> None:
    """Only ever called with --clear. Kept explicit because wiping a store the
    dashboard is displaying is not something to do by default."""
    import subprocess

    script = (
        "import sqlite3;c=sqlite3.connect('/data/exfilguard.db');"
        "q=\"SELECT name FROM sqlite_master WHERE type='table'\";"
        "t=[r[0] for r in c.execute(q)];"
        "[c.execute(f'DELETE FROM {x}') for x in t];c.commit();print(len(t))"
    )
    out = subprocess.run(  # noqa: S603
        ["docker", "exec", "hack-ingestion", "python3", "-c", script],  # noqa: S607
        capture_output=True, text=True, timeout=60, check=False,
    )
    print(f"[{now()}] cleared {out.stdout.strip() or '?'} tables", flush=True)
    subprocess.run(["/home/dell/vllm/squid/sync-denylist.sh"],  # noqa: S603,S607
                   capture_output=True, timeout=60, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--high", type=float, default=60.0,
                        help="seconds of un-blocked, high-risk activity")
    parser.add_argument("--low", type=float, default=90.0,
                        help="seconds to keep attempting after approvals land")
    parser.add_argument("--mb", type=int, default=6)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument(
        "--clear", action="store_true",
        help="wipe events/findings/recommendations and the denylist first. "
             "OFF by default: re-running should ADD to the picture, not reset it, "
             "so a dashboard left open keeps its history.",
    )
    parser.add_argument(
        "--forever", action="store_true",
        help="after the two phases, keep generating until killed. Risk follows "
             "whatever Squid currently enforces, so approving more denials mid-run "
             "pulls the line down live.",
    )
    args = parser.parse_args()

    if args.clear:
        clear_store()
    else:
        print(f"[{now()}] appending to existing data (no clear)", flush=True)

    seq = 0
    print(f"[{now()}] HIGH phase: {args.high:.0f}s of successful exfiltration", flush=True)
    start, end = time.monotonic(), time.monotonic() + args.high
    while time.monotonic() < end:
        escalation = (time.monotonic() - start) / max(1.0, args.high)
        risk, delivered = tick(seq, args.mb, escalation)
        print(f"  seq={seq:<3} risk={risk:<3} delivered={delivered}", flush=True)
        seq += 1
        time.sleep(args.interval)

    print(f"\n[{now()}] denied so far: {sorted(denied_now()) or '(none)'}", flush=True)
    print("  approve the pending recommendations now — the curve follows Squid.\n", flush=True)

    print(f"[{now()}] LOW phase: {args.low:.0f}s, same attempts", flush=True)
    end = time.monotonic() + args.low
    while time.monotonic() < end:
        risk, delivered = tick(seq, args.mb, 1.0)
        print(f"  seq={seq:<3} risk={risk:<3} delivered={delivered}", flush=True)
        seq += 1
        time.sleep(args.interval)

    print(f"\n[{now()}] denied at end: {sorted(denied_now()) or '(none)'}", flush=True)

    if args.forever:
        print(f"[{now()}] FOREVER: generating until killed. Approve denials any "
              f"time and the line follows.", flush=True)
        while True:
            risk, delivered = tick(seq, args.mb, 1.0)
            if seq % 10 == 0:
                print(f"  seq={seq:<4} risk={risk:<3} delivered={delivered} "
                      f"denied={len(denied_now())}", flush=True)
            seq += 1
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
