import assert from "node:assert/strict";
import test from "node:test";

import {
  ApiError,
  getVulnerabilities,
  rejectVulnerability,
  restoreVulnerability,
  startFindingInvestigation,
  submitRecommendationDecision,
} from "./client.js";

test("submits only the versioned explicit recommendation decision", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return new Response(
      JSON.stringify({ schema_version: "1.0", decision: { decision: "approved" } }),
      { status: 200 },
    );
  };

  try {
    await submitRecommendationDecision("rec/one", "approved");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(captured.url, "/api/v1/recommendations/rec%2Fone/decision");
  const body = JSON.parse(captured.options.body);
  assert.equal(body.schema_version, "1.0");
  assert.equal(body.recommendation_id, "rec/one");
  assert.equal(body.decision, "approved");
  assert.equal(body.analyst, "local-analyst");
  assert.equal(Number.isNaN(Date.parse(body.timestamp)), false);
});

test("rejects unsupported response schema versions", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ schema_version: "2.0" }));

  try {
    await assert.rejects(
      submitRecommendationDecision("rec-one", "rejected"),
      (error) => error instanceof ApiError && error.code === "UNSUPPORTED_SCHEMA_VERSION",
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("starts investigation without sending finding evidence from the browser", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return new Response(
      JSON.stringify({ schema_version: "1.0", investigation: { status: "completed" } }),
      { status: 200 },
    );
  };

  try {
    await startFindingInvestigation("fnd-one");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(captured.url, "/api/v1/findings/fnd-one/investigate");
  assert.deepEqual(JSON.parse(captured.options.body), { schema_version: "1.0" });
});

test("loads vulnerabilities through the ingestion proxy", async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return new Response(JSON.stringify({ schema_version: "1.0", vulnerabilities: [] }));
  };

  try {
    await getVulnerabilities();
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(captured.url, "/api/v1/vulnerabilities");
  assert.equal(captured.options.method, "GET");
});

test("persists and restores a CVE rejection policy", async () => {
  const originalFetch = globalThis.fetch;
  const captured = [];
  globalThis.fetch = async (url, options) => {
    captured.push({ url, options });
    return new Response(JSON.stringify({ schema_version: "1.0" }));
  };

  try {
    await rejectVulnerability("CVE-2026-12345");
    await restoreVulnerability("CVE-2026-12345");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(captured[0].url, "/api/v1/vulnerability-policies/CVE-2026-12345");
  assert.equal(captured[0].options.method, "POST");
  assert.deepEqual(JSON.parse(captured[0].options.body), {
    schema_version: "1.0",
    cve_id: "CVE-2026-12345",
    disposition: "rejected",
    analyst: "local-analyst",
  });
  assert.equal(captured[1].options.method, "DELETE");
});
