"""Both surfaces, one store — the tests exist mostly to prove they agree.

No live Squid, no agent runtime, no network: fixtures only.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

# The app opens its database at import time, so the env var has to be set first.
_tmpdir = tempfile.mkdtemp()
os.environ["INGESTION_DB"] = os.path.join(_tmpdir, "test.db")

from ingestion import store  # noqa: E402
from ingestion.app import app, conn, mcp  # noqa: E402

SQUID_EVENT: dict[str, Any] = {
    "ts": 1785107042.961,
    "src": "172.20.0.1",
    "method": "CONNECT",
    "uri": "evil.test:443",
    "status": 200,
    "req_bytes": 101326,
    "resp_bytes": 105727,
    "result": "TCP_TUNNEL",
    "dst_ip": "13.223.23.68",
}


@pytest.fixture(autouse=True)
def clean_db() -> Iterator[None]:
    for table in (
        "events",
        "findings",
        "recommendations",
        "decisions",
        "enforcement_results",
        "finding_labels",
        "snapshots",
        "rules",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Entering the context manager runs the lifespan. If app were built without
    # mcp_app.lifespan, the MCP session manager would never initialise — see
    # test_mcp_endpoint_is_mounted_with_lifespan.
    with TestClient(app) as c:
        yield c


def test_health_reports_database_reachability(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["schema_version"] == "1.0"


def test_every_rest_response_is_versioned(client: TestClient) -> None:
    # services/dashboard/src/api/client.js throws on any payload without this.
    for path in ("/health", "/v1/events", "/v1/rules", "/v1/recommendations"):
        assert client.get(path).json()["schema_version"] == "1.0"


def test_post_then_get_events(client: TestClient) -> None:
    posted = client.post("/v1/events", json=[SQUID_EVENT])
    assert posted.status_code == 201
    assert posted.json()["accepted"] == 1

    events = client.get("/v1/events").json()["events"]
    assert len(events) == 1
    # `uri` of a CONNECT reduces to the destination the rules key on.
    assert events[0]["destination"] == "evil.test:443"
    assert events[0]["req_bytes"] == 101326


def test_unknown_fields_are_preserved_not_rejected(client: TestClient) -> None:
    # The exfilguard field set is provisional until dxnvh-332.2 freezes it.
    client.post("/v1/events", json=[{**SQUID_EVENT, "future_field": "keep me"}])
    raw = client.get("/v1/events").json()["events"][0]["raw"]
    assert "future_field" in raw


def test_canonical_pipeline_is_persisted_and_returned_in_contract_shape(
    client: TestClient,
) -> None:
    event = {
        "schema_version": "1.0",
        "event_id": "evt-canonical-001",
        "timestamp": "2026-07-26T14:00:00Z",
        "source_type": "mitmproxy",
        "actor": "business-agent",
        "action": "http_post",
        "destination": "receiver.demo.local",
        "request_bytes": 25_000_000,
        "attributes": {
            "body_stored": False,
            "openshell_run_id": "run-synthetic-001",
        },
    }
    finding = {
        "schema_version": "1.0",
        "finding_id": "finding-canonical-001",
        "event_ids": [event["event_id"]],
        "risk_score": 95,
        "severity": "critical",
        "detectors": ["large_transfer"],
        "summary": "Synthetic suspicious transfer.",
    }
    recommendation = {
        "schema_version": "1.0",
        "recommendation_id": "rec-canonical-001",
        "finding_id": finding["finding_id"],
        "action_type": "deny_destination",
        "target": "receiver.demo.local",
        "scope": "business-agent",
        "reason": "Synthetic evidence exceeded the threshold.",
    }

    assert client.post("/v1/events", json=event).status_code == 201
    assert client.post("/v1/findings", json=finding).status_code == 201
    assert client.post("/v1/recommendations", json=recommendation).status_code == 201
    returned = client.get("/v1/events").json()["events"][0]
    assert returned["event_id"] == event["event_id"]
    assert returned["action"] == event["action"]
    assert returned["attributes"] == event["attributes"]
    assert returned["finding_id"] == finding["finding_id"]

    decision = client.post(
        "/v1/recommendations/rec-canonical-001/decision",
        json={"schema_version": "1.0", "decision": "approved"},
    )
    assert decision.status_code == 200
    assert decision.json()["decision"]["decision"] == "approved"
    assert client.get("/v1/rules/check", params={"dst": "receiver.demo.local"}).json()["denied"]

    enforcement = {
        "schema_version": "1.0",
        "enforcement_result_id": "enf-canonical-001",
        "recommendation_id": "rec-canonical-001",
        "status": "applied",
    }
    assert client.post("/v1/enforcement-results", json=enforcement).status_code == 201
    assert client.get("/v1/enforcement-results").json()["count"] == 1
    snapshot = client.post("/v1/snapshots")
    assert snapshot.status_code == 201
    assert client.get(f"/v1/snapshots/{snapshot.json()['snapshot_id']}").status_code == 200

    unrelated = {**event, "event_id": "evt-real-001", "attributes": {"body_stored": False}}
    assert client.post("/v1/events", json=unrelated).status_code == 201
    cleared = client.delete("/v1/demo-data")
    assert cleared.status_code == 200
    assert cleared.json()["removed"] == {
        "events": 1,
        "findings": 1,
        "recommendations": 1,
        "decisions": 1,
        "enforcement_results": 1,
        "labels": 0,
        "rules": 1,
    }
    remaining = client.get("/v1/events").json()["events"]
    assert [item["event_id"] for item in remaining] == ["evt-real-001"]
    assert client.get("/v1/recommendations").json()["count"] == 0


# --- the path that actually enforces ------------------------------------


def test_recommendation_only_becomes_a_rule_after_approval(client: TestClient) -> None:
    rec_id = store.add_recommendation(conn, "deny_destination", "evil.test", "25MB upload")

    # Pending: nothing is denied yet.
    assert client.get("/v1/rules").json()["rules"] == []
    assert client.get("/v1/rules/check", params={"dst": "evil.test"}).json()["denied"] is False

    approved = client.post(
        f"/v1/recommendations/{rec_id}/decision",
        json={"approve": True, "actor": "analyst@example.test"},
    )
    assert approved.status_code == 200
    assert approved.json()["recommendation"]["status"] == "approved"

    rules = client.get("/v1/rules").json()["rules"]
    assert [r["destination"] for r in rules] == ["evil.test"]
    assert rules[0]["approved_by"] == "analyst@example.test"


def test_rejection_does_not_create_a_rule(client: TestClient) -> None:
    rec_id = store.add_recommendation(conn, "deny_destination", "fine.test", "false positive")
    client.post(
        f"/v1/recommendations/{rec_id}/decision",
        json={"approve": False, "actor": "analyst@example.test"},
    )
    assert client.get("/v1/rules").json()["rules"] == []


def test_rules_txt_is_squid_dstdomain_format(client: TestClient) -> None:
    rec_id = store.add_recommendation(conn, "deny_destination", "evil.test", "why")
    client.post(
        f"/v1/recommendations/{rec_id}/decision",
        json={"approve": True, "actor": "a@b.test"},
    )
    body = client.get("/v1/rules.txt")
    assert body.headers["content-type"].startswith("text/plain")
    # One destination per line, no envelope — squid parses this, not the dashboard.
    assert body.text == "evil.test\n"


def test_check_matches_subdomains(client: TestClient) -> None:
    rec_id = store.add_recommendation(conn, "deny_destination", "evil.test", "why")
    client.post(
        f"/v1/recommendations/{rec_id}/decision",
        json={"approve": True, "actor": "a@b.test"},
    )
    check = "/v1/rules/check"
    # Parent-domain match, matching squid's own dstdomain semantics.
    assert client.get(check, params={"dst": "upload.evil.test:443"}).json()["denied"] is True
    assert client.get(check, params={"dst": "evil.test:443"}).json()["denied"] is True
    assert client.get(check, params={"dst": "notevil.test"}).json()["denied"] is False
    # A rule on evil.test must not deny an unrelated domain that ends similarly.
    assert client.get(check, params={"dst": "evil.test.other.test"}).json()["denied"] is False


def test_decision_on_unknown_recommendation_is_404(client: TestClient) -> None:
    assert (
        client.post(
            "/v1/recommendations/rec-nope/decision",
            json={"approve": True, "actor": "a@b.test"},
        ).status_code
        == 404
    )


# --- MCP surface --------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_client_lists_and_calls_tools() -> None:
    from fastmcp import Client

    async with Client(mcp) as mcp_client:
        names = {t.name for t in await mcp_client.list_tools()}
        assert {
            "query_events",
            "get_evidence",
            "get_rules",
            "submit_finding",
            "recommend_policy",
        } <= names

        store.add_event(conn, SQUID_EVENT)
        result = await mcp_client.call_tool("query_events", {"limit": 10})
        assert len(result.data["events"]) == 1


@pytest.mark.asyncio
async def test_recommend_policy_rejects_an_action_outside_the_enum() -> None:
    """The enum is enforced by the tool schema, so a bad action fails at the
    protocol boundary rather than inside handler code (dxnvh-2jb.7)."""
    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    async with Client(mcp) as mcp_client:
        with pytest.raises(ToolError):
            await mcp_client.call_tool(
                "recommend_policy",
                {"action_type": "rm -rf /", "destination": "evil.test", "rationale": "x"},
            )


@pytest.mark.asyncio
async def test_mcp_recommendation_is_visible_to_rest(client: TestClient) -> None:
    """The two surfaces share one store — an agent's recommendation must show
    up for the analyst without any syncing step."""
    from fastmcp import Client

    async with Client(mcp) as mcp_client:
        result = await mcp_client.call_tool(
            "recommend_policy",
            {
                "action_type": "deny_destination",
                "destination": "evil.test",
                "rationale": "25MB to an unseen host",
            },
        )
        rec_id = result.data["recommendation_id"]

    pending = client.get("/v1/recommendations", params={"status": "pending"}).json()
    assert [r["recommendation_id"] for r in pending["recommendations"]] == [rec_id]


def test_mcp_endpoint_is_mounted_with_lifespan(client: TestClient) -> None:
    """Regression guard for the documented failure mode: constructing FastAPI
    without mcp_app.lifespan mounts fine and then fails on session state, with
    no startup error pointing at the cause."""
    assert app.router.lifespan_context is not None
    # A GET without the MCP headers is rejected by the protocol, not 404 —
    # which proves something is actually mounted and speaking MCP.
    assert client.get("/mcp/").status_code != 404
