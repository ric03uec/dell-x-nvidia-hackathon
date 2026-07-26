# nemoclaw-lessons

Local Claude Code plugin bundling this repo's NemoClaw/OpenShell operating
skills, ported from the nvidia-hackathon prototyping repo's `libs/skills/`.

`skills/*` are symlinks into [`libs/skills/`](../libs/skills/) — this folder
just packages them for loading, it isn't a second copy. Edit the skills at
their source.

Install locally in Claude Code:

```
/plugin marketplace add /path/to/dell-x-nvidia-hackathon/claude-plugin
/plugin install nemoclaw-lessons
```

## Pi compatibility

The same skills are also symlinked at [`.agents/skills/`](../.agents/skills/)
at the repo root — the shared `SKILL.md` convention Pi (and NemoClaw's own
sandboxed agents) scan for project-level skills automatically, no install
step needed. Both directories point at the same `libs/skills/` files.
