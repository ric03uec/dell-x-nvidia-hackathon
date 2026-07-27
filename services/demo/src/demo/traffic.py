"""Background business traffic — the boring baseline the incident stands out against.

Concurrency plus Faker, driven through Squid so every request becomes a real
access.log line and therefore a real event.
"""

from __future__ import annotations

import random
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from faker import Faker

from .catalog import ROUTINE

PROXY = "http://127.0.0.1:3128"


@dataclass
class Stats:
    sent: int = 0
    failed: int = 0
    bytes_up: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, ok: bool, up: int) -> None:
        with self.lock:
            if ok:
                self.sent += 1
                self.bytes_up += up
            else:
                self.failed += 1


def _opener(proxy: str) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))


def user_pool(size: int, seed: int = 1337) -> list[str]:
    """A stable cast of employees, so the same names recur across a run and the
    dashboard looks like an organisation rather than random noise."""
    Faker.seed(seed)
    fake = Faker()
    return [fake.user_name() for _ in range(size)]


def _one_request(
    opener: urllib.request.OpenerDirector, fake: Faker, stats: Stats, users: list[str]
) -> None:
    host = random.choice(ROUTINE)  # noqa: S311 - demo traffic shaping, not crypto
    user = random.choice(users)  # noqa: S311

    # Mostly reads, with the occasional modest write — the shape of a workday.
    if random.random() < 0.15:  # noqa: S311
        payload = fake.text(max_nb_chars=random.randint(200, 4000)).encode()  # noqa: S311
        request = urllib.request.Request(
            f"http://{host}/api/v1/{fake.uri_path()}",
            data=payload,
            method="POST",
            headers={"X-Actor": user},
        )
        up = len(payload)
    else:
        request = urllib.request.Request(
            f"http://{host}/api/v1/{fake.uri_path()}", headers={"X-Actor": user}
        )
        up = 0

    try:
        with opener.open(request, timeout=10) as response:
            response.read()
        stats.record(True, up)
    except (urllib.error.URLError, OSError):
        stats.record(False, 0)


def run(
    duration: float = 30.0,
    workers: int = 6,
    rate: float = 8.0,
    proxy: str = PROXY,
    seed: int = 1337,
    users: int = 40,
) -> Stats:
    """Drive `rate` requests/second for `duration` seconds across `workers` threads."""
    random.seed(seed)
    Faker.seed(seed)
    cast = user_pool(users, seed)
    stats = Stats()
    deadline = time.monotonic() + duration
    interval = workers / rate if rate > 0 else 0

    def worker() -> None:
        fake = Faker()
        opener = _opener(proxy)
        while time.monotonic() < deadline:
            _one_request(opener, fake, stats, cast)
            if interval:
                time.sleep(interval)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=duration + 30)
    return stats
