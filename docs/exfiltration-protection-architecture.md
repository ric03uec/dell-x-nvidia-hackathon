# Squid-Centered Local Exfiltration Protection

**Hackathon architecture with a path to production**

**Target:** Dell system with NVIDIA GB10

**Core rule:** Customer traffic metadata, events, models, and analysis stay on the appliance.

## 1. What we are building

For the hackathon, **Squid is the main collection and enforcement point**. Test clients use Squid as an explicit web proxy. A local collector streams Squid access logs into a fast anomaly detector. A more powerful GPU model analyzes the complete history offline each night and proposes improvements to the live detector.

Additional local context comes from:

- **CVE records and security advisories:** MITRE CVE, NIST NVD, CISA KEV, and vendor advisories.
- **Authorized Nmap discovery:** identifies test assets and services.
- **Analyst feedback:** marks alerts as normal or malicious.

CVEs add asset-risk context but do not directly prove exfiltration.

## 2. Hackathon MVP architecture

```mermaid
flowchart LR
    CLIENT[Test Clients]
    INTERNET[Test Internet Destination]

    subgraph Appliance[Local GB10 Appliance]
        SQUID[Squid Proxy] --> LOG[Squid access.log]
        LOG -->|Live tail| COLLECTOR[Log Collector]
        CVE[CVE + CISA KEV Snapshot] --> ENRICH
        NMAP[Authorized Nmap Scan] --> ENRICH

        COLLECTOR --> API[FastAPI Ingestion]
        API --> ENRICH[Normalize + Enrich]
        ENRICH --> DB[(PostgreSQL)]

        subgraph Online[Online / Live - Seconds]
            FEATURES[Squid Features]
            RULES[Rules + Rolling Baselines]
            SMALL[Small Isolation Forest]
            SCORE[Risk Score]
        end

        ENRICH --> FEATURES
        FEATURES --> RULES
        FEATURES --> SMALL
        RULES --> SCORE
        SMALL --> SCORE
        SCORE --> DB
        SCORE --> UI[Streamlit Dashboard]
        SCORE -.-> LLM[Local LLM Explanation] --> UI

        subgraph Offline[Offline / Nightly - GPU]
            SNAPSHOT[Historical Snapshot]
            LARGE[Powerful Offline Model]
            EVAL[Replay + Evaluate]
            APPROVE{Analyst Approval}
        end

        DB -->|Nightly| SNAPSHOT --> LARGE --> EVAL --> APPROVE
        APPROVE -->|Thresholds / new small model| SMALL
        APPROVE -->|Deeper incidents| UI
        UI -->|Labels| DB

        POLICY[Local Denylist / ACL Policy]
        UI -->|Approved policy only| POLICY
        POLICY -.->|Future requests| SQUID
    end

    CLIENT -->|Explicit proxy| SQUID
    SQUID --> INTERNET
```

**Online** means fast, local event-time scoring. **Offline** means local batch analysis, normally run nightly. Neither means cloud processing.

### Important timing boundary

Squid normally writes an access-log record during or after a request. Therefore:

- The log stream can provide near-live detection and alerting.
- It cannot retroactively stop the first completed transfer.
- An approved denylist or Squid external ACL can block later requests before they start.
- The LLM and powerful offline model must never run inside Squid's request path.

For the hackathon, start in **observe mode**. Demonstrate that an approved policy blocks a repeated request to the same destination.

## 3. Minimal components

Use one Docker Compose deployment with six services:

| Component | Hackathon choice | Responsibility |
|---|---|---|
| Proxy | Squid | Routes test web traffic and writes access logs |
| API | FastAPI | Receives structured Squid events |
| Worker/collector | Python | Tails logs, normalizes events, scans, scores, and runs nightly jobs |
| Database | PostgreSQL | Events, baselines, assets, CVEs, labels, and model versions |
| Dashboard | Streamlit | Alerts, explanations, labels, policy, and model approval |
| Model service | PyTorch plus Ollama/llama.cpp | Powerful offline model and local LLM |

PostgreSQL can also hold MVP jobs. Do not add Kafka, Kubernetes, a separate feature store, or production endpoint agents during the hackathon.

## 4. Squid live ingestion

### 4.1 Explicit proxy

Configure only the hackathon test clients to use the GB10 appliance as an explicit proxy, for example:

```text
Proxy host: gb10.local
Proxy port: 3128
```

Do not transparently redirect a business network during the demo.

### 4.2 Structured access log

Add a custom log format to `squid.conf`:

```conf
logformat exfilguard ts=%ts.%03tu src=%>a user=%un method=%rm uri=%ru status=%>Hs req_bytes=%>st resp_bytes=%<st mime=%mt result=%Ss
access_log /var/log/squid/access.log exfilguard

# Reduces demo latency; revisit for production throughput.
buffered_logs off
```

Validate and reload the configuration:

```bash
squid -k parse
squid -k reconfigure
```

Field availability and byte accounting can differ by Squid version and HTTPS mode. Verify `req_bytes` and `resp_bytes` with known test transfers before relying on them.

### 4.3 Collector

The worker tails `/var/log/squid/access.log` continuously and posts new records to FastAPI.

For the first demo, `tail -F` is acceptable. The collector should still:

- Remember its file position when possible.
- Handle log rotation.
- Buffer briefly if FastAPI is unavailable.
- Batch events under high volume.
- Avoid logging credentials or sensitive URL query parameters.

Vector or Fluent Bit can replace the Python tailer later without changing the API.

### 4.4 Normalized event

```json
{
  "timestamp": "2026-03-15T22:15:00Z",
  "source_type": "squid",
  "user": "alice",
  "source_ip": "10.0.0.17",
  "device": "laptop-17",
  "method": "POST",
  "destination": "unknown-storage.example",
  "request_bytes": 25000000,
  "response_bytes": 842,
  "status": 200,
  "outside_work_hours": true,
  "asset_has_kev": true
}
```

## 5. HTTPS limitation

Without TLS interception, Squid usually sees the HTTPS `CONNECT` destination but not the encrypted request path, filename, content, or reliable per-request details inside the tunnel.

The MVP will **not** enable TLS interception. It will use:

- Destination and connection metadata from normal HTTPS proxy traffic.
- A controlled HTTP test upload with non-sensitive generated data when request-size visibility is required.
- Simulated file-sensitivity metadata if that feature is shown in the dashboard.

A production endpoint agent or explicitly authorized ICAP/TLS inspection can add file-level context later. The architecture must not claim that Squid alone identifies the uploaded file inside ordinary HTTPS traffic.

## 6. Live detection model

The live path uses three simple signals:

1. Deterministic rules.
2. Per-user, source-IP, and destination rolling baselines.
3. A small Isolation Forest model running on CPU.

Initial Squid-derived features:

- Request method, especially `POST`, `PUT`, and `PATCH`
- `log(request_bytes + 1)` when available
- Destination new to the user or organization
- Transfer size relative to the user's baseline
- Requests and unique destinations in the last hour
- Activity outside normal working hours
- Squid allow/deny/result status
- Source asset matched to a CVE or CISA KEV entry

Example decision:

```text
Risk: 86/100
- New destination: +20
- 8x normal request size: +25
- POST outside working hours: +15
- Known-exploited vulnerability on source asset: +10
- Isolation Forest anomaly: +16
```

For the MVP, a model anomaly creates an alert. Blocking requires an analyst-approved destination or policy.

## 7. Squid enforcement

### MVP enforcement

Maintain a local file of approved denied domains:

```conf
acl exfil_denied dstdomain "/etc/squid/exfil-denied-domains.txt"
http_access deny exfil_denied
```

Place this deny rule before the general `http_access allow` rule. The dashboard adds a destination only after analyst approval. The worker then safely validates and reloads Squid. This demonstrates prevention on the next request without putting ML in the request path.

### Eventual live policy check

A production version can use a fast local `external_acl_type` helper:

```conf
external_acl_type exfil_policy ttl=10 negative_ttl=2 %SRC %LOGIN %DST /opt/exfil/check-policy
acl exfil_denied_dynamic external exfil_policy
http_access deny exfil_denied_dynamic
```

The helper may check only cached, deterministic policy such as a denied destination, restricted user, or isolated device. It must have strict timeouts and a defined fail-open/fail-closed policy. It must not call the LLM or GPU model.

## 8. Powerful offline model on the GB10

Each night, the GB10 runs a more powerful model over the local Squid history. For the hackathon, use a **PyTorch autoencoder** over time-window features. A temporal transformer can be an eventual enhancement.

The offline model can analyze:

- A user's previous 20–100 proxy events
- 1-hour, 24-hour, and 7-day behavior
- Slow repeated uploads that look harmless individually
- Relationships among users, devices, and destinations
- CVE/KEV context for source assets
- Analyst-confirmed normal and malicious events

It produces:

- Deeper anomaly scores and related-event groups
- New incidents for review
- Recommended live thresholds
- Teacher-generated labels or a candidate small model

The offline model also supports on-demand investigation. It is powerful but does not need to meet Squid request latency.

### Safe learning loop

```mermaid
flowchart LR
    SQUID[Squid Events] --> LIVE[Live Scoring]
    LIVE --> STORE[(Local History)]
    LIVE --> REVIEW[Analyst Review]
    REVIEW -->|Labels| STORE
    STORE -->|Nightly snapshot| GPU[Powerful GPU Model]
    GPU --> TEST[Replay + Evaluate]
    TEST --> GATE{Better and Safe?}
    GATE -->|Approve| VERSION[Versioned Candidate]
    VERSION --> DEPLOY[Update Small Model / Thresholds]
    GATE -->|Reject| KEEP[Keep Current Version]
```

Do not train on unresolved high-risk events as if they were normal. Every promoted model is versioned and supports rollback.

## 9. Local LLM

The local LLM receives structured evidence after scoring and:

- Explains why a Squid event was flagged.
- Summarizes a user's related proxy activity.
- Adds relevant CVE/KEV context.
- Suggests investigation steps.

It recommends actions but cannot modify Squid policy directly. Squid logs, URLs, CVE text, and report content are untrusted data, not LLM instructions.

## 10. Hackathon demo

1. Start Docker Compose on the GB10.
2. Configure one test client or `curl` to use Squid.
3. Load a local CVE/NVD sample and CISA KEV snapshot.
4. Run Nmap against one authorized test subnet and associate a test asset with a KEV.
5. Generate several normal requests through Squid.
6. Send a large, off-hours test upload to a new destination through Squid.
7. Stream the Squid log into FastAPI and score it immediately.
8. Show the risk evidence and local-LLM explanation in Streamlit.
9. Label the event and trigger the nightly GPU job manually.
10. Show the powerful model's deeper result and candidate threshold/model.
11. Approve the candidate or roll it back.
12. Approve the suspicious destination for the denylist, repeat the request, and show Squid blocking it.

## 11. Installation on the GB10

1. Install Docker, Docker Compose, the NVIDIA driver, and NVIDIA Container Toolkit.
2. Verify GPU access with `nvidia-smi`.
3. Check `uname -m`; use `linux/arm64` images if the Grace-based host requires them.
4. Download models once and store them locally.
5. Start Squid, FastAPI, PostgreSQL, the worker, Streamlit, and the model service.
6. Bind-mount the Squid log directory read-only into the worker.
7. Load the CVE/KEV snapshot and configure one authorized scan range.
8. Expose port 3128 only to test clients and restrict the dashboard to the internal management network.

Suggested resource allocation:

- CPU: Squid, API, PostgreSQL, collector, rules, and small live model
- GPU: powerful offline model and local LLM
- Disk: Squid history, normalized events, CVEs, labels, models, and audit history

A connected installation can refresh CVE data through an allowlisted outbound-only updater that sends no customer data. An air-gapped installation imports a signed update bundle.

## 12. Four-person split

### Member 1 — Squid and live collection

- Squid container and explicit-proxy configuration
- Structured log format and collector
- Test traffic and upload generator
- Denylist/reload integration

### Member 2 — Processing and live detection

- FastAPI ingestion and normalized event schema
- Rolling baselines and feature extraction
- Rules, Isolation Forest, and risk score
- CVE/Nmap enrichment

### Member 3 — Powerful offline model

- PyTorch autoencoder and nightly job
- Historical windows and training exclusions
- Evaluation, model versions, promotion, and rollback
- Optional teacher-to-small-model update

### Member 4 — Dashboard, LLM, and GB10 deployment

- Streamlit alerts and analyst labels
- Local LLM explanations
- Policy and model approval screens
- Docker Compose and GB10 GPU setup

## 13. Eventual architecture

```mermaid
flowchart LR
    USERS[Managed Users] --> SQUID[Highly Available Squid Proxy]
    SQUID --> WEB[Internet]
    SQUID --> STREAM[Durable Log Stream]

    subgraph Context[Additional Context]
        AGENTS[Signed Endpoint Agents]
        NET[Zeek / NetFlow / DNS]
        INTEL[CVE / KEV / Vendor Intelligence]
        ID[Asset + Identity Systems]
    end

    subgraph Live[Production Live Path]
        PIPE[Validation + Enrichment]
        FEATURE[Streaming Feature Store]
        POLICY[Rules + DLP]
        MODEL[Small Model Serving]
        RESPONSE[Alert + Squid/EDR Enforcement]
    end

    subgraph Offline[GB10 Offline Intelligence]
        HISTORY[(Encrypted History)]
        LARGE[Powerful Temporal / Graph Model]
        LLM[Local LLM Investigation]
        REGISTRY[Signed Model Registry]
    end

    STREAM --> PIPE
    AGENTS --> PIPE
    NET --> PIPE
    INTEL --> PIPE
    ID --> PIPE
    PIPE --> FEATURE
    FEATURE --> POLICY
    FEATURE --> MODEL
    POLICY --> RESPONSE
    MODEL --> RESPONSE
    RESPONSE --> SQUID
    PIPE --> HISTORY
    HISTORY --> LARGE --> LLM
    LARGE --> REGISTRY --> MODEL
```

Production additions include endpoint metadata for HTTPS/file visibility, durable queues, high availability, RBAC, encrypted backups, retention controls, tamper-evident audit logs, signed policy/model artifacts, and staged enforcement.

## 14. Definition of success

> A test upload passes through Squid, its log is scored locally within seconds, and the alert is explained in the dashboard. The powerful GB10 model later analyzes the broader history and proposes a reviewed improvement. An analyst can approve a policy that causes Squid to block the next matching request, with no customer telemetry leaving the appliance.
