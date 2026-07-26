# gb10 inference host

This directory is the **source of truth** for the vLLM + LiteLLM stack on
`dell-gb10` (`promaxgb10-5d0c`). The box holds a copy; changes are made here
and pushed.

- `PROVENANCE.md` — what came with the device. Inherited baseline, not managed.
- `provision.sh` — reproduces what we installed, and where it came from.
- everything else — the config, below.

## Getting on the box

```bash
ssh dell-gb10          # once the block below is in your ~/.ssh config
```

That alias is not automatic — add it to `~/.ssh/config` (or a file under
`~/.ssh/config.d/` if your config `Include`s that directory):

```sshconfig
Host dell-gb10
  HostName 192.168.0.100
  User dell
```

`192.168.0.100` is the wired interface (`enP7s7`). The box is dual-homed and
also sits at `172.16.10.127` on wifi (`wlP9s9`), which carries the default
route — but the wired address is the stable one to target. Your key needs to be
in `dell@promaxgb10-5d0c:~/.ssh/authorized_keys`; ask someone already on the
box to append it. There is a single shared `dell` account with passwordless
sudo — see `PROVENANCE.md` for who else currently holds access.

The repo is checked out on the box at
`~/workspace/github/ric03uec/dell-x-nvidia-hackathon`, and the running stacks
read their config from `~/vllm`. Those are two different places on purpose:
the checkout is the source, `~/vllm` is the deployment target.

## Host

Ubuntu 24.04.3, kernel 6.17.0-1021-nvidia, aarch64, NVIDIA GB10 (driver
580.159.03, CUDA 13.0), ~119.7 GiB unified memory, 3.6T root with 3.0T free.
Outbound internet works (PyPI and Hugging Face reachable) — the USB bundles at
`/mnt/modelshub` are a bandwidth convenience, not an airgap requirement.

`openshell` v0.0.91 remains installed via uv but is not used by this deployment.
OpenClaw is managed directly by the Ansible playbooks in `ansible/`.

## What runs

| Container | Image | Listen |
|---|---|---|
| `vllm-qwen3.6-27b-fp8` | `vllm-inx:26.06-py3-patched` | `127.0.0.1:8000` |
| `hack-litellm` | `ghcr.io/berriai/litellm:v1.88.1` | `0.0.0.0:4000` |
| `hack-litellm-postgres` | `postgres:16-alpine` | internal |

`:8000` serves `Qwen/Qwen3.6-27B-FP8` at 262144 context, unauthenticated on
loopback. `:4000` is LiteLLM on **all interfaces** and requires
`Authorization: Bearer $LITELLM_MASTER_KEY`.

`127.0.0.1:11000` is the stock NVIDIA DGX Dashboard — pre-installed, unrelated.

## Files

| Path | Role |
|---|---|
| `docker-compose.large-qwen.yml` | The two large vLLM services, behind compose profiles `qwen36` and `qwen-next-thinking`. Only one can run — both bind `:8000`. |
| `docker-compose.qwen-verify.yml` | Small Qwen3-4B on `:8000` for smoke tests. Not profile-gated. |
| `docker-compose.litellm.yml` | LiteLLM + Postgres. |
| `litellm/config.qwen36.yaml` | LiteLLM source config for the Qwen3.6 backend. |
| `litellm/config.qwen-next-thinking.yaml` | LiteLLM source config for the 80B backend. |
| `litellm/config.yaml` | **GENERATED — do not edit.** `bin/hack-litellm-large-qwen` copies one of the two above over it at start. Committed only as a record of the last selection. |
| `models/*.yml` | Descriptive registry: sizing, VRAM estimates, virtual-model aliases, hard-won tuning notes. **Nothing reads these** — the compose files hardcode their own flags. Treat as documentation that happens to be YAML. |
| `bin/hack-vllm-large-qwen` | Operator wrapper: `start <profile>`, `stop`, `status`, `logs`, `models`, `chat`. Lives at `~/bin` on the box. |
| `bin/hack-litellm-large-qwen` | Same for LiteLLM, plus config selection and secret generation. |
| `chat-templates/` | Mounted read-only by every compose file. None of the three matches a cached model — leftovers, kept for fidelity. |
| `env/litellm.env.example` | Redacted shape of the two secrets. |
| `Dockerfile.vllm-inx` | Rebuilds `vllm-inx:26.06-py3-patched` (NGC 26.06 base + one pip layer). |

### Secrets

`env/litellm.env` holds `LITELLM_MASTER_KEY` and `LITELLM_DB_PASSWORD`. It is
**generated on the box** by `ensure_env()` in the LiteLLM wrapper (`openssl
rand -hex 24`), is `chmod 600`, and is never pushed from here or committed.
`provision.sh config` excludes it explicitly.

## Models on disk

`hf-cache/` (113G), mounted at `/root/.cache/huggingface`. `HF_HUB_OFFLINE=1`
in every compose file, so nothing downloads at run time. Imported from the USB
export of our other host (`inx`); upstream is Hugging Face at these revisions:

| HF repo | Size | Revision |
|---|---|---|
| `Qwen/Qwen3-Next-80B-A3B-Thinking-FP8` | 77G | `1a28d48a94e799860201879be67616b9e21c4bd2` |
| `Qwen/Qwen3.6-27B-FP8` | 29G | `e89b16ebf1988b3d6befa7de50abc2d76f26eb09` |
| `Qwen/Qwen3-4B-Instruct-2507` | 7.6G | `cdbee75f17c01a7cc42f958dc650907174af0554` |

Three entries in `models/` describe models **not** on this box — they were
exported to the USB but never imported: `nemotron-3-nano-30b-a3b-nvfp4`,
`qwen3.6-27b-nvfp4`, `kokoro-82m`. Dormant notes, not runnable config.

## Changing something

The inference-only maintenance loop is: **edit here → push → restart →
verify.**

```bash
just gb10-push                 # rsync this dir to the box (never secrets, never weights)
just gb10-restart              # restart both stacks, wait for ready
just gb10-status               # what's up, and which models each endpoint serves
```

Or directly, if you want one piece:

```bash
./provision.sh config
ssh dell-gb10 'bin/hack-vllm-large-qwen start qwen36'
ssh dell-gb10 'bin/hack-litellm-large-qwen start qwen36'
```

Both wrappers block until the endpoint answers and dump container logs on
timeout, so a failed restart is loud rather than silent.

### Switching the served model

The two halves must agree — vLLM decides what's loaded, LiteLLM decides what's
advertised, and nothing reconciles them:

```bash
ssh dell-gb10 'bin/hack-vllm-large-qwen    start qwen-next-thinking'
ssh dell-gb10 'bin/hack-litellm-large-qwen start qwen-next-thinking'
```

Skip the second and LiteLLM keeps proxying to a backend that no longer exists
— `:4000` returns errors while `:8000` looks perfectly healthy. `just
gb10-status` prints both so the mismatch is visible.

### Changing vLLM serve flags

Edit `docker-compose.large-qwen.yml` — the `command:` list is the real
configuration. Mirror the change into the matching `models/*.yml` so the
registry doesn't drift, then push and restart. Read that file's `notes:` first;
the sizing numbers there were paid for with failed startups.

### Adding a model to LiteLLM

Add an entry to the relevant `litellm/config.<backend>.yaml` — **not**
`config.yaml`, which gets overwritten. `api_base` uses the compose service
name, not localhost.

## NemoClaw and OpenClaw

The complete agent stack is deployed through Ansible and uses the existing
LiteLLM service without changing its Compose topology:

```bash
just gb10-up
just gb10-status
just gb10-recover
```

`gb10-recover` reconnects over SSH, recovers inference if needed, and starts the
OpenClaw user service. The host currently has user-service linger disabled, so
run this command after a reboot if no `dell` login has started the service. The
default inventory targets the working SSH alias `hack`.

OpenClaw runs directly as the `dell` user's systemd service; NemoClaw and
OpenShell are not part of this deployment. Its operator-authored desired state
lives in `../openclaw/`. The token-authenticated dashboard binds directly to
`0.0.0.0:18789`; it is reachable from every network that can route to the host.
This deployment does not enable the GB10's currently disabled shared-host
firewall because doing so could disrupt unrelated services. Apply host or
upstream network filtering separately if access must be restricted.

## Egress visibility (squid)

**Docker, not apt.** Compose is already the pattern here and is pre-installed;
an apt squid drops a systemd unit and `/etc/squid` onto a box whose provenance
we deliberately track, and rollback becomes `apt purge` plus leftovers instead
of `docker compose down`. The container is pinned and disposable, and its
config lives in this repo. The one case for going direct — transparent
interception needing host netfilter — is reachable anyway with
`network_mode: host`.

Bring it up (nothing is running yet — this has been built and validated, not
deployed):

```bash
just gb10-push
ssh dell-gb10 'docker compose -f vllm/docker-compose.squid.yml up -d'
ssh dell-gb10 'docker exec hack-squid tail -f /var/log/squid/access.log'
```

### What you actually see

The `exfilguard` format (architecture §4.2, plus `dst_ip`). Live from the box:

```
ts=1785107165.560 src=172.20.0.1 user=- method=CONNECT uri=pypi.org:443       status=200 req_bytes=1033   resp_bytes=24382997 mime=- result=TCP_TUNNEL dst_ip=151.101.128.223
ts=1785107042.961 src=172.20.0.1 user=- method=CONNECT uri=httpbin.org:443    status=200 req_bytes=101326 resp_bytes=105727   mime=- result=TCP_TUNNEL dst_ip=13.223.23.68
ts=1785107040.866 src=172.20.0.1 user=- method=POST    uri=http://httpbin.org/post status=0 req_bytes=100200 resp_bytes=0 mime=- result=TCP_MISS_ABORTED dst_ip=54.147.121.219
```

Plain HTTP gives a full URL. **HTTPS gives `CONNECT host:443` and nothing
more** — no paths, no payload. That is the right granularity rather than a
limitation: the OpenShell records this feeds key on host:port, so the proxy log
and the OCSF stream describe egress in the same unit.

**But `req_bytes` survives the tunnel.** Measured with a known 100,000-byte
POST: `req_bytes=101326` over HTTPS CONNECT, `100200` over plain HTTP. Upload
volume — the exfiltration signal — is visible *without* TLS interception,
accurate to roughly 1.5%. Do not treat it as exact payload size, and do not
read `resp_bytes=0` with `TCP_MISS_ABORTED` as "nothing was uploaded": the
third line above uploaded 100KB on exactly such a record.

`dst_ip` is an addition to §4.2, pending the decision on `dxnvh-332.2`. It
earns its place immediately — the two `httpbin.org` lines above resolved to
*different* IPs, which is precisely the correlation a hostname alone loses.

### Getting traffic into it

**1. LAN laptops via explicit proxy — start here.** Real traffic, no
interception, nothing to install on the clients. The box is reachable at
`192.168.0.100` (its ethernet address, the one `dell-gb10` resolves to):

```bash
export http_proxy=http://192.168.0.100:3128
export https_proxy=http://192.168.0.100:3128
```

macOS system-wide: System Settings → Network → your interface → Details →
Proxies → enable Web Proxy *and* Secure Web Proxy, host `192.168.0.100`, port
`3128`. `squid.conf` already allows all three RFC1918 ranges, so it doesn't
matter which segment a laptop sits on.

**2. The box's own egress.** Same variables in a shell, or for containers, a
daemon-level proxy in `/etc/docker/daemon.json`. This is what catches what
agents and jobs on the Spark actually reach.

**3. Transparent interception.** Only needed for processes that ignore proxy
env vars: an `iptables REDIRECT` of :80/:443 into a squid `intercept` port.
Costs host networking and a firewall rule, and for HTTPS you additionally need
`ssl_bump peek` + `splice` to read the SNI. Worth it only if option 2 proves
leaky — **not built here.**

### Simulated traffic

To develop a parser without waiting for humans to browse:

```bash
./squid/simulate-traffic.sh http://192.168.0.100:3128
```

It drives a dozen requests shaped like real agent egress — package registries,
model hosts, LLM APIs, and telemetry endpoints — including one plain-HTTP
target so you get a full-URL line alongside the CONNECTs.

### On SSL-bump

Decrypting HTTPS to get paths and payloads means installing a squid-generated
CA on every client, and it breaks anything with certificate pinning. It also
means reading your colleagues' traffic in the clear, which is a consent
question before it is a technical one. Domains are enough for egress-policy
work; if you later need URLs, `ssl_bump peek`/`splice` gets you SNI without
decrypting, and full bump should be a deliberate, announced decision.

### Config notes

`squid.conf` is caching-disabled on purpose — a cache hit is egress that
doesn't appear twice, which defeats the point. And the access log **cannot** go
to `/dev/stdout`: squid runs as uid 13 and dies at startup with a message that
looks like a cache error. It logs to the `hack-squid-logs` volume instead.

## Known issues

- `docker default-cgroupns-mode=host` is **not** set in `/etc/docker/daemon.json`
  — verified absent. This is **moot for the current deployment** (OpenShell is
  not in the path), but if OpenShell ever returns, note it is an open
  contradiction rather than a known fix: `libs/skills/openshell-egress-audit`
  records the daemon.json workaround as obsolete from OpenShell 0.0.85 onward
  because the gateway sets host cgroupns itself. Observed 2026-07-26: an
  openshell gateway did start on this box without it, as a plain host process.
  `dxnvh-bht.1` owns settling it — don't apply a possibly-stale fix first.
- `scripts/doctor.sh dell-gb10` reports `FAIL nemoclaw installed` — accurate,
  and expected now that NemoClaw is deliberately out of the deployment.
