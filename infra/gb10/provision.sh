#!/usr/bin/env bash
# Reproduce everything WE installed on gb10 on 2026-07-26. Idempotent — safe to
# re-run. Does not touch the pre-installed baseline (driver, CUDA, Docker, the
# DGX stack); see PROVENANCE.md for what that is and why it's out of scope.
#
#   ./provision.sh all          # everything below, in order
#   ./provision.sh tools        # uv + openshell
#   ./provision.sh images       # docker images
#   ./provision.sh models       # hf-cache
#   ./provision.sh config       # push this directory to the box
#   ./provision.sh devtools     # optional: beads/agentguides tooling
#
# Runs FROM YOUR LAPTOP against $HOST over ssh.
set -euo pipefail

HOST="${HOST:-dell-gb10}"
REMOTE_DIR="${REMOTE_DIR:-/home/dell/vllm}"
USB="${USB:-/mnt/modelshub}"
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

on() { ssh "$HOST" "export PATH=\$HOME/.local/bin:\$PATH; set -euo pipefail; $1"; }
step() { printf '\n==> %s\n' "$1"; }

# --- tools --------------------------------------------------------------
# SOURCE: uv from the official Astral installer. The box has working outbound
# internet (pypi 200, huggingface 200) — the USB bundles were a bandwidth
# convenience, not an airgap requirement.
# SOURCE: openshell from PyPI. Confirmed to be NVIDIA's OpenShell CLI (it has
# the sandbox/gateway/policy/inference verbs), despite a same-named npm package
# on the USB at a different version. nemoclaw is NOT installed and never was.
tools() {
    step "uv"
    on 'command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh'
    step "openshell"
    on 'uv tool install --upgrade openshell'
    on 'openshell --version'
}

# --- images -------------------------------------------------------------
# SOURCE, in preference order:
#   1. USB tarballs at $USB/docker-vllm-airgap/images/*.tar.zst
#   2. upstream registries — ghcr.io and Docker Hub pull anonymously;
#      nvcr.io/nvidia/vllm:26.06-py3 needs an NGC login.
# vllm-inx:26.06-py3-patched has no upstream: it is the NGC 26.06 base plus one
# pip layer (see Dockerfile.vllm-inx), and is also on the USB prebuilt.
images() {
    step "docker images"
    on "
    load() { # load <image-ref> <usb-tar-basename>
        if docker image inspect \"\$1\" >/dev/null 2>&1; then
            echo \"  have \$1\"
        elif [ -f '$USB/docker-vllm-airgap/images/'\"\$2\" ]; then
            echo \"  loading \$2 from USB\"
            zstd -dc '$USB/docker-vllm-airgap/images/'\"\$2\" | docker load
        else
            echo \"  pulling \$1\"
            docker pull \"\$1\"
        fi
    }
    load ghcr.io/berriai/litellm:v1.88.1 litellm-v1.88.1.tar.zst
    load postgres:16-alpine postgres-16-alpine.tar.zst
    load nvcr.io/nvidia/vllm:25.11-py3 nvidia-vllm-25.11-py3.tar.zst
    load vllm-inx:26.06-py3-patched vllm-inx-26.06-py3-patched.tar.zst
    "
}

# --- models -------------------------------------------------------------
# SOURCE: exported from our other host (inx) to the USB, then imported here.
# Upstream is Hugging Face; the pinned revisions are in README.md. HF_HUB_OFFLINE
# is set in the compose files, so nothing re-downloads at run time.
# The USB is removable — this copies onto internal disk and is complete
# (COPY_EXIT_CODE=0) without it.
models() {
    step "hf-cache models"
    on "
    if [ ! -d '$USB/qwen-export' ]; then
        echo '  USB not mounted at $USB — skipping.' >&2
        echo '  sudo mount /dev/disk/by-label/modelshub $USB' >&2
        exit 1
    fi
    '$USB/qwen-export/scripts/import-qwen-models.sh'
    "
}

# --- config -------------------------------------------------------------
# This repo is the source of truth for everything under ~/vllm and ~/bin.
# hf-cache and env/ are deliberately excluded: one is 113G of weights, the
# other is secrets.
config() {
    step "push config to $HOST:$REMOTE_DIR"
    rsync -a --exclude hf-cache --exclude env --exclude 'bin/' \
        "$here/" "$HOST:$REMOTE_DIR/"
    rsync -a "$here/bin/" "$HOST:/home/dell/bin/"
    # ponytail: secrets are generated on the box by the litellm wrapper's
    # ensure_env(), never shipped from here. env/litellm.env.example documents
    # the shape only.
    on "ls -la $REMOTE_DIR && ls -la ~/bin"
}

# --- devtools (optional) ------------------------------------------------
# Our agent tooling, not the inference stack. SOURCE: PyPI via uv.
# EXCEPT bv (beads TUI v0.9.2) — landed 2026-07-26 18:33 with no uv receipt and
# no recorded provenance. Origin UNKNOWN; likely a release binary. Re-derive it
# before depending on it.
devtools() {
    step "devtools"
    on 'uv tool install --upgrade "beadhive[otel]"'
    on 'uv tool install --upgrade agentguides'
}

case "${1:-all}" in
all) tools; images; models; config ;;
tools) tools ;;
images) images ;;
models) models ;;
config) config ;;
devtools) devtools ;;
*) sed -n '2,14p' "$0" >&2; exit 2 ;;
esac

step "done"
