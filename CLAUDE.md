# dell-x-nvidia-hackathon

Monorepo scaffold for NemoClaw agent projects with OpenShell sandbox
policies, ported from the nvidia-hackathon prototyping repo.

## The one rule

**One owner per top-level component directory.** A worktree building agent `X`
touches only its own component directory:

- `agents/business-agent`, `agents/security-agent`, `agents/hello-agent` under `agents/`
- `services/ingestion`, `services/processing`, `services/dashboard` under `services/`

`contracts/` and the root `uv.lock` (plus root `pyproject.toml` and the root
`justfile`) are jointly-owned, review-gated shared surfaces — every component
depends on them, so changes there need review rather than a single owner's say-so
(see `CODEOWNERS`). If `uv.lock` conflicts, see "uv.lock conflicts" below —
regenerate it, never hand-merge it.

## uv.lock conflicts

`uv.lock` is machine-generated and marked `-merge` in `.gitattributes`, so a
conflicting merge/rebase leaves it flagged conflicted with no `<<<<<<<`
markers inside it. **Never hand-edit `uv.lock`.** Resolve it by taking one
side and regenerating:

```bash
just relock          # or: just relock theirs
```

## Commands

```bash
just a <name> check     # lint + typecheck one agent
just s <name> check     # lint + typecheck one service
just each check         # everything, across agents/ and services/
```

Run the check before calling work done.
