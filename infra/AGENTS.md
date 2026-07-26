# Infra Agent Notes

This directory contains infrastructure configuration for the hackathon project.

## Host Model

- All project infrastructure work targets the logical host `gb10`.
- `gb10` maps to the local SSH host alias `hack`.
- SSH connects as user `dell`.
- The verified GB10 host is `promaxgb10-5d0c`.

## SSH Connectivity

The local SSH alias `hack` should prefer the normal Wi-Fi address and fall back to the direct Ethernet link-local address:

- Primary: `172.16.10.127`
- Fallback: `fe80::16d4:1666:34b0:cf4%enp195s0f0`

In `~/.ssh/config`, the fallback address must escape `%` as `%%` inside `ProxyCommand`.

The verified working form is:

```sshconfig
Host hack
    HostName 172.16.10.127
    User dell
    ProxyCommand sh -c 'if nc -z -w 2 172.16.10.127 22 2>/dev/null; then exec nc 172.16.10.127 22; else exec nc fe80::16d4:1666:34b0:cf4%%enp195s0f0 22; fi'
```

Do not use `nc -w` for the live SSH stream. Use it only for probing, then `exec nc` without a stream timeout. A timeout on the live proxy disconnects long-running Ansible tasks.

## GB10 Ansible Setup

The GB10 Ansible configuration lives in `infra/gb10`.

- `inventory.yml` maps `gb10` to `hack` with `ansible_user: dell`.
- `playbooks/install.yml` installs user-level tooling.
- `scripts/provision.sh` is the entrypoint from the repository root.

Run provisioning with:

```bash
infra/gb10/scripts/provision.sh
```

Verify connectivity with:

```bash
cd infra/gb10
ansible gb10 -m ping
```

## Current Provisioning Behavior

The playbook installs:

- `uv` into the remote user's home directory via the official installer.
- `openshell` via `uv tool install openshell`.
- A managed `~/.profile` block that prepends `$HOME/.local/bin` to `PATH`.

Most tasks do not require sudo. Package installation tasks only run when `curl` is missing, and then require sudo for installing `curl` and `ca-certificates` on Debian/Ubuntu or RedHat-family hosts.

Use Ansible `shell` for `command -v` checks. Ansible `command` does not run through a shell and should not be used for shell builtins.

## Overrides

If the OpenShell package or binary name changes, override these variables:

```bash
infra/gb10/scripts/provision.sh \
  -e openshell_package=openshell \
  -e openshell_command=openshell
```
