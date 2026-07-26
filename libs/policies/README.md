# Reusable OpenShell policy fragments

Each file here is a `network_policies` fragment — the *dynamic*, hot-reloadable
half of an OpenShell policy. Paste the block you need into an agent's
`policy.yaml` under `network_policies:`.

Copy, don't import. OpenShell has no include mechanism, and a templating layer
here would be the wrong trade at four agents. See the cut list in
[../../docs/DESIGN.md](../../docs/DESIGN.md) for when that changes.

## Using one

```bash
openshell policy get <sandbox> --base > policy.yaml   # pull what's live
# paste a fragment under network_policies:
openshell policy set <sandbox> --policy policy.yaml --wait
```

Or incrementally, without editing a file:

```bash
openshell policy update <sandbox> \
  --add-endpoint api.github.com:443:read-only:rest:enforce \
  --binary /usr/bin/gh --wait
```

## Iterating

Start closed, run the agent, watch what it's denied, add exactly that:

```bash
nemoclaw <sandbox> logs --follow
```

`enforcement: audit` logs a violation instead of blocking it — useful while
discovering what an agent actually needs, wrong to leave on.
