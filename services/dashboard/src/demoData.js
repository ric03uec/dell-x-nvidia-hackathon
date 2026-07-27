const spark = {
  up: [8, 10, 9, 13, 12, 16, 15, 19, 22, 20, 26, 31],
  down: [28, 26, 27, 22, 24, 19, 20, 17, 15, 16, 12, 10],
  flat: [18, 17, 19, 18, 20, 19, 18, 20, 19, 21, 20, 19],
};

export const demoPageData = {
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
};
