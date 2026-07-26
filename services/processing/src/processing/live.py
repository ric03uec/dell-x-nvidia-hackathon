"""Polling live scorer that degrades independently from GPU and inference."""

from __future__ import annotations

import json
import time
from collections import deque
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from processing.anomaly import IsolationForestModel
from processing.client import IngestionClient
from processing.pipeline import detect_window


class LiveScorer:
    def __init__(
        self,
        ingestion_url: str,
        *,
        model: IsolationForestModel | None = None,
        known_destinations: set[str] | None = None,
        window_size: int = 20,
        threshold: float = 70.0,
    ) -> None:
        self.ingestion_url = ingestion_url.rstrip("/")
        self.client = IngestionClient(self.ingestion_url)
        self.model = model
        self.known_destinations = known_destinations or set()
        self.window: deque[dict[str, Any]] = deque(maxlen=window_size)
        self.threshold = threshold
        self.after_id: str | None = None

    def poll_once(self) -> int:
        query = urlencode({"after_id": self.after_id}) if self.after_id else ""
        url = f"{self.ingestion_url}/v1/events" + (f"?{query}" if query else "")
        try:
            with urlopen(url, timeout=10) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"ingestion returned HTTP {error.code}") from error
        except (URLError, json.JSONDecodeError) as error:
            raise RuntimeError("failed to poll ingestion") from error
        events = payload.get("events", []) if isinstance(payload, dict) else payload
        if not isinstance(events, list):
            raise RuntimeError("ingestion returned an invalid event list")
        for event in events:
            if not isinstance(event, dict):
                continue
            self.window.append(event)
            self.after_id = str(event.get("event_id", self.after_id or ""))
            detection = detect_window(
                self.window,
                known_destinations=self.known_destinations,
                anomaly_model=self.model,
                threshold=self.threshold,
            )
            if detection.finding is not None:
                self.client.post_finding(detection.finding)
        return len(events)

    def run(self, *, interval: float = 1.0) -> None:
        while True:
            self.poll_once()
            time.sleep(interval)
