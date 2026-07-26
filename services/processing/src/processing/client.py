"""Minimal ingestion REST client that never logs response payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class IngestionClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: Mapping[str, Any]) -> None:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"ingestion returned HTTP {response.status}")
        except HTTPError as error:
            raise RuntimeError(f"ingestion returned HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError("ingestion request failed") from error

    def post_finding(self, finding: Mapping[str, Any]) -> None:
        self._post("/v1/findings", finding)

    def post_recommendation(self, recommendation: Mapping[str, Any]) -> None:
        self._post("/v1/recommendations", recommendation)
