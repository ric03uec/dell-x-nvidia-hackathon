---
name: openshell-egress-audit
description: Catch and enforce unregistered network egress from an OpenShell sandbox by reading its structured OCSF violation stream. Use when locking down what a sandboxed job may reach, when harvesting what egress a job actually attempts, when a sandbox call is blocked with "CONNECT tunnel failed, response 403", or when building an agent that reasons over blocked-egress records. Triggers on "egress policy", "sandbox is blocking my request", "audit network calls", "what is this sandbox reaching", "allow this endpoint", "policy update --add-endpoint", "OCSF DENIED".
---

# OpenShell egress audit: the harvest-enforce ratchet

Verified on `factory-orca` (x86_64 Debian, OpenShell **0.0.85**, NemoClaw
**v0.0.93**, Docker sandbox driver) during nvhack-497.4. Every claim below is
tagged **[verified-on-host]** (observed on 0.0.85 here) or **[UNVERIFIED]**
(extrapolated / not run). See `docs/spikes/nvhack-ca7.md` §"Run on host (497.4)"
for the raw captures behind each claim.

**Arch caveat:** findings here are from **amd64 (x86_64)**; the GB10/DGX Spark
target is **aarch64**. The network/proxy/OCSF-shape findings are protocol-level
and transfer well. The Landlock/filesystem lines (`Landlock ruleset built …
compat:BestEffort`) are kernel-adjacent and are the **[UNVERIFIED]** risk across
that gap — re-check them on aarch64.

## The core idea: default-deny IS the audit posture

There is **no top-level `enforcement: audit` switch** — OpenShell rejects an
`enforcement` key at policy top level outright **[verified-on-host]**:

```
failed to parse sandbox policy YAML
unknown field `enforcement`, expected one of `version`, `filesystem_policy`,
`landlock`, `process`, `network_policies`
```

`enforcement` is a **per-endpoint** field (`enforce` | `audit`) inside
`network_policies[].endpoints[]` **[verified-on-host]**. To surface *unregistered*
egress you don't name endpoints at all — you run **default-deny** (empty
`network_policies: {}`) and read the `DENIED` records the sandbox emits. A
per-endpoint `:audit` rule is the opposite tool: it *allows and logs* a host you
already named, and its record reads `ALLOWED`, so it never surfaces the unknown
host you were trying to catch **[verified-on-host]**.

## The violation record (OCSF)

A denied egress produces a structured **OCSF** (Open Cybersecurity Schema
Framework) line, readable from the **host** (outside the sandbox)
**[verified-on-host]**:

```
[1785052548.742] [sandbox] [OCSF ] [ocsf] NET:OPEN [MED] DENIED /usr/bin/curl(51) -> api.mixpanel.com:443 [policy:- engine:opa] [reason:network connections not allowed by policy]
```

Fields you can key on **[verified-on-host]**:

- `1785052548.742` — epoch seconds.millis
- `[sandbox]` — source (vs `[gateway]`)
- `NET:OPEN` — class:activity (also `HTTP:GET`, `SSH:OPEN`, `CONFIG:*`)
- `[MED]` — severity (`[INFO]` on allows)
- `DENIED` / `ALLOWED` — disposition
- `/usr/bin/curl(51)` — **binary + pid** (kernel-resolved `/proc/<pid>/exe`)
- `api.mixpanel.com:443` — **destination host:port**; a raw IP fills the host
  slot verbatim (`203.0.113.5:443`), so there is always a value to match
- `[policy:- engine:opa]` — matched rule (`-` = none) and engine: `opa`
  (L3/L4 CONNECT) or `l7` (HTTP method/path)
- `[reason:…]` — human+machine readable cause

One sandbox emits **multiple independently-attributable records** (one per call,
distinguished by pid and rule) — the stream does not collapse per sandbox
**[verified-on-host]**.

## Where the log lives / how to tail it

```bash
openshell logs <sandbox> --source sandbox --level debug   # OCSF stream
openshell logs <sandbox> --source sandbox --tail          # follow live
openshell logs <sandbox> --since 5m
```

`openshell logs` is a **bounded ring buffer** — it warns *"log buffer contains
only the last 217 lines"* **[verified-on-host]**. The records are **not** in the
gateway's own file (`~/.local/state/nemoclaw/openshell-docker-gateway/openshell-gateway.log`
has zero `DENIED` lines) **[verified-on-host]**. Instead the sandbox flushes
denial **analysis + activity summaries** to the gateway (*"Flushed denial
analysis to gateway proposals=1 … denied_action_count=1"*), persisted in the
gateway's `openshell.db` **[verified-on-host]**. So a durable auditor must
`--tail` the stream or read the persisted proposals; **do not rely on
scrollback**. The exact CLI/API to read persisted proposals back out was not
found in `openshell --help` **[UNVERIFIED]** — treat `--tail` capture as the
reliable path today.

## The ratchet: harvest → enforce (runnable)

Start closed, run the job, watch what it was denied, allow exactly that, re-run.

**1. Create a default-deny sandbox** (static filesystem posture is locked at
creation — you cannot change `filesystem_policy`/`include_workdir` on a live
sandbox, only the network half hot-reloads) **[verified-on-host]**:

```bash
openshell sandbox create --name job1 --policy policy.yaml   # network_policies: {}
```

**2. Run the job and harvest denials** (from the host):

```bash
openshell sandbox exec -n job1 -- bash -s < jobs/the-job.sh
openshell logs job1 --source sandbox --level debug | grep DENIED
# -> NET:OPEN ... DENIED /usr/bin/curl(65) -> api.github.com:443 [reason:network connections not allowed by policy]
```

**3. Enforce: allow exactly the denied endpoint, live, no restart.** The
**load-bearing gotcha**: endpoints are **binary-scoped** — you must pass
`--binary` for the binary that made the call, or it stays denied with a *new*
reason (`binary '/usr/bin/curl' not allowed in policy '<rule>'`)
**[verified-on-host]**:

```bash
openshell policy update job1 \
  --add-endpoint 'api.github.com:443:read-write:rest:enforce' \
  --binary /usr/bin/curl \
  --rule-name allow-github \
  --wait
# -> Policy version N loaded (active version: N)   (sub-second, no restart)
```

**4. Re-run — the same call now succeeds** and logs `ALLOWED … [policy:allow-github
engine:opa]` **[verified-on-host]**. That closes one turn of the ratchet; repeat
for each real denial until the job is clean.

Endpoint syntax: `host:port[:access[:protocol[:enforcement[:options]]]]` where
access ∈ `read-only|read-write`, protocol ∈ `rest|websocket`, enforcement ∈
`enforce|audit`. The `host:port:access:protocol:enforcement` prefix was run on
host **[verified-on-host]**; the trailing `:options` segment is from help text
and was never exercised **[UNVERIFIED]**. `--add-allow host:port:METHOD:/path/**`
adds L7 method/path rules: `engine:l7` `ALLOWED` records were observed on host
(from applying the fixture policy) **[verified-on-host]**, but the `--add-allow`
CLI form itself is from help text and was not invoked during 497.4 **[UNVERIFIED]**.

## Local inference is reachable but NOT proxy-exempt

A sandbox reaches `https://inference.local/...` and gets a real completion even
under fully-closed default-deny **[verified-on-host]** — but it is **proxied,
not exempt**. The OCSF stream shows `NET:OPEN [INFO] ALLOWED inference.local:443`
then `openshell_router routing proxy inference request
endpoint=http://host.openshell.internal:11435/v1` **[verified-on-host]**.
`inference.local` is a **built-in gateway route** (not governed by user
`network_policies`, so always reachable) that OpenShell proxies to the host's
Ollama and audits like any other egress. Rely on the reachability; do **not**
describe it as "bypassing the proxy" (correction to `spark-inference/SKILL.md`,
filed nvhack-ujl).

## Recurring gotchas

- **No top-level audit mode.** Default-deny is the audit posture; `:audit` is
  per-endpoint allow-and-log. **[verified-on-host]**
- **Endpoints are binary-scoped.** `--add-endpoint` without `--binary` denies
  the caller. The deny reason even includes a SYMLINK HINT: the path is the
  kernel-resolved `/proc/<pid>/exe` target, not the symlink you typed.
  **[verified-on-host]**
- **Static policy is create-time only.** `filesystem_policy`, `landlock`,
  `process` are locked at `sandbox create`; only `network_policies` hot-reload.
  **[verified-on-host]**
- **`openshell logs` is a ring buffer.** Tail it or read persisted proposals.
  **[verified-on-host]**
- **A blocked call is expected to surface inside the sandbox as a forward-proxy
  CONNECT failure (e.g. `curl: (56) CONNECT tunnel failed, response 403`), so
  the job's own exit code — not just the log — should flag the block. [UNVERIFIED]**
  The 497.4 run captured the host-side OCSF `DENIED` records but did **not**
  capture the in-sandbox exit code or the exact proxy error string; the `403`
  wording is reasoned from the forward-CONNECT-proxy architecture, not observed.
  Confirm the exact string on host before relying on it — the OCSF `DENIED`
  record read from the host is the only **[verified-on-host]** block signal.

## Prerequisites learned the hard way

- Docker reachable + user in the `docker` group is enough; **no root needed** to
  install OpenShell (lands in `~/.local/bin` in non-interactive mode), the
  NemoClaw CLI (`npm link`), or Ollama (user-local, no systemd)
  **[verified-on-host]**.
- The installer hard-requires `strings` (binutils). If absent and you lack root,
  a python3 `strings` shim on `PATH` satisfies it (filed nvhack-ikl)
  **[verified-on-host]**.
- On current OpenShell the old `default-cgroupns-mode: host` daemon.json fix is
  **obsolete** — the gateway sets host cgroupns on its own cluster container
  (`preflight.ts: requiresHostCgroupnsFix: false`) **[verified-on-host on 0.0.85;
  UNVERIFIED on older gateways / aarch64]**.
