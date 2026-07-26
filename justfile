# nvidia-hackathon — monorepo of NemoClaw agent projects.
# See docs/DESIGN.md. One rule: a worktree building agent X touches only agents/X/**.

set shell := ["bash", "-uc"]

agents_dir := "agents"
dashboard := "services/dashboard"
lib := "libs/agentkit"
template := "hello-agent"
gb10 := "dell-gb10"

# List available recipes
[group('workspace')]
default:
    @just --list

# Sync the shared library venv and every agent project
[group('workspace')]
setup:
    uv sync --project {{ lib }}
    @just each setup
    pnpm --dir {{ dashboard }} install --frozen-lockfile

# Lint, format-check, and typecheck the shared libs and every agent
[group('workspace')]
check:
    uv run --project {{ lib }} ruff check {{ lib }}
    uv run --project {{ lib }} ruff format --check {{ lib }}
    uv run --project {{ lib }} mypy {{ lib }}/src
    @just each check
    @just dashboard-check

# Run the shared library tests and every agent's tests
[group('workspace')]
test:
    uv run --project {{ lib }} pytest {{ lib }}
    @just each test
    @just dashboard-test

# Start the SquidWard dashboard locally
[group('dashboard')]
dashboard-dev:
    pnpm --dir {{ dashboard }} dev

# Install the dashboard's pinned dependencies
[group('dashboard')]
dashboard-setup:
    pnpm --dir {{ dashboard }} install --frozen-lockfile

# Lint and typecheck the dashboard
[group('dashboard')]
dashboard-check:
    pnpm --dir {{ dashboard }} lint
    pnpm --dir {{ dashboard }} typecheck

# Build the dashboard as its current test gate
[group('dashboard')]
dashboard-test:
    pnpm --dir {{ dashboard }} test

# Check the local toolchain, and a DGX Spark host if one is given
[group('workspace')]
doctor host="":
    ./scripts/doctor.sh {{ host }}

# Run a recipe inside one agent project: just a hello-agent test
[group('agent')]
a name +args="check":
    @just --justfile {{ agents_dir }}/{{ name }}/justfile --working-directory {{ agents_dir }}/{{ name }} {{ args }}

# Run a recipe inside every agent project: just each test
[group('agent')]
each +args="check":
    #!/usr/bin/env bash
    set -euo pipefail
    for d in {{ agents_dir }}/*/; do
      [[ -f "$d/justfile" ]] || continue
      printf '\n==> %s\n' "${d%/}"
      just --justfile "$d/justfile" --working-directory "$d" {{ args }}
    done

# Scaffold a new agent project by copying the worked example
[group('agent')]
new name:
    ./scripts/new-agent.sh {{ agents_dir }}/{{ template }} {{ agents_dir }}/{{ name }}

# Deploy one agent to a Spark: just deploy hello-agent spark.local [--image]
[group('deploy')]
deploy name host +flags="--source":
    ./scripts/deploy.sh {{ agents_dir }}/{{ name }} {{ host }} {{ flags }}

# Push infra/gb10 config to the box. Never ships secrets or model weights.
[group('gb10')]
gb10-push:
    ./infra/gb10/provision.sh config

# Restart vLLM and LiteLLM together on a profile: qwen36 | qwen-next-thinking
[group('gb10')]
gb10-restart profile="qwen36":
    ssh {{ gb10 }} 'bin/hack-vllm-large-qwen start {{ profile }}'
    ssh {{ gb10 }} 'bin/hack-litellm-large-qwen start {{ profile }}'

# Show what's running and what each endpoint actually serves
[group('gb10')]
gb10-status:
    @ssh {{ gb10 }} 'bin/hack-vllm-large-qwen status'
    @printf '\nvLLM :8000 serves: '
    @ssh {{ gb10 }} 'bin/hack-vllm-large-qwen models' | jq -r '.data[].id'
    @printf 'LiteLLM :4000 serves: '
    @ssh {{ gb10 }} 'bin/hack-litellm-large-qwen models' | jq -r '.data[].id'
