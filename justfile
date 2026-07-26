# nvidia-hackathon — monorepo of NemoClaw agent projects.
# See docs/DESIGN.md. One rule: a worktree building agent X touches only agents/X/**.

set shell := ["bash", "-uc"]

agents_dir := "agents"
services_dir := "services"
lib := "libs/agentkit"
template := "hello-agent"
gb10 := "dell-gb10"

# List available recipes
[group('workspace')]
default:
    @just --list

# Sync the shared library venv and every agent/service project
[group('workspace')]
setup:
    uv sync --project {{ lib }}
    @just each setup

# Lint, format-check, and typecheck the shared libs and every agent/service
[group('workspace')]
check:
    uv run --project {{ lib }} ruff check {{ lib }}
    uv run --project {{ lib }} ruff format --check {{ lib }}
    uv run --project {{ lib }} mypy {{ lib }}/src
    @just contracts-check
    @just fixtures-check
    @just each check

# Run the shared library tests and every agent/service's tests
[group('workspace')]
test:
    uv run --project {{ lib }} pytest {{ lib }}
    @just each test

# Check the local toolchain, and a DGX Spark host if one is given
[group('workspace')]
doctor host="":
    ./scripts/doctor.sh {{ host }}

# Resolve a conflicted uv.lock by taking one side and regenerating it from
# the (already-merged) pyproject.tomls — never hand-edit uv.lock.
# Run after a merge/rebase leaves uv.lock conflicted: just relock [ours|theirs]
[group('workspace')]
relock side="ours":
    git checkout --{{ side }} -- uv.lock
    uv lock
    git add uv.lock

# Validate contracts/examples/* against their JSON Schemas (rejects unlisted policy action_type)
[group('contracts')]
contracts-check:
    uv run --with jsonschema python3 contracts/validate.py

# Validate fixtures/expected/* canonical events against contracts/event.schema.json
[group('fixtures')]
fixtures-check:
    uv run --with jsonschema python3 fixtures/validate.py

# Run a recipe inside one agent project: just a hello-agent test
[group('agent')]
a name +args="check":
    @just --justfile {{ agents_dir }}/{{ name }}/justfile --working-directory {{ agents_dir }}/{{ name }} {{ args }}

# Run a recipe inside every agent and service project: just each test
[group('workspace')]
each +args="check":
    #!/usr/bin/env bash
    set -euo pipefail
    for d in {{ agents_dir }}/*/ {{ services_dir }}/*/; do
      [[ -f "$d/justfile" ]] || continue
      printf '\n==> %s\n' "${d%/}"
      just --justfile "$d/justfile" --working-directory "$d" {{ args }}
    done

# Scaffold a new agent project by copying the worked example
[group('agent')]
new name:
    ./scripts/new-agent.sh {{ agents_dir }}/{{ template }} {{ agents_dir }}/{{ name }}

# Run a recipe inside one service project (the polyglot seam, e.g. pnpm): just s dashboard dev
[group('service')]
s name +args="check":
    @just --justfile {{ services_dir }}/{{ name }}/justfile --working-directory {{ services_dir }}/{{ name }} {{ args }}

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
