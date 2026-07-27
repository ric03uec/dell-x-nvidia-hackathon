#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-}"
api_url="${2:-http://127.0.0.1:8100}"

usage() {
  printf 'Usage: %s {seed|clear} [api-url]\n' "$0" >&2
  exit 2
}

[[ "$action" == "seed" || "$action" == "clear" ]] || usage
curl -fsS "$api_url/health" >/dev/null || {
  printf 'Ingestion API is not reachable at %s\n' "$api_url" >&2
  exit 1
}

if [[ "$action" == "seed" ]]; then
  python3 "$repo_root/scripts/generate_dummy_events.py" \
    --post-to "$api_url/v1/events"
  printf 'Seeded 26 synthetic events through %s/v1/events\n' "$api_url"
else
  response="$(curl -fsS -X DELETE "$api_url/v1/demo-data")"
  python3 - "$response" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
removed = payload["removed"]
print("Cleared synthetic demo data: " + ", ".join(f"{key}={value}" for key, value in removed.items()))
PY
fi
