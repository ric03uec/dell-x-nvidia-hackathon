"""Cached client for CISA's Known Exploited Vulnerabilities catalog."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CISA_KEV_URL = os.environ.get(
    "CISA_KEV_URL",
    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
)


class VulnerabilityFeedError(RuntimeError):
    pass


def _fetch_catalog(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "SquidWard/1.0"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise VulnerabilityFeedError("CISA KEV feed is unavailable") from error
    if not isinstance(payload, dict):
        raise VulnerabilityFeedError("CISA KEV feed returned an invalid catalog")
    return payload


class CisaKevFeed:
    def __init__(
        self,
        *,
        url: str = CISA_KEV_URL,
        ttl_seconds: float = 900,
        fetch: Callable[[str], dict[str, Any]] = _fetch_catalog,
    ) -> None:
        self.url = url
        self.ttl_seconds = ttl_seconds
        self.fetch = fetch
        self._catalog: dict[str, Any] | None = None
        self._cached_at = 0.0
        self._lock = Lock()

    def get(self, limit: int) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            stale = False
            if self._catalog is None or now - self._cached_at >= self.ttl_seconds:
                try:
                    self._catalog = self._normalize(self.fetch(self.url))
                    self._cached_at = now
                except VulnerabilityFeedError:
                    if self._catalog is None:
                        raise
                    stale = True

            assert self._catalog is not None
            vulnerabilities = self._catalog["vulnerabilities"][:limit]
            return {
                **self._catalog,
                "shown": len(vulnerabilities),
                "stale": stale,
                "vulnerabilities": vulnerabilities,
            }

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        records = payload.get("vulnerabilities")
        if not isinstance(records, list):
            raise VulnerabilityFeedError("CISA KEV feed returned an invalid catalog")

        vulnerabilities = []
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("cveID"), str):
                continue
            vulnerabilities.append(
                {
                    "cve_id": record["cveID"],
                    "vendor": record.get("vendorProject"),
                    "product": record.get("product"),
                    "name": record.get("vulnerabilityName"),
                    "date_added": record.get("dateAdded"),
                    "due_date": record.get("dueDate"),
                    "ransomware_use": record.get("knownRansomwareCampaignUse"),
                    "description": record.get("shortDescription"),
                    "required_action": record.get("requiredAction"),
                    "source_url": f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={record['cveID']}",
                }
            )
        vulnerabilities.sort(key=lambda item: item.get("date_added") or "", reverse=True)
        return {
            "source": "CISA Known Exploited Vulnerabilities",
            "source_url": self.url,
            "catalog_version": payload.get("catalogVersion"),
            "catalog_released_at": payload.get("dateReleased"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "count": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
        }
