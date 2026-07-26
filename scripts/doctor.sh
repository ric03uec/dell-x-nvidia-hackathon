#!/usr/bin/env bash
# Check the local toolchain, and a DGX Spark trial host either over SSH or,
# if the host running this script IS the trial host, directly (no sshd
# required).
#
#   scripts/doctor.sh
#   scripts/doctor.sh spark.local
#   scripts/doctor.sh local        # or: localhost
set -euo pipefail

host=${1:-}
failed=0

check() { # check <label> <command...>
    if "${@:2}" >/dev/null 2>&1; then
        printf '  ok    %s\n' "$1"
    else
        printf '  FAIL  %s\n' "$1"
        failed=1
    fi
}

echo "local:"
check "just"   command -v just
check "uv"     command -v uv
check "rsync"  command -v rsync
check "ssh"    command -v ssh
check "docker (only needed for --image deploys)" command -v docker

if [[ -z $host ]]; then
    echo
    echo "no host given; pass one to check a Spark over ssh ($0 spark.local)" \
         "or 'local'/'localhost' to check this machine directly ($0 local)"
    exit "$failed"
fi

local_mode=0
if [[ $host == "local" || $host == "localhost" ]]; then
    local_mode=1
fi

# remote <shell-command-string> -- runs on $host over ssh, or directly on
# this machine (bash -c) when $host is "local"/"localhost".
#
# PATH is set explicitly: a non-interactive ssh shell skips the profile that
# adds ~/.local/bin, so uv-installed tools (openshell) look absent when they
# are not.
remote() {
    if [[ $local_mode -eq 1 ]]; then
        bash -c "$1"
    else
        ssh "$host" "export PATH=\$HOME/.local/bin:\$PATH; $1"
    fi
}

echo
echo "$host:"
if [[ $local_mode -eq 1 ]]; then
    check "running checks directly on this host (no ssh)" true
else
    check "reachable over ssh" ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" true
fi
check "nemoclaw installed" remote "command -v nemoclaw"
check "openshell installed" remote "command -v openshell"

# The OpenShell gateway embeds k3s in Docker, which fails on cgroup v2 without
# host cgroup namespaces. This is the single most common DGX Spark failure.
check "docker default-cgroupns-mode=host" \
    remote "grep -Eq '\"default-cgroupns-mode\"[[:space:]]*:[[:space:]]*\"host\"' /etc/docker/daemon.json"

check "local inference responding on :8000" \
    remote "curl -fsS --max-time 10 http://127.0.0.1:8000/v1/models"
check "GPU utilization telemetry available" \
    remote "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits"
check "unified memory telemetry available" remote "test -r /proc/meminfo"

if [[ $failed -ne 0 ]]; then
    echo
    echo "see docs/DESIGN.md and libs/skills/spark-inference/SKILL.md" >&2
fi
exit "$failed"
