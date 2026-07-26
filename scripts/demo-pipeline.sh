#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mock_port="${MOCK_API_PORT:-8100}"
dashboard_port="${DASHBOARD_PORT:-8300}"
api_url="http://127.0.0.1:${mock_port}"
model="$repo_root/services/processing/artifacts/registry/isolation-forest-001.pkl"
tmp="$(mktemp -d)"
mock_pid=""

cleanup() {
  if [[ -n "$mock_pid" ]]; then
    kill "$mock_pid" 2>/dev/null || true
    wait "$mock_pid" 2>/dev/null || true
  fi
  rm -rf "$tmp"
}
trap cleanup EXIT INT TERM

if [[ ! -f "$model" ]]; then
  just --justfile "$repo_root/services/processing/justfile" \
    --working-directory "$repo_root/services/processing" train
fi

MOCK_PIPELINE_MODE=1 MOCK_API_PORT="$mock_port" \
  python3 "$repo_root/services/dashboard/mocks/mock_api.py" \
  >"$tmp/mock-api.log" 2>&1 &
mock_pid=$!

for _ in $(seq 1 30); do
  if curl -fsS "$api_url/health" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$mock_pid" 2>/dev/null; then
    cat "$tmp/mock-api.log" >&2
    exit 1
  fi
  sleep 0.2
done
curl -fsS "$api_url/health" >/dev/null

python3 "$repo_root/scripts/generate_dummy_events.py" \
  --output-dir "$tmp/generated" \
  --post-to "$api_url/v1/events"

uv run --project "$repo_root/services/processing" squidward-process detect \
  --events "$tmp/generated/events.jsonl" \
  --baseline "$repo_root/fixtures/expected/normal.json" \
  --model "$model" \
  --post-to "$api_url" \
  >"$tmp/detection.json"

python3 - "$api_url" "$tmp/detection.json" <<'PY'
import json
import sys
from urllib.request import urlopen

api_url, detection_path = sys.argv[1:]
detection = json.load(open(detection_path))
with urlopen(f"{api_url}/v1/events") as response:
    events = json.load(response)
with urlopen(f"{api_url}/v1/findings") as response:
    findings = json.load(response)
with urlopen(f"{api_url}/v1/recommendations") as response:
    recommendations = json.load(response)
assert events["count"] == 26
assert findings["count"] == 1
assert recommendations["count"] == 1
assert detection["finding"]["severity"] == "critical"
print(
    "Demo pipeline ready: "
    f"{events['count']} events -> risk {detection['risk_score']:.2f} -> "
    f"{recommendations['recommendations'][0]['action_type']}"
)
PY

if [[ "${DEMO_PIPELINE_NO_UI:-0}" == "1" ]]; then
  exit 0
fi

printf 'Dashboard: http://127.0.0.1:%s\n' "$dashboard_port"
printf 'Mock API:  %s\n' "$api_url"
cd "$repo_root/services/dashboard"
if command -v pnpm >/dev/null 2>&1; then
  pnpm run dev -- --host 127.0.0.1 --port "$dashboard_port"
else
  npx -y pnpm@11.17.0 run dev -- --host 127.0.0.1 --port "$dashboard_port"
fi
