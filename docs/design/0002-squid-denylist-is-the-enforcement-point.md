# ADR 0002 — Squid denylist is the enforcement point

**Status:** accepted (recorded retroactively)
**Date:** 2026-07-26
**Depends on:** [ADR 0001](./0001-openclaw-gateway-replaces-nemoclaw.md)

## Context

[exfiltration-protection-architecture.md](../exfiltration-protection-architecture.md)
§2 names **OpenShell policy** as the MVP enforcement point and Squid ACL as "an
optional second enforcement example". The demo's climax is stated as *"OpenShell
blocks the repeated transfer"*, and §7 keeps the Squid denylist as the fallback.

Planning inverted the risk on that ordering. Every OpenShell finding available was
established on x86_64 / OpenShell 0.0.85 / kernel 6.12, while the GB10 is aarch64 /
0.0.91 / kernel 6.17 — so `dxnvh-bht.3` was filed to settle whether
`network_policies` hot-reload actually blocks there, with the Squid denylist named
as the NO-GO fallback.

ADR 0001 removed the runtime that decision depended on.

## Decision

**Squid is the enforcement point.** The ingestion service owns the denied-destination
list and serves it in the two shapes Squid consumes.

Evidence in `services/ingestion/src/ingestion/app.py`:

- `GET /v1/rules` — JSON list of denied destinations, for the dashboard.
- `GET /v1/rules.txt` — one destination per line, deliberately un-enveloped. Its
  docstring: *"squid's `dstdomain \"file\"` format directly. This is the MVP
  enforcement path from architecture §7: fetch to a file, then `squid -k
  reconfigure`. No envelope: squid parses this, not the dashboard."*
- `GET /v1/rules/check?dst=` — *"Point query for the external_acl helper. `denied`
  true means deny."*

That covers both tiers §7 describes: the static denylist file for the MVP, and the
`external_acl_type` helper for the eventual live path.

`infra/gb10/squid/squid.conf` is on `main` with the `exfilguard` logformat from §4.2
verbatim (`logformat exfilguard ts=%ts.%03tu src=%>a …`, plus a `dst_ip=%<a` field
beyond the spec), writing to `/var/log/squid/access.log`.

## Consequences

**The §7 latency constraint now binds the demo.** Squid writes its access-log record
*during or after* a request, so the log stream cannot retroactively stop the first
completed transfer — it can only block the *next* one after an approved denylist
update and a reconfigure. The demo must therefore narrate: transfer completes →
detected → analyst approves → denylist updated → **repeat** transfer blocked. That is
what the architecture already prescribed ("start in observe mode"), but with
OpenShell it was tempting to imply pre-emptive blocking. It is not available.

**The helper must stay dumb.** §7 is explicit that an `external_acl` helper may check
only cached deterministic policy, with strict timeouts and a defined
fail-open/fail-closed stance, and **must not** call the LLM or the GPU model.
`/v1/rules/check` is a single point query against SQLite, which satisfies this — but
the fail-open/fail-closed behaviour on ingestion being unreachable is **not yet
specified** and needs deciding before the helper is wired into `squid.conf`.

**Invalidated.** `dxnvh-bht.3` (does `network_policies` hot-reload block on aarch64,
and is it legible) no longer gates anything — the question it existed to answer has
been routed around. Its NO-GO branch is now the chosen design.

**Lost capability worth naming.** OpenShell's OCSF `DENIED` record was a
machine-readable, per-process, timestamped block event — the enforcement-audit
artifact `dxnvh-xe5.2` and dashboard screen `dxnvh-7t2.7` were designed against.
Squid's equivalent is an access-log line with `result=TCP_DENIED`, which is coarser:
no binary, no pid. Enforcement-result records must now be synthesised from the
access log rather than read from a structured stream.

**Still open.** `squid.conf` on `main` has the logformat but **no `acl exfil_denied
dstdomain` / `http_access deny` block**, and nothing yet fetches `/v1/rules.txt` to
a file or runs `squid -k reconfigure`. The enforcement loop is served but not wired.

## Alternatives not taken

Waiting for `dxnvh-bht.3` to return a verdict on OpenShell network policy. Overtaken
by ADR 0001 — there is no NemoClaw sandbox to apply a policy to.
