# Shared demo fixtures

Deterministic raw source records and the canonical events they normalize to,
for the two scenarios the end-to-end acceptance test replays (see
[`docs/modular-implementation-plan.md` §9](../docs/modular-implementation-plan.md#9-end-to-end-acceptance-test)
and [`docs/exfiltration-protection-architecture.md`](../docs/exfiltration-protection-architecture.md)).
Per the plan's Milestone 1, every component builds against these files —
**no component waits on another team's running service.**

```text
fixtures/
  squid/      raw Squid access-log records, exfilguard logformat
  openshell/  raw OpenShell OCSF-style action/audit log lines
  expected/   the canonical events (contracts/event.schema.json) those raw
              records normalize to, one array per scenario
  validate.py schema + determinism check for fixtures/expected/*.json
```

These are hand-authored, fixed-content fixtures, not a live capture — they
exist so ingestion (`dxnvh-2jb`), processing (`dxnvh-0e6`), and the dashboard
(`dxnvh-7t2`) can all build and test against the same two scenarios before
Squid, OpenShell, or a real business agent are running. `dxnvh-0f2.6` later
reproduces the same two scenarios for real, against live infrastructure.

## The two scenarios

### `normal` — an ordinary work session

The business agent reads a project file, fetches two ordinary destinations
through Squid during work hours, and writes a note. Nothing here should clear
the live alert threshold (implementation plan §5, Component 3 "definition of
done").

1. `openshell` `read_file` — `/workspace/project/README.md`
2. `squid` `GET` — `docs.internal.example` (612 request bytes)
3. `squid` `GET` — `pypi.org` (584 request bytes)
4. `openshell` `write_file` — `/workspace/project/notes.md`

### `suspicious` — a cross-action sequence ending in a transfer

Four correlated actions across **two sources**, not one large upload — see
`docs/epics/0f2-infrastructure.md`: "three or more correlated actions ending
in a transfer to a new destination... a single upload is caught by a
one-line rule and demonstrates nothing about correlation." This is the
`read sensitive file -> stage/compress -> attempt network egress -> transfer`
shape:

1. `openshell` `read_file` — a sensitive file, `/data/customers/export.csv`
2. `openshell` `archive_file` — stages/compresses it to `/tmp/staging/export-2026-03-15.tar.gz`
3. `openshell` `network_egress_attempt` — the sandboxed process opens a
   connection to the explicit Squid proxy (`gb10-proxy.local:3128`); OpenShell's
   own audit only sees the proxy hop, not the final HTTP destination inside it
   — that is exactly why correlating it with the Squid record below is the
   point of this scenario, not a shortcut around it
4. `squid` `POST` — 25,000,000 request bytes to `test-storage.local`, a
   destination unseen elsewhere in these fixtures, outside working hours

Deliberately mirrors the risk example already frozen in
[`contracts/examples/event.json`](../contracts/examples/event.json) (same
destination, byte count, and `outside_work_hours: true`) — that example *is*
event 4 of this sequence; the three events before it are what turn a single
upload into a correlated incident.

## Raw formats

### `fixtures/squid/*.access.log`

One line per request, in the `exfilguard` logformat from
`exfiltration-protection-architecture.md` §4.2:

```text
ts=%ts.%03tu src=%>a user=%un method=%rm uri=%ru status=%>Hs req_bytes=%>st resp_bytes=%<st mime=%mt result=%Ss
```

i.e. `ts=<unix>.<ms> src=<ip> user=<user> method=<METHOD> uri=<uri>
status=<code> req_bytes=<n> resp_bytes=<n> mime=<mime> result=<tag>/<code>`.

### `fixtures/openshell/*.ocsf.log`

One line per audited action, in the verified OCSF-style shape emitted by a
real OpenShell sandbox (see `libs/skills/openshell-egress-audit/SKILL.md`
"The violation record (OCSF)"):

```text
[<epoch>.<ms>] [sandbox] [OCSF ] [ocsf] <CLASS>:<ACTIVITY> [<SEVERITY>] <DISPOSITION> <binary>(<pid>) -> <destination> [policy:<rule> engine:<opa|l7>] [reason:<text>]
```

`NET:OPEN` is verified on-host for network egress. `FILE:READ` / `FILE:WRITE`
extend the same shape to filesystem actions for this fixture — OpenShell's
own filesystem-class audit line format has not been observed on a live host
(the runtime was absent during that spike); treat the class name, not the
overall line shape, as the part still to confirm once `dxnvh-bht` lands.

## Canonical events (`fixtures/expected/*.json`)

Each file is a JSON array of events matching `contracts/event.schema.json`,
in chronological order. Fields beyond the schema's required set follow the
raw record they came from:

- Squid-derived events keep `method`, `uri`, `status`, `response_bytes`,
  `mime`, and `result` under `attributes`, and set the schema's top-level
  `destination` / `request_bytes` to the proxied host / request size.
- OpenShell-derived events keep `binary`, `pid`, `class`, `severity`,
  `disposition`, `policy`, `engine`, and `reason` under `attributes` (the
  fields carried by the raw OCSF line), and use the schema's top-level
  `destination` only for the one network-class event — filesystem actions
  keep their path under `attributes.path` instead, since `destination` reads
  as a network target elsewhere in the contract.

Every id (`evt-normal-NNN` / `evt-susp-NNN`) and timestamp is hardcoded in the
file, not generated at fixture-authoring time (no `now()`/`uuid4()`
anywhere in these fixtures) — this is what makes replaying a fixture twice
produce byte-identical canonical events.

## Validating

```sh
just fixtures-check   # this fixtures/ tree only
just check            # everything, including fixtures-check
```

`fixtures/validate.py` checks each event in `fixtures/expected/*.json`
against `contracts/event.schema.json`, that `event_id`s are unique within
each file, and that every `timestamp` is an explicit UTC instant
(`...T...Z`).
