"""SquidWard demo driver — two modes.

    demo live                  # real traffic: point a laptop at the proxy
    demo simulate              # an enterprise's worth of synthetic traffic
    demo agent                 # the security agent's MCP loop, on demand
    demo aliases               # DNS aliases the sink container needs

LIVE is for showing it works on real traffic: a laptop on the LAN sets the
proxy and browses, and the events appear. Nothing is fabricated.

SIMULATE is for the video: dozens of users, sustained throughput, and planted
anomalies the agent is meant to catch — all offline, so it does not depend on
the room's wifi and runs the same way every time.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.request

from . import agent, anomalies, run, traffic
from .catalog import ALL, ROUTINE

INGESTION = "http://127.0.0.1:8100"
PROXY_HOST = "192.168.0.100"
DASHBOARD = f"http://{PROXY_HOST}:8300/"


def _beat(text: str) -> None:
    print(f"\n\033[1m▶ {text}\033[0m", flush=True)


def _count() -> int:
    """Total events stored.

    NOTE the limit: ingestion's `count` is how many this response carried, not
    how many exist, so asking with limit=1 always answers 1. Ask for more than
    a demo will ever generate.
    """
    try:
        with urllib.request.urlopen(f"{INGESTION}/v1/events?limit=100000", timeout=15) as r:
            body = json.load(r)
        return int(body.get("count") or len(body.get("events", [])))
    except (OSError, ValueError):
        return -1


def _rules() -> list[str]:
    try:
        with urllib.request.urlopen(f"{INGESTION}/v1/rules.txt", timeout=5) as r:
            return [x for x in r.read().decode().split() if x]
    except OSError:
        return []


# --- modes --------------------------------------------------------------


def cmd_aliases(_: argparse.Namespace) -> int:
    """Emit the compose network aliases the sink needs, so the catalog and the
    compose file cannot drift."""
    for host in ALL:
        print(f"          - {host}")
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    _beat("LIVE mode — real traffic from real machines")
    print("  On the laptop you want to record:")
    print(f"    export http_proxy=http://{PROXY_HOST}:3128")
    print(f"    export https_proxy=http://{PROXY_HOST}:3128")
    print("  or System Settings -> Network -> Proxies -> Web + Secure Web Proxy")
    print(f"\n  Dashboard: {DASHBOARD}")
    print("\n  HTTPS shows CONNECT host:443 and byte counts, not URLs or content.")
    print("  That is the honest limit without TLS interception — do not claim more.\n")

    start = _count()
    print(f"  watching... ({start} events stored). Ctrl-C to stop.\n")
    seen = start
    try:
        while True:
            time.sleep(args.interval)
            now = _count()
            if now != seen:
                print(f"  +{now - seen:<4} events   (total {now})", flush=True)
                seen = now
    except KeyboardInterrupt:
        print(f"\n  stopped. {seen - start} events captured from live traffic.")
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    print("=" * 74)
    print("  SquidWard — egress observed, correlated, and enforced on a DGX Spark")
    print("=" * 74)

    before = _count()

    _beat(f"A normal working day — {args.users} users, {args.duration:.0f}s of routine egress")
    stats = traffic.run(
        duration=args.duration, workers=args.workers, rate=args.rate, users=args.users
    )
    time.sleep(4)
    print(f"  {stats.sent} requests across {len(ROUTINE)} internal systems ({stats.failed} failed)")
    print(f"  events stored: {before} -> {_count()}")

    _beat("Something changes")
    opener = traffic._opener(traffic.PROXY)  # noqa: SLF001 - same package
    cast = traffic.user_pool(args.users)
    for key in args.anomalies:
        an = anomalies.BY_KEY[key]
        actor = cast[hash(key) % len(cast)]
        print(f"\n  [{an.title}] — {an.why}   actor={actor}")
        for note in an.run(opener, actor, args.pause):
            print(f"    · {note}")
    time.sleep(5)
    print(f"\n  events stored: {_count()}")

    if not args.no_agent:
        cmd_agent(args)
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    _beat("The security agent investigates — over MCP, not HTTP")
    report = asyncio.run(agent.investigate(set(ROUTINE)))

    print(f"  query_events        -> {report.get('events_seen')} events read")
    verdict = report.get("verdict")
    if not verdict:
        print("  nothing crossed the bar; no finding raised.")
        return 0

    print(
        f"  correlated          -> {verdict['destination']} "
        f"({verdict['bytes_up']:,} bytes up, {len(verdict['event_ids'])} events)"
    )
    print(f"  submit_finding      -> {report.get('finding_id')} (risk {verdict['risk']})")
    print(f"  recommend_policy    -> {report.get('recommendation_id')} [{report.get('status')}]")

    print(f"\n  Rules right now: {_rules() or '(none)'}")
    print("  The agent proposed a block. It did NOT apply one — recommend_policy")
    print("  only ever produces a pending recommendation. Enforcement needs a human.")
    print(f"\n  Approve it in the dashboard: {DASHBOARD}")
    print("  or:  curl -X POST $API/v1/recommendations/<id>/decision \\")
    print('         -d \'{"schema_version":"1.0","decision":"approved","actor":"you"}\'')
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    return run.main(
        prime_s=args.prime,
        enforce_s=args.enforce,
        progress_s=args.progress,
        auto_approve=not args.no_auto_approve,
        log_path=args.log,
        attack_mb=args.attack_mb,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("aliases").set_defaults(func=cmd_aliases)

    live = sub.add_parser("live", help="watch real traffic from LAN clients")
    live.add_argument("--interval", type=float, default=3.0)
    live.set_defaults(func=cmd_live)

    sim = sub.add_parser("simulate", help="synthetic enterprise traffic + anomalies")
    sim.add_argument("--users", type=int, default=40)
    sim.add_argument("--duration", type=float, default=45.0)
    sim.add_argument("--workers", type=int, default=8)
    sim.add_argument("--rate", type=float, default=12.0)
    sim.add_argument("--pause", type=float, default=1.2)
    sim.add_argument(
        "--anomalies",
        nargs="+",
        default=["sweep", "beacon", "exfil"],
        choices=list(anomalies.BY_KEY),
    )
    sim.add_argument("--no-agent", action="store_true")
    sim.set_defaults(func=cmd_simulate)

    ag = sub.add_parser("agent", help="run the MCP investigation loop on demand")
    ag.set_defaults(func=cmd_agent)

    r = sub.add_parser("run", help="the full phased demo: prime, decide, enforce")
    r.add_argument("--prime", type=float, default=60.0)
    r.add_argument("--enforce", type=float, default=90.0)
    r.add_argument("--progress", type=float, default=5.0)
    r.add_argument("--attack-mb", type=int, default=4)
    r.add_argument("--log", default="/home/dell/ingestion-data/demo-run.log")
    r.add_argument("--no-auto-approve", action="store_true")
    r.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
