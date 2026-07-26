---
name: spark-inference
description: Inspect and switch the local inference route on a DGX Spark running NemoClaw. Use when a sandboxed agent reports inference errors, when checking which model is actually serving, or when switching between managed vLLM, Ollama, and llama.cpp. Triggers on "which model am I using", "inference is failing", "switch models", "check the inference route".
---

# Local inference on a DGX Spark

All inference stays on the box. There is no cloud fallback — if the local route
is down, the correct outcome is a clear error, not a silent egress.

## Check what's actually serving

```bash
nemoclaw <sandbox> status          # phase, GPU, policy, active route
nemoclaw <sandbox> doctor          # probes the inference route
nemoclaw inference list            # configured providers
curl http://127.0.0.1:8000/v1/models   # managed vLLM, direct
```

`doctor` probing green while an agent still fails usually means the model name
in `agents.yaml` isn't one this route serves. Compare against `/v1/models`.

## Switch model or provider

```bash
nemoclaw inference set --provider <provider> --model <model> --sandbox <sandbox>
```

The DGX Spark Express Install default is managed vLLM serving
`qwen3.6-35b-a3b-nvfp4` on `127.0.0.1:8000`. Ollama, when installed, is on
`127.0.0.1:11434`. llama.cpp and anything else OpenAI-compatible attach as a
custom endpoint.

## Per-agent model choice

A model set in an agent's `agents.yaml` (`agents[].model`) is scoped to that
agent. The *route* is a property of the host and is set once with
`nemoclaw inference set`. Don't encode host routing in a manifest — it makes
the manifest non-portable between the laptop and the Spark.

Unified memory means a large model and a small one contend for the same pool.
Giving a read-only subagent a nano-class model is usually a bigger win than
tuning the big one.

## Local inference is reachable but not proxy-exempt

A sandbox reaches `https://inference.local/...` and gets a real completion
even under a fully-closed default-deny policy — but it is proxied, not
exempt. The OCSF stream shows `NET:OPEN [INFO] ALLOWED inference.local:443`
followed by `openshell_router routing proxy inference request
endpoint=http://host.openshell.internal:11435/v1`. `inference.local` is a
built-in gateway route: always reachable because it isn't governed by user
`network_policies`, but OpenShell still proxies it to the host's local model
server and logs it like any other egress. Rely on the reachability; don't
describe it as "bypassing the proxy" (doc-sourced from the nvhack-497.4
verified-on-host finding, relayed here rather than re-verified today).

## When it won't start

The OpenShell gateway embeds k3s inside Docker, which fails on cgroup v2
without host cgroup namespaces. Confirm:

```bash
grep default-cgroupns-mode /etc/docker/daemon.json   # want "host"
sudo systemctl restart docker                        # after fixing
```
