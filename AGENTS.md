# dell-x-nvidia-hackathon

Pi editor configuration for this repository.

## Project Shape

This is a monorepo scaffold for NemoClaw agent projects with OpenShell sandbox
policies. Each agent or service is isolated under its own component directory
(`agents/<name>/` or `services/<name>/`) and owns its own manifest, policy,
and tests, sharing one workspace-wide `uv.lock`.

## Core Rule

One owner per top-level component directory. A worktree building agent `X`
touches only its own component directory: `agents/business-agent`,
`agents/security-agent`, `agents/hello-agent` under `agents/`, and
`services/ingestion`, `services/processing`, `services/dashboard` under
`services/`.

`contracts/` and the root `uv.lock` (plus root `pyproject.toml` and the root
`justfile`) are jointly-owned, review-gated shared surfaces — see
`CODEOWNERS`. Do not modify them while implementing a specific component
unless the user explicitly asks for a shared change. If `uv.lock` conflicts,
see CLAUDE.md's "uv.lock conflicts" section — regenerate it with `just
relock`, never hand-merge it.

## Commands

Use the repo recipes when available:

```bash
just a <name> check     # one agent
just s <name> check     # one service
just each check         # everything, across agents/ and services/
```

If `just` is not installed, run the equivalent commands inside the target
project:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Run the relevant check before calling work done.

## Pi Skills

Project-level Pi skills are exposed through `.agents/skills/`. Keep those
entries linked to the canonical copies under `libs/skills/`.

## Pi Model

For this repository only, Pi must use the local LiteLLM OpenAI-compatible
endpoint on the `hack` host with the Qwen model registered by the repo-local
Pi extension:

```bash
pi -a --no-extensions --extension .pi/extensions/vllm-hack.ts --provider vllm-hack --model Qwen3.6-27B-FP8 --models vllm-hack/Qwen3.6-27B-FP8
```

The extension is `.pi/extensions/vllm-hack.ts`, loaded by `.pi/settings.json`
for normal project-local Pi startup. For strict repo-local inference, use the
command above: `--no-extensions` prevents global provider extensions from being
loaded, and the explicit `--extension` loads only this repo's Qwen provider. It
registers provider `vllm-hack` and model `Qwen3.6-27B-FP8`, served by the
LiteLLM instance on `hack`. This workstation cannot currently reach
`172.16.10.127:4000` directly, so the extension uses an SSH tunnel to `hack`
and talks to `http://127.0.0.1:14000/v1`.

Authentication is intentionally outside the repo. The `.pi/bin/vllm-hack-key`
helper uses SSH to fetch the running `hack-litellm` container's key without
writing it to disk.

Do not use other models for repo-local Pi work. Do not fall back to a cloud
provider if the LiteLLM endpoint or Qwen model is unavailable; report the local
inference failure instead. Do not switch this repo back to global Pi defaults or
cloud providers.

Available repo skills:

- `nemoclaw-fanout`: reason about subagent fan-out and concurrency limits.
- `openshell-data-boundary`: reason about sandbox filesystem boundaries.
- `openshell-egress-audit`: inspect and tighten OpenShell network egress.
- `spark-inference`: inspect or switch local DGX Spark inference routes.

Treat `libs/skills/` as canonical. If a skill needs to change, edit the shared
copy there rather than forking skill text under `.agents/skills/`.

## Development Guidance

- Start by reading the target agent's existing files before editing.
- Make the smallest correct change.
- Preserve per-agent isolation and avoid central registries.
- Do not add broad network policy exceptions; widen sandbox policy only from
  observed denials.
- Prefer local inference. Do not add cloud fallback unless explicitly requested.
