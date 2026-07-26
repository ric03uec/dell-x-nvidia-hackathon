from __future__ import annotations

import unittest

from mock_api import FINDING_ID, RECOMMENDATION_ID, LiteLLMClient, MockApi


class FakeInferenceClient:
    model = "Qwen3.6-27B-FP8"

    def __init__(self) -> None:
        self.calls = 0

    def status(self) -> dict:
        return {
            "status": "healthy",
            "advertised_model": self.model,
            "loaded_model": self.model,
            "route_match": True,
        }

    def investigate(self, finding: dict) -> dict:
        self.calls += 1
        return {
            "schema_version": "1.0",
            "status": "completed",
            "summary": f"Investigated {finding['finding_id']} locally.",
            "served_model": self.model,
            "route": "litellm-local",
        }


class MockApiTests(unittest.TestCase):
    def test_source_events_and_finding_exclude_resource_evidence(self) -> None:
        api = MockApi()

        status, events_response = api.get("/v1/events")
        self.assertEqual(status, 200)
        self.assertEqual(
            [event["event_id"] for event in events_response["events"]],
            [f"evt-{index:03d}" for index in range(1, 23)],
        )
        self.assertNotIn("risk_score", events_response["events"][0])
        self.assertEqual(events_response["events"][-1]["risk_score"], 92)

        status, finding_response = api.get(f"/v1/findings/{FINDING_ID}")
        self.assertEqual(status, 200)
        finding = finding_response["finding"]
        self.assertEqual(finding["investigation_status"], "completed")
        self.assertEqual(finding["event_ids"], [f"evt-{index:03d}" for index in range(16, 23)])
        self.assertEqual(finding["recommendation_ids"], [RECOMMENDATION_ID])

    def test_approved_decision_is_idempotent_and_creates_ordered_results(self) -> None:
        api = MockApi()
        status, before = api.get("/v1/enforcement-results")
        self.assertEqual((status, before["enforcement_results"]), (200, []))

        request = {"schema_version": "1.0", "decision": "approved"}
        first_status, first = api.decide(request)
        second_status, second = api.decide(request)
        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first["decision"], second["decision"])

        status, after = api.get("/v1/enforcement-results")
        self.assertEqual(status, 200)
        self.assertEqual(
            [(item["status"], item["event_id"]) for item in after["enforcement_results"]],
            [("applied", "evt-025"), ("block_observed", "evt-026")],
        )

        conflict_status, conflict = api.decide({"schema_version": "1.0", "decision": "rejected"})
        self.assertEqual(conflict_status, 409)
        self.assertEqual(conflict["decision"]["decision"], "approved")

    def test_rejected_decision_leaves_enforcement_empty_and_removes_pending(self) -> None:
        api = MockApi()
        status, _ = api.decide({"schema_version": "1.0", "decision": "rejected"})
        self.assertEqual(status, 200)

        status, pending = api.get("/v1/recommendations", {"status": ["pending"]})
        self.assertEqual((status, pending["recommendations"]), (200, []))
        status, enforcement = api.get("/v1/enforcement-results")
        self.assertEqual((status, enforcement["enforcement_results"]), (200, []))

    def test_invalid_decisions_return_json_errors(self) -> None:
        api = MockApi()
        status, response = api.decide({"schema_version": "2.0", "decision": "approved"})
        self.assertEqual(status, 400)
        self.assertEqual(response["schema_version"], "1.0")
        self.assertEqual(response["error"]["code"], "invalid_schema_version")

    def test_local_investigation_is_separate_and_cached(self) -> None:
        client = FakeInferenceClient()
        api = MockApi(client)

        _, before = api.get(f"/v1/findings/{FINDING_ID}")
        self.assertEqual(before["finding"]["investigation"]["status"], "pending")

        first_status, first = api.investigate()
        second_status, second = api.investigate()
        self.assertEqual((first_status, second_status), (200, 200))
        self.assertEqual(first["investigation"], second["investigation"])
        self.assertEqual(first["investigation"]["served_model"], client.model)
        self.assertEqual(client.calls, 1)

        _, system = api.get("/v1/system-status")
        self.assertEqual(system["status"], "operational")
        self.assertTrue(system["model"]["route_match"])

    def test_litellm_ui_url_is_normalized_to_api_base(self) -> None:
        client = LiteLLMClient(
            "http://172.16.10.127:4000/ui/?page=api-keys",
            "not-a-real-key",
            "Qwen3.6-27B-FP8",
        )
        self.assertEqual(client.base_url, "http://172.16.10.127:4000")


if __name__ == "__main__":
    unittest.main()
