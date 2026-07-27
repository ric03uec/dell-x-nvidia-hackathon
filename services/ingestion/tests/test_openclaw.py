from __future__ import annotations

import json
from typing import Any

from ingestion import openclaw
from ingestion.openclaw import OpenClawClient


class FakeResponse:
    status = 200

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        return b'{"id":"response-001"}'


def test_investigation_trigger_sends_only_the_finding_reference(monkeypatch) -> None:
    captured = None

    def fake_urlopen(request, timeout):
        nonlocal captured
        captured = (request, timeout)
        return FakeResponse()

    monkeypatch.setattr(openclaw, "urlopen", fake_urlopen)
    client = OpenClawClient("http://127.0.0.1:18789", "secret-token", timeout=12)
    client.investigate("finding-001")

    request, timeout = captured
    payload = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:18789/v1/responses"
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert request.headers["X-openclaw-agent-id"] == "main"
    assert timeout == 12
    assert payload["model"] == "openclaw"
    assert "finding-001" in payload["input"]
    assert "evidence" not in payload
