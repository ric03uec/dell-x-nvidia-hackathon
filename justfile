# nvidia-hackathon — monorepo of NemoClaw agent projects.
# See docs/DESIGN.md. One rule: a worktree building agent X touches only agents/X/**.

set shell := ["bash", "-uc"]

agents_dir := "agents"
services_dir := "services"
dashboard := "services/dashboard"
lib := "libs/agentkit"
template := "hello-agent"
gb10 := "hack"

# List available recipes
[group('workspace')]
default:
    @just --list

# Sync the shared library venv and every agent project
[group('workspace')]
setup:
    uv sync --project {{ lib }}
    @just each setup
    @just s processing setup
    pnpm --dir {{ dashboard }} install --frozen-lockfile

# Lint, format-check, and typecheck the shared libs and every agent
[group('workspace')]
check:
    uv run --project {{ lib }} ruff check {{ lib }}
    uv run --project {{ lib }} ruff format --check {{ lib }}
    uv run --project {{ lib }} mypy {{ lib }}/src
    @just contracts-check
    @just fixtures-check
    @just each check
    @just s processing check
    @just dashboard-check

# Run the shared library tests and every agent's tests
[group('workspace')]
test:
    uv run --project {{ lib }} pytest {{ lib }}
    @just each test
    @just s processing test
    @just dashboard-test

# Start the SquidWard dashboard locally
[group('dashboard')]
dashboard-dev:
    @just s dashboard dev

# Run SquidWard with its preloaded contract-shaped local mock API
[group('dashboard')]
dashboard-demo:
    @just s dashboard demo

# Generate events, POST them through the demo API, score them, and launch the dashboard.
[group('dashboard')]
demo-pipeline:
    ./scripts/demo-pipeline.sh

# Install the dashboard's pinned dependencies
[group('dashboard')]
dashboard-setup:
    @just s dashboard setup

# Lint and typecheck the dashboard
[group('dashboard')]
dashboard-check:
    @just s dashboard check

# Build the dashboard as its current test gate
[group('dashboard')]
dashboard-test:
    @just s dashboard test

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
    HOST={{ gb10 }} ./infra/gb10/provision.sh config

# Restart vLLM and LiteLLM together on a profile: qwen36 | qwen-next-thinking
[group('gb10')]
gb10-restart profile="qwen36":
    ssh {{ gb10 }} 'bin/hack-vllm-large-qwen start {{ profile }}'
    ssh {{ gb10 }} 'bin/hack-litellm-large-qwen start {{ profile }}'

# Install, configure, start, and verify OpenClaw on the GB10
[group('gb10')]
gb10-up +flags="":
    ANSIBLE_CONFIG=infra/gb10/ansible/ansible.cfg ansible-playbook -i infra/gb10/ansible/inventory.yml infra/gb10/ansible/site.yml {{ flags }}

# Check inference and OpenClaw gateway health
[group('gb10')]
gb10-status:
    @ANSIBLE_CONFIG=infra/gb10/ansible/ansible.cfg ansible-playbook -i infra/gb10/ansible/inventory.yml infra/gb10/ansible/status.yml

# Recover inference and the OpenClaw gateway after reboot
[group('gb10')]
gb10-recover +flags="":
    ANSIBLE_CONFIG=infra/gb10/ansible/ansible.cfg ansible-playbook -i infra/gb10/ansible/inventory.yml infra/gb10/ansible/recover.yml {{ flags }}

# Validate the GB10 Ansible and checked-in OpenClaw configuration
[group('gb10')]
gb10-check:
    ANSIBLE_CONFIG=infra/gb10/ansible/ansible.cfg ansible-playbook -i infra/gb10/ansible/inventory.yml infra/gb10/ansible/site.yml --syntax-check
    ANSIBLE_CONFIG=infra/gb10/ansible/ansible.cfg ansible-playbook -i infra/gb10/ansible/inventory.yml infra/gb10/ansible/recover.yml --syntax-check
    ANSIBLE_CONFIG=infra/gb10/ansible/ansible.cfg ansible-playbook -i infra/gb10/ansible/inventory.yml infra/gb10/ansible/status.yml --syntax-check
    jq --exit-status 'type == "object" and all(keys[]; length > 0)' infra/openclaw/settings/openclaw.json >/dev/null
