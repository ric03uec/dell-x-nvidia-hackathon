"""No live squid, no live ingestion — a fixture file and a stub server."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from collector.main import replay, run
from collector.parse import parse_line

CONNECT = (
    "ts=1785107042.961 src=172.20.0.1 user=- method=CONNECT uri=httpbin.org:443 "
    "status=200 req_bytes=101326 resp_bytes=105727 mime=- result=TCP_TUNNEL "
    "dst_ip=13.223.23.68"
)
WITH_CREDENTIAL = (
    "ts=1785107040.866 src=172.20.0.1 user=- method=POST "
    "uri=http://x.test/upload?token=SECRET123&user=bob "
    "status=200 req_bytes=100200 resp_bytes=0 mime=- result=TCP_MISS dst_ip=54.147.121.219"
)


# --- parsing ------------------------------------------------------------


def test_parses_a_connect_line_with_typed_numbers() -> None:
    record = parse_line(CONNECT)
    assert record["method"] == "CONNECT"
    assert record["uri"] == "httpbin.org:443"
    assert record["req_bytes"] == 101326  # int, not "101326"
    assert record["ts"] == pytest.approx(1785107042.961)
    assert record["dst_ip"] == "13.223.23.68"


def test_absent_fields_become_none_not_a_dash() -> None:
    assert parse_line(CONNECT)["user"] is None
    assert parse_line(CONNECT)["mime"] is None


def test_non_log_lines_are_ignored() -> None:
    assert parse_line("") == {}
    assert parse_line("some unrelated stderr noise") == {}


def test_query_string_is_stripped() -> None:
    """A credential in the event store is a real incident, not a blemish."""
    record = parse_line(WITH_CREDENTIAL)
    assert record["uri"] == "http://x.test/upload"
    assert "SECRET123" not in json.dumps(record)


# --- replay -------------------------------------------------------------


def test_replay_emits_one_json_object_per_log_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "access.log"
    log.write_text(CONNECT + "\n" + WITH_CREDENTIAL + "\n")

    assert replay(str(log)) == 0

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["uri"] == "httpbin.org:443"


# --- posting ------------------------------------------------------------


class _Capture(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        _Capture.received.extend(json.loads(self.rfile.read(length)))
        self.send_response(201)
        self.end_headers()
        self.wfile.write(b'{"schema_version":"1.0","accepted":1}')

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture
def stub_ingestion() -> Iterator[str]:
    _Capture.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Capture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_lines_from_the_source_reach_ingestion(tmp_path: Path, stub_ingestion: str) -> None:
    log = tmp_path / "access.log"
    log.write_text(CONNECT + "\n" + WITH_CREDENTIAL + "\n")

    # `cat` stands in for the docker exec tail: same contract, no docker.
    assert run(f"cat {log}", stub_ingestion, retry=False) == 0

    assert len(_Capture.received) == 2
    assert _Capture.received[0]["uri"] == "httpbin.org:443"


def test_no_credential_reaches_ingestion(tmp_path: Path, stub_ingestion: str) -> None:
    log = tmp_path / "access.log"
    log.write_text(WITH_CREDENTIAL + "\n")

    run(f"cat {log}", stub_ingestion, retry=False)

    assert "SECRET123" not in json.dumps(_Capture.received)


def test_a_dead_ingestion_drops_loudly_instead_of_crashing(tmp_path: Path) -> None:
    """The tail must survive an ingestion outage; prototype scope drops rather
    than buffers, but it must not die."""
    log = tmp_path / "access.log"
    log.write_text(CONNECT + "\n")

    # Port 1 is reserved and nothing listens there.
    assert run(f"cat {log}", "http://127.0.0.1:1", retry=False) == 1
