# SquidWard

Monorepo scaffold for **NemoClaw** agent projects with shared **OpenShell**
sandbox policy libraries. Prototype locally, deploy to a **DGX Spark** over
SSH, inference entirely local to the Spark.

<img width="1719" height="915" alt="squidward-logo" src="https://github.com/user-attachments/assets/e7fb97b8-bca8-428a-afb5-b0b0d158e3f8" />

Built in **8h 14min** using [BeadHive](https://github.com/beadhive/beadhive) <img src="https://avatars.githubusercontent.com/u/302386366?v=4" alt="BeadHive" height="28" width="28">

## Quick start

```bash
just                      # list recipes
just each setup           # sync every project's venv
just each check           # lint + format + typecheck everywhere
just each test             # tests everywhere
just a hello-agent run     # run one agent's service locally
just dashboard-setup       # install the SquidWard dashboard dependencies
just dashboard-dev         # run the dashboard locally
just dashboard-demo        # run the real local ingestion pipeline and dashboard
just demo-pipeline         # generate → ingest → detect → recommend → dashboard
```

`just demo-pipeline` starts the durable SQLite ingestion API, posts 100
deterministic input events, runs them through deterministic rules and the promoted
Isolation Forest, persists rolling risk assessments for every event, stores the
resulting finding for OpenClaw investigation, and launches the dashboard at
`http://127.0.0.1:8300`. Data remains available
in `data/demo-pipeline.db` after the demo stops. Set `DEMO_PIPELINE_RESET=0` to
reuse the existing database instead of resetting it at startup.

Fixture-backed CVE, asset, model, and analyst-feedback pages are enabled by
default for presentations. Set `VITE_ENABLE_DEMO_PAGES=false` before starting
the dashboard or app stack to remove those pages from navigation.

To populate the database used by an already-running ingestion API, or remove
only that synthetic run while preserving real captures:

```bash
just s ingestion run              # terminal 1; SQLite is durable
just demo-seed                     # terminal 2; posts 26 events through the API
just demo-clear                    # removes demo events/findings/actions only
just demo-live                     # continuously add traffic and active findings
just demo-seed http://HOST:8100    # target another running appliance
```

`just demo-live` emits mostly normal traffic with a suspicious correlated burst
every third cycle. Each burst is scored by the real deterministic processing
pipeline and creates a pending `deny_destination` recommendation. It runs until
Ctrl-C; pass an ingestion URL as the recipe argument to target another host.

Demo cleanup identifies the synthetic `run-synthetic-001` marker and also
removes findings, recommendations, decisions, enforcement results, and rules
derived exclusively from those events. It does not truncate the database.

On the GB10, the ingestion API reads GPU utilization from `nvidia-smi` and
unified-memory usage from `/proc/meminfo`. Configure `.env`, then run:

```bash
just doctor local
just gb10-up
just gb10-app-up
```

From a workstation, `just doctor <ssh-host>` performs the same readiness checks
over SSH. The dashboard binds to `MGMT_BIND_ADDR`; ingestion, FastMCP, OpenClaw,
and LiteLLM remain on host-local or private container interfaces.

## Add an agent

```bash
just new my-agent
```

Copies `agents/hello-agent/` to `agents/my-agent/`, renames the package, and
leaves you a self-contained project: its own `pyproject.toml`,
`agents.yaml` (NemoClaw manifest), `policy.yaml` (OpenShell policy), and
`justfile`. It gets no lockfile of its own — it resolves and locks into the
single root `uv.lock` (see "The one rule" below).

## The one rule

**One owner per component directory** — `agents/<name>/`, `services/<name>/`,
or `libs/<name>/`. Stay inside yours and parallel worktrees merge cleanly.

The shared surfaces are CODEOWNERS-gated and need review: `contracts/`, the
root `pyproject.toml`, `uv.lock`, and the root `justfile`.

`uv.lock` is a single root lock shared by every Python member, so it *will*
conflict. It is machine-generated — never hand-edit it. Take one side and
regenerate:

```bash
just relock          # or: just relock theirs
```

## Deploy to the Spark

```bash
just check && just each test          # gate locally first
just deploy hello-agent spark.local   # rsync source + apply on the box
just deploy hello-agent spark.local --image   # ship a built image instead
```

## Layout

| Path | What |
|---|---|
| `agents/<name>/` | One self-contained agent project. Own manifest + policy, shares the root `uv.lock`. |
| `services/dashboard/` | SquidWard React dashboard. Own pnpm lockfile and build. |
| `services/ingestion/` | Durable SQLite ingestion API; GPU/memory telemetry, findings, recommendations. |
| `services/processing/` | Deterministic rules + Isolation Forest/autoencoder detection pipeline. |
| `services/demo/` | Demo traffic generation and live/simulate CLIs (`just s demo ...`). |
| `services/collector/` | Event collection service. |
| `libs/agentkit/` | Shared Python package — FastAPI service factory, `agents.yaml`/`policy.yaml` validation. |
| `libs/policies/` | Reusable OpenShell policy fragments. |
| `libs/skills/` | Shared OpenClaw/Claude skills, symlinked into `claude-plugin/`. |
| `contracts/` | Shared, review-gated schema/contract definitions. |
| `infra/` | GB10 deployment (Ansible/Docker) and OpenClaw desired state. |
| `scripts/deploy.sh` | rsync+apply, or image push. |
