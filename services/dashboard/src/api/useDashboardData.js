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
  const [summaryError, setSummaryError] = useState(null);
  const [activityError, setActivityError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  async function loadSummary(signal) {
    const [statusResult, summaryResult] = await Promise.allSettled([
      getSystemStatus({ signal }),
      getMetricsSummary(range, { signal }),
    ]);
    if (statusResult.status === "fulfilled") setStatus(statusResult.value);
    if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    const nextError = [statusResult, summaryResult]
      .find((result) => result.status === "rejected" && result.reason.code !== "ABORTED");
    setSummaryError(nextError?.reason ?? null);
  }

  async function loadActivity(signal) {
    const [eventsResult, findingsResult] = await Promise.allSettled([
      getEvents({ signal }),
      getFindings({ signal }),
    ]);
    if (eventsResult.status === "fulfilled") setEvents(eventsResult.value);
    if (findingsResult.status === "fulfilled") setFindings(findingsResult.value);
    const nextError = [eventsResult, findingsResult]
      .find((result) => result.status === "rejected" && result.reason.code !== "ABORTED");
    setActivityError(nextError?.reason ?? null);
  }

  usePolling(loadSummary, 30_000, [range, refreshKey]);
  usePolling(loadActivity, 5_000, [refreshKey]);

  const error = activityError ?? summaryError;
  return {
    error,
    events,
    findings,
    refresh: () => setRefreshKey((value) => value + 1),
    stale: error !== null,
    status,
    summary,
  };
}
