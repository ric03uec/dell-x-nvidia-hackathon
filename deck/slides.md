# SquidWard

## Autonomous defense. Zero data egress.

**Dell x NVIDIA Hackathon 2026**

> An always-on local security agent that detects suspicious agent behavior, investigates it on the GB10, and turns analyst-approved recommendations into enforced OpenShell policy.

**Speaker notes (0:00-0:30)**
Autonomous agents can now take real actions, but every action expands the attack surface. Sending their evidence to a cloud security model creates another risk. SquidWard gives every local business agent a local defender, without exporting the evidence.

---

# Four builders. One local defense loop.

## Team V-X

| Team member | GitHub |
|---|---|
| Shrivara Jois | [@shrivara](https://github.com/shrivara) |
| Brian Cripe | [@briancripe](https://github.com/briancripe) |
| Devashish Meena | [@ric03uec](https://github.com/ric03uec) |
| Rohan Hasabe | [@Hasaber8](https://github.com/Hasaber8) |

**Speaker notes (0:30-0:40)**
We are team V-X: Shrivara, Brian, Devashish Meena, and Rohan. We built SquidWard as a local-first security control plane for enterprise agents.

---

# Cloud security can break the trust boundary it is meant to protect.

## Enterprise security teams face an impossible trade-off

| Send evidence to the cloud | Keep evidence private |
|---|---|
| Sensitive prompts, URLs, actions, and incident context leave the appliance | Existing tools lose the reasoning power needed to correlate agent behavior |
| External inference adds latency and dependency | Static policy misses suspicious sequences across multiple actions |

**SquidWard removes the trade-off:** powerful investigation and enforcement stay on the appliance.

**Speaker notes (0:30-1:10)**
The evidence required to investigate an autonomous agent is often the exact data an enterprise cannot send elsewhere: actions, destinations, prompts, and business context. Traditional rules preserve privacy but miss sequences. Cloud AI can reason across the sequence but crosses the trust boundary.

---

# SquidWard closes the loop from suspicious action to enforced policy on one GB10.

```text
OBSERVE              DETECT               INVESTIGATE
OpenShell + Squid -> Rules + models ----> OpenClaw security agent
                                                |
                                                v
ENFORCE <----------- APPROVE <----------- RECOMMEND
OpenShell policy     Human analyst         Constrained action
```

## The outcome

A suspicious transfer is detected locally, explained locally, approved by a human, and blocked when it is attempted again.

**Speaker notes (1:10-1:55)**
This is not another alert generator. SquidWard creates a closed response loop. It observes agent actions, detects anomalies, uses a dedicated security agent to investigate, proposes one constrained action, waits for human approval, and then changes the policy at the enforcement point.

---

# Every event, model, and inference stays inside the GB10.

```text
+------------------------ DELL GB10 APPLIANCE -------------------------+
|                                                                      |
| Business agent -> OpenShell -> Squid -> FastAPI -> SQLite            |
|                                     |                                |
|                          Live rules + Isolation Forest                |
|                                     |                                |
| SQLite snapshot -> PyTorch sequence model -> Security agent          |
|                                              |                       |
|                                   NemoClaw -> Local model             |
|                                              |                       |
| Dashboard -> Analyst approval -> OpenShell policy -> Audit event      |
|                                                                      |
+---------------------------------------------------------------------+
                         X  NO CLOUD LLM CALLS
```

## Local-first is an architectural boundary, not a deployment option.

- No external inference fallback
- SQLite remains appliance-local
- Customer telemetry never leaves the GB10
- The complete demo can run with outbound access disabled

## Local inference is tuned and observable.

| Runtime evidence | Why it matters |
|---|---|
| vLLM multi-token prediction enabled | Maximizes local decoding throughput |
| `max-num-seqs=3` | Allows three concurrent inference sequences for multiple consumers |
| LiteLLM daily token accounting | Shows token usage for the current day without exporting telemetry |

**Speaker notes (1:55-2:45)**
The entire data and inference path is inside one boundary. vLLM runs with multi-token prediction and max-num-seqs set to three, our max-throughput configuration that lets multiple consumers share local inference. LiteLLM meters today's token usage, giving us an observable live metric without exporting prompts or telemetry. There is no cloud fallback.

---

# Two detection speeds catch both obvious spikes and slow cross-action attacks.

| LIVE: seconds | OFFLINE: deep history |
|---|---|
| Rules and rolling baselines | Safe SQLite snapshot |
| CPU Isolation Forest | GPU PyTorch sequence model |
| Scores each new event | Finds slow and related anomalies |
| Keeps working if the LLM is unavailable | Gives the security agent richer evidence |

## Both paths converge on one always-on security agent.

The agent correlates Squid and OpenShell activity, adds risk context, explains why the sequence matters, and emits a schema-validated finding.

**Speaker notes (2:45-3:25)**
Fast and deep analysis have different jobs. The live path catches an immediate anomaly in seconds and never depends on an LLM. The offline path uses the GPU and historical windows to find slower patterns. Both produce deterministic evidence before the security agent adds its explanation.

---

# The model recommends; a human authorizes; OpenShell enforces.

```text
Finding
  -> { action_type: "deny_destination",
       target: "test-storage.local",
       scope: "business-agent",
       expires_at: "..." }
  -> Analyst: APPROVE / REJECT
  -> Allowlisted policy adapter
  -> OpenShell enforcement
```

## Generative output never becomes an executable command.

- No model-generated shell commands
- No direct model access to the enforcement point
- Only predefined action types pass schema validation
- Every decision and enforcement result is audited

**Speaker notes (3:25-4:05)**
Autonomous defense cannot mean autonomous privilege escalation. The model can only recommend an allowlisted policy action. A human must approve it. The adapter validates it again before OpenShell applies it, and the outcome comes back as an audit event.

---

# One demo proves privacy, control, and prevention with four observable outcomes.

| Proof point | What judges can observe |
|---|---|
| **0 cloud LLM calls** | NemoClaw routes inference to the local GB10 model |
| **1 analyst decision** | The policy cannot apply before explicit approval |
| **2nd attempt blocked** | OpenShell prevents the repeated transfer |
| **100% local audit trail** | Detection, reasoning, approval, and enforcement remain visible locally |

## Business value

SquidWard gives enterprise security teams a private control plane for autonomous agents: shorter investigation cycles, enforceable guardrails, and deployment in environments where cloud AI is not acceptable.

**Speaker notes (4:05-4:35)**
The business value is not an abstract AI score. It is an observable reduction in exposure and response friction. One local appliance detects the event, gives an analyst the evidence needed to decide, and prevents the repeat attempt without exporting customer data.

---

# Now watch the same transfer go from allowed to blocked.

## Live demo

1. **Normal activity:** the business agent works inside OpenShell.
2. **Suspicious sequence:** the agent stages data and uploads to a new destination.
3. **Local response:** SquidWard detects, investigates, and recommends a constrained policy.
4. **Human control:** the analyst approves the recommendation.
5. **Enforcement:** the repeated transfer is blocked and audited.

### Watch these three surfaces

`Incident timeline`  ->  `Policy review`  ->  `Enforcement audit`

**Speaker notes (4:35-5:00)**
The first transfer gives us evidence; the second proves prevention. Watch the incident timeline for the correlated actions, the policy review for the human gate, and the enforcement audit for the blocked result. Then switch to the live demo.

---

# Autonomous agents deserve a local line of defense.

## SquidWard

**Detect locally. Decide safely. Enforce immediately.**

| Local-first + always-on | Business value | Demo + pitch | Technical execution |
|---|---|---|---|
| Full GB10 execution | Private agent control plane | Complete detect-to-block story | Layered, schema-validated, auditable |

**Speaker notes (post-demo, 0:20)**
SquidWard makes local AI operationally safe: the evidence stays private, the security agent stays on, the human stays in control, and policy is enforced where the agent acts.
