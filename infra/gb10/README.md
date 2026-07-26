# GB10 Infrastructure

Ansible configuration for the GB10 host. The inventory maps the logical host `gb10` to the SSH host alias `hack`, using SSH user `dell`.

## Files

- `inventory.yml`: host inventory, with `gb10` using `ansible_host: hack` and `ansible_user: dell`.
- `playbooks/install.yml`: installs `uv`, then installs `openshell` with `uv tool install`.
- `scripts/provision.sh`: convenience wrapper for running the playbook.

## Run

From the repository root:

```bash
infra/gb10/scripts/provision.sh
```

Most tasks install into the remote user's home directory and should not need sudo. The wrapper checks whether `curl` exists on `gb10`; if it is missing, it adds `--ask-become-pass` so Ansible can prompt for sudo for the package task only. You can also request the prompt explicitly:

```bash
infra/gb10/scripts/provision.sh --ask-become-pass
```

## Overrides

`openshell` is installed as a uv tool by default. If the package or command name differs, override it:

```bash
infra/gb10/scripts/provision.sh \
  -e openshell_package=openshell \
  -e openshell_command=openshell
```
