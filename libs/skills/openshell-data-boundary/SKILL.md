---
name: openshell-data-boundary
description: Stop one agent from reading what another agent can, using OpenShell's filesystem_policy (Landlock). Use when designing an agent pair or fleet that must hold different filesystem views over shared data, when deciding whether one sandbox or two sandboxes is required, when setting include_workdir, or when a demo needs to show a denial happening. Triggers on "per-agent filesystem access", "data boundary between agents", "can agent A read what agent B reads", "Landlock", "filesystem_policy", "include_workdir", "show the denial", "restrict one agent's read access".
---

# Stopping agent A from reading what agent B can

## The straight answer

**One sandbox cannot do it. Two sandboxes can, but the setup cost is unmeasured
and the denial you'd show in a demo is probably invisible.** Read the caveat
below before trusting any of this on a different host.

- Inside one OpenShell sandbox, per-agent `tools.allow` only gates *whether*
  an agent may call `read`/`write`/`exec` at all — it has no path-scoped
  form. Both agents in one sandbox inherit the same Landlock ruleset, so the
  best a single sandbox expresses is "has read" vs "has no read", never
  "agent A sees `public/` only; agent B sees `public/` + `restricted/`".
- Real path-scoped asymmetry — agent A genuinely cannot open a path agent B
  can — requires **two sandboxes**, each with its own `filesystem_policy`.
  This is kernel-enforced (Landlock), not prompt-enforced: it does not
  depend on what the agent tries or how it phrases the request. **But it
  only covers the direct read path.** Adversarial probing (nvhack-zy9.4) shows
  a shared writable dir (`/tmp` / `/sandbox/scratch`, granted to both candidate
  sandboxes) leaks restricted bytes across the boundary, and a hardlink into
  the granted subtree reads through — see
  ["The boundary only covers the direct read path"](#the-boundary-only-covers-the-direct-read-path--side-channels-defeat-it).
- The cost of standing up two sandboxes over one shared tree was **not
  measured** on this repo's trial host, because the multi-sandbox framework
  gap (nvhack-497.3) and the absent NemoClaw/OpenShell runtime (nvhack-jfx)
  both blocked it. Budget time to actually stand up two sandboxes before you
  promise this in a demo plan.
- A denial (an agent hitting the boundary) is, at the kernel layer on the
  trial host, a **bare `EACCES`** — nothing an unprivileged process or a live
  demo can point at as a discrete, timestamped, legible event. See
  ["If your demo's climax is a denial"](#if-your-demos-climax-is-a-denial-you-cannot-show)
  before you build a demo around watching one happen.

## Read this before trusting anything below

Every claim in this skill was established on:

```
$ uname -a
Linux factory-orca 6.12.94+deb13-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.12.94-1 (2026-06-20) x86_64 GNU/Linux
```

**x86_64, kernel 6.12.94.** Landlock is a kernel LSM; both its enforcement
and — critically — its *logging* behavior are kernel-version-dependent.

**Before you build on this on a GB10 (aarch64, unknown kernel):**

```sh
uname -r
```

If the GB10 reports **>= 6.15**, the denial-visibility verdict in this doc
(NO-GO) may flip to GO — Landlock gained audit-log emission in 6.15. Do not
assume the NO-GO transfers, and do not assume it's already fixed. Re-run the
probe (see [Reproduce](#reproduce)) on the actual host and update this
verdict before you rely on it.

**A second, load-bearing caveat: NemoClaw/OpenShell was never available to
test against.** Everything below that says `verified-on-host` was verified
by exercising Landlock *directly* via the same three syscalls
(`landlock_create_ruleset` / `landlock_add_rule` / `landlock_restrict_self`)
that OpenShell's `filesystem_policy` compiles down to — not by running an
actual `nemoclaw` agent. Claims about the YAML→Landlock wiring inside
NemoClaw, the exact `/sandbox/...` path mapping, and NemoClaw's own userspace
log surface are marked `UNVERIFIED` and stay that way until a real runtime is
available. Do not let a kernel-layer `verified-on-host` tag bleed into a
claim about NemoClaw's actual behavior — they are not the same claim.

## Design (a): one sandbox, two agents, per-agent `tools.allow` — NO-GO for path asymmetry

**Verdict: NO-GO for genuine path-scoped asymmetry. Provenance is split, and
was corrected in the adversarial review (nvhack-zy9.4): the *kernel mechanism*
is `verified-on-host`; the *NemoClaw agent→ruleset mapping* is `UNVERIFIED`.**

`tools.allow` / `tools.deny` draw from `TOOL_VERBS = {read, write, exec}` — a
verb allowlist, not a path scope (**schema-derived**). `filesystem_policy` (the
Landlock half) is a property of the *sandbox*, applied once at
`landlock_restrict_self`, and a Landlock ruleset is inherited by the whole
process tree under that sandbox. That inheritance is now **`verified-on-host`**:
`attack_probe.py` shows a forked child that never calls `restrict_self` itself is
still denied restricted (`[INHERIT] child (no own restrict) restricted -> DENIED
EACCES`). (The original `landlock_probe.py` did **not** demonstrate this — it was
mechanism-reasoning tagged as verified until zy9.4 actually ran it.) What stays
`UNVERIFIED` is that NemoClaw in fact runs *both agents inside one sandbox / one
restrict_self scope* rather than resolving per-agent tool calls through distinct
rulesets — that is NemoClaw behavior, and the runtime was absent.
Two agents running inside one sandbox therefore share one identical ruleset.
The most you can express with per-agent `tools.allow` is "has the read tool"
vs "has none" — never "agent A reads `public/` only; agent B reads both".

If you only need a binary split ("this agent may never read anything" vs
"this agent may read"), one sandbox is enough and is cheaper. The moment you
need two agents to see *different subsets* of the same tree, one sandbox
cannot express it — move to design (b).

## Design (b): two sandboxes, asymmetric `filesystem_policy` — mechanism GO, cost UNMEASURED

**Verdict on the mechanism: GO. `verified-on-host` — a direct Landlock probe
demonstrated real kernel-enforced asymmetry:**

```
$ python3 agents/asym-pair/probes/landlock_probe.py corpus
[public   ] .../corpus/public/contract-acme-msa.txt
           -> READ OK
[restricted] .../corpus/restricted/escalation-approval-thresholds.txt
           -> DENIED | errno=13 (EACCES) Permission denied
```

Give each sandbox its own `filesystem_policy.read_only`: a "reader" sandbox
that lists only `public/`, and an "escalator" sandbox that lists both
`public/` and `restricted/`, over the same underlying tree. The restricted
read fails at the kernel boundary regardless of how the agent phrases the
request, its prompt, or its model — this is the genuine article, not a
prompt-level convention.

**Verdict on affordability: UNMEASURED / BLOCKED — not a soft "we didn't get
to it", a real gap.** Two things blocked measuring the setup cost on the
trial host:

1. Multi-sandbox-per-agent-project support is still an open framework gap
   (nvhack-497.3) — outside this skill's territory, but you need it landed
   (or a manual two-sandbox stand-up) before you can even start the clock.
2. NemoClaw/OpenShell's own runtime was absent from the trial host
   (nvhack-jfx), so even a manual two-sandbox stand-up against real
   `nemoclaw`/`openshell` tooling was impossible.

The original go/no-go bar for this pattern was "two-sandbox setup cost under
20 minutes." That bar has **not been cleared or missed — it has never been
measured.** Do not carry forward an assumption either way. Measure it the
moment either the framework gap lands or a real NemoClaw host is available,
before you commit demo time to this pattern.

## The boundary only covers the direct read path — side channels DEFEAT it

**Verdict: the Landlock read boundary is real, but it is not the whole
containment. Adversarial probing (nvhack-zy9.4,
`agents/asym-pair/probes/attack_probe.py`) found two ways restricted bytes
reach the "reader" side that the direct-read probe never tested.** Do not read
"reader genuinely cannot reach restricted data" as airtight — it is airtight
only for a *direct open of a `restricted/` path*.

- **Shared writable dir = exfiltration channel. `verified-on-host` (kernel
  layer); shared-mount assumption `UNVERIFIED`.** Both candidate design-(b)
  policies (`policy.reader.yaml` and `policy.escalator.yaml`) grant
  `read_write: [/tmp, /sandbox/scratch]`. If those are backed by the same host
  mount across the two sandboxes, the "escalator" (which may read `restricted/`)
  can copy restricted bytes there and the "reader" reads them back — the read
  asymmetry is fully defeated without the reader ever touching `restricted/`:

  ```
  $ python3 agents/asym-pair/probes/attack_probe.py corpus
  [C: reader reads escalator's /tmp drop   ] READ OK == SECRET LEAKED
  ```

  Whether OpenShell shares those mounts between sandboxes is `UNVERIFIED`
  (runtime absent) — but the policy files as written contain the channel.
  **If two sandboxes must not share data, they must not share a writable mount.**
  Give each sandbox its own scratch/tmp, or treat any shared `read_write` path as
  a hole as large as `include_workdir`.

- **Landlock is PATH-based, not inode-based → a hardlink into the granted
  subtree reads through. `verified-on-host`.** A hardlink placed inside the
  granted `public/` dir whose inode is a `restricted/` file is readable, with no
  error and no log (`[B: hardlink in public (inode=restricted)] READ OK`). The
  reader's own `read_only` scope stops it planting one at runtime, so this is a
  **provisioning-time landmine** (a dedup pass, `cp -l`, `rsync --hard-links`, or
  a careless author), not a unilateral runtime break — but it collapses the
  boundary just as silently as `include_workdir`. Verify no hardlink crosses from
  a granted dir into restricted content when you stage the corpus.

- **Symlinks are safe. `verified-on-host`.** A symlink inside `public/` pointing
  at `restricted/` is resolved by Landlock to its real path and DENIED
  (`[A: symlink public->restricted] DENIED errno=13`). Symlink traversal does not
  defeat the boundary; hardlinks and shared writable dirs do.

## The `include_workdir` trap — CONFIRMED silent hole

**Verdict: CONFIRMED at the Landlock layer. `verified-on-host`.**

Landlock path-beneath rules grant a whole subtree. If any ancestor directory
of your restricted path is also granted — the workdir being the obvious one
— that grant silently re-includes everything beneath it, restricted content
included:

```
$ python3 agents/asym-pair/probes/landlock_probe.py corpus --include-workdir
[restricted] .../corpus/restricted/escalation-approval-thresholds.txt
           -> READ OK          <-- restricted is back; the boundary is gone
```

**No error. No log. The boundary just silently stops existing.**
`include_workdir: false` in `policy.yaml` is therefore not a stylistic
default — it is load-bearing. Treat it, and any ancestor directory you add
to `read_only`/`read_write`, as a landmine: adding `/sandbox/corpus` (the
parent of both `public/` and `restricted/`) to a "reader" sandbox's allowlist
defeats the whole design just as effectively as `include_workdir: true`
would.

Caveat: confirmed at the kernel/Landlock layer directly. The exact mapping
from NemoClaw's `include_workdir` flag to a Landlock path-beneath grant is
`UNVERIFIED` — inferred from the mechanism, not observed via a real
`include_workdir: true` run against `nemoclaw`, because the runtime was
absent.

## Is a denial visible? NO-GO at the kernel layer on this host's kernel

**Verdict: NO-GO. `verified-on-host` (kernel layer only). This is the single
most important finding for anyone planning a demo around this pattern.**

From the restricted process's own point of view, a Landlock denial is
*only* an `open()` failure:

```
[restricted] .../corpus/restricted/escalation-approval-thresholds.txt
           -> DENIED | errno=13 (EACCES) Permission denied
```

That is exactly the failure shape an agent will narrate around as "I
couldn't find/open that file" — not a discrete, timestamped, legible
security event. There is no out-of-process record an unprivileged agent (or
a live demo) can point at on this kernel:

```
# unprivileged (uid=995, empty CapEff) — the vantage an agent actually runs from
$ python3 -c "import os; os.open('/dev/kmsg', os.O_RDONLY)"
-> errno=1 Operation not permitted
$ journalctl -k -n 20
No journal files were opened due to insufficient permissions.
$ ls /var/log/audit
ls: cannot access '/var/log/audit': No such file or directory
```

**Why (doc-sourced, not host-verifiable here):** Landlock audit-log emission
(`LANDLOCK_RESTRICT_SELF_LOG_*`) landed in **Linux 6.15** — an upstream-kernel
fact about a kernel *not present on this host*, so it is documentation-sourced,
not `verified-on-host`, and the "GB10 >= 6.15 may flip to GO" advice below
inherits that caveat. This host runs 6.12.94, which predates it — and that part
*is* observed: Landlock emits nothing to the audit subsystem here, regardless of
`CONFIG_AUDIT=y`.
There is no kernel-side legible event to surface even to root on this
kernel.

**The one escape hatch — and it is `UNVERIFIED`:** visibility could still
come from NemoClaw/OpenShell's own userspace wrapper, if it logs a failed
tool call (the `nemoclaw <sandbox> logs --follow` surface) with a legible
reason rather than passing the bare `EACCES` straight through. Whether it
does this is exactly what the trial host could not tell us, because the
runtime (nvhack-jfx) was never available to test. Do not assume either
answer.

### If your demo's climax is a denial you cannot show

If you're planning a demo whose payoff is "watch agent A get denied and see
it happen live," do this **before** you commit to that plan, not during
rehearsal:

1. **Check the kernel first**: `uname -r` on your actual host. If it's
   `< 6.15`, assume the kernel gives you nothing to show, same as here.
2. **Independently verify NemoClaw's own log surface** on your actual host —
   run a real denial through a real sandbox and watch `nemoclaw <sandbox>
   logs --follow` (or whatever the current log command is) yourself. Do not
   promise a live-denial climax on the strength of this doc alone; this doc
   only clears the kernel layer, and NemoClaw's userspace layer is
   unverified everywhere in this trial.
3. **If NemoClaw doesn't surface it either**, don't build the demo around
   *watching* the denial happen. Instead:
   - Show the **before/after contrast**: read succeeds from the "escalator"
     sandbox, the identical read fails from the "reader" sandbox — the
     boundary is real even if the moment of denial isn't legible.
   - Narrate the boundary as a **design guarantee** ("this agent's sandbox
     was never given this path — it's not a runtime check that can fail
     open, it's absent from what the process can even name"), not as a
     live security event you caught on camera.
   - If you need an actual timestamped log line for the demo, put the
     logging in your own application layer (log the read attempt and its
     outcome from inside your own tool wrapper) rather than depending on
     Landlock or NemoClaw to supply one — this repo's trial did not verify
     that either of those two layers will do it for you.

A NO-GO here does not mean the isolation is worthless — the filesystem
boundary is still real and kernel-enforced (see design (b) above). It means
"a denial happening" is not, by itself, a demo-safe event on this kernel.

## The static/dynamic split — decide before the first `onboard`

`filesystem_policy` (the Landlock half of `policy.yaml`) is **static**: it
is compiled and applied once, at sandbox creation, via
`landlock_restrict_self`, and **cannot be loosened afterward**. This is
`verified-on-host` (nvhack-zy9.4): a second `restrict_self` that tries to
re-grant `restricted/` after a `public/`-only restrict is a no-op —
`[MONOTONIC] after 2nd restrict_self trying to re-grant restricted -> DENIED
EACCES`. (Like the inheritance claim above, the original probe only *asserted*
this from the kernel guarantee; zy9.4 demonstrated it.) `network_policies`
is different: it's the **dynamic** half and can be hot-reloaded on a running
sandbox.

Practical consequence: **the filesystem boundary decision is made before you
run the first `onboard`**, not iterated on later like network policy. If you
under-scope `read_only` at creation time, the fix is a new sandbox, not a
policy update. Decide the asymmetry design (one sandbox vs two, and exactly
which paths each sandbox's `filesystem_policy` lists) up front, and budget
for the fact that discovering you were wrong costs a rebuild, not a
reload.

## `process.run_as_user` / `run_as_group` — UNVERIFIED, not exercised

Both candidate policies authored for this trial (`policy.yaml` for design
(a), and `policy.reader.yaml` / `policy.escalator.yaml` for design (b)) set
`process.run_as_user: sandbox` and `process.run_as_group: sandbox`
identically — this value was never varied between the "reader" and
"escalator" sandboxes, and no host run (the runtime was absent) exercised
what happens if it were. **Nothing was actually tested about how
`process.run_as_user/group` interacts with `filesystem_policy`** — whether
per-sandbox UID/GID adds a second, POSIX-permission-based boundary on top of
the Landlock one, whether it matters at all when both sandboxes already have
disjoint Landlock rulesets, or whether it's load-bearing for some other
reason. Treat any claim about this interaction as `UNVERIFIED` until someone
actually varies it on a live NemoClaw host and observes the result — don't
invent behavior here.

## Deploying a policy: the `/sandbox` path mapping — inferred, not verified

**Bead:** nvhack-m26 (from the build-framework-gaps epic, nvhack-av3m).
**Provenance:** read directly from `scripts/deploy.sh` and
`agents/hello-agent/policy.yaml`; the host-side mapping itself is
`UNVERIFIED` — no host run confirmed it (the runtime absence, nvhack-jfx,
blocks this the same way it blocks everything else in this doc).

`scripts/deploy.sh` (`--source` mode, the default) does exactly three things
on the host, in order: `rsync -az --delete` the agent folder to
`~/agents/<agent>/` on the host (not `/sandbox`, not any OpenShell-internal
path), then `nemoclaw '$sandbox' agents apply -f agents.yaml --yes` and
`openshell policy set '$sandbox' --policy policy.yaml --wait`, both run from
inside that same rsynced folder. Meanwhile `filesystem_policy.read_write` in
this repo's policy files (e.g. `/sandbox`, `/tmp`) names paths *as seen from
inside the sandbox's own mount namespace* — nothing in `deploy.sh` or
`policy.yaml`'s comments states how the rsync destination on the host
becomes `/sandbox` inside the sandbox.

**Inferred (not asserted as fact):** `/sandbox` is most plausibly a
bind-mount of the rsynced project directory into the sandbox's mount
namespace, set up by `nemoclaw agents apply` / `openshell policy set` (or an
earlier `onboard`) rather than by `deploy.sh` itself. **What would confirm
or falsify this:** write a marker file into the rsynced host directory
before `agents apply`, then `nemoclaw <sandbox> exec -- ls /sandbox` and
check whether the marker is visible there. Until that run happens, treat any
`/sandbox/...` path in a `filesystem_policy` as an unverified placeholder,
not a confirmed mount — `openshell policy set` could silently scope the
wrong directory, or nothing at all, if this inference is wrong.

## agentkit's local validator: coverage and known blind spots

**Beads:** nvhack-8tu, nvhack-24w (from nvhack-av3m). **Provenance:** read
directly from `agentkit.manifest.validate_agents` /
`validate_policy()` (`libs/agentkit/src/agentkit/manifest.py`).

`agentkit-validate` (`just a <agent> check`) is a **shape**, not a
**semantics**, checker — passing it is not evidence a policy is correct
against real NemoClaw/OpenShell behavior:

- `tools.allow`/`tools.deny` are checked as lists drawn from
  `TOOL_VERBS = {read, write, exec}` — but unknown keys inside a `tools:`
  block are silently accepted (only `allow`/`deny` are inspected). A typo'd
  or invented field like `tools.allow_paths` would pass validation without
  meaning anything to real NemoClaw.
- `filesystem_policy.read_only`/`.read_write`, if present, are checked as
  lists. `filesystem_policy.include_workdir` is now type-checked (must be a
  `bool` if present — fixed as part of nvhack-8tu, covered by
  `test_reports_non_bool_include_workdir`/`test_accepts_bool_include_workdir`
  in `libs/agentkit/tests/test_manifest.py`).
- The `landlock` block (e.g. `landlock.compatibility`) and the `process`
  block (e.g. `process.run_as_user`/`run_as_group`) are **not validated at
  all** — present, absent, misspelled, or wrong-typed, `agentkit-validate`
  reports "ok" regardless. This is a deliberate, documented gap rather than
  an oversight to guess-fix: neither block's accepted value set is
  confirmable from this repo alone (is `landlock.compatibility` an enum? is
  `process.run_as_user` a uid, a host username that must exist, case
  sensitive?) — writing validation logic against a schema you can't confirm
  is the same trap the module's own docstring warns against. Since
  `filesystem_policy`/`landlock`/`process` are all static (locked at sandbox
  creation, see above), a bad value here is not cheaply fixable after the
  fact — sanity-check these two blocks by hand before a real
  `openshell policy set` against a host; a green `agentkit-validate` does
  not cover you.

## Reproduce

The probe used for every `verified-on-host` claim above is a stdlib-only,
unprivileged, dependency-free ctypes driver for the same three syscalls
OpenShell's `filesystem_policy` compiles to (x86_64 syscall numbers — port
the numbers before running on aarch64):

```sh
python3 agents/asym-pair/probes/landlock_probe.py agents/asym-pair/corpus
python3 agents/asym-pair/probes/landlock_probe.py agents/asym-pair/corpus --include-workdir
# adversarial companion (nvhack-zy9.4): symlink / hardlink / shared-/tmp attacks,
# plus the ruleset-inheritance and monotonicity demonstrations:
python3 agents/asym-pair/probes/attack_probe.py agents/asym-pair/corpus
```

Re-run them (after checking `uname -r` and porting syscall numbers for
aarch64) on the actual GB10 before trusting any verdict in this doc there.
The candidate policy files for both designs live in
`agents/asym-pair/policy.yaml` (design a) and
`agents/asym-pair/designs/two-sandboxes/policy.{reader,escalator}.yaml`
(design b).

## Provenance summary

| Claim | Status |
|---|---|
| Design (a) NO-GO — kernel mechanism (ruleset inherited across process tree) | `verified-on-host` (kernel 6.12.94, x86_64) — demonstrated by `attack_probe.py`, nvhack-zy9.4 |
| Design (a) NO-GO — NemoClaw runs both agents in one restrict_self scope | `UNVERIFIED` — NemoClaw behavior, runtime absent |
| Design (b) path asymmetry — direct-read mechanism | `verified-on-host` (kernel 6.12.94, x86_64) |
| Design (b) containment complete (no side channel) | **REFUTED** — shared `/tmp`/`/sandbox/scratch` leaks (nvhack-zy9.4); shared-mount assumption `UNVERIFIED` |
| Hardlink into granted subtree reads restricted content | `verified-on-host` (Landlock is path-based) — nvhack-zy9.4 |
| Symlink into restricted from granted subtree | `verified-on-host` — DENIED, boundary holds — nvhack-zy9.4 |
| Design (b) two-sandbox setup cost < 20 min | `UNVERIFIED` / unmeasured — blocked on nvhack-497.3 + nvhack-jfx |
| Denial visible at kernel layer | `verified-on-host`, verdict **NO-GO** (kernel 6.12.94, x86_64) |
| Denial visible via NemoClaw's own log surface | `UNVERIFIED` — runtime absent on trial host |
| Landlock audit logging landed in 6.15 (basis for GB10 flip) | **doc-sourced**, not host-verifiable here |
| `include_workdir: true` silently re-grants | `verified-on-host` at the Landlock layer; NemoClaw's flag→grant mapping is `UNVERIFIED` |
| `filesystem_policy` is static, cannot loosen post-creation | `verified-on-host` — monotonicity demonstrated by `attack_probe.py`, nvhack-zy9.4 |
| `process.run_as_user/group` interaction with `filesystem_policy` | `UNVERIFIED` — never varied, never tested |

Full evidence, pasted command output, and the wrong/held predictions:
`docs/spikes/nvhack-xf1.md`. Adversarial re-review (attacks, side channels,
provenance corrections): `docs/spikes/nvhack-xf1-adversarial-review.md`.
Advance predictions (written before the host run) and their results:
`agents/asym-pair/PREDICTIONS.md`.
