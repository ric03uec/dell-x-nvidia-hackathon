from __future__ import annotations

import unittest

from mock_api import FINDING_ID, MockApi, RECOMMENDATION_ID


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
        self.assertEqual(
            finding["event_ids"], [f"evt-{index:03d}" for index in range(16, 23)]
        )
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

        conflict_status, conflict = api.decide(
            {"schema_version": "1.0", "decision": "rejected"}
        )
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


if __name__ == "__main__":
    unittest.main()
