import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, submitRecommendationDecision } from "./client.js";

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
  assert.deepEqual(JSON.parse(captured.options.body), {
    schema_version: "1.0",
    decision: "approved",
  });
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
