# OpenClaw desired state

This directory contains the operator-authored OpenClaw state deployed directly
to the `hack` GB10 host. The repository is authoritative for these files;
generated runtime state is not copied here.

## Layout

- `settings/openclaw.json` configures the local LiteLLM model and authenticated
  gateway.
- `agents.yaml` is the NemoClaw manifest for the agent.
- `promptlog.md` is the operator-maintained prompt/session log.
- `policy/` holds OpenShell policy presets for the agent.
- `workspace/` contains the main agent's checked-in workspace files, including
  the vulnerability-intelligence subsystem (`config/`, `cron/`, `schemas/`,
  `tools/`, `tests/`) that collects and scores CVE/URL findings.
- `skills/` is reserved for reviewed OpenClaw skills.

Do not add API keys, gateway or channel tokens, pairing state, sessions, logs,
caches, indexes, databases, or generated resolver values. Ansible reads the
LiteLLM key from the existing host secret file and generates the gateway token
on the host.
