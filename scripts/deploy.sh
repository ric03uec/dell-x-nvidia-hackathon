#!/usr/bin/env bash
# Deploy one agent project to a DGX Spark over SSH.
#
#   scripts/deploy.sh agents/hello-agent spark.local             # source (default)
#   scripts/deploy.sh agents/hello-agent spark.local --image     # built image
#
# Source mode rsyncs the agent's own subfolder and applies its manifest and
# policy on the box. Image mode builds locally and ships the image instead.
#
# Both assume NemoClaw is already installed on the host:
#   curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
#
# One sandbox per call — this couples exactly one agents.yaml + one
# policy.yaml to one sandbox. A project needing more than one sandbox
# (e.g. one job sandbox per fixture, or two peer sandboxes with different
# filesystem scopes) applies the extras by hand after this script runs.
# --source's rsync below already ships the whole agent_dir, so any
# extra sandboxes/<role>/ subfolder arrives on the host for free.
set -euo pipefail

agent_dir=${1:-}
host=${2:-}
mode=${3:---source}

usage() {
    echo "usage: $0 <agent-dir> <host> [--source|--image]" >&2
}

if [[ -z $agent_dir || -z $host ]]; then
    usage
    exit 2
fi
[[ -d $agent_dir ]] || { echo "no such agent: $agent_dir" >&2; exit 2; }

agent=$(basename "$agent_dir")
sandbox=${NEMOCLAW_SANDBOX:-$agent}
remote_dir=${REMOTE_DIR:-agents/$agent}

echo "==> validating $agent locally"
just --justfile "$agent_dir/justfile" --working-directory "$agent_dir" validate

case $mode in
--source)
    echo "==> rsync $agent_dir -> $host:$remote_dir"
    rsync -az --delete \
        --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
        --exclude '.ruff_cache' --exclude '.mypy_cache' \
        "$agent_dir/" "$host:$remote_dir/"

    echo "==> applying manifest and policy on $host"
    # shellcheck disable=SC2029  # client-side expansion is intended: these are local values
    ssh "$host" "cd '$remote_dir' \
        && nemoclaw '$sandbox' agents apply -f agents.yaml --yes \
        && openshell policy set '$sandbox' --policy policy.yaml --wait"
    ;;
--image)
    [[ -f $agent_dir/Dockerfile ]] || {
        echo "--image needs a Dockerfile in $agent_dir" >&2
        exit 2
    }
    image="$agent:$(git rev-parse --short HEAD)"

    echo "==> building $image"
    docker build -t "$image" "$agent_dir"

    echo "==> shipping $image to $host"
    docker save "$image" | gzip | ssh "$host" "gunzip | docker load"

    # ponytail: `nemoclaw onboard --from` is documented as taking a custom image
    # but its placeholder reads <Dockerfile>. Confirm against `nemoclaw onboard
    # --help` on the box the first time; swap to shipping the Dockerfile and
    # building remotely if it wants a path.
    echo "==> onboarding $sandbox from $image on $host"
    # shellcheck disable=SC2029  # client-side expansion is intended: these are local values
    ssh "$host" "nemoclaw onboard --name '$sandbox' --from '$image' --non-interactive"
    ;;
*)
    usage
    exit 2
    ;;
esac

echo "==> deployed. check with: ssh $host nemoclaw $sandbox status"
