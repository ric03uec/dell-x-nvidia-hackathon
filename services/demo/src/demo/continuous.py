"""Continuous mode: keep the incident running so OpenClaw can drive the response.

`demo run` is the scripted arc — prime, decide, enforce, done. This is the
open-ended version: traffic and exfiltration keep going for N minutes while the
agent re-investigates on a cycle and files recommendations, and NOTHING is
auto-approved. The pending queue keeps filling so an operator (or OpenClaw,
through the same MCP tools) can be the one to apply them and watch the
delivered rate fall live.

Preflight checks that OpenClaw is up and that ingestion's MCP endpoint is
reachable and registered with it, because the whole point of this mode is that
OpenClaw is the actor — discovering it was never connected after five minutes
of traffic would waste the take.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .run import Runner

MCP_URL = "http://127.0.0.1:8100/mcp/"
INGESTION = "http://127.0.0.1:8100"


def _openclaw_state() -> tuple[bool, str]:
    """Is the OpenClaw gateway service up?"""
    try:
        out = subprocess.run(  # noqa: S603
            ["systemctl", "--user", "is-active", "openclaw-gateway"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        state = out.stdout.strip() or out.stderr.strip()
        return state == "active", state
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"unavailable ({type(exc).__name__})"


def _mcp_reachable() -> bool:
    """MCP speaks its own protocol; any non-404 means something is mounted."""
    try:
        urllib.request.urlopen(MCP_URL, timeout=8)  # noqa: S310
        return True
    except urllib.error.HTTPError:
        return True
    except OSError:
        return False


def _register_mcp(name: str = "squidward") -> str:
    """Register ingestion's MCP surface with OpenClaw. `add` probes before saving,
    so a failure here means OpenClaw genuinely could not reach the endpoint."""
    try:
        out = subprocess.run(  # noqa: S603
            ["openclaw", "mcp", "add", name, "--url", MCP_URL],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if out.returncode == 0:
            return "registered"
        tail = (out.stderr or out.stdout).strip().splitlines()
        return f"not registered: {tail[-1][:120] if tail else 'unknown error'}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"not registered ({type(exc).__name__})"


def preflight(runner: Runner, register: bool) -> bool:
    runner.beat("PREFLIGHT — OpenClaw must be able to act")
    ok, state = _openclaw_state()
    runner.say(f"  openclaw-gateway : {state}")
    reachable = _mcp_reachable()
    runner.say(f"  ingestion MCP    : {'reachable' if reachable else 'UNREACHABLE'} at {MCP_URL}")

    if register and ok and reachable:
        runner.say(f"  registering MCP  : {_register_mcp()}")
    elif register:
        runner.say("  skipping registration: preconditions not met")

    if not reachable:
        runner.say("  ABORT: ingestion's MCP endpoint is not answering; nothing to drive.")
        return False
    if not ok:
        runner.say(
            "  WARNING: OpenClaw is not active. Traffic will run and "
            "recommendations will queue, but OpenClaw cannot apply them."
        )
    return True


def pending_count() -> int:
    try:
        with urllib.request.urlopen(
            f"{INGESTION}/v1/recommendations?status=pending", timeout=15
        ) as r:
            return len(json.load(r).get("recommendations", []))
    except (OSError, ValueError):
        return -1


def run(runner: Runner, minutes: float, cycle: float, register: bool) -> int:
    """Traffic for `minutes`, re-investigating every `cycle` seconds."""
    if not preflight(runner, register):
        return 2

    runner.reset()
    from .traffic import user_pool

    cast = user_pool(30)
    threads = [
        threading.Thread(target=runner._normal_worker, args=(cast,), daemon=True)  # noqa: SLF001
        for _ in range(4)
    ]
    threads.append(
        threading.Thread(target=runner._attack_worker, args=("m.reeves",), daemon=True)  # noqa: SLF001
    )
    threads.append(
        threading.Thread(target=runner._progress, args=(5.0,), daemon=True)  # noqa: SLF001
    )
    for t in threads:
        t.start()

    deadline = time.monotonic() + minutes * 60
    runner.phase = "LIVE"
    runner.beat(f"LIVE — {minutes:.0f} minutes of traffic; the agent files, OpenClaw applies")
    runner.say("  nothing is auto-approved: the pending queue is the hand-off point")

    cycles = 0
    try:
        # Let evidence accumulate before the first investigation, or the agent
        # reasons about an almost-empty store.
        time.sleep(min(cycle, max(0.0, deadline - time.monotonic())))
        while time.monotonic() < deadline:
            cycles += 1
            runner.say("")
            runner.say(f"  --- investigation cycle {cycles} ---")
            try:
                runner.decide()
            except (OSError, RuntimeError, ValueError) as exc:
                runner.say(f"  cycle failed ({type(exc).__name__}: {exc}); continuing")
            runner.say(f"  pending recommendations awaiting approval: {pending_count()}")
            time.sleep(min(cycle, max(0.0, deadline - time.monotonic())))
    finally:
        runner.stop.set()
        time.sleep(1.5)

    c = runner.counters.snapshot()
    runner.beat("RESULT")
    runner.say(f"  investigation cycles : {cycles}")
    runner.say(f"  events stored        : {runner.events()}")
    runner.say(f"  pending for OpenClaw : {pending_count()}")
    runner.say(f"  denied so far        : {runner.rules() or '(none)'}")
    runner.say(f"  exfil delivered/blocked: {c['delivered']} / {c['blocked']}")
    runner.log.close()
    return 0
