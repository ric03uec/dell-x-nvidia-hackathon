"""The fictional company whose egress the demo shows.

Destinations are FIXED, not generated, because Squid has to resolve them: each
one is a network alias on the sink container (infra/gb10/docker-compose.squid.yml).
Faker generates everything *around* them — users, paths, filenames, sizes — so
the traffic reads like a real workday without depending on the internet.

Keeping the catalog here means the traffic generator, the scenario, and the
compose aliases cannot drift apart: `demo aliases` prints the list compose
needs.
"""

from __future__ import annotations

# Routine business egress. A baseline detector should learn these and stay quiet.
ROUTINE = [
    "crm.northwind-labs.test",
    "files.northwind-labs.test",
    "docs.confluence-cloud.test",
    "api.billing-sandbox.test",
    "registry.npm-mirror.test",
    "pypi.package-mirror.test",
    "telemetry.metrics-agent.test",
    "mail.smtp-relay.test",
    "auth.okta-sandbox.test",
    "status.uptime-probe.test",
]

# Never seen before the incident. This is what the story turns on: not the size
# of one upload, but a large transfer to a destination with no history.
#
# A POOL, not one host, so the demo is re-runnable. Once an analyst approves a
# block, Squid enforces it permanently — a second take against the same host
# would be refused before the incident could happen, and the recording would
# show nothing. Each run picks a destination that is not yet denied, which
# needs no reset endpoint and no database surgery between takes.
EXFIL_POOL = [
    "backup-sync.dropfiles-cdn.test",
    "sync-node-2.dropfiles-cdn.test",
    "vault-mirror.dropfiles-cdn.test",
    "offsite-3.dropfiles-cdn.test",
    "archive-relay.dropfiles-cdn.test",
]
EXFIL = EXFIL_POOL[0]

ALL = [*ROUTINE, *EXFIL_POOL]

# Staging actions that precede the transfer. The point of the demo is
# CORRELATION — a single big POST is catchable by a one-line rule and proves
# nothing about why the product needs a model or an agent.
STAGING = [
    ("crm.northwind-labs.test", "/api/v2/customers/export", "customer records queried"),
    ("files.northwind-labs.test", "/finance/q3-forecast.xlsx", "finance workbook read"),
    ("files.northwind-labs.test", "/hr/salary-bands-2026.csv", "HR compensation data read"),
    (
        "docs.confluence-cloud.test",
        "/wiki/spaces/SEC/pages/credentials",
        "internal creds page read",
    ),
]
