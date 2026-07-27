const UNAVAILABLE = "Unavailable";

const SUMMARY_METRICS = [
  ["total_events", "Total events"],
  ["normal_events", "Normal events"],
  ["suspicious_events", "Suspicious events"],
  ["findings", "Findings"],
  ["pending_recommendations", "Pending recommendations"],
  ["enforcement_results", "Enforcement results"],
];

function present(value) {
  return value === undefined || value === null || value === "" ? UNAVAILABLE : String(value);
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatBytes(bytes) {
  if (!finiteNumber(bytes) || bytes < 0) return UNAVAILABLE;
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1000)), units.length - 1);
  const value = bytes / 1000 ** unitIndex;
  const fractionDigits = unitIndex === 0 ? 0 : unitIndex === 1 && Number.isInteger(value) ? 0 : 1;
  return `${value.toFixed(fractionDigits)} ${units[unitIndex]}`;
}

export function formatTimestamp(timestamp, { includeDate = false } = {}) {
  if (typeof timestamp !== "string" && !(timestamp instanceof Date)) return UNAVAILABLE;

  const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
  if (Number.isNaN(date.getTime())) return UNAVAILABLE;

  const time = [date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  if (!includeDate) return time;

  const day = [date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate()]
    .map((part, index) => (index === 0 ? String(part) : String(part).padStart(2, "0")))
    .join("-");
  return `${day} ${time} UTC`;
}

export function toRiskEvent(projection) {
  const event = projection && projection.event ? projection.event : projection || {};
  const finding = projection && projection.finding ? projection.finding : {};

  return {
    id: event.event_id ?? projection?.event_id ?? null,
    findingId: projection?.finding_id ?? finding.finding_id ?? null,
    time: formatTimestamp(event.timestamp ?? projection?.timestamp),
    user: present(event.user ?? projection?.user ?? event.actor ?? projection?.actor),
    device: present(event.device ?? projection?.device),
    destination: present(event.destination ?? projection?.destination),
    bytes: formatBytes(event.request_bytes ?? projection?.request_bytes),
    risk: projection?.risk_score ?? finding.risk_score ?? event.risk_score ?? null,
  };
}

export function toRiskEvents(projections) {
  const events = Array.isArray(projections) ? projections : projections?.events;
  return Array.isArray(events) ? events.map(toRiskEvent) : [];
}

export function toCvePage(catalog) {
  const vulnerabilities = Array.isArray(catalog?.vulnerabilities) ? catalog.vulnerabilities : [];
  const rejected = new Set(
    (Array.isArray(catalog?.policies) ? catalog.policies : [])
      .filter((policy) => policy.disposition === "rejected")
      .map((policy) => policy.cve_id),
  );
  const ransomware = vulnerabilities.filter((item) => item.ransomware_use === "Known").length;
  const fetched = formatTimestamp(catalog?.fetched_at, { includeDate: true });

  return {
    metrics: [
      ["KEVs tracked", present(catalog?.count), UNAVAILABLE, "neutral", []],
      ["High-risk entries", String(vulnerabilities.length), UNAVAILABLE, "neutral", []],
      ["Ransomware linked", String(ransomware), UNAVAILABLE, "negative", []],
      ["Rejected locally", String(rejected.size), UNAVAILABLE, "positive", []],
    ],
    title: "CISA KEV Watchlist",
    meta: catalog ? `${catalog.stale ? "Stale cache" : "Live feed"} · fetched ${fetched}` : "Waiting for CISA KEV",
    columns: [
      { key: "id", label: "CVE ID", width: "1.4fr" },
      { key: "added", label: "Added", width: ".65fr" },
      { key: "due", label: "Remediate by", width: ".65fr" },
      { key: "ransomware", label: "Ransomware", width: ".7fr" },
      { key: "status", label: "Status", width: ".65fr" },
      { key: "policy", label: "Policy", width: ".6fr" },
    ],
    rows: vulnerabilities.map((item) => [
      [item.cve_id, [item.vendor, item.product].filter(Boolean).join(" · ") || "Product unavailable"],
      present(item.date_added),
      present(item.due_date),
      present(item.ransomware_use),
      rejected.has(item.cve_id)
        ? { badge: "Rejected", level: "muted" }
        : { badge: "High risk", level: item.ransomware_use === "Known" ? "critical" : "high" },
      {
        action: rejected.has(item.cve_id) ? "restore" : "reject",
        cveId: item.cve_id,
        label: rejected.has(item.cve_id) ? "Restore" : "Reject",
      },
    ]),
  };
}

// Matches the incident drawer's decision badge in App.jsx.
const VERDICT_LEVELS = { approved: "ok", rejected: "critical", pending: "muted" };

export function toFeedbackPage(catalog) {
  const recommendations = Array.isArray(catalog?.recommendations) ? catalog.recommendations : [];
  const byStatus = (status) => recommendations.filter((item) => item.status === status).length;
  const reviewed = recommendations.filter((item) => item.decision).length;
  const rate = recommendations.length
    ? `${Math.round((reviewed / recommendations.length) * 100)}%`
    : UNAVAILABLE;

  return {
    metrics: [
      ["Pending review", String(byStatus("pending")), UNAVAILABLE, "negative", []],
      ["Approved", String(byStatus("approved")), UNAVAILABLE, "neutral", []],
      ["Rejected", String(byStatus("rejected")), UNAVAILABLE, "positive", []],
      ["Reviewed", rate, UNAVAILABLE, "neutral", []],
    ],
    title: "Review Queue",
    meta: catalog
      ? `${reviewed} of ${recommendations.length} recommendations reviewed`
      : "Waiting for API",
    columns: [
      { key: "target", label: "Recommendation", width: "1.3fr" },
      { key: "analyst", label: "Analyst", width: ".7fr" },
      { key: "at", label: "Reviewed", width: ".5fr", align: "right" },
      { key: "scope", label: "Scope", width: ".6fr" },
      { key: "verdict", label: "Verdict", width: ".7fr" },
    ],
    rows: recommendations.map((item) => [
      [present(item.target), present(item.reason)],
      present(item.decision?.analyst),
      formatTimestamp(item.decision?.timestamp),
      present(item.scope),
      { badge: present(item.status), level: VERDICT_LEVELS[item.status] ?? "muted" },
    ]),
  };
}

function formatNumber(value) {
  if (!finiteNumber(value)) return present(value);
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

function formatMetricValue(metric) {
  const value = metric.value;
  switch (metric.unit) {
    case "bytes":
      return formatBytes(value);
    case "percent":
    case "%":
      return finiteNumber(value) ? `${formatNumber(value)}%` : UNAVAILABLE;
    case "milliseconds":
    case "ms":
      return finiteNumber(value) ? `${formatNumber(value)} ms` : UNAVAILABLE;
    default:
      return formatNumber(value);
  }
}

function formatDelta(metric) {
  const delta = metric.delta;
  if (!finiteNumber(delta)) return present(delta);

  const sign = delta > 0 ? "+" : "";
  const unit = metric.delta_unit ?? (metric.unit === "percent" || metric.unit === "%" ? "%" : "");
  return `${sign}${formatNumber(delta)}${unit === "milliseconds" ? " ms" : unit}`;
}

function fallbackSeries(fallback, metric, index) {
  if (typeof fallback === "function") return fallback(metric, index);
  if (Array.isArray(fallback)) {
    return Array.isArray(fallback[index]) ? fallback[index] : fallback;
  }
  if (fallback && typeof fallback === "object") {
    return fallback[metric.key] ?? fallback[metric.label] ?? [];
  }
  return [];
}

export function toMetricStrip(summary, sparkFallback) {
  let metrics = Array.isArray(summary) ? summary : summary?.metrics;
  if (!Array.isArray(metrics) && summary && typeof summary === "object") {
    metrics = SUMMARY_METRICS
      .filter(([key]) => finiteNumber(summary[key]))
      .map(([key, label]) => ({ key, label, value: summary[key] }));
  }
  if (!Array.isArray(metrics)) return [];

  return metrics.map((metric, index) => [
    present(metric.label ?? metric.name ?? metric.key),
    formatMetricValue(metric),
    formatDelta(metric),
    present(metric.tone ?? metric.trend_tone ?? "neutral"),
    fallbackSeries(sparkFallback, metric, index),
  ]);
}

function statusLabel(status) {
  return status?.overall_status ?? status?.status ?? null;
}

function egressLabel(appliance, status) {
  const explicit = appliance.egress ?? status?.egress;
  if (explicit !== undefined && explicit !== null && explicit !== "") return String(explicit);

  const allowed = appliance.cloud_egress_allowed ?? status?.cloud_egress_allowed;
  if (allowed === true) return "Allowed";
  if (allowed === false) return "Blocked";
  return UNAVAILABLE;
}

export function toSystemStatusView(status) {
  const source = status && typeof status === "object" ? status : {};
  const appliance = source.appliance && typeof source.appliance === "object" ? source.appliance : {};
  const gpu = appliance.gpu ?? source.gpu ?? {};
  const ingestion = source.ingestion ?? {};
  const model = source.model ?? {};
  const utilization = gpu.utilization_percent ?? source.gpu_utilization_percent;
  const memoryUsed = gpu.memory_used_bytes ?? source.gpu_memory_used_bytes;
  const memoryTotal = gpu.memory_total_bytes ?? source.gpu_memory_total_bytes;
  const rawStatus = statusLabel(source);

  return {
    appliance: {
      name: present(appliance.name ?? source.appliance_name),
      model: present(appliance.model ?? source.appliance_model),
      mode: present(appliance.mode ?? source.mode),
      egress: egressLabel(appliance, source),
      gpuUtilization: finiteNumber(utilization) ? utilization : null,
      gpuMemory: finiteNumber(memoryUsed) && finiteNumber(memoryTotal)
        ? `${formatBytes(memoryUsed)} / ${formatBytes(memoryTotal)}`
        : UNAVAILABLE,
      gpuMemoryLabel: gpu.memory_scope === "unified"
        ? "Unified"
        : gpu.memory_scope === "device"
          ? "VRAM"
          : "Memory",
      gpuObservedAt: formatTimestamp(gpu.observed_at, { includeDate: true }),
      gpuSource: present(gpu.source),
      gpuStatus: present(gpu.status),
    },
    footer: {
      status: present(rawStatus),
      healthy: rawStatus === "healthy" || rawStatus === "ok" || rawStatus === "operational"
        ? true
        : rawStatus === null || rawStatus === undefined || rawStatus === ""
          ? null
          : false,
      appliance: present(appliance.name ?? source.appliance_name),
      address: present(appliance.address ?? source.address),
      egress: egressLabel(appliance, source),
      ingestRate: finiteNumber(ingestion.events_per_second ?? source.events_per_second)
        ? ingestion.events_per_second ?? source.events_per_second
        : null,
      queueDepth: finiteNumber(ingestion.queue_depth ?? source.queue_depth)
        ? ingestion.queue_depth ?? source.queue_depth
        : null,
      activeModel: present(model.active_version ?? source.active_model),
      updatedAt: formatTimestamp(source.updated_at ?? source.generated_at, { includeDate: true }),
    },
  };
}
