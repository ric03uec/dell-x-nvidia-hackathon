# Reusable agent skills

`SKILL.md`-format skills that any agent in `agents/` can be given. Same
convention NemoClaw uses for its own `.agents/skills/`, so these are portable
to a coding assistant working on this repo as well as to a sandboxed agent.

## Giving a skill to an agent

Skills are data, not code — an agent gets one by having it in its workspace.
The deploy path rsyncs an agent's own folder, so symlink or copy what that
agent needs into `agents/<name>/skills/` and it ships with it.

Keep the shared copy here canonical; if an agent needs a variant, that's a sign
the skill wants a parameter, not a fork.
