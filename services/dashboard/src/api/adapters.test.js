import assert from "node:assert/strict";
import test from "node:test";

import {
  formatBytes,
  toCvePage,
  toFeedbackPage,
  toRiskEvent,
  toSystemStatusView,
} from "./adapters.js";

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
  assert.equal(view.appliance.gpuMemoryLabel, "Memory");
  assert.equal(view.appliance.gpuStatus, "Unavailable");
  assert.equal(view.footer.healthy, false);
  assert.equal(view.footer.queueDepth, null);
});

test("formats decimal byte units used by the existing console", () => {
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(25_000_000), "25.0 MB");
});

test("adapts the live CISA KEV feed without inventing asset or CVSS data", () => {
  const page = toCvePage({
    count: 1653,
    fetched_at: "2026-07-26T14:00:00Z",
    stale: false,
    policies: [{ cve_id: "CVE-2026-12345", disposition: "rejected" }],
    vulnerabilities: [{
      cve_id: "CVE-2026-12345",
      vendor: "Example Vendor",
      product: "Gateway",
      date_added: "2026-07-24",
      due_date: "2026-08-01",
      ransomware_use: "Known",
    }],
  });

  assert.equal(page.title, "CISA KEV Watchlist");
  assert.deepEqual(page.columns.map((column) => column.label), [
    "CVE ID", "Added", "Remediate by", "Ransomware", "Status", "Policy",
  ]);
  assert.deepEqual(page.rows[0][0], ["CVE-2026-12345", "Example Vendor · Gateway"]);
  assert.equal(page.rows[0][4].badge, "Rejected");
  assert.deepEqual(page.rows[0][5], {
    action: "restore",
    cveId: "CVE-2026-12345",
    label: "Restore",
  });
  assert.equal(page.metrics[3][1], "1");
});

test("adapts analyst decisions without inventing review timings", () => {
  const page = toFeedbackPage({
    count: 2,
    recommendations: [
      {
        recommendation_id: "rec-001",
        target: "unknown-storage.example",
        reason: "Evidence exceeded threshold.",
        scope: "business-agent",
        status: "approved",
        decision: { analyst: "J. Ortiz", timestamp: "2026-07-26T14:02:00Z" },
      },
      {
        recommendation_id: "rec-002",
        target: "pastebin.com",
        reason: "Paste site upload.",
        scope: "business-agent",
        status: "pending",
      },
    ],
  });

  assert.equal(page.meta, "1 of 2 recommendations reviewed");
  assert.deepEqual(page.metrics.map((metric) => metric[1]), ["1", "1", "0", "50%"]);
  assert.deepEqual(page.rows[0][0], ["unknown-storage.example", "Evidence exceeded threshold."]);
  assert.equal(page.rows[0][1], "J. Ortiz");
  assert.equal(page.rows[0][2], "14:02:00");
  assert.equal(page.rows[0][4].level, "ok");
  // A recommendation nobody has reviewed must not borrow another analyst's name.
  assert.equal(page.rows[1][1], "Unavailable");
  assert.equal(page.rows[1][2], "Unavailable");
  assert.equal(page.rows[1][4].badge, "pending");
});

test("shows an empty review queue rather than fabricating rows", () => {
  const page = toFeedbackPage(null);

  assert.equal(page.meta, "Waiting for API");
  assert.deepEqual(page.rows, []);
});
