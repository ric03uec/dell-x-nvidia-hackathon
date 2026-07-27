const spark = {
  up: [8, 10, 9, 13, 12, 16, 15, 19, 22, 20, 26, 31],
  down: [28, 26, 27, 22, 24, 19, 20, 17, 15, 16, 12, 10],
  flat: [18, 17, 19, 18, 20, 19, 18, 20, 19, 21, 20, 19],
};

export const demoPageData = {
  cve: {
    metrics: [
      ["CVEs tracked", "1,204", "+18", "neutral", spark.up],
      ["KEV matches", "7", "+1", "negative", spark.flat],
      ["Critical unpatched", "3", "0", "neutral", spark.flat],
      ["Assets affected", "22", "-4", "positive", spark.down],
    ],
    title: "CVE / KEV Watchlist",
    meta: "Demo-only vulnerability context",
    columns: [
      { key: "id", label: "CVE ID", width: "1.1fr" },
      { key: "assets", label: "Affected", width: ".6fr", align: "right" },
      { key: "published", label: "Published", width: ".7fr" },
      { key: "exploit", label: "Exploit", width: ".7fr" },
      { key: "sev", label: "CVSS", width: ".6fr" },
    ],
    rows: [
      [["CVE-2024-3400", "Palo Alto PAN-OS · fw-edge-02"], "14", "2024-04-12", "Weaponized", { badge: "10.0", level: "critical" }],
      [["CVE-2024-21762", "Fortinet FortiOS · vpn-gw-03"], "9", "2024-02-09", "Weaponized", { badge: "9.8", level: "critical" }],
      [["CVE-2023-4966", "Citrix NetScaler · citrix-adc-01"], "6", "2023-10-10", "Weaponized", { badge: "9.4", level: "critical" }],
      [["CVE-2024-1086", "Linux kernel · srv-db02"], "11", "2024-01-31", "PoC public", { badge: "8.8", level: "high" }],
      [["CVE-2023-38831", "WinRAR · fin-ws-114"], "5", "2023-08-23", "PoC public", { badge: "7.8", level: "high" }],
      [["JetBrains TeamCity", "CVE-2024-27198 · ci-build-01"], "2", "2024-03-04", "None", { badge: "6.5", level: "medium" }],
    ],
  },
  assets: {
    metrics: [
      ["Total assets", "312", "+6", "neutral", spark.up],
      ["New this week", "6", "+2", "neutral", spark.up],
      ["Unmanaged", "14", "-3", "positive", spark.down],
      ["High-risk assets", "5", "0", "neutral", spark.flat],
    ],
    title: "Discovered Assets",
    meta: "Demo-only passive inventory",
    columns: [
      { key: "device", label: "Device", width: "1fr" },
      { key: "ip", label: "IP Address", width: ".7fr" },
      { key: "owner", label: "Owner", width: ".7fr" },
      { key: "seen", label: "Last Seen", width: ".6fr", align: "right" },
      { key: "risk", label: "Risk", width: ".6fr" },
    ],
    rows: [
      [["LAPTOP-17", "Windows 11 · managed"], "10.20.4.17", "alice", "2m ago", { risk: 92 }],
      [["WKS-204", "macOS 14.4 · managed"], "10.20.4.204", "rjohnson", "5m ago", { risk: 76 }],
      [["SRV-DB02", "Ubuntu 22.04 · server"], "10.20.1.52", "platform", "1m ago", { risk: 61 }],
      [["LAPTOP-08", "Windows 11 · unmanaged"], "10.20.4.8", "dpatel", "8m ago", { risk: 58 }],
      [["WKS-119", "macOS 14.4 · managed"], "10.20.4.119", "kwallace", "3m ago", { risk: 44 }],
      [["LAPTOP-45", "Windows 11 · managed"], "10.20.4.45", "tlee", "12m ago", { risk: 22 }],
      [["PRN-FLOOR3", "Unknown · unmanaged"], "10.20.7.31", "—", "41m ago", { risk: 18 }],
    ],
  },
  models: {
    metrics: [
      ["Active version", "v1.4", "6d ago", "neutral", spark.flat],
      ["Candidate", "v1.5", "pending", "neutral", spark.up],
      ["Last trained", "02:14", "today", "neutral", spark.flat],
      ["Approval rate", "94%", "+2 pts", "positive", spark.up],
    ],
    title: "Version History",
    meta: "Demo-only model lifecycle",
    columns: [
      { key: "version", label: "Version", width: "1fr" },
      { key: "precision", label: "Precision", width: ".6fr", align: "right" },
      { key: "recall", label: "Recall", width: ".6fr", align: "right" },
      { key: "samples", label: "Samples", width: ".6fr", align: "right" },
      { key: "status", label: "Status", width: ".7fr" },
    ],
    rows: [
      [["v1.5", "trained 2026-07-26 02:14"], "0.94", "0.88", "418k", { badge: "Candidate", level: "info" }],
      [["v1.4", "trained 2026-07-20 02:11"], "0.91", "0.84", "402k", { badge: "Active", level: "ok" }],
      [["v1.3", "trained 2026-07-13 02:09"], "0.90", "0.83", "377k", { badge: "Archived", level: "muted" }],
      [["v1.2", "trained 2026-07-06 02:14"], "0.88", "0.80", "351k", { badge: "Archived", level: "muted" }],
      [["v1.1", "trained 2026-06-29 02:12"], "0.85", "0.79", "330k", { badge: "Archived", level: "muted" }],
    ],
  },
  feedback: {
    metrics: [
      ["Pending review", "23", "+4", "negative", spark.up],
      ["Reviewed today", "41", "+9", "positive", spark.up],
      ["True positive rate", "87%", "+3 pts", "positive", spark.up],
      ["Avg review time", "2m 40s", "-20s", "positive", spark.down],
    ],
    title: "Review Queue",
    meta: "Demo-only analyst feedback",
    columns: [
      { key: "event", label: "Event", width: "1.3fr" },
      { key: "analyst", label: "Analyst", width: ".7fr" },
      { key: "at", label: "Reviewed", width: ".5fr", align: "right" },
      { key: "dwell", label: "Dwell", width: ".5fr", align: "right" },
      { key: "verdict", label: "Verdict", width: ".7fr" },
    ],
    rows: [
      [["alice", "→ unknown-storage.example"], "J. Ortiz", "09:14", "3m 02s", { badge: "True positive", level: "critical" }],
      [["rjohnson", "→ gdrive-personal.com"], "J. Ortiz", "09:02", "1m 44s", { badge: "False positive", level: "ok" }],
      [["msingh", "→ pastebin.com"], "K. Wallace", "08:47", "4m 18s", { badge: "Escalated", level: "high" }],
      [["dpatel", "→ transfer.sh"], "K. Wallace", "08:39", "2m 51s", { badge: "Escalated", level: "high" }],
      [["tlee", "→ corp-approved-cloud.com"], "K. Wallace", "08:30", "0m 58s", { badge: "False positive", level: "ok" }],
      [["jortiz", "→ corp-approved-cloud.com"], "M. Chen", "08:22", "1m 12s", { badge: "False positive", level: "ok" }],
    ],
  },
};
