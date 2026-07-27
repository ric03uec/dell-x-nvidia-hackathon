import React, { useEffect, useMemo, useRef, useState } from "react";

import {
  getEnforcementResults,
  getFinding,
  getRecommendations,
  rejectVulnerability,
  restoreVulnerability,
  startFindingInvestigation,
  submitRecommendationDecision,
  toMetricStrip,
  toCvePage,
  toFeedbackPage,
  toRiskEvents,
  toSystemStatusView,
} from "./api/index.js";
import { useDashboardData } from "./api/useDashboardData.js";
import { demoPageData } from "./demoData.js";

const DEMO_PAGES_ENABLED = import.meta.env.VITE_ENABLE_DEMO_PAGES !== "false";

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
      { id: "events", label: "Live Events", icon: "activity" },
      { id: "cve", label: "CVE Intelligence", icon: "shield" },
      { id: "feedback", label: "Analyst Feedback", icon: "review" },
    ],
  },
  ...(DEMO_PAGES_ENABLED
    ? [{
        label: "Inventory",
        items: [
          { id: "assets", label: "Asset Discovery", icon: "server" },
          { id: "models", label: "Model Registry", icon: "layers" },
        ],
      }]
    : []),
];

const pageMeta = {
  dashboard: ["Security Operations", "Exfiltration protection", "local first"],
  events: ["Live Events", "Event stream", "local inference"],
  cve: ["CVE Intelligence", "CISA KEV", "live feed"],
  assets: ["Asset Discovery", "Network inventory", "demo data"],
  models: ["Model Registry", "Detection models", "demo data"],
  feedback: ["Analyst Feedback", "Review queue", "local first"],
};

const ranges = ["1H", "4H", "1D", "1W", "1M"];

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
  const [activePage, setActivePage] = useState("dashboard");
  const [range, setRange] = useState("1D");
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "dark");
  const [incident, setIncident] = useState(null);
  const [decisionPending, setDecisionPending] = useState(false);
  const [cvePolicyPending, setCvePolicyPending] = useState(null);
  const [title, scope, context] = pageMeta[activePage];
  const needle = query.trim().toLowerCase();
  const live = useDashboardData(range);
  const liveEvents = useMemo(() => {
    return toRiskEvents(live.events).reverse();
  }, [live.events]);
  const overviewMetrics = useMemo(() => {
    return toMetricStrip(live.summary).slice(0, 4);
  }, [live.summary]);
  const system = useMemo(() => toSystemStatusView(live.status), [live.status]);
  const cvePage = useMemo(() => toCvePage(live.vulnerabilities), [live.vulnerabilities]);
  const feedbackPage = useMemo(() => toFeedbackPage(live.recommendations), [live.recommendations]);
  const dataUnavailable = !live.status || !live.summary || !live.events;

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

  async function openIncident(findingId) {
    if (!findingId) {
      notify("No incident is linked to this event");
      return;
    }
    setIncident({ findingId, loading: true });
    try {
      const [findingResponse, recommendationsResponse, enforcementResponse] = await Promise.all([
        getFinding(findingId),
        getRecommendations(),
        getEnforcementResults(findingId),
      ]);
      const finding = findingResponse.finding;
      const recommendation = recommendationsResponse.recommendations?.find(
        (item) => item.finding_id === findingId,
      ) ?? null;
      setIncident({
        enforcement: enforcementResponse.enforcement_results ?? [],
        finding,
        findingId,
        loading: false,
        recommendation,
      });
      if (finding.investigation?.status === "pending") {
        try {
          const investigationResponse = await startFindingInvestigation(findingId);
          setIncident((current) => current?.findingId === findingId ? {
            ...current,
            finding: {
              ...current.finding,
              investigation: investigationResponse.investigation,
              investigation_status: investigationResponse.investigation.status,
            },
          } : current);
        } catch (error) {
          const failedInvestigation = error.details?.investigation ?? {
            status: "failed",
            summary: null,
            served_model: finding.investigation.served_model,
          };
          setIncident((current) => current?.findingId === findingId ? {
            ...current,
            finding: {
              ...current.finding,
              investigation: failedInvestigation,
              investigation_status: failedInvestigation.status,
            },
          } : current);
        }
      }
    } catch (error) {
      setIncident({ error: error.message, findingId, loading: false });
    }
  }

  async function decideRecommendation(decision) {
    const recommendation = incident?.recommendation;
    if (!recommendation || decisionPending) return;
    setDecisionPending(true);
    try {
      const response = await submitRecommendationDecision(
        recommendation.recommendation_id,
        decision,
      );
      const enforcementResponse = await getEnforcementResults(incident.findingId);
      setIncident((current) => ({
        ...current,
        enforcement: enforcementResponse.enforcement_results ?? [],
        recommendation: {
          ...current.recommendation,
          decision: response.decision,
          status: response.decision.decision,
        },
      }));
      live.refresh();
      notify(`Recommendation ${response.decision.decision}`);
    } catch (error) {
      notify(error.message);
    } finally {
      setDecisionPending(false);
    }
  }

  async function changeCvePolicy(action, cveId) {
    if (cvePolicyPending) return;
    setCvePolicyPending(cveId);
    try {
      if (action === "reject") await rejectVulnerability(cveId);
      else await restoreVulnerability(cveId);
      live.refresh();
      notify(`${cveId} ${action === "reject" ? "added to reject policy" : "restored"}`);
    } catch (error) {
      notify(error.message);
    } finally {
      setCvePolicyPending(null);
    }
  }

  return (
    <div className="app">
      <Sidebar activePage={activePage} onNavigate={setActivePage} status={system.appliance} />

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
            <button
              className="icon-button"
              onClick={() => {
                live.refresh();
                notify("Refresh requested");
              }}
              title="Refresh"
              type="button"
            >
              <Glyph name="refresh" />
            </button>
            <button
              className="icon-button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              type="button"
            >
              <Glyph name={theme === "dark" ? "sun" : "moon"} />
            </button>
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
            <span className="chip">source:<b>ingestion</b></span>
            {DEMO_PAGES_ENABLED ? <span className="chip chip-warn">demo pages</span> : null}
            <span className={`chip ${live.stale || dataUnavailable ? "chip-warn" : "chip-ok"}`}>
              <i /> {live.stale ? "Stale data" : dataUnavailable ? "Waiting for API" : system.appliance.mode}
            </span>
          </div>
          <div className="toolbar-right">
            <span className="muted">Auto-refresh 30s</span>
          </div>
        </div>

        <main className="content">
          {activePage === "dashboard" ? (
            <Dashboard
              findings={live.findings?.findings ?? []}
              needle={needle}
              notify={notify}
              range={range}
              system={system}
              theme={theme}
              events={liveEvents}
              metrics={overviewMetrics}
              onOpenIncident={openIncident}
            />
          ) : activePage === "events" ? (
            <LiveEventsPage events={liveEvents} metrics={overviewMetrics} needle={needle} onOpenIncident={openIncident} />
          ) : activePage === "cve" ? (
            <DataPage
              data={cvePage}
              error={live.vulnerabilityError}
              needle={needle}
              notify={notify}
              onAction={changeCvePolicy}
              pendingAction={cvePolicyPending}
            />
          ) : activePage === "feedback" ? (
            <DataPage data={feedbackPage} error={live.error} needle={needle} notify={notify} />
          ) : DEMO_PAGES_ENABLED && demoPageData[activePage] ? (
            <DataPage data={demoPageData[activePage]} needle={needle} notify={notify} />
          ) : null}
        </main>

        <footer className="statusbar">
          <span>
            <i className={system.footer.healthy ? "live" : "stale"} /> {system.footer.appliance} · {system.footer.address} · Egress {system.footer.egress}
          </span>
          <span className="muted">
            Ingest {system.footer.ingestRate ?? "Unavailable"} evt/s · Queue {system.footer.queueDepth ?? "Unavailable"} · Model {system.footer.activeModel} · Updated {system.footer.updatedAt}
          </span>
        </footer>
      </div>

      {toast && <div className="toast" role="status">{toast}</div>}
      {incident && (
        <IncidentDrawer
          incident={incident}
          onClose={() => setIncident(null)}
          onDecision={decideRecommendation}
          pending={decisionPending}
        />
      )}
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

function Sidebar({ activePage, onNavigate, status }) {
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
        <div className="appliance-row"><span>Appliance</span><b>{status.model}</b></div>
        <div className="appliance-row"><span>Mode</span><b className="ok">{status.mode}</b></div>
        <div className="appliance-row"><span>Egress</span><b>{status.egress}</b></div>
        <div className="meter"><i style={{ width: `${status.gpuUtilization ?? 0}%` }} /></div>
        <p title={`${status.gpuStatus} · ${status.gpuSource} · ${status.gpuObservedAt}`}>
          GPU {status.gpuUtilization === null ? "Unavailable" : `${status.gpuUtilization}%`} · {status.gpuMemoryLabel} {status.gpuMemory}
        </p>
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
  if (!Array.isArray(points) || points.length < 2) return null;
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
            {delta === "Unavailable" ? (
              <span>No comparison recorded</span>
            ) : (
              <>{delta.startsWith("+") ? "▲" : delta.startsWith("-") ? "▼" : "–"} {delta}<span> vs. prev period</span></>
            )}
          </p>
        </div>
      ))}
    </section>
  );
}

function Dashboard({ findings, notify, range, system, theme, needle, events, metrics, onOpenIncident }) {
  const visibleFindings = findings.filter((finding) => matches(finding, needle));
  const assessedEvents = events.filter((event) => typeof event.risk === "number");
  const visibleEvents = assessedEvents.filter((event) => matches(event, needle));

  return (
    <>
      <MetricStrip metrics={metrics} />

      <div className="grid grid-a">
        <Panel
          action={<span className="panel-badge">{range}</span>}
          className="chart-panel"
          meta="Rolling event-assessment buckets"
          title="Observed risk trend"
        >
          <RiskTrendChart events={events} theme={theme} />
        </Panel>

        <Panel
          action={<CountBadge shown={visibleFindings.length} total={findings.length} />}
          meta="Persisted detector findings"
          title="Active findings"
        >
          <table className="grid-table compact">
            <thead>
              <tr>
                <th className="num w-cvss">Risk</th>
                <th>Finding</th>
                <th className="num w-asset">Severity</th>
              </tr>
            </thead>
            <tbody>
              {visibleFindings.length === 0 && <EmptyRow span={3} />}
              {visibleFindings.map((finding) => {
                const open = () => onOpenIncident(finding.finding_id);
                return (
                  <tr key={finding.finding_id} onClick={open} onKeyDown={activateOnKey(open)} tabIndex={0}>
                    <td className="num"><span className={`score ${finding.severity}`}>{finding.risk_score}</span></td>
                    <td>
                      <span className="cell-lead">{finding.finding_id}</span>
                      <span className="cell-sub">{finding.summary || "No summary recorded"}</span>
                    </td>
                    <td className="num mono">{finding.severity}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      </div>

      <div className="grid grid-b">
        <Panel meta="Measured by the local runtime" title="GB10 service status">
          <div className="recommendation-card">
            <dl>
              <div><dt>Appliance</dt><dd>{system.appliance.name}</dd></div>
              <div><dt>GPU</dt><dd>{system.appliance.gpuStatus}</dd></div>
              <div><dt>Memory</dt><dd>{system.appliance.gpuMemory}</dd></div>
              <div><dt>Model</dt><dd>{system.footer.activeModel}</dd></div>
              <div><dt>Ingestion</dt><dd>{system.footer.ingestRate ?? "Unavailable"} evt/s</dd></div>
            </dl>
          </div>
        </Panel>

        <Panel
          action={<CountBadge shown={visibleEvents.length} total={assessedEvents.length} />}
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
                const open = () => event.findingId
                  ? onOpenIncident(event.findingId)
                  : notify(`${event.user} → ${event.destination}`);
                return (
                  <tr key={event.id ?? event.time} onClick={open} onKeyDown={activateOnKey(open)} tabIndex={0}>
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

function LiveEventsPage({ events, metrics, needle, onOpenIncident }) {
  const visible = events.filter((event) => matches(event, needle));

  return (
    <>
      <MetricStrip metrics={metrics} />
      <Panel
        action={<CountBadge shown={visible.length} total={events.length} />}
        className="table-panel"
        meta="Canonical events with their latest assessment"
        title="Live Event Stream"
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
            {visible.length === 0 && <EmptyRow span={5} />}
            {visible.map((event) => {
              const open = () => onOpenIncident(event.findingId);
              return (
                <tr key={event.id ?? event.time} onClick={open} onKeyDown={activateOnKey(open)} tabIndex={0}>
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
    </>
  );
}

function IncidentDrawer({ incident, onClose, onDecision, pending }) {
  const finding = incident.finding;
  const recommendation = incident.recommendation;
  const decision = recommendation?.decision?.decision
    ?? (["approved", "rejected"].includes(recommendation?.status) ? recommendation.status : null);
  const decided = decision === "approved" || decision === "rejected";

  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside
        aria-label="Incident detail"
        aria-modal="true"
        className="incident-drawer"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <header className="drawer-head">
          <div>
            <span className="drawer-eyebrow">Incident investigation</span>
            <h2>{finding?.title ?? incident.findingId}</h2>
          </div>
          <button aria-label="Close incident" className="drawer-close" onClick={onClose} type="button">×</button>
        </header>

        {incident.loading && <div className="drawer-message">Loading deterministic evidence…</div>}
        {incident.error && <div className="drawer-message error">{incident.error}</div>}

        {finding && (
          <div className="drawer-content">
            <div className="incident-summary">
              <span className={`score ${finding.severity}`}>{finding.risk_score}</span>
              <div>
                <strong>{finding.severity} risk</strong>
                <p>{finding.summary}</p>
              </div>
            </div>

            <DrawerSection meta={`${finding.timeline?.length ?? 0} correlated actions`} title="Cross-action timeline">
              <table className="grid-table compact drawer-table">
                <thead>
                  <tr><th>Time</th><th>Action</th><th>Destination</th></tr>
                </thead>
                <tbody>
                  {finding.timeline?.map((event) => (
                    <tr key={event.event_id}>
                      <td className="mono dim">{event.timestamp?.slice(11, 19) ?? "Unavailable"}</td>
                      <td>
                        <span className="cell-lead">{event.action}</span>
                        <span className="cell-sub">{event.source_type}</span>
                      </td>
                      <td className="truncate dim">{event.destination}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DrawerSection>

            <DrawerSection meta="Deterministic before model prose" title="Risk contributions">
              <div className="evidence-list">
                {finding.evidence?.map((item) => (
                  <div className="evidence-row" key={item.code ?? item.detector}>
                    <span className="evidence-score mono">+{item.score_contribution ?? item.points}</span>
                    <div>
                      <strong>{item.label ?? item.description ?? item.detector}</strong>
                      <small>{(item.event_ids ?? finding.event_ids ?? []).join(" · ")}</small>
                    </div>
                  </div>
                ))}
              </div>
            </DrawerSection>

            <DrawerSection
              meta={finding.investigation?.served_model ?? "Unavailable"}
              title="Local security-agent analysis"
            >
              <div className="investigation-copy">
                <span className={`badge ${finding.investigation?.status === "completed" ? "ok" : "muted"}`}>
                  <i />{finding.investigation?.status ?? "unavailable"}
                </span>
                <p>{finding.investigation?.summary ?? "Deterministic evidence remains available while local inference is unavailable."}</p>
              </div>
            </DrawerSection>

            <DrawerSection meta="Dashboard records a decision only" title="Policy recommendation">
              {recommendation ? (
                <div className="recommendation-card">
                  <dl>
                    <div><dt>Action</dt><dd className="mono">{recommendation.action_type}</dd></div>
                    <div><dt>Target</dt><dd className="mono">{recommendation.target}</dd></div>
                    <div><dt>Scope</dt><dd>{recommendation.scope}</dd></div>
                  </dl>
                  <p>{recommendation.reason}</p>
                  {decided ? (
                    <span className={`badge ${decision === "approved" ? "ok" : "critical"}`}>
                      <i />{decision}
                    </span>
                  ) : (
                    <div className="decision-actions">
                      <button className="ghost-button" disabled={pending} onClick={() => onDecision("rejected")} type="button">Reject</button>
                      <button className="primary-button" disabled={pending} onClick={() => onDecision("approved")} type="button">
                        {pending ? "Recording…" : "Approve"}
                      </button>
                    </div>
                  )}
                </div>
              ) : <div className="drawer-message">No recommendation has been issued.</div>}
            </DrawerSection>

            <DrawerSection meta="Approval is not enforcement" title="Enforcement audit">
              {incident.enforcement?.length ? (
                <div className="enforcement-list">
                  {incident.enforcement.map((result) => (
                    <div className="enforcement-row" key={result.enforcement_result_id}>
                      <span className={`badge ${result.status === "failed" ? "critical" : "ok"}`}><i />{result.status}</span>
                      <span className="mono dim">
                        {result.enforcement_point ?? "Unavailable"} · {result.observed_at?.slice(11, 19) ?? result.policy_version ?? "Unavailable"}
                      </span>
                    </div>
                  ))}
                </div>
              ) : <div className="drawer-message">No enforcement action has been recorded.</div>}
            </DrawerSection>
          </div>
        )}
      </aside>
    </div>
  );
}

function DrawerSection({ children, meta, title }) {
  return (
    <section className="drawer-section">
      <header><h3>{title}</h3><span>{meta}</span></header>
      {children}
    </section>
  );
}

function DataPage({ data, error, notify, needle, onAction, pendingAction }) {
  const visible = data.rows.filter((row) => matches(row, needle));
  const total = data.columns.reduce((sum, item) => sum + parseFloat(item.width), 0);

  return (
    <>
      <MetricStrip metrics={data.metrics} />
      {error && <div className="drawer-message error">Live vulnerability feed unavailable: {error.message}</div>}
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
                    <Cell
                      align={data.columns[cellIndex].align}
                      cell={cell}
                      key={data.columns[cellIndex].key}
                      onAction={onAction}
                      pendingAction={pendingAction}
                    />
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

function Cell({ cell, align, onAction, pendingAction }) {
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
    if (cell.action) {
      return (
        <td>
          <button
            className="ghost-button cve-policy-button"
            disabled={Boolean(pendingAction)}
            onClick={(event) => {
              event.stopPropagation();
              onAction?.(cell.action, cell.cveId);
            }}
            type="button"
          >
            {pendingAction === cell.cveId ? "Saving…" : cell.label}
          </button>
        </td>
      );
    }
    return <td><span className={`badge ${cell.level}`}><i />{cell.badge}</span></td>;
  }
  return <td className={`${align === "right" ? "num mono" : ""}`}>{cell}</td>;
}

function RiskMeter({ risk }) {
  if (typeof risk !== "number") return <span className="badge muted"><i />Pending</span>;
  const tone = risk >= 80 ? "critical" : risk >= 60 ? "high" : risk >= 40 ? "medium" : "ok";
  return (
    <span className={`risk ${tone}`}>
      <span className="risk-track"><i style={{ width: `${risk}%` }} /></span>
      <b className="mono">{risk}</b>
    </span>
  );
}

function RiskTrendChart({ events, theme }) {
  const canvasRef = useRef(null);
  const scores = useMemo(
    () => events
      .filter((event) => typeof event.risk === "number")
      .slice()
      .reverse()
      .map((event) => event.risk),
    [events],
  );
  const live = useMemo(() => {
    const bucketSize = Math.max(1, Math.ceil(scores.length / 24));
    const buckets = [];
    for (let index = 0; index < scores.length; index += bucketSize) {
      const bucket = scores.slice(index, index + bucketSize);
      buckets.push(bucket.reduce((sum, value) => sum + value, 0) / bucket.length);
    }
    return buckets;
  }, [scores]);
  const baseline = useMemo(
    () => live.map((_, index) => {
      const window = live.slice(Math.max(0, index - 4), index + 1);
      return window.reduce((sum, value) => sum + value, 0) / window.length;
    }),
    [live],
  );

  useEffect(() => {
    if (live.length < 2) return undefined;
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
      context.fillStyle = textColor;
      context.textAlign = "left";
      context.fillText("oldest", padLeft, height - padBottom / 2 - 2);
      context.textAlign = "right";
      context.fillText("latest", width - padRight, height - padBottom / 2 - 2);

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
  }, [live, baseline, theme]);

  if (live.length < 2) {
    return <div className="drawer-message">Risk trend requires at least two assessed events.</div>;
  }

  const peak = Math.round(Math.max(...scores));
  const average = (scores.reduce((sum, value) => sum + value, 0) / scores.length).toFixed(1);

  return (
    <div className="chart">
      <div className="chart-body"><canvas ref={canvasRef} /></div>
      <div className="legend">
        <span><i className="live" />Bucketed event risk</span>
        <span><i className="baseline" />Observed rolling mean</span>
        <span className="legend-right mono">peak {peak} · avg {average}</span>
      </div>
    </div>
  );
}

export default App;
