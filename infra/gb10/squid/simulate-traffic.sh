#!/usr/bin/env bash
# Drive synthetic egress through the proxy so there is something in the log to
# build a parser against, without waiting for a human to browse.
#
#   ./simulate-traffic.sh                          # against localhost:3128
#   ./simulate-traffic.sh http://192.168.0.100:3128
#
# Watch it land, in another terminal:
#   ssh dell-gb10 'docker exec hack-squid tail -f /var/log/squid/access.log'
set -euo pipefail

PROXY="${1:-http://127.0.0.1:3128}"

# Shaped like real agent egress: package registries, model hosts, LLM APIs, and
# the telemetry endpoints that are the whole reason to audit in the first place.
TARGETS=(
    https://pypi.org/simple/
    https://registry.npmjs.org/
    https://github.com
    https://huggingface.co
    https://api.github.com
    https://api.anthropic.com
    https://api.openai.com
    https://api.mixpanel.com
    https://www.google-analytics.com
    https://sentry.io
    http://neverssl.com          # plain HTTP — logs a full URL, not just CONNECT
    https://example.com
)

echo "proxy: $PROXY"
for url in "${TARGETS[@]}"; do
    # A 401/403/404 from the far end is fine — the point is the CONNECT, which
    # squid logs either way. Only a proxy-level failure matters.
    code=$(curl -s -o /dev/null -w '%{http_code}' \
        --proxy "$PROXY" --max-time 15 "$url" || echo "---")
    printf '  %-36s %s\n' "$url" "$code"
done

echo
echo "done. Capture these into a fixture with:"
echo "  just s collector replay <(docker exec hack-squid cat /var/log/squid/access.log)"
