"""No proxy, no ingestion, no network — the demo's logic only."""

from __future__ import annotations

from demo import anomalies, traffic
from demo.agent import triage
from demo.catalog import ALL, EXFIL, ROUTINE


def test_catalog_has_no_duplicate_hosts() -> None:
    """Every host becomes a compose network alias; a duplicate would be a
    silently broken alias rather than an error."""
    assert len(ALL) == len(set(ALL))


def test_exfil_destination_is_not_part_of_the_baseline() -> None:
    """The whole story is that this host has no history. If it were also in
    ROUTINE the traffic generator would give it one."""
    assert EXFIL not in ROUTINE


def test_user_pool_is_stable_for_a_seed() -> None:
    """A recorded demo has to be re-recordable."""
    assert traffic.user_pool(10, seed=7) == traffic.user_pool(10, seed=7)
    assert len(set(traffic.user_pool(40))) > 1


def test_every_anomaly_is_reachable_by_key() -> None:
    for key, anomaly in anomalies.BY_KEY.items():
        assert anomaly.key == key
        assert anomaly.title and anomaly.why


# --- the agent's correlation --------------------------------------------


def _event(dest: str, up: int, eid: str) -> dict:
    return {"event_id": eid, "destination": dest, "req_bytes": up}


def test_triage_picks_the_unseen_destination_not_the_busiest() -> None:
    """A baseline host with heavy traffic must not outrank a quiet stranger."""
    events = [
        _event("crm.northwind-labs.test", 50_000_000, "e1"),  # busy, but known
        _event(EXFIL, 8_000_000, "e2"),  # unknown
    ]
    verdict = triage(events, set(ROUTINE))
    assert verdict is not None
    assert verdict.destination == EXFIL


def test_triage_ignores_small_transfers_to_unknown_hosts() -> None:
    """Visiting a new site is not an incident; bulk upload to one is."""
    assert triage([_event("someones-blog.test", 4_000, "e1")], set(ROUTINE)) is None


def test_triage_returns_none_when_only_baseline_traffic_exists() -> None:
    events = [_event(h, 9_000_000, f"e{i}") for i, h in enumerate(ROUTINE)]
    assert triage(events, set(ROUTINE)) is None


def test_triage_rationale_names_the_evidence() -> None:
    """The finding has to be explainable to an analyst, not just a score."""
    verdict = triage([_event(EXFIL, 8_000_000, "e1")], set(ROUTINE))
    assert verdict is not None
    assert EXFIL in verdict.rationale
    assert "8,000,000" in verdict.rationale
    assert 60 <= verdict.risk <= 99
