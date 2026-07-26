# dell-x-nvidia-hackathon

Monorepo scaffold for NemoClaw agent projects with OpenShell sandbox
policies, ported from the nvidia-hackathon prototyping repo.

## The one rule

**A worktree building agent `X` touches only `agents/X/**`.**

No central registry, no shared lockfile — that's what lets parallel worktrees
merge cleanly. Changes to `libs/`, `docs/`, or the root `justfile` are their
own separate change.

## Commands

```bash
just a <name> check     # lint + typecheck one agent
just a <name> test      # its tests
just each check         # everything
```

Run the check before calling work done.
