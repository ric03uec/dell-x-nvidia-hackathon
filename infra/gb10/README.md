# gb10 inference host

This directory is the **source of truth** for the vLLM + LiteLLM stack on
`dell-gb10` (`promaxgb10-5d0c`). The box holds a copy; changes are made here
and pushed.

- `PROVENANCE.md` — what came with the device. Inherited baseline, not managed.
- `provision.sh` — reproduces what we installed, and where it came from.
- everything else — the config, below.

## Host

Ubuntu 24.04.3, kernel 6.17.0-1021-nvidia, aarch64, NVIDIA GB10 (driver
580.159.03, CUDA 13.0), ~119.7 GiB unified memory, 3.6T root with 3.0T free.
Outbound internet works (PyPI and Hugging Face reachable) — the USB bundles at
`/mnt/modelshub` are a bandwidth convenience, not an airgap requirement.

`openshell` v0.0.91 is installed via uv; `nemoclaw` is not.

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

The loop is: **edit here → push → restart → verify.**

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

## Known issues

- `docker default-cgroupns-mode=host` is **not** set in `/etc/docker/daemon.json`.
  Harmless today, but the OpenShell gateway embeds k3s in Docker and will fail
  on cgroup v2 without it. Fix before the first gateway start.
- `scripts/doctor.sh dell-gb10` reports `FAIL nemoclaw installed` — accurate,
  nemoclaw genuinely isn't there.
