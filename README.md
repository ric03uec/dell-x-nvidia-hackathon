# dell-x-nvidia-hackathon

Monorepo scaffold for **NemoClaw** agent projects with shared **OpenShell**
sandbox policy libraries. Prototype locally, deploy to a **DGX Spark** over
SSH, inference entirely local to the Spark.

<img width="1719" height="915" alt="squidward-logo" src="https://github.com/user-attachments/assets/e7fb97b8-bca8-428a-afb5-b0b0d158e3f8" />

## Quick start

```bash
just                      # list recipes
just each setup           # sync every project's venv
just each check           # lint + format + typecheck everywhere
just each test             # tests everywhere
just a hello-agent run     # run one agent's service locally
just dashboard-setup       # install the SquidWard dashboard dependencies
just dashboard-dev         # run the dashboard locally
```

## Add an agent

```bash
just new my-agent
```

Copies `agents/hello-agent/` to `agents/my-agent/`, renames the package, and
leaves you a self-contained project: its own `pyproject.toml`, `uv.lock`,
`agents.yaml` (NemoClaw manifest), `policy.yaml` (OpenShell policy), and
`justfile`.

## The one rule

**A branch or worktree building agent `X` touches only `agents/X/**`.**

There is no central registry to append to and no shared lockfile, so any
number of agent worktrees merge to `main` without conflicting. Changes to
`libs/` or the root `justfile` are their own separate change.

## Deploy to the Spark

```bash
just check && just each test          # gate locally first
just deploy hello-agent spark.local   # rsync source + apply on the box
just deploy hello-agent spark.local --image   # ship a built image instead
```

## Layout

| Path | What |
|---|---|
| `agents/<name>/` | One self-contained agent project. Own deps, own lock, own manifest + policy. |
| `services/dashboard/` | SquidWard React dashboard. Own pnpm lockfile and build. |
| `libs/agentkit/` | Shared Python package — FastAPI service factory, `agents.yaml`/`policy.yaml` validation. |
| `libs/policies/` | Reusable OpenShell policy fragments. |
| `scripts/deploy.sh` | rsync+apply, or image push. |
