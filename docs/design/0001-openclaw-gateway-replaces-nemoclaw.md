# ADR 0001 — OpenClaw gateway replaces NemoClaw sandboxes

**Status:** accepted (recorded retroactively)
**Date:** 2026-07-26
**Supersedes:** the NemoClaw/OpenShell-sandbox assumption in
[exfiltration-protection-architecture.md](../exfiltration-protection-architecture.md)
and [modular-implementation-plan.md](../modular-implementation-plan.md)

## Context

The architecture docs and the planned bead molecules assume **NemoClaw** sandboxes
with **OpenShell** `filesystem_policy` / `network_policies` as the agent runtime, and
`libs/skills/` carries three skills documenting that stack's behaviour in detail.

`infra/gb10/README.md` recorded from the start that `openshell` v0.0.91 was installed
but **`nemoclaw` was not**, and `scripts/doctor.sh dell-gb10` reported `FAIL nemoclaw
installed`.

Rather than install it, the team went the other way.

## Decision

The GB10 runs an **OpenClaw gateway** as a user systemd service. NemoClaw is not
installed and is actively removed.

Evidence in the repository:

- `infra/gb10/ansible/site.yml` deploys and starts `openclaw-gateway.service`
  (user scope, enabled), then has an explicit task **"Remove NemoClaw user state and
  executable"** deleting `~/.nemoclaw`, `~/.config/nemoclaw`,
  `~/.local/share/nemoclaw`, `~/.local/state/nemoclaw` and `~/.local/bin/nemoclaw`.
- `infra/openclaw/` holds the checked-in configuration: `settings/openclaw.json`,
  `agents.yaml`, `policy/presets/`, and a `workspace/` tree.
- Inference is routed through the existing LiteLLM endpoint —
  `openclaw.json` sets `models.litellm.baseUrl` to `http://127.0.0.1:4000/v1` with
  primary model `litellm/Qwen3.6-27B-FP8`.
- Root `justfile` drives it with `gb10-up`, `gb10-status`, `gb10-recover` and
  `gb10-check`, all Ansible playbooks.

Inference therefore still terminates on the GB10 and still has no external
provider fallback — the local-only guarantee is unchanged. What changed is the
agent runtime and policy surface, not the data boundary.

## Consequences

**Invalidated.** Planned work that presupposed a NemoClaw runtime:

- `dxnvh-bht.1` — stand up the NemoClaw/OpenShell runtime on the GB10.
- `dxnvh-bht.5` — two-sandbox data boundary for the business/security agent pair.
  Landlock `filesystem_policy` asymmetry across two NemoClaw sandboxes is not a
  mechanism this stack has.
- `dxnvh-bht.4` — the OCSF stream as an event source. `openshell logs <sandbox>` is
  a NemoClaw-sandbox surface; whether OpenClaw emits an equivalent structured
  stream is a **new, open question**, not the one that spike asked.

**Still valid.** `dxnvh-bht.2` (GPU/memory contention between always-on vLLM and
nightly PyTorch training) is independent of the runtime choice and remains
unanswered.

**Stale documentation.** `docs/ROADMAP.md` and `docs/epics/*` describe NemoClaw
sandboxes and OpenShell policy as the enforcement path throughout. `libs/skills/`
(`openshell-data-boundary`, `openshell-egress-audit`, `spark-inference`,
`nemoclaw-fanout`) document a stack this repo no longer deploys — they load into
every agent session here, so their scope needs re-labelling rather than deletion.

**`agents/business-agent` and `agents/security-agent`** were scaffolded with
`agents.yaml` + `policy.yaml` in the NemoClaw manifest shape (`dxnvh-332.8`). Their
manifests need porting to `infra/openclaw/agents.yaml`, which currently reads
`agents: []`.

## Alternatives not taken

Installing NemoClaw to match the plan. Rejected implicitly: OpenClaw was already
working, and the demo's enforcement need is met by Squid (see ADR 0002) without a
sandbox policy engine.
