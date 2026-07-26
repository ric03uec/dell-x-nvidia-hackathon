import assert from "node:assert/strict";
import test from "node:test";

import { formatBytes, toRiskEvent, toSystemStatusView } from "./adapters.js";

test("formats event projections without turning missing risk into zero", () => {
  const event = toRiskEvent({
    event_id: "evt-001",
    timestamp: "2026-07-26T14:00:00Z",
    actor: "business-agent",
    request_bytes: 25_000_000,
  });

  assert.equal(event.id, "evt-001");
  assert.equal(event.bytes, "25.0 MB");
  assert.equal(event.risk, null);
});

test("keeps unavailable system values explicit", () => {
  const view = toSystemStatusView({ schema_version: "1.0", status: "unknown" });

  assert.equal(view.appliance.egress, "Unavailable");
  assert.equal(view.appliance.gpuUtilization, null);
  assert.equal(view.footer.healthy, false);
  assert.equal(view.footer.queueDepth, null);
});

test("formats decimal byte units used by the existing console", () => {
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(25_000_000), "25.0 MB");
});
