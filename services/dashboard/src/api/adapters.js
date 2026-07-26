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
