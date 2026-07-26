# services/dashboard

The dashboard's dev server area — Vite + React + TypeScript. Scaffolded by
`dxnvh-332.3` as the drop-in point for the prototype TypeScript/React
dashboard: replace `src/App.tsx` with the real app without touching the
surrounding toolchain.

Deliberately **not** a `uv` workspace member — this is the polyglot seam.
Python components are `libs/*`, `services/*` Python dirs, and `agents/*`;
this directory is reached only through the justfile's `just s <name> <verb>`
vocabulary (mirrors `just a <name> <verb>` for agents), never `uv sync`.

Per [`docs/ports.md`](../../docs/ports.md), the dev server listens on the
port from `DASHBOARD_PORT` (`.env.example`, default `8300`).

## Commands

Run from the repo root:

```bash
just s dashboard setup   # pnpm install
just s dashboard dev     # vite dev server on $DASHBOARD_PORT (default 8300)
just s dashboard check   # typecheck (tsc -b) + lint (oxlint)
just s dashboard build   # production build (dist/)
```

Or directly with pnpm inside this directory (`pnpm install`, `pnpm dev`,
`pnpm run check`, `pnpm run build`).
