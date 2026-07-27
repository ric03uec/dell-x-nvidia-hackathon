"""Authenticated client for triggering the local OpenClaw security agent."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenClawError(RuntimeError):
    pass


class OpenClawClient:
    def __init__(self, base_url: str, token: str, timeout: float = 600) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> OpenClawClient | None:
        token = os.environ.get("OPENCLAW_GATEWAY_TOKEN")
        if not token:
            return None
        return cls(
            os.environ.get("OPENCLAW_GATEWAY_URL", "http://127.0.0.1:18789"),
            token,
            float(os.environ.get("OPENCLAW_TIMEOUT", "600")),
        )

    def investigate(self, finding_id: str) -> None:
        prompt = (
            f"Investigate finding {finding_id}. Retrieve authoritative evidence using the "
            "squidward-ingestion MCP tools. Persist a concise factual result with "
            "submit_investigation. If warranted, submit only a pending deny_destination "
            "recommendation. Never approve or enforce a recommendation."
        )
        request = Request(
            f"{self.base_url}/v1/responses",
            data=json.dumps({"model": "openclaw:main", "input": prompt}).encode(),
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "x-openclaw-agent-id": "main",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if not 200 <= response.status < 300:
                    raise OpenClawError(f"OpenClaw returned HTTP {response.status}")
                json.loads(response.read())
        except HTTPError as error:
            raise OpenClawError(f"OpenClaw returned HTTP {error.code}") from error
        except URLError as error:
            raise OpenClawError("OpenClaw is unavailable") from error
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OpenClawError("OpenClaw returned an invalid response") from error
