---
name: nemoclaw-fanout
description: Decide whether a NemoClaw agent can fan out to N concurrent subagents, and how wide, before you build a demo around it. Use when designing any parallel-subagent / delegation / orchestrator-worker pattern on NemoClaw/OpenClaw, when picking a fan-out width, when `sessions_spawn` isn't spawning anything, or when a "delegate to 20 workers" plan needs a reality check. Triggers on "fan out", "concurrent subagents", "sessions_spawn", "delegationMode", "maxConcurrent", "subagents.maxChildrenPerAgent", "how many agents can run at once", "orchestrator worker", "why won't my agent delegate", "parallel agent -m".
---

# NemoClaw fan-out: how wide can you actually go?

Established on `factory-orca` (x86_64 Debian, kernel 6.12.94, 4 CPU / 7.8 GiB,
**no GPU**) during nvhack-qo4w.3. Stack: NemoClaw **v0.0.93** / OpenShell
**0.0.85** / OpenClaw **2026.7.1** / Ollama serving **`llama3.2:1b`**. Every
claim below is tagged **verified-on-host** (this run's own NemoClaw/OpenClaw
logs on factory-orca demonstrated it — the actual stack), **verified-offline**
(empirically exercised, but only against a *stand-in* surface — Ollama's raw
OpenAI `tools=[…]` API — **not** through NemoClaw's own delegation surface, so
it says nothing about how NemoClaw behaves), or **UNVERIFIED** (read from
OpenClaw's shipped docs, reasoned from stated behavior, or extrapolated — never
actually exercised). **`verified-on-host` means demonstrated on the NemoClaw
stack itself.** A behavior only shown against raw Ollama is `verified-offline`
even though that Ollama ran on the same physical box — and note that the one
forcing-prompt behavior that *was* exercised through NemoClaw here **failed**
(see the model-capability floor). Raw captures behind each claim:
`docs/spikes/nvhack-3iy.md`. (Provenance corrected under adversarial review
nvhack-qo4w.5 — beads nvhack-d0b6 (offline mislabel) and nvhack-k84m (ceiling
layer). nvhack-d0b6 independently re-checked the three forcing-prompt claims
above and the provenance-table rows below against `docs/spikes/nvhack-3iy.md`
§5 and `docs/spikes/nvhack-3iy-adversarial-review.md` §2(a): all three already
carry `verified-offline` with the NemoClaw-failure caveat, no residual
unqualified `verified-on-host` tag found.)

**Read the provenance tags, don't skim them.** Two different things wear the
"observed" hat in this doc and they are NOT the same claim: what the *scheduler*
did (measured on the host, verified-on-host) and what the *forcing prompt* did
(validated only against Ollama's raw OpenAI-style `tools=[…]` API — **offline**,
NOT through NemoClaw's own delegation surface, which actually **failed** on this
model). Keep them apart.

**Arch caveat:** this host is **amd64 (x86_64)**; the GB10/DGX Spark target is
**aarch64** and would run a different (larger) model. The scheduler-config
ceiling is protocol/config-level and should transfer; the model-capability floor
(below) is entirely model-dependent and will change with the model. Re-run the
probe (see [Reproduce](#reproduce)) on the real host before trusting any number
here there.

## The straight answer

**Concurrent width on this host/config = 4. It is a genuine-concurrency
finding, not a serialization finding — the width is *capped*, not *sequential*.
verified-on-host.** Six independent `agent -m` runs launched simultaneously
produced exactly **4** overlapping in-flight inference requests at peak; the 5th
was admitted only *after* the 1st finished. Requests genuinely overlap in
flight — delegation does NOT serialize — but the scheduler holds the line at 4.

**The ceiling is client-side admission control upstream of the model, NOT
Ollama's inference queue. verified-on-host — but WHICH client-side layer is
UNVERIFIED.** If inference were the limiter, all 6 requests would have hit the
model at once and Ollama would have queued them internally. Instead only 4
`model-fetch start` lines fired, then the rest were withheld until a slot freed
— semaphore admission control upstream of the model. That much is solid: it
rules out Ollama's *server-side* queue. What it does **not** prove is that the
gate is specifically `agents.defaults.maxConcurrent` (the OpenClaw scheduler
knob). At least two other client-side layers fit the identical log equally
well: (a) an **HTTP transport connection-pool / maxSockets cap** — note the
throttled lines are emitted by the `[provider-transport-fetch]` *transport*
component, not by a scheduler component; and (b) a **CPU-count-derived worker
limit** — this host has exactly **4 CPU** and the observed cap is exactly **4**,
a coincidence never disentangled here (no run changed `maxConcurrent` to a
non-CPU value or ran on a different CPU count to see which the cap tracks).
So "it's the scheduler semaphore" is the most plausible of ≥2 unconfirmed
guesses, not a demonstrated fact — treat the *layer* as **UNVERIFIED**
(nvhack-k84m).

**Next step to disambiguate the layer (not yet run):** set `maxConcurrent`
explicitly to a value that is *not* the host CPU count (e.g. 3 or 6, not 4)
and re-run the width probe — if the observed cap tracks the new config value,
that's evidence for (a) the scheduler semaphore or (b) the transport
socket-pool, not (c) CPU-count; if the cap stays pinned at 4 regardless of
config, that's evidence for the CPU-count coincidence instead. Independently,
re-running the unmodified probe on a host with a *different* CPU count (the
GB10 target qualifies) is the second half of the same disambiguation — if the
cap moves with CPU count on an unchanged config, that also implicates (c).
Neither half of this experiment has been run; do it before treating the layer
as settled.

**Decision rule (state it out loud, don't leave it implicit):**

> Every fan-out-shaped idea in the pool — nvhack-3lh, nvhack-xrg, nvhack-d7c,
> nvhack-b5r, and anything else gated on this finding — must plan around a
> width ceiling of **~4 concurrent subagents** on this class of host/config,
> **OR** re-architect toward **host-driven parallel `agent -m` processes** if it
> needs wider fan-out than that. Do not design for width 8 (or 20) on the
> default config and discover the cap during rehearsal.

Note the fallback and the finding are the *same* mechanism: host-driven parallel
`agent -m` is exactly what was measured at width 4, because the gateway
`maxConcurrent` semaphore caps *those* too. "Re-architect to parallel `agent -m`"
buys you genuine concurrency but **not** more than 4 wide until you raise
`maxConcurrent` at onboard time (see [Raising the ceiling](#raising-the-ceiling)).

**Second, distinct gate — do not conflate it with the width cap:** on this host
the 1B model **never successfully emitted a single structured `sessions_spawn`
call at all. verified-on-host.** In-model delegation was not "capped at 4" — it
was never exercised, because the model couldn't drive NemoClaw's tool surface.
The width-4 number above came from *host-driven* parallel `agent -m` processes,
not from one agent spawning children. See [The model-capability
floor](#the-model-capability-floor--a-second-distinct-gate).

## The width measurement (how 4 was established)

**verified-on-host.** Six `nemoclaw <sandbox> agent -m "Reply with only the
number 42."` processes, each with its own `--session-id`, launched at the same
wall-clock instant. Process exits staggered ~27 s apart over ~1m50s. The sandbox
log's `model-fetch` sweep shows why — peak in-flight never exceeded 4:

```
2026-07-26T17:08:32.384 [provider-transport-fetch] [model-fetch] start  model=llama3.2:1b   # inflight=1
2026-07-26T17:08:32.811 [provider-transport-fetch] [model-fetch] start  model=llama3.2:1b   # inflight=2
2026-07-26T17:08:33.156 [provider-transport-fetch] [model-fetch] start  model=llama3.2:1b   # inflight=3
2026-07-26T17:08:33.496 [provider-transport-fetch] [model-fetch] start  model=llama3.2:1b   # inflight=4  <-- PEAK
2026-07-26T17:08:48.623 [provider-transport-fetch] [model-fetch] response status=200        # inflight=3
2026-07-26T17:08:51.052 [provider-transport-fetch] [model-fetch] start  model=llama3.2:1b   # inflight=4  (5th admitted only AFTER a slot freed)
...steady-state 4 held for the whole window...
```

That "emit 4, then wait for a response before emitting the 5th" shape **is** the
semaphore signature. It is the single load-bearing observation for the whole
NO-GO. If you re-run on the real host and see all N `model-fetch start` lines
fire at t≈0, the ceiling has moved and this verdict no longer holds.

## Where the ceiling lives (the knobs)

The default values were **measured** where noted; the config *names, defaults,
and semantics* are **read from OpenClaw's shipped docs on the host**
(`docs/gateway/config-agents.md`, `docs/tools/subagents.md`), NOT exercised —
so the name→behavior mapping is UNVERIFIED except for the two that were
measured.

| Knob | What it caps | Default | Provenance |
|---|---|---|---|
| `maxConcurrent` (gateway, `agents.defaults`) | parallel agent runs across sessions | **4** | **verified-on-host** — the width-4 measurement above matches the documented default; name attribution is doc-sourced |
| `subagents.maxChildrenPerAgent` | active children one agent session may spawn | **5** | **UNVERIFIED** — doc schema only, never exercised (in-model spawn never fired) |
| `subagents.maxConcurrent` | concurrent child-agent runs across subagent execution | **8** | **UNVERIFIED** — doc schema only, never reached |
| `subagents.maxSpawnDepth` | nesting depth for spawning (range 1–5) | **1** (no nesting) | **UNVERIFIED** — doc schema only |

Even on paper, a single main agent's own fan-out is capped at **5**
(`maxChildrenPerAgent`) and the gateway admits **4** at a time — both under any
width-8 bar — until raised. **None of these are inference-queue properties.**

### These knobs are recreate-time, not runtime-adjustable

**verified-on-host that the CLI says so; UNVERIFIED that a recreate actually
moves the ceiling** (the recreate was deliberately not spent on this shared box —
see [Stewardship](#stewardship-why-the-matrix-wasnt-fully-walked)).
`nemoclaw <sandbox> agents apply --help` states plainly:

```
Per-agent `model`, `subagents.*`, top-level `defaults`, and `main` overrides
require a sandbox rebuild and are reported as warnings; rerun
`nemoclaw onboard --agents <file> --recreate-sandbox` to bake them.
```

So you **cannot** `agents apply` your way to a wider cap on a live sandbox. Every
`subagents.*` / `maxConcurrent` change is a full `onboard --recreate-sandbox` —
an irreversible cut on a shared sandbox. Plan the width you need **before** the
first onboard — the same static/dynamic split `openshell-data-boundary`
documents for `policy.yaml`: `filesystem_policy` is **static** (compiled once
at sandbox creation, cannot be loosened afterward) while `network_policies` is
**dynamic** (hot-reloadable on a running sandbox). `subagents.*` / `defaults`
/ `main` sit on the static side of that same split.

## How to force delegation reliably (and what fails)

There are two layers here and the provenance splits hard between them.

**The prompt *shape* that works — driven, one-directive-per-turn, explicit
target `agent_id`. verified-OFFLINE only — against Ollama's raw OpenAI-style
`tools=[…]` API (offline half, nvhack-qo4w.2), NOT through NemoClaw (whose own
surface this same prompt FAILED on — see the model floor; nvhack-d0b6).** The driver
advances one item at a time: it sends a single directive naming *both* the task
text *and* the target `agent_id` explicitly, waits for exactly one tool call,
feeds back a result, and only then sends the next directive. Against
`llama3.2:1b` on Ollama's raw API this landed **20/20** clean, well-formed
delegations at temperature 0 and 12/12 at the model's default 0.7.

**The negative control — a single message listing all N items and asking for N
tool calls back — is NOT reliable. verified-OFFLINE (same offline Ollama API).**
The model emitted **1** real (malformed) tool call and dumped the other ~19
attempted delegations as unstructured pseudo-JSON in the response body, never
through the structured tool channel a harness can parse. A batch-listing prompt
produces a near-zero *structured* delegation count that has nothing to do with
any scheduler knob — exactly the confound to rule out first.

**A second reason the per-turn directive names `agent_id` explicitly:** left to
choose, the model reused the **same** `agent_id` for every item, silently
collapsing "N distinct workers" to one before the scheduler ever saw it.
verified-OFFLINE (offline Ollama API).

**The load-bearing caveat: the shape that worked offline against Ollama's raw
API FAILED through NemoClaw's own surface with this model.** See next section.
So "driven-one-per-turn is reliable" is a claim about *elicitation from a small
model under a generic tool schema*, not about NemoClaw delegation. Re-validate
on the real host and model with `scripts/validate_forcing_prompt.py --url … --model …`
before trusting it end-to-end.

## Count real spawns from logs — never trust model self-report

**Why this distinction was load-bearing here, stated plainly: the model never
successfully self-reported a `sessions_spawn` call at all. verified-on-host.**
Had anyone trusted the model's *narration* — it emitted a JSON-looking block
that *reads* like three delegations — they'd have recorded "3 subagents spawned."
The real log showed **zero** `agent:main:subagent:<uuid>` sessions and **one**
`run … ended`. The gap between "the model said it delegated" and "the scheduler
actually spawned a child" was the entire finding. Count from logs, always.

Capture the sandbox log across the delegation run and count structured events,
not prose:

```bash
nemoclaw <sandbox> logs > run.log
uv run agents/delegation-probe/scripts/count_spawns.py run.log
```

```
run_count:        6     # `run <uuid> ended` lines — how many agent runs actually ran
subagent_spawns:  0     # `agent:<id>:subagent:<uuid>` session keys — REAL children spawned
fetch_starts:     11    # `model-fetch start` — inference requests dispatched
fetch_responses:  11    # `model-fetch response` — inference requests completed
max_concurrent:   4     # peak simultaneous in-flight model-fetch — the width ceiling
toolcall_as_text: 0     # "reply looks like a tool call but no structured invocation" — MODEL failures
```

Two counters carry the whole story:

- **`max_concurrent`** is the observed width ceiling — derived from the
  `model-fetch start`/`response` sweep, not from anything the model claims.
- **`toolcall_as_text`** is the tell that a low delegation count is a **model
  failure, not a scheduler cap.** If it's non-zero, the model tried to delegate
  as text and the run never reached the scheduler — do not read the resulting
  low `subagent_spawns` as "the scheduler blocked it."

**Provenance:** the log line *shapes* the counter keys on
(`run … ended`, `model-fetch start/response`, `agent:<id>:subagent:<uuid>`,
`Assistant reply looks like a tool call …`) are **verified-on-host** — they were
captured from real host output and `spawn_log.py` was rewritten from its earlier
*guessed* OCSF `TAG:SUBTAG` shape to match (that guess was wrong; bead
nvhack-tel7). The fixture `agents/delegation-probe/tests/fixtures/host_concurrency_run.log`
is that real capture.

**Don't reach for OCSF here.** An `EPOCH [component] TAG:SUBTAG` shape *does*
exist on this stack — e.g. `[1785052548.742] [sandbox] [OCSF ] [ocsf] NET:OPEN
[MED] DENIED …` (see `libs/skills/openshell-egress-audit/SKILL.md`) — but it's
OpenShell's **network/config plane** (`NET:OPEN`, `SSH:OPEN`, `CONFIG:APPLYING`)
and carries **zero** agent-spawn events. Agent runs and spawns are the OpenClaw
shape above (`<ISO-8601+offset> [component] [subcomponent] message`), never
`TAG:SUBTAG`. Parsing logs for spawn counts against the OCSF shape will silently
match nothing.

## The model-capability floor — a second, distinct gate

**Known-bad model choice: `llama3.2:1b`.** If you're picking a small local
model for delegation-heavy work, do not pick this one — it could not reliably
drive `sessions_spawn` through OpenClaw's tool-search surface on this host (see
below). This is a model-capability finding, not a scheduler-config one; picking
a different config won't fix it.

**verified-on-host.** Independent of the scheduler ceiling, `llama3.2:1b` could
**not drive NemoClaw's `sessions_spawn` surface at all**. Given an explicit
orchestrator forcing prompt (call `sessions_spawn` three times, then
`sessions_yield`), the model returned a fake JSON code block as assistant *text*
— no structured tool invocation. OpenClaw's own log:

```
[agent/embedded] Assistant reply looks like a tool call, but no structured tool
                 invocation was emitted; treating it as text.
[agents/agent-command] [agent] run <uuid> ended with stopReason=stop
```

Zero subagent sessions. **Root cause: verified-on-host.** OpenClaw hides all
tools behind a **tool-search compact surface** (`tool-search: cataloged 31 tools
behind compact prompt surface`), requiring a `tool_search` → `tool_call` two-step
the 1B model cannot navigate (an earlier turn failed with `Unknown tool id:
hello`). This is why the offline forcing-prompt validation (against Ollama's raw
`tools=[…]` API, which exposes tools *directly*) does not transfer: the offline
harness never had to clear the tool-search hurdle that defeated the model here.

**Do not conflate the two gates.** "The scheduler capped us at 4" and "the model
never actually tried to delegate" are separate failures with separate fixes:

| Gate | What it is | Fix |
|---|---|---|
| Scheduler ceiling (width 4) | config semaphore, upstream of inference | raise `maxConcurrent` at `onboard --recreate-sandbox` |
| Model-capability floor | small model can't drive tool-search → tool-call | use a larger, better tool-tuned model (**UNVERIFIED** that a bigger model clears it — extrapolated; re-test on the real host's model) |

A width-8 test on the real GB10 could still fail at the model floor before the
scheduler ceiling is ever in play, if the host model can't navigate tool-search.
Test the floor first: confirm the model emits *one* structured `sessions_spawn`
before you believe any width number about *many*.

## Raising the ceiling

**UNVERIFIED — reasoned, not run.** To get past width 4 you must raise
`maxConcurrent` (and, for in-model fan-out, `subagents.maxConcurrent` /
`maxChildrenPerAgent`) in the agents manifest and `nemoclaw onboard --agents
<file> --recreate-sandbox` to bake it. Two costs to budget, neither measured
here:

1. The recreate is the irreversible-cut (nvhack-j40) — it rebuilds the sandbox.
2. Even if the config allows width N, running N concurrent inferences on a
   **4-CPU GPU-less** box is a *hardware* ceiling below the config ceiling —
   width-4 turns already took 15–34 s each on this host. On the GB10 (GPU) this
   changes entirely, but that is unmeasured here.

Whether `subagents.maxConcurrent: 8` is genuinely reachable after a recreate on
dedicated GB10 hardware is the natural follow-up — **UNVERIFIED**, never reached.

## Stewardship — why the matrix wasn't fully walked

The host was **shared with the live session's own agent processes** (4 CPU /
7.8 GiB, no GPU). Two escalations were deliberately not taken: (1) walking the
`subagents.*` knob matrix, because each cell needs a full sandbox recreate that
risks the running session; (2) forcing width ≥ 8, which needs both a recreate and
≥ 8 concurrent 1B inferences on a box where width-4 already saturated. The
measured width-4 default plus the documented config ceilings are sufficient for a
NO-GO with a located ceiling; the recreate-on-dedicated-hardware test is left for
the GB10.

## Reproduce

All three probe tools live in `agents/delegation-probe/` and re-run against a
different endpoint/model/host:

```bash
# 1. Forcing-prompt elicitation (offline validation half — Ollama raw tools API).
#    Re-point at the real host model before trusting it end-to-end:
uv run agents/delegation-probe/scripts/validate_forcing_prompt.py --n 20 --trials 1
uv run agents/delegation-probe/scripts/validate_forcing_prompt.py --naive --n 20   # the failing negative control

# 2. Width measurement — launch N parallel `agent -m` runs, each its own --session-id.
#    Simultaneity is load-bearing: the semaphore signature ("emit 4, wait, admit
#    the 5th only after a slot frees") is only legible if all N start within the
#    same few ms — a serial loop just measures your own launch latency instead.
#    Background every process from a single shell line, then `wait` for all exits:
N=6
for i in $(seq 1 "$N"); do
  nemoclaw <sandbox> agent -m "Reply with only the number 42." \
    --session-id "probe-$i" &
done
wait
#    ... then capture the sandbox log and count real spawns/concurrency:
nemoclaw <sandbox> logs > run.log
uv run agents/delegation-probe/scripts/count_spawns.py run.log
# -> read max_concurrent (the width ceiling) and toolcall_as_text (model-failure tell)
```

Before trusting any verdict here on the GB10: check `uname -r` and the actual
model in use, confirm the model emits **one** structured `sessions_spawn` (clears
the model floor), then measure `max_concurrent` under a real fan-out.

## Provenance summary

| Claim | Status |
|---|---|
| Concurrent width = 4, genuine concurrency (capped, not serialized) | **verified-on-host** (kernel 6.12.94, x86_64, llama3.2:1b) — 6-run measurement |
| Admission is client-side, upstream of Ollama's server-side queue | **verified-on-host** — "emit 4, wait, admit 5th" admission-control signature rules out Ollama serializing internally |
| The gating layer is specifically the OpenClaw scheduler (`agents.defaults.maxConcurrent`) vs. an HTTP transport socket-pool cap vs. a CPU-count(=4) limit | **UNVERIFIED** — all three fit the identical log; throttle logged at the `[provider-transport-fetch]` layer, cap == host CPU count, never disentangled (nvhack-k84m). Next step: set `maxConcurrent` to a non-CPU value and re-run; separately re-run unmodified on a different CPU count |
| Gateway `maxConcurrent` default = 4 | **verified-on-host** (measured) / config-name attribution doc-sourced |
| `subagents.maxConcurrent` 8 / `maxChildrenPerAgent` 5 / `maxSpawnDepth` 1 | **UNVERIFIED** — OpenClaw doc schema, never exercised |
| Knobs are recreate-time, not `apply`-time | **verified-on-host** (CLI help text) / that a recreate actually moves the ceiling is **UNVERIFIED** |
| Driven one-per-turn forcing prompt elicits N clean delegations | **verified-offline** — Ollama's raw `tools=[…]` API only; the same prompt FAILED through NemoClaw (nvhack-d0b6) |
| Batch single-message listing is unreliable (negative control) | **verified-offline** (same offline Ollama API) — 1/20 structured |
| Model must not pick `agent_id` itself (reuses one) | **verified-offline** (offline Ollama API) |
| Model never emitted a structured `sessions_spawn` through NemoClaw | **verified-on-host** — 0 subagent sessions, reply treated as text |
| Cause = OpenClaw tool-search compact surface the 1B can't navigate | **verified-on-host** — `tool-search: cataloged 31 tools` + `Unknown tool id` |
| A larger model clears the tool-search floor | **UNVERIFIED** — extrapolated; re-test on the real host model |
| Log line shapes the counters key on (`run … ended`, `model-fetch`, `subagent:<uuid>`) | **verified-on-host** — real capture, corrected from a wrong OCSF guess (nvhack-tel7) |
| Raising `maxConcurrent` at recreate reaches width > 4 | **UNVERIFIED** — never run; hardware ceiling on a GPU-less box also unmeasured |

Full evidence, pasted command output, and the four lesson beads:
`docs/spikes/nvhack-3iy.md`. Offline forcing-prompt methodology and transcripts:
`agents/delegation-probe/PROMPT-VALIDATION.md`. Lesson beads filed from the run:
nvhack-59t6 (knobs need recreate), nvhack-j6ot (1B can't drive `sessions_spawn`),
nvhack-h96z (ceiling attribution — superseded by nvhack-k84m's corrected,
hedged finding above), nvhack-tel7 (real log
shape correction).
