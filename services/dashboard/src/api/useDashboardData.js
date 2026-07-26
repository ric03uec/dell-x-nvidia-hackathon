import { useEffect, useState } from "react";

import { getEvents, getFindings, getMetricsSummary, getSystemStatus } from "./client.js";

function usePolling(load, intervalMs, dependencies) {
  useEffect(() => {
    let controller = null;
    let inFlight = false;
    let active = true;

    async function poll() {
      if (!active || inFlight || document.hidden) return;
      inFlight = true;
      controller = new AbortController();
      try {
        await load(controller.signal);
      } finally {
        inFlight = false;
      }
    }

    function onVisibilityChange() {
      if (!document.hidden) poll();
    }

    poll();
    const timer = window.setInterval(poll, intervalMs);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      active = false;
      controller?.abort();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, dependencies);
}

export function useDashboardData(range) {
  const [status, setStatus] = useState(null);
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState(null);
  const [findings, setFindings] = useState(null);
  const [error, setError] = useState(null);
  const [stale, setStale] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  async function loadSummary(signal) {
    try {
      const [nextStatus, nextSummary] = await Promise.all([
        getSystemStatus({ signal }),
        getMetricsSummary(range, { signal }),
      ]);
      setStatus(nextStatus);
      setSummary(nextSummary);
      setError(null);
      setStale(false);
    } catch (nextError) {
      if (nextError.code !== "ABORTED") {
        setError(nextError);
        setStale(true);
      }
    }
  }

  async function loadActivity(signal) {
    try {
      const [nextEvents, nextFindings] = await Promise.all([
        getEvents({ signal }),
        getFindings({ signal }),
      ]);
      setEvents(nextEvents);
      setFindings(nextFindings);
      setError(null);
    } catch (nextError) {
      if (nextError.code !== "ABORTED") {
        setError(nextError);
        setStale(true);
      }
    }
  }

  usePolling(loadSummary, 30_000, [range, refreshKey]);
  usePolling(loadActivity, 5_000, [refreshKey]);

  return {
    error,
    events,
    findings,
    refresh: () => setRefreshKey((value) => value + 1),
    stale,
    status,
    summary,
  };
}
