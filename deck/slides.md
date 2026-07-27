# SquidWard

## Enforce agentic traffic at AI speed.

**Dell x NVIDIA Hackathon 2026**

> AI agents connect to dynamic endpoints faster than static firewall rules can keep up. SquidWard detects behavioral risk locally and turns it into analyst-approved agent policy.

**Speaker notes (0:00-0:30)**
Traditional IT firewalls were built for humans and predictable traffic. AI agents act continuously, discover tools, and connect to dynamic endpoints. Policy maintained at human speed becomes stale before the next action. SquidWard closes that speed gap without removing human control.

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

# Traditional firewalls were built for humans and static traffic.

## Enterprise security teams now face a speed mismatch

| Human-speed firewall policy | AI-speed agent traffic |
|---|---|
| Static destinations and manual rule changes | Autonomous actions and newly discovered tools |
| Ticket-driven response | Dynamic endpoints and continuous change |

**SquidWard closes the speed gap:** it turns live agent behavior into safe, enforceable policy updates.

**Speaker notes (0:30-1:10)**
The firewall is not obsolete; its operating model is. Security teams cannot manually anticipate every destination an agent may discover or update rules between machine-speed actions. SquidWard continuously observes behavior, detects risk, and prepares the policy response at AI speed.

---

# Pre-AI IT Systems

```text
Internal systems  ->  Firewall  ->  Internet
Users, laptops,       Static        External
and applications      rules         destinations
```

**Speaker notes**
Before AI agents, enterprise traffic was comparatively predictable. Internal users and applications reached known internet destinations through firewalls maintained with static rules and human-speed updates.

---

# Post-AI: SquidWard keeps the firewall current.

```text
                  LIVE TRAFFIC

Internal systems -> Firewall / Squid Proxy -> Internet
Users, laptops,       reads current rules     allowed traffic
and agents                    |
                              v
IT operators ---> +---------- SQUIDWARD / SECURE GB10 ----------+ <--> Public CVE DB
                  |                                               |     scheduled scan
                  | SquidWard agent -> API -> GB10 + local LLM    |
                  |                         |                     |
                  |                    Rules database              |
                  |                                               |
                  | Rules, questions, and inference stay inside.  |
                  +-----------------------------------------------+
```

## The current system has two simple paths.

- **Traffic:** internal users, laptops, and agents reach the internet through the existing firewall. Squid Proxy is the current implementation.
- **Policy:** IT operators and scheduled public CVE scans feed SquidWard. Its agent, API, local LLM, and rules database remain inside the secure GB10 boundary.
- **Expansion:** additional firewall adapters can read from the same private rules database.

**Speaker notes (1:55-2:45)**
The top line is the network path enterprises already have: internal users, laptops, and agents send traffic through a firewall to the internet. Squid Proxy is our current firewall, with room for other adapters. Below it, SquidWard keeps policy current. IT operators work through the SquidWard agent, the agent uses the API and local GB10 model, and scheduled scans bring in public CVE intelligence. The local model and rules database both remain inside the secure boundary. The firewall reads the resulting rules without changing the traffic path.

---

# SquidWard turns agent behavior into enforceable policy on one GB10.

```text
OBSERVE              DETECT               INVESTIGATE
OpenShell + Squid -> Rules + models ----> OpenClaw security agent
                                                |
                                                v
ENFORCE <----------- APPROVE <----------- RECOMMEND
Agent policy         Human analyst         Constrained action
```

## The outcome

AI-speed detection and policy recommendation; human-approved enforcement before the next attempt.

**Speaker notes (1:10-1:55)**
SquidWard is the adaptive policy layer between autonomous agents and the firewall. It observes actions, detects anomalies, investigates locally, and proposes a constrained policy update at machine speed. The analyst retains final authority, and the agent enforces the approved change.

---

# Fast and slow detection catch different threats.

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

# The model recommends; a human authorizes; the agent enforces.

```text
Finding
  -> { action_type: "deny_destination",
       target: "test-storage.local",
       scope: "business-agent",
       expires_at: "..." }
  -> Analyst: APPROVE / REJECT
  -> Allowlisted policy adapter
  -> Agent enforcement
```

## Generative output never becomes an executable command.

- No model-generated shell commands
- No direct model access to the enforcement point
- Only predefined action types pass schema validation
- Every decision and enforcement result is audited

**Speaker notes (3:25-4:05)**
Autonomous defense cannot mean autonomous privilege escalation. The model can only recommend an allowlisted policy action. A human must approve it. The adapter validates it again before the agent applies it, and the outcome comes back as an audit event.

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

# Agentic traffic needs a firewall that can keep up.

## SquidWard

**Observe continuously. Adapt at AI speed. Enforce with control.**

| Local-first + always-on | Business value | Demo + pitch | Technical execution |
|---|---|---|---|
| Full GB10 execution | Private agent control plane | Complete detect-to-block story | Layered, schema-validated, auditable |

**Speaker notes (post-demo, 0:20)**
SquidWard upgrades the firewall operating model for the agentic era: continuous observation, AI-speed detection and policy recommendation, human authority, and enforcement where the agent acts.
