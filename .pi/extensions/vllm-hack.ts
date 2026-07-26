// pi extension: register the vLLM + LiteLLM inference plane on hack
// (DGX Spark) as the `vllm-hack` provider. Auto-discovered by pi when invoked
// inside this trusted repo (`.pi/settings.json`).
//
// Backing service on hack:
//   - LiteLLM: hack-litellm, host port 4000
//   - vLLM: vllm-qwen3.6-27b-fp8, model Qwen3.6-27B-FP8
//
// This workstation currently cannot connect directly to 172.16.10.127:4000,
// so the provider talks to a local SSH tunnel. The apiKey helper starts that
// tunnel if needed, then prints the LiteLLM key from the running container on
// hack. No secret is stored in this repo.

import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  const keyHelper = path.join(__dirname, "../bin/vllm-hack-key");

  pi.registerProvider("vllm-hack", {
    name: "vLLM-Hack (DGX Spark)",
    baseUrl: "http://127.0.0.1:14000/v1",
    apiKey: `!${keyHelper}`,
    api: "openai-completions",
    models: [
      {
        id: "Qwen3.6-27B-FP8",
        name: "Qwen3.6-27B-FP8 (256K, hack GB10) - reasoning + tools + MTP",
        reasoning: true,
        input: ["text"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 262144,
        maxTokens: 32768,
      },
    ],
  });
}
