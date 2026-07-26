#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${INFRA_DIR}"

ASK_BECOME=false
for arg in "$@"; do
  case "${arg}" in
    --ask-become-pass|-K)
      ASK_BECOME=true
      ;;
  esac
done

EXTRA_ARGS=()
if [[ "${ASK_BECOME}" == "false" ]]; then
  if ! ansible gb10 -m raw -a 'command -v curl >/dev/null' >/dev/null 2>&1; then
    EXTRA_ARGS+=(--ask-become-pass)
  fi
fi

exec ansible-playbook playbooks/install.yml "${EXTRA_ARGS[@]}" "$@"
