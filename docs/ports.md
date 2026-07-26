# Ports, service names, and environment variables

**Table of record** for Milestone 0 (see
[Modular Hackathon Implementation Plan §7](./modular-implementation-plan.md#7-parallel-execution-plan)).
Every service in the exfiltration-protection stack — existing GB10 occupants
and everything this repo adds — is listed here exactly once. Do not pick a
port independently; add a row here first.

Companion file: [`.env.example`](../.env.example) at the repo root lists every
variable the compose stack reads.

## GB10 occupants (pre-existing — do not reassign)

These already run on the box per `infra/gb10/README.md`. Nothing new may bind
these ports. Their bind addresses are inherited as-is; this bead does not
change them.

| Service | Container name | Host port | Binds on |
|---|---|---|---|
| Squid forward proxy | `hack-squid` | **3128** | `0.0.0.0` (test clients configure this as their explicit proxy) |
| vLLM inference backend | `vllm-qwen3.6-27b-fp8` (profile-dependent; see `infra/gb10/docker-compose.large-qwen.yml`) | **8000** | `127.0.0.1` |
| LiteLLM model gateway | `hack-litellm` | **4000** | `0.0.0.0` *(pre-existing; see [Known deviation](#known-deviation-litellm-is-not-loopback-only) below)* |
| Stock NVIDIA DGX Dashboard | vendor-managed, not ours | **11000** | `127.0.0.1` |

## New services (this stack)

Container names use the `hack-` prefix already established by
`infra/gb10/docker-compose.litellm.yml`.

| Service | Container name | Host port | Binds on | Component |
|---|---|---|---|---|
| Ingestion API (FastAPI + FastMCP: REST for infra/dashboard, MCP tools for the security agent) | `hack-ingestion` | **8100** | `${MGMT_BIND_ADDR}` — management network | 2. Ingestion and storage |
| Squid/OpenShell log collector | `hack-collector` | *not published* | n/a — outbound only, posts to ingestion | 1. Infrastructure and sources |
| Processing — live scoring loop (rules + rolling baselines + Isolation Forest) | `hack-processing-live` | **8200** | `${PRIVATE_BIND_ADDR}` (`127.0.0.1`) — private to GB10 | 3. Refinement and processing |
| Processing — offline batch runner (PyTorch autoencoder, snapshot-driven) | `hack-processing-offline` | **8201** | `${PRIVATE_BIND_ADDR}` (`127.0.0.1`) — private to GB10; only listens while a manual/nightly run is active | 3. Refinement and processing |
| Dashboard dev server (`services/dashboard`, pnpm/TypeScript — scaffolded by `dxnvh-332.3`) | `hack-dashboard` | **8300** | `${MGMT_BIND_ADDR}` — management network | 4. UX and dashboard |

`8300` is the dashboard's dev-server port. It is deliberately distinct from
the stock NVIDIA DGX Dashboard on `11000` — `dxnvh-332.3` should read its dev
server's `port` config from `DASHBOARD_PORT` (see `.env.example`), not
hardcode a framework default (Vite's `5173`, Next's `3000`, etc.).

## Deliberately not in this table

- **`agents/business-agent` and `agents/security-agent`** (the OpenClaw
  business agent and the always-on OpenClaw security agent — `dxnvh-332.8`).
  These run as NemoClaw-managed agents inside an OpenShell sandbox (the same
  pattern as `agents/hello-agent`: `nemoclaw <sandbox> agents apply` +
  `openshell policy set`), not as `docker compose` services this repo defines.
  They have no host port to assign: the business agent reaches the network
  only through Squid, and the security agent reaches ingestion only through
  its MCP tool surface (outbound) and the existing LiteLLM/vLLM endpoints
  (outbound, via the local inference adapter — `dxnvh-0e6.2`). OpenShell's own
  gateway ports belong to the OpenShell/NemoClaw installation itself, not to
  this stack.
- **The OpenShell policy enforcement adapter.** Deliberately excluded from
  `dxnvh-0f2` pending `dxnvh-bht`'s spike verdict — not yet designed, so not
  yet portable.

## Bind-address classes and the exposure rule

The architecture's exposure rule
([`exfiltration-protection-architecture.md` §11](./exfiltration-protection-architecture.md#11-installation-on-the-gb10)):
"Expose port 3128 only to test clients, restrict the dashboard to the
management network, and keep NemoClaw/model endpoints private to the GB10
network." That maps to three bind classes, each backed by an env var so
`dxnvh-332.12`'s compose stack has one knob per class rather than four:

| Class | Env var | Placeholder default | Used by |
|---|---|---|---|
| Test-client reachable | — (Squid only; pre-existing, unchanged) | `0.0.0.0` | `hack-squid` |
| Management network | `MGMT_BIND_ADDR` | `192.0.2.10` (RFC 5737 `TEST-NET-1` — a real management-VLAN IP is not known until the box is on-site; **never leave this as a routable/public address**) | `hack-ingestion`, `hack-dashboard` |
| Private to GB10 | `PRIVATE_BIND_ADDR` | `127.0.0.1` | `hack-processing-live`, `hack-processing-offline` |

Ingestion shares the dashboard's management-network bind class rather than
staying loopback-only: the dashboard is a browser SPA that calls ingestion's
REST API directly (`dxnvh-7t2`'s "the dashboard holds no authority of its
own... reads and writes only through ingestion's REST API"), so ingestion
must be reachable from wherever the dashboard's frontend runs. Everything
that either has no external caller (the collector) or exists purely to serve
processing/inference (`hack-processing-live`, `hack-processing-offline`) gets
the private class instead, extending the doc's "NemoClaw/model endpoints
private to the GB10" principle to the rest of the backend, not just the
inference call itself.

### Known deviation: LiteLLM is not loopback-only

`hack-litellm` binds `0.0.0.0:4000` today (see `infra/gb10/README.md`), which
sits in tension with "NemoClaw and any local model gateway must listen only
on private GB10 interfaces" (architecture doc §9). This bead does not change
it — `4000` is a listed pre-existing occupant this bead must not collide
with, not touch. Flagged here as a known follow-up for whoever hardens
`infra/gb10` next; it does not block Milestone 0.

## Port ranges, for future additions

New services should stay within these ranges so a glance at the port number
tells you the component, without re-reading this file:

| Range | Component |
|---|---|
| `8100`–`8199` | Ingestion and storage |
| `8200`–`8299` | Refinement and processing |
| `8300`–`8399` | UX and dashboard |
| `8400`–`8499` | Infrastructure and sources (reserved; the collector currently needs no published port) |
