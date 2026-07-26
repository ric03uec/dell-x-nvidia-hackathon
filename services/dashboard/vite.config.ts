import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// docs/ports.md is the table of record: the dashboard dev server is 8300.
// DASHBOARD_PORT lives in the repo-root .env / .env.example (not a
// services/dashboard-local .env), so read it from there rather than
// hardcoding a framework default (Vite's 5173).
const REPO_ROOT = fileURLToPath(new URL('../..', import.meta.url))
const DEFAULT_DASHBOARD_PORT = 8300

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, REPO_ROOT, 'DASHBOARD_PORT')
  const port = Number(rootEnv.DASHBOARD_PORT) || DEFAULT_DASHBOARD_PORT

  return {
    plugins: [react()],
    server: { port },
    preview: { port },
  }
})
