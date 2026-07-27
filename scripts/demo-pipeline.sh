#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ingestion_port="${INGESTION_PORT:-8100}"
dashboard_port="${DASHBOARD_PORT:-8300}"
api_url="http://127.0.0.1:${ingestion_port}"
model="$repo_root/services/processing/artifacts/registry/isolation-forest-001.pkl"
database="${DEMO_PIPELINE_DB:-$repo_root/data/demo-pipeline.db}"
tmp="$(mktemp -d)"
ingestion_pid=""

cleanup() {
  if [[ -n "$ingestion_pid" ]]; then
    kill "$ingestion_pid" 2>/dev/null || true
    wait "$ingestion_pid" 2>/dev/null || true
  fi
  rm -rf "$tmp"
}
trap cleanup EXIT INT TERM

if [[ ! -f "$model" ]]; then
  just --justfile "$repo_root/services/processing/justfile" \
    --working-directory "$repo_root/services/processing" train
fi

mkdir -p "$(dirname "$database")"
if [[ "${DEMO_PIPELINE_RESET:-1}" == "1" ]]; then
  rm -f "$database" "${database}-wal" "${database}-shm"
fi
INGESTION_DB_PATH="$database" \
  uv run --project "$repo_root/services/ingestion" \
    uvicorn ingestion.app:app --host 127.0.0.1 --port "$ingestion_port" \
    >"$tmp/ingestion.log" 2>&1 &
ingestion_pid=$!

for _ in $(seq 1 30); do
  if curl -fsS "$api_url/health" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$ingestion_pid" 2>/dev/null; then
    cat "$tmp/ingestion.log" >&2
    exit 1
  fi
  sleep 0.2
done
curl -fsS "$api_url/health" >/dev/null

python3 "$repo_root/scripts/generate_dummy_events.py" \
  --output-dir "$tmp/generated" \
  --event-count 22 \
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
assert events["count"] == 22
assert findings["count"] == 1
assert recommendations["count"] == 0
assert detection["finding"]["severity"] in {"high", "critical"}
print(
    "Demo pipeline ready: "
    f"{events['count']} events -> risk {detection['risk_score']:.2f} -> "
    "finding persisted; OpenClaw investigation pending"
)
PY

if [[ "${DEMO_PIPELINE_NO_UI:-0}" == "1" ]]; then
  exit 0
fi

printf 'Dashboard: http://127.0.0.1:%s\n' "$dashboard_port"
printf 'Ingestion: %s\n' "$api_url"
printf 'SQLite:   %s\n' "$database"
cd "$repo_root/services/dashboard"
if command -v pnpm >/dev/null 2>&1; then
  pnpm run dev -- --host 127.0.0.1 --port "$dashboard_port"
else
  npx -y pnpm@11.17.0 run dev -- --host 127.0.0.1 --port "$dashboard_port"
fi
