from __future__ import annotations

import pytest

from ingestion.vulnerabilities import CisaKevFeed, VulnerabilityFeedError


def catalog() -> dict[str, object]:
    return {
        "catalogVersion": "2026.07.24",
        "dateReleased": "2026-07-24T17:40:56Z",
        "vulnerabilities": [
            {
                "cveID": "CVE-2026-10001",
                "vendorProject": "Earlier Vendor",
                "product": "Earlier Product",
                "vulnerabilityName": "Earlier vulnerability",
                "dateAdded": "2026-07-20",
                "dueDate": "2026-08-10",
                "knownRansomwareCampaignUse": "Unknown",
            },
            {
                "cveID": "CVE-2026-10002",
                "vendorProject": "Recent Vendor",
                "product": "Recent Product",
                "vulnerabilityName": "Recent vulnerability",
                "dateAdded": "2026-07-24",
                "dueDate": "2026-08-01",
                "knownRansomwareCampaignUse": "Known",
            },
        ],
    }


def test_feed_normalizes_sorts_and_limits_cisa_records() -> None:
    feed = CisaKevFeed(fetch=lambda _url: catalog())

    result = feed.get(1)

    assert result["count"] == 2
    assert result["shown"] == 1
    assert result["stale"] is False
    assert result["vulnerabilities"][0] == {
        "cve_id": "CVE-2026-10002",
        "vendor": "Recent Vendor",
        "product": "Recent Product",
        "name": "Recent vulnerability",
        "date_added": "2026-07-24",
        "due_date": "2026-08-01",
        "ransomware_use": "Known",
        "description": None,
        "required_action": None,
        "source_url": (
            "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
            "?search_api_fulltext=CVE-2026-10002"
        ),
    }


def test_feed_serves_stale_cache_after_refresh_failure() -> None:
    responses = iter([catalog(), VulnerabilityFeedError("offline")])

    def fetch(_url: str) -> dict[str, object]:
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    feed = CisaKevFeed(ttl_seconds=0, fetch=fetch)
    assert feed.get(10)["stale"] is False
    assert feed.get(10)["stale"] is True


def test_feed_fails_explicitly_without_a_cache() -> None:
    def unavailable(_url: str) -> dict[str, object]:
        raise VulnerabilityFeedError("offline")

    with pytest.raises(VulnerabilityFeedError, match="offline"):
        CisaKevFeed(fetch=unavailable).get(10)
