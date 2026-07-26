# gb10: what shipped vs. what we added

Inventoried 2026-07-26 from `dell-gb10` (`promaxgb10-5d0c`).

**The rule:** we took delivery of the device on 2026-07-26. Anything written to
this disk before that date is **pre-installed** — it arrived with the box,
whoever put it there. Anything from 2026-07-26 is **ours**.

## How the dates were read

mtime alone is misleading here: `rsync -a` preserves the *source* host's mtime,
so files copied onto this box today can carry June timestamps. ctime — when the
inode was last written on *this* filesystem — can't be preserved that way, so
provenance below is settled on ctime. Two items flip on this:

- The `hf-cache` models read `m=2026-06-13` / `m=2026-07-04` but
  `c=2026-07-26 17:19–17:28`. They were copied here **today** off the USB from
  our other host (`inx`). Ours.
- `~/.local/bin/bv` reads `m=2025-11-27` but `c=2026-07-26 18:33`. Ours.

Conversely `/usr/local/bin/ollama` has `c=2026-06-14 20:48` — genuinely written
to this disk six weeks before we had it. Pre-installed.

---

## Pre-installed

### Factory image (2025-08-06)

Ubuntu Server 24.04.3 LTS "Noble Numbat" arm64, build `20250806.1`. The apt log
for that date is a long run of `apt-get install --reinstall` on base packages —
image assembly, not desk work. `nsys` / `nsys-ui` (Nsight Systems) date from
2025-08-13.

### First boot / NVIDIA-Dell OOBE (2026-06-02 → 06-03)

Powered on 2026-06-02 21:07 (`/lost+found`, `/etc/machine-id`). The whole DGX
stack landed in three apt transactions over ~45 minutes:

| What | Evidence |
|---|---|
| NVIDIA driver 580.95.05-open, CUDA toolkit 13.0 | apt 2026-06-02 21:13 |
| `dgx-dashboard` (the `:11000` web UI), `dgx-oobe`, `dgx-oobe-desktop` | apt 21:13 |
| `nvidia-ai-workbench`, `/opt/NVIDIA AI Workbench` | apt 21:13 |
| **Docker + `docker-compose-plugin` + `docker-buildx-plugin`** | apt 21:13; `/opt/containerd` 21:25 |
| Mellanox/RDMA (`rdma-core`, `mstflint`, `perftest`, `ucx-utils`) | apt 21:13 |
| `linux-nvidia-hwe-24.04` → running kernel 6.17.0-1021-nvidia | apt 21:09 |
| `dell-dgx-wallpaper`, `dgx-oobe-customize` (Dell OEM repo) | apt 21:23 |
| GNOME, Firefox, snapd bases | `snap list`, all `canonical**` |

Docker is **not** something we installed — it came with the box. Note OOBE
**purged `unattended-upgrades`** at 21:23, so this machine does not self-patch.

### Prior user's hackathon session (2026-06-14 → 06-15)

Someone used this device for ~6 hours six weeks before we got it. It is one
coherent project, not scattered leftovers: `~/fuze.disabled...` is a git repo
pointing at **`github.com/stephenhungg/fuze`**, last commit *"generate chat
answers with local ollama"* by Stephen Hung, Jun 14 18:35 -0700. Everything
else that evening is that app's stack.

| What | Footprint | Written |
|---|---|---|
| **Ollama** + models `qwen3`, `nomic-embed-text` | **33G** (+34M binary) | 2026-06-14 20:48 |
| `nodejs`, `npm`, `python3-pip`, `python3-venv` (apt), `pnpm` | — | 2026-06-14 20:54 |
| Python libs in `~/.local/bin`: `fastapi`, `uvicorn`, `pytest`, `spacy`, `httpx`, `numpy`, `typer`, `tldextract`, `weasel` | — | 2026-06-14 20:55 |
| **Qdrant** — `~/qdrant_storage` + `qdrant/qdrant` image | 1.6M + 197M | 2026-06-14 22:03 |
| `cloudflared` (no `~/.cloudflared` creds present) | 36M | 2026-06-15 00:41 |
| `fuze` app itself — API, web, pitch deck. Renamed `.disabled` by us today 17:31 | 16M | 2026-06-14 → 06-15 |

Neither Ollama nor Qdrant is running now, and nothing in this repo references
either. **~33G reclaimable**, nearly all of it Ollama's model blobs.

### Prior access still live

`~/.ssh/authorized_keys` carries four keys. One is ours; three predate us:

```
devashish@ibex
rohanhasabe8@gmail.com
shrivara@Mac.localdomain
brian@xenophon.dev        <- ours, added today 16:52
```

Those three can still SSH in as `dell`, which is the only non-system account
and has passwordless sudo. Not a finding about the prior team — just the
default state of a re-issued device. Your call whether to prune.

---

## Ours — not documented here

Everything we added on 2026-07-26 is **adopted into IaC**, not described in
prose: `provision.sh` reproduces it and records where each piece came from,
and `README.md` covers the config and the redeploy loop. This file stays a
record of the baseline we inherited and do not manage.

One thing worth stating because its absence surprises people: `nemoclaw` is
**not** installed — by us or by anyone before us. The serving stack is plain
Docker + vLLM + LiteLLM.

## Open questions

1. **Reclaim the prior project?** ~33G in Ollama models, plus Qdrant, the
   `fuze` repo, and node/pnpm. Nothing here depends on any of it.
2. **Prune the three inherited `authorized_keys` entries?**
3. **Restore `unattended-upgrades`,** or leave it purged for hackathon
   stability?
4. `/mnt/modelshub` is removable — the `hf-cache` copy is complete on internal
   disk (`COPY_EXIT_CODE=0`), so nothing breaks when it's unplugged. Confirm?
