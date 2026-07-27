#!/usr/bin/env python3
"""Generate reproducible synthetic actionable-URL findings for agent demos."""

from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_SEED = 20260726
DEFAULT_COUNT = 1000
WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = WORKSPACE / "data" / "synthetic" / "actionable-urls.json"

FINDINGS = (
    (
        "Outdated TLS configuration",
        "TLS 1.0 or a weak cipher suite was accepted by the synthetic endpoint check",
        "Encrypted traffic could be downgraded or intercepted",
        "Disable TLS 1.0/1.1 and weak ciphers; require TLS 1.2 or newer",
    ),
    (
        "HTTPS not enforced",
        "The synthetic endpoint accepted an unencrypted HTTP request without redirecting",
        "Credentials or session data could cross the network unencrypted",
        "Redirect HTTP to HTTPS and enable HSTS after validating all subdomains",
    ),
    (
        "Missing Content-Security-Policy",
        "The synthetic response did not include a Content-Security-Policy header",
        "Injected browser content could execute with fewer restrictions",
        "Deploy and test a restrictive Content-Security-Policy header",
    ),
    (
        "Exposed administrative endpoint",
        "The synthetic administrative route was reachable without a network restriction",
        "Attackers could target a privileged management interface",
        "Restrict the endpoint to the management network and require strong authentication",
    ),
    (
        "Insecure cookie attributes",
        "The synthetic session cookie omitted Secure, HttpOnly, or SameSite attributes",
        "Session tokens could be exposed or sent in unsafe contexts",
        "Set Secure, HttpOnly, and an appropriate SameSite policy on session cookies",
    ),
    (
        "Known vulnerable server version",
        "The synthetic service banner matched a version with a published vulnerability",
        "A known exploit could compromise the exposed service",
        "Upgrade to the vendor-fixed release and verify the reported version",
    ),
    (
        "Permissive CORS policy",
        "The synthetic response allowed credentials with an untrusted origin",
        "An untrusted site could issue authenticated cross-origin requests",
        "Allow only approved origins and reject credentialed wildcard access",
    ),
    (
        "Directory listing enabled",
        "The synthetic endpoint returned an index of files and directories",
        "Internal files and deployment details could be disclosed",
        "Disable directory listing and explicitly publish only required files",
    ),
    (
        "Missing authentication rate limit",
        "The synthetic login endpoint accepted repeated attempts without throttling",
        "Automated password guessing could compromise user accounts",
        "Add account-aware rate limiting, backoff, and suspicious-login monitoring",
    ),
    (
        "Verbose error disclosure",
        "The synthetic response exposed stack and component details",
        "Implementation details could help an attacker refine an exploit",
        "Return generic client errors and keep detailed diagnostics in protected logs",
    ),
)

RATING_RANGES = {
    "Critical": (9.0, 10.0),
    "High": (7.0, 8.9),
    "Medium": (4.0, 6.9),
    "Low": (0.1, 3.9),
    "Informational": (0.0, 0.0),
}
STATUSES = ("Open", "In Progress", "Scheduled", "Pending Validation")
PATHS = ("login", "admin", "api", "portal", "files", "account", "status", "dashboard")


def build_dataset(count: int, seed: int, generated_at: str) -> dict[str, Any]:
    if count < 1:
        raise ValueError("count must be positive")

    rng = random.Random(seed)
    checked_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    findings: list[dict[str, Any]] = []
    ratings = tuple(RATING_RANGES)

    for index in range(1, count + 1):
        vulnerability, evidence, risk, fix = rng.choice(FINDINGS)
        rating = rng.choice(ratings)
        minimum, maximum = RATING_RANGES[rating]
        cvss = round(rng.uniform(minimum, maximum), 1) if maximum else 0.0
        last_checked = checked_at - timedelta(
            days=rng.randint(0, 30),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        path = rng.choice(PATHS)
        findings.append(
            {
                "URL": f"https://asset-{index:04d}.example.test/{path}",
                "Insecurity / Vulnerability": vulnerability,
                "Rating": rating,
                "CVSS": cvss,
                "Evidence": f"SYNTHETIC: {evidence}",
                "Business Risk": risk,
                "Recommended Fix": fix,
                "Status": rng.choice(STATUSES),
                "Last Checked": last_checked.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            }
        )

    return {
        "schema_version": "1.0",
        "synthetic": True,
        "seed": seed,
        "generated_at": generated_at,
        "count": count,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--generated-at",
        default=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    args = parser.parse_args()

    dataset = build_dataset(args.count, args.seed, args.generated_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, indent=2) + "\n")
    print(json.dumps({key: dataset[key] for key in ("count", "seed", "generated_at")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
