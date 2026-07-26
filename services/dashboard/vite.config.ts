import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Bind all interfaces by default so a laptop on the LAN can open the dev
    // server; this box has no separate management VLAN, and a loopback-only
    // default meant the dashboard was only viewable via an SSH tunnel.
    // Set MGMT_BIND_ADDR to narrow it to one interface (docs/ports.md treats
    // the dashboard as management-network-only). Note the API it proxies to
    // stays on 127.0.0.1 — the proxy is server-side, so ingestion is never
    // itself exposed.
    host: process.env.MGMT_BIND_ADDR || "0.0.0.0",
    port: Number(process.env.DASHBOARD_PORT || 8300),
    watch: { useFsEvents: false, usePolling: true },
    proxy: {
      "/api": {
        target: process.env.DASHBOARD_API_TARGET || "http://127.0.0.1:8100",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
