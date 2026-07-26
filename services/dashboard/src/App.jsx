import React, { useEffect, useMemo, useRef, useState } from "react";

const Icon = {
  grid: "M2.5 2.5h4v4h-4zM9.5 2.5h4v4h-4zM2.5 9.5h4v4h-4zM9.5 9.5h4v4h-4z",
  activity: "M1.5 8h2.8l2.2-4.6 2.6 9.2 2-4.6h3.4",
  shield: "M8 1.8 3.2 3.6v3.8c0 2.9 1.9 5 4.8 5.8 2.9-.8 4.8-2.9 4.8-5.8V3.6zM8 5.6v2.6M8 10.3v.1",
  server: "M2.5 3h11v3.6h-11zM2.5 9.4h11V13h-11zM4.6 4.8h.1M4.6 11.2h.1",
  layers: "M8 2 1.8 5.2 8 8.4l6.2-3.2zM1.8 8.6 8 11.8l6.2-3.2",
  review: "M2.5 2.5h11v11h-11zM5.2 8.1l1.9 1.9 3.7-3.8",
  search: "M7.2 2.6a4.6 4.6 0 1 0 0 9.2 4.6 4.6 0 0 0 0-9.2zM10.6 10.6l2.8 2.8",
  refresh: "M13 6.6A5.2 5.2 0 0 0 3.4 5.4M3 9.4a5.2 5.2 0 0 0 9.6 1.2M13.2 2.8v3.8h-3.8M2.8 13.2V9.4h3.8",
  bell: "M8 2.2a3.6 3.6 0 0 0-3.6 3.6c0 3.2-1.1 4.2-1.1 4.2h9.4s-1.1-1-1.1-4.2A3.6 3.6 0 0 0 8 2.2zM6.8 12.2a1.3 1.3 0 0 0 2.4 0",
  sun: "M8 5.2a2.8 2.8 0 1 0 0 5.6 2.8 2.8 0 0 0 0-5.6zM8 1.4v1.5M8 13.1v1.5M14.6 8h-1.5M2.9 8H1.4M12.7 3.3l-1.1 1.1M4.4 11.6l-1.1 1.1M12.7 12.7l-1.1-1.1M4.4 4.4 3.3 3.3",
  moon: "M13.4 9.7A5.7 5.7 0 0 1 6.3 2.6a5.7 5.7 0 1 0 7.1 7.1z",
};

function Glyph({ name, size = 14 }) {
  return (
    <svg aria-hidden="true" className="glyph" height={size} viewBox="0 0 16 16" width={size}>
      <path d={Icon[name]} />
    </svg>
  );
}

const navSections = [
  {
    label: "Monitor",
    items: [
      { id: "dashboard", label: "Overview", icon: "grid" },
      { id: "events", label: "Live Events", icon: "activity", count: 37 },
      { id: "cve", label: "CVE Intelligence", icon: "shield", count: 7 },
    ],
  },
  {
    label: "Inventory",
    items: [
      { id: "assets", label: "Asset Discovery", icon: "server" },
      { id: "models", label: "Model Registry", icon: "layers" },
      { id: "feedback", label: "Analyst Feedback", icon: "review", count: 23 },
    ],
  },
];

const pageMeta = {
  dashboard: ["Security Operations", "Exfiltration protection", "gb10-appliance-01"],
  events: ["Live Events", "Event stream", "local inference"],
  cve: ["CVE Intelligence", "Vulnerability context", "KEV-prioritized"],
  assets: ["Asset Discovery", "Network inventory", "passive discovery"],
  models: ["Model Registry", "Detection models", "nightly retrain"],
  feedback: ["Analyst Feedback", "Review queue", "feeds retraining"],
};

const ranges = ["1H", "4H", "1D", "1W", "1M"];

const rangeSpecs = {
  "1H": { points: 25, seed: 21, base: 46, drift: 0.5, ticks: ["13:00", "13:15", "13:30", "13:45", "14:00"] },
  "4H": { points: 25, seed: 57, base: 38, drift: 0.9, ticks: ["10:00", "11:00", "12:00", "13:00", "14:00"] },
  "1D": { points: 25, seed: 9, base: 14, drift: 3.1, ticks: ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"] },
  "1W": { points: 22, seed: 33, base: 30, drift: 1.2, ticks: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] },
  "1M": { points: 31, seed: 71, base: 24, drift: 1.1, ticks: ["Jun 26", "Jul 2", "Jul 8", "Jul 14", "Jul 20", "Jul 26"] },
};

function makeSeries(seed, count, base, drift, jitter) {
  let state = seed >>> 0;
  const random = () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
  const out = [];
  let value = base;
  for (let i = 0; i < count; i += 1) {
    value += drift + (random() - 0.5) * jitter;
    out.push(Math.max(3, Math.min(97, value)));
  }
  return out;
}

const cves = [
  { score: "10.0", id: "CVE-2024-3400", vendor: "Palo Alto PAN-OS", detail: "command injection", asset: "fw-edge-02", kev: true, level: "critical" },
  { score: "9.8", id: "CVE-2024-21762", vendor: "Fortinet FortiOS", detail: "SSL-VPN OOB write", asset: "vpn-gw-03", kev: true, level: "critical" },
  { score: "9.4", id: "CVE-2023-4966", vendor: "Citrix NetScaler", detail: "session token leak", asset: "citrix-adc-01", kev: true, level: "critical" },
  { score: "8.8", id: "CVE-2024-1086", vendor: "Linux kernel", detail: "nf_tables UAF", asset: "srv-db02", kev: true, level: "high" },
  { score: "7.8", id: "CVE-2023-38831", vendor: "WinRAR", detail: "arbitrary code exec", asset: "fin-ws-114", kev: false, level: "high" },
  { score: "6.5", id: "CVE-2024-27198", vendor: "TeamCity", detail: "auth bypass", asset: "ci-build-01", kev: false, level: "medium" },
];

const riskEvents = [
  { time: "14:02:11", user: "alice", device: "LAPTOP-17", destination: "unknown-storage.example", bytes: "25.0 MB", risk: 92 },
  { time: "14:01:47", user: "rjohnson", device: "WKS-204", destination: "gdrive-personal.com", bytes: "8.4 MB", risk: 76 },
  { time: "13:58:02", user: "msingh", device: "SRV-DB02", destination: "pastebin.com", bytes: "1.2 MB", risk: 61 },
  { time: "13:55:30", user: "dpatel", device: "LAPTOP-08", destination: "transfer.sh", bytes: "512 KB", risk: 58 },
  { time: "13:51:19", user: "kwallace", device: "WKS-119", destination: "dropbox-personal.com", bytes: "3.1 MB", risk: 44 },
  { time: "13:47:55", user: "tlee", device: "LAPTOP-45", destination: "corp-approved-cloud.com", bytes: "40.0 MB", risk: 22 },
  { time: "13:44:02", user: "jortiz", device: "WKS-077", destination: "corp-approved-cloud.com", bytes: "12.6 MB", risk: 14 },
];

const spark = {
  up: [8, 10, 9, 13, 12, 16, 15, 19, 22, 20, 26, 31],
  down: [28, 26, 27, 22, 24, 19, 20, 17, 15, 16, 12, 10],
  flat: [18, 17, 19, 18, 20, 19, 18, 20, 19, 21, 20, 19],
  spike: [10, 11, 10, 12, 11, 13, 12, 15, 14, 22, 30, 34],
};

const pageData = {
  events: {
    metrics: [
      ["Events / min", "18,204", "+3.4%", "positive", spark.up],
      ["Blocked transfers", "146", "+12", "negative", spark.spike],
      ["Flagged users", "9", "+2", "negative", spark.up],
      ["Detection latency", "184 ms", "-18 ms", "positive", spark.down],
    ],
    title: "Live Event Stream",
    meta: "All flagged data-movement events, most recent first",
    columns: [
      { key: "time", label: "Time", width: ".5fr" },
      { key: "user", label: "User / Device", width: "1fr" },
      { key: "dest", label: "Destination", width: "1.2fr" },
      { key: "bytes", label: "Bytes", width: ".5fr", align: "right" },
      { key: "risk", label: "Risk", width: ".6fr" },
    ],
    rows: riskEvents.map((e) => [e.time, [e.user, e.device], e.destination, e.bytes, { risk: e.risk }]),
  },
  cve: {
    metrics: [
      ["CVEs tracked", "1,204", "+18", "neutral", spark.up],
      ["KEV matches", "7", "+1", "negative", spark.flat],
      ["Critical unpatched", "3", "0", "neutral", spark.flat],
      ["Assets affected", "22", "-4", "positive", spark.down],
    ],
    title: "CVE / KEV Watchlist",
    meta: "Known Exploited Vulnerabilities affecting on-prem assets",
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
    meta: "Devices observed via passive network discovery",
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
    meta: "Detection model training runs and promotion status",
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
      [["v1.0", "trained 2026-06-22 02:10"], "0.81", "0.74", "298k", { badge: "Archived", level: "muted" }],
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
    meta: "Analyst verdicts on flagged exfiltration events",
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

function flatten(value) {
  if (value == null) return "";
  if (Array.isArray(value)) return value.map(flatten).join(" ");
  if (typeof value === "object") return Object.values(value).map(flatten).join(" ");
  return String(value);
}

function matches(value, needle) {
  return !needle || flatten(value).toLowerCase().includes(needle);
}

function activateOnKey(handler) {
  return (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handler();
    }
  };
}

function App() {
  const [toast, setToast] = useState("");
  const [promoted, setPromoted] = useState(false);
  const [activePage, setActivePage] = useState("dashboard");
  const [range, setRange] = useState("1D");
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "dark");
  const [title, scope, context] = pageMeta[activePage];
  const needle = query.trim().toLowerCase();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem("squidward-theme", theme);
    } catch {
      /* private browsing or storage disabled - theme just won't persist */
    }
  }, [theme]);

  function notify(message) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2000);
  }

  return (
    <div className="app">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />

      <div className="main">
        <header className="topbar">
          <div className="crumbs">
            <span className="crumb-dim">{scope}</span>
            <span className="crumb-sep">/</span>
            <h1>{title}</h1>
            <span className="tag">{context}</span>
          </div>
          <div className="topbar-right">
            <div className="segmented" role="group" aria-label="Time range">
              {ranges.map((item) => (
                <button
                  aria-pressed={range === item}
                  className={range === item ? "active" : ""}
                  key={item}
                  onClick={() => setRange(item)}
                  type="button"
                >
                  {item}
                </button>
              ))}
            </div>
            <button className="icon-button" onClick={() => notify("Refreshed")} title="Refresh" type="button">
              <Glyph name="refresh" />
            </button>
            <button className="icon-button" onClick={() => notify("No new notifications")} title="Notifications" type="button">
              <Glyph name="bell" />
              <em className="dot" />
            </button>
            <button
              className="icon-button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              type="button"
            >
              <Glyph name={theme === "dark" ? "sun" : "moon"} />
            </button>
            <div className="divider-v" />
            <button className="avatar" onClick={() => notify("Signed in as J. Ortiz")} title="J. Ortiz" type="button">JO</button>
          </div>
        </header>

        <div className="toolbar">
          <label className="search">
            <Glyph name="search" size={13} />
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter by user, device, destination…"
              value={query}
            />
            {query && (
              <button className="search-clear" onClick={() => setQuery("")} title="Clear filter" type="button">×</button>
            )}
          </label>
          <div className="chips">
            <span className="chip">env:<b>prod</b></span>
            <span className="chip">site:<b>hq-dc1</b></span>
            <span className="chip chip-ok"><i /> Observe mode</span>
          </div>
          <div className="toolbar-right">
            <span className="muted">Auto-refresh 30s</span>
            <button className="ghost-button" onClick={() => notify("Export queued")} type="button">Export</button>
          </div>
        </div>

        <main className="content">
          {activePage === "dashboard" ? (
            <Dashboard
              needle={needle}
              notify={notify}
              promoted={promoted}
              range={range}
              setPromoted={setPromoted}
              theme={theme}
            />
          ) : (
            <DataPage data={pageData[activePage]} needle={needle} notify={notify} />
          )}
        </main>

        <footer className="statusbar">
          <span><i className="live" /> gb10-appliance-01 · 127.0.0.1 · no cloud egress</span>
          <span className="muted">Ingest 18.2k evt/s · Queue 0 · Model v1.4 · Updated 14:02:11</span>
        </footer>
      </div>

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}

// Shield mark lifted from public/squidward-logo.svg. Inlined rather than an
// <img> so it cannot flash in late, and kept full-color so it reads on both themes.
function BrandMark() {
  return (
    <svg aria-hidden="true" className="brand-mark" viewBox="-1.5 12 267 267">
      <path d="M132 12 240 58v78c0 62-40 107-108 139C64 243 24 198 24 136V58L132 12Z" fill="#6546E8" />
      <path d="M121 58 132 52l11 6v104c0 36 18 61 50 78l-18 19c-20-12-34-26-43-43-9 17-23 31-43 43l-18-19c32-17 50-42 50-78V58Z" fill="#fff" />
      <path d="M62 136c17 0 31-7 42-21 5-7 9-15 12-24l25 8c-5 16-12 29-21 40-15 18-34 29-58 31l-7-33 7-1Z" fill="#fff" />
      <path d="M202 136c-17 0-31-7-42-21-5-7-9-15-12-24l-25 8c5 16 12 29 21 40 15 18 34 29 58 31l7-33-7-1Z" fill="#fff" />
      <path d="m132 250 23 15-23 14-23-14 23-15Z" fill="#4AA9A1" />
    </svg>
  );
}

function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <BrandMark />
        <span className="brand-text">
          <strong>SquidWard</strong>
          <small>Enterprise + local first</small>
        </span>
      </div>

      <nav aria-label="Security views">
        {navSections.map((section) => (
          <div className="nav-section" key={section.label}>
            <p className="nav-label">{section.label}</p>
            {section.items.map((item) => (
              <button
                aria-current={activePage === item.id ? "page" : undefined}
                className={`nav-item ${activePage === item.id ? "active" : ""}`}
                key={item.id}
                onClick={() => onNavigate(item.id)}
                type="button"
              >
                <Glyph name={item.icon} />
                <span>{item.label}</span>
                {item.count ? <em>{item.count}</em> : null}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="appliance">
        <div className="appliance-row"><span>Appliance</span><b>GB10</b></div>
        <div className="appliance-row"><span>Mode</span><b className="ok">Observe</b></div>
        <div className="appliance-row"><span>Egress</span><b>Blocked</b></div>
        <div className="meter"><i style={{ width: "62%" }} /></div>
        <p>GPU 62% · 24.1 / 128 GB</p>
      </div>
    </aside>
  );
}

function Panel({ children, className = "", title, meta, action }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <h2>{title}</h2>
        {meta ? <span className="panel-meta">{meta}</span> : null}
        {action}
      </div>
      {children}
    </section>
  );
}

function CountBadge({ shown, total }) {
  return <span className="panel-badge">{shown === total ? `${total} results` : `${shown} of ${total}`}</span>;
}

function EmptyRow({ span }) {
  return <tr className="empty-row"><td colSpan={span}>No rows match the current filter</td></tr>;
}

function Sparkline({ points, tone }) {
  const width = 62;
  const height = 18;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = max - min || 1;
  const path = points
    .map((value, index) => {
      const x = (width / (points.length - 1)) * index;
      const y = height - ((value - min) / span) * (height - 2) - 1;
      return `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg aria-hidden="true" className={`spark ${tone}`} height={height} viewBox={`0 0 ${width} ${height}`} width={width}>
      <path d={path} />
    </svg>
  );
}

function MetricStrip({ metrics }) {
  return (
    <section className="metric-strip">
      {metrics.map(([label, value, delta, tone, series]) => (
        <div className="metric" key={label}>
          <p className="metric-label">{label}</p>
          <div className="metric-body">
            <strong>{value}</strong>
            <Sparkline points={series} tone={tone} />
          </div>
          <p className={`metric-delta ${tone}`}>
            {delta.startsWith("+") ? "▲" : delta.startsWith("-") ? "▼" : "–"} {delta}
            <span> vs. prev period</span>
          </p>
        </div>
      ))}
    </section>
  );
}

function Dashboard({ notify, promoted, setPromoted, range, theme, needle }) {
  const visibleCves = cves.filter((cve) => matches(cve, needle));
  const visibleEvents = riskEvents.filter((event) => matches(event, needle));

  return (
    <>
      <MetricStrip
        metrics={[
          ["Events processed", "2.14M", "+8.2%", "neutral", spark.up],
          ["Active alerts", "37", "+5", "negative", spark.spike],
          ["Avg. risk score", "42.6", "-3.1%", "positive", spark.down],
          ["Agents online", "1,248", "99.2%", "neutral", spark.flat],
        ]}
      />

      <div className="grid grid-a">
        <Panel
          action={<span className="panel-badge">{range}</span>}
          className="chart-panel"
          meta="Rolling baseline vs. live score"
          title="Event volume & risk trend"
        >
          <RiskTrendChart range={range} theme={theme} />
        </Panel>

        <Panel
          action={<CountBadge shown={visibleCves.length} total={cves.length} />}
          meta="Matched to vulnerable assets"
          title="CVE / KEV context"
        >
          <table className="grid-table compact">
            <thead>
              <tr>
                <th className="num w-cvss">CVSS</th>
                <th>Vulnerability</th>
                <th className="num w-asset">Asset</th>
              </tr>
            </thead>
            <tbody>
              {visibleCves.length === 0 && <EmptyRow span={3} />}
              {visibleCves.map((cve) => {
                const open = () => notify(`${cve.id} selected`);
                return (
                  <tr key={cve.id} onClick={open} onKeyDown={activateOnKey(open)} tabIndex={0}>
                    <td className="num"><span className={`score ${cve.level}`}>{cve.score}</span></td>
                    <td>
                      <span className="cell-lead">
                        {cve.id}
                        {cve.kev ? <em className="kev">KEV</em> : null}
                      </span>
                      <span className="cell-sub">{cve.vendor} · {cve.detail}</span>
                    </td>
                    <td className="num mono">{cve.asset}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      </div>

      <div className="grid grid-b">
        <Panel meta="Candidate vs. active model" title="Nightly learning loop">
          <ol className="pipeline">
            {[["Dataset", "done"], ["Train", "done"], ["Evaluate", "active"], ["Approve", promoted ? "done" : "idle"]].map(([label, state], index) => (
              <li className={state} key={label}>
                <span className="pipeline-mark">{state === "done" ? "✓" : index + 1}</span>
                <span className="pipeline-label">{label}</span>
              </li>
            ))}
          </ol>

          <table className="grid-table compare">
            <thead>
              <tr>
                <th>Metric</th>
                <th className="num">Active v1.4</th>
                <th className="num">{promoted ? "Promoted v1.5" : "Candidate v1.5"}</th>
                <th className="num">Δ</th>
              </tr>
            </thead>
            <tbody>
              {[["Precision", "0.91", "0.94", "+0.03"], ["Recall", "0.84", "0.88", "+0.04"], ["Alerts / analyst / day", "6.2", "5.1", "-1.1"]].map((row) => (
                <tr key={row[0]}>
                  <td>{row[0]}</td>
                  <td className="num mono">{row[1]}</td>
                  <td className="num mono">{row[2]}</td>
                  <td className="num mono positive">{row[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="panel-footer">
            <span className={`status-text ${promoted ? "ok" : "warn"}`}>
              <i />{promoted ? "Model promoted to production" : "Pending analyst approval"}
            </span>
            <div className="button-row">
              <button className="ghost-button" onClick={() => notify("Evaluation report opened")} type="button">Report</button>
              <button
                className="primary-button"
                disabled={promoted}
                onClick={() => {
                  setPromoted(true);
                  notify("Candidate v1.5 promoted");
                }}
                type="button"
              >
                {promoted ? "Promoted" : "Promote"}
              </button>
            </div>
          </div>
        </Panel>

        <Panel
          action={<CountBadge shown={visibleEvents.length} total={riskEvents.length} />}
          meta="Rules + isolation forest"
          title="Live high-risk events"
        >
          <table className="grid-table">
            <thead>
              <tr>
                <th className="w-time">Time</th>
                <th>User / Device</th>
                <th>Destination</th>
                <th className="num">Bytes</th>
                <th className="w-risk">Risk</th>
              </tr>
            </thead>
            <tbody>
              {visibleEvents.length === 0 && <EmptyRow span={5} />}
              {visibleEvents.map((event) => {
                const open = () => notify(`${event.user} → ${event.destination}`);
                return (
                  <tr key={event.time} onClick={open} onKeyDown={activateOnKey(open)} tabIndex={0}>
                    <td className="mono dim">{event.time}</td>
                    <td>
                      <span className="cell-lead">{event.user}</span>
                      <span className="cell-sub">{event.device}</span>
                    </td>
                    <td className="truncate dim">{event.destination}</td>
                    <td className="num mono">{event.bytes}</td>
                    <td><RiskMeter risk={event.risk} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      </div>
    </>
  );
}

function DataPage({ data, notify, needle }) {
  const visible = data.rows.filter((row) => matches(row, needle));
  const total = data.columns.reduce((sum, item) => sum + parseFloat(item.width), 0);

  return (
    <>
      <MetricStrip metrics={data.metrics} />
      <Panel
        action={<CountBadge shown={visible.length} total={data.rows.length} />}
        className="table-panel"
        meta={data.meta}
        title={data.title}
      >
        <table className="grid-table">
          <colgroup>
            {data.columns.map((column) => (
              <col key={column.key} style={{ width: `${(parseFloat(column.width) / total) * 100}%` }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {data.columns.map((column) => (
                <th className={column.align === "right" ? "num" : ""} key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && <EmptyRow span={data.columns.length} />}
            {visible.map((row) => {
              const label = flatten(row[0]);
              const open = () => notify(`${label} selected`);
              return (
                <tr key={label} onClick={open} onKeyDown={activateOnKey(open)} tabIndex={0}>
                  {row.map((cell, cellIndex) => (
                    <Cell align={data.columns[cellIndex].align} cell={cell} key={data.columns[cellIndex].key} />
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </>
  );
}

function Cell({ cell, align }) {
  if (Array.isArray(cell)) {
    return (
      <td>
        <span className="cell-lead">{cell[0]}</span>
        <span className="cell-sub">{cell[1]}</span>
      </td>
    );
  }
  if (cell && typeof cell === "object") {
    if (typeof cell.risk === "number") return <td><RiskMeter risk={cell.risk} /></td>;
    return <td><span className={`badge ${cell.level}`}><i />{cell.badge}</span></td>;
  }
  return <td className={`${align === "right" ? "num mono" : ""}`}>{cell}</td>;
}

function RiskMeter({ risk }) {
  const tone = risk >= 80 ? "critical" : risk >= 60 ? "high" : risk >= 40 ? "medium" : "ok";
  return (
    <span className={`risk ${tone}`}>
      <span className="risk-track"><i style={{ width: `${risk}%` }} /></span>
      <b className="mono">{risk}</b>
    </span>
  );
}

function RiskTrendChart({ range, theme }) {
  const canvasRef = useRef(null);
  const spec = rangeSpecs[range];

  const { live, baseline } = useMemo(() => ({
    live: makeSeries(spec.seed, spec.points, spec.base, spec.drift, 11),
    baseline: makeSeries(spec.seed + 977, spec.points, spec.base + 14, spec.drift * 0.4, 5),
  }), [spec]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas.getContext("2d");
    const palette = getComputedStyle(document.documentElement);
    const token = (name) => palette.getPropertyValue(name).trim();

    const gridColor = token("--chart-grid");
    const axisColor = token("--chart-axis-line");
    const textColor = token("--chart-text");
    const liveColor = token("--blue");
    const baselineColor = token("--violet");
    const fillColor = token("--chart-fill");

    function draw() {
      const rect = canvas.getBoundingClientRect();
      const scale = window.devicePixelRatio || 1;
      canvas.width = Math.round(rect.width * scale);
      canvas.height = Math.round(rect.height * scale);
      context.setTransform(scale, 0, 0, scale, 0, 0);

      const width = rect.width;
      const height = rect.height;
      const padLeft = 34;
      const padRight = 10;
      const padTop = 10;
      const padBottom = 22;
      const plotWidth = width - padLeft - padRight;
      const plotHeight = height - padTop - padBottom;

      context.clearRect(0, 0, width, height);
      context.font = "10px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      context.textBaseline = "middle";

      for (let i = 0; i <= 4; i += 1) {
        const y = Math.round(padTop + (plotHeight / 4) * i) + 0.5;
        context.strokeStyle = i === 4 ? axisColor : gridColor;
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(padLeft, y);
        context.lineTo(width - padRight, y);
        context.stroke();

        context.fillStyle = textColor;
        context.textAlign = "right";
        context.fillText(String(100 - i * 25), padLeft - 8, y);
      }

      const step = plotWidth / (live.length - 1);
      const lastTick = spec.ticks.length - 1;
      context.fillStyle = textColor;
      spec.ticks.forEach((label, tickIndex) => {
        const pointIndex = Math.round((tickIndex / lastTick) * (live.length - 1));
        const x = padLeft + step * pointIndex;
        context.textAlign = tickIndex === 0 ? "left" : tickIndex === lastTick ? "right" : "center";
        context.fillText(label, x, height - padBottom / 2 - 2);
        context.strokeStyle = gridColor;
        context.beginPath();
        context.moveTo(Math.round(x) + 0.5, padTop);
        context.lineTo(Math.round(x) + 0.5, padTop + plotHeight);
        context.stroke();
      });

      function trace(values) {
        context.beginPath();
        values.forEach((value, index) => {
          const x = padLeft + step * index;
          const y = padTop + plotHeight - (value / 100) * plotHeight;
          if (index === 0) context.moveTo(x, y);
          else context.lineTo(x, y);
        });
      }

      trace(live);
      context.lineTo(padLeft + plotWidth, padTop + plotHeight);
      context.lineTo(padLeft, padTop + plotHeight);
      context.closePath();
      context.fillStyle = fillColor;
      context.fill();

      trace(live);
      context.strokeStyle = liveColor;
      context.lineWidth = 1.5;
      context.setLineDash([]);
      context.stroke();

      trace(baseline);
      context.strokeStyle = baselineColor;
      context.lineWidth = 1.5;
      context.setLineDash([3, 3]);
      context.stroke();
      context.setLineDash([]);
    }

    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [live, baseline, spec, theme]);

  const peak = Math.round(Math.max(...live));
  const average = (live.reduce((sum, value) => sum + value, 0) / live.length).toFixed(1);

  return (
    <div className="chart">
      <div className="chart-body"><canvas ref={canvasRef} /></div>
      <div className="legend">
        <span><i className="live" />Live risk score</span>
        <span><i className="baseline" />Rolling baseline</span>
        <span className="legend-right mono">peak {peak} · avg {average}</span>
      </div>
    </div>
  );
}

export default App;
