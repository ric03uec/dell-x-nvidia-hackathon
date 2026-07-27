const API_BASE = "/api/v1";
const SCHEMA_VERSION = "1.0";

export class ApiError extends Error {
  constructor(message, { code, status = null, details = null, cause } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code || "API_ERROR";
    this.status = status;
    this.details = details;

    if (cause !== undefined) {
      this.cause = cause;
    }
  }
}

function assertSupportedSchema(payload) {
  if (payload === null || typeof payload !== "object") {
    throw new ApiError("API response is not a versioned object", {
      code: "INVALID_RESPONSE",
      details: payload,
    });
  }

  if (Array.isArray(payload)) {
    payload.forEach(assertSupportedSchema);
    return;
  }

  const version = payload.schema_version;
  if (typeof version !== "string") {
    throw new ApiError("API response is missing schema_version", {
      code: "INVALID_RESPONSE",
      details: payload,
    });
  }

  if (!/^1(?:\.|$)/.test(version)) {
    throw new ApiError(`Unsupported API schema version: ${version}`, {
      code: "UNSUPPORTED_SCHEMA_VERSION",
      details: { expected_major: 1, received: version },
    });
  }
}

async function parseResponse(response) {
  if (response.status === 204 || response.status === 205) {
    return null;
  }

  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch (cause) {
    throw new ApiError("API returned invalid JSON", {
      code: "INVALID_JSON",
      status: response.status,
      cause,
    });
  }
}

function errorMessage(payload, response) {
  if (payload && typeof payload === "object") {
    if (typeof payload.message === "string") return payload.message;
    if (typeof payload.detail === "string") return payload.detail;
    if (payload.error && typeof payload.error.message === "string") return payload.error.message;
  }

  return `API request failed with status ${response.status}`;
}

export async function request(path, { method = "GET", body, signal } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (cause) {
    if (cause && cause.name === "AbortError") {
      throw new ApiError("API request was aborted", { code: "ABORTED", cause });
    }
    throw new ApiError("Unable to reach the API", { code: "NETWORK_ERROR", cause });
  }

  const payload = await parseResponse(response);
  if (!response.ok) {
    throw new ApiError(errorMessage(payload, response), {
      code: "HTTP_ERROR",
      status: response.status,
      details: payload,
    });
  }

  if (payload !== null) {
    assertSupportedSchema(payload);
  }
  return payload;
}

function queryString(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, value);
    }
  });
  const value = query.toString();
  return value ? `?${value}` : "";
}

export function getSystemStatus(options) {
  return request("/system-status", options);
}

export function getMetricsSummary(range, options) {
  return request(`/metrics/summary${queryString({ range })}`, options);
}

export function getEvents(options) {
  return request("/events", options);
}

export function getFindings(options) {
  return request("/findings", options);
}

export function getVulnerabilities(options) {
  return request("/vulnerabilities", options);
}

export function rejectVulnerability(cveId, options) {
  const { analyst = "local-analyst", ...requestOptions } = options ?? {};
  return request(`/vulnerability-policies/${encodeURIComponent(cveId)}`, {
    ...requestOptions,
    method: "POST",
    body: {
      schema_version: SCHEMA_VERSION,
      cve_id: cveId,
      disposition: "rejected",
      analyst,
    },
  });
}

export function restoreVulnerability(cveId, options) {
  return request(`/vulnerability-policies/${encodeURIComponent(cveId)}`, {
    ...options,
    method: "DELETE",
  });
}

export function getFinding(id, options) {
  return request(`/findings/${encodeURIComponent(id)}`, options);
}

export function startFindingInvestigation(id, options) {
  return request(`/findings/${encodeURIComponent(id)}/investigate`, {
    ...options,
    method: "POST",
    body: { schema_version: SCHEMA_VERSION },
  });
}

export function getRecommendations(status, options) {
  return request(`/recommendations${queryString({ status })}`, options);
}

export function submitRecommendationDecision(id, decision, options) {
  const { analyst = "local-analyst", ...requestOptions } = options ?? {};
  return request(`/recommendations/${encodeURIComponent(id)}/decision`, {
    ...requestOptions,
    method: "POST",
    body: {
      schema_version: SCHEMA_VERSION,
      recommendation_id: id,
      decision,
      analyst,
      timestamp: new Date().toISOString(),
    },
  });
}

export function addRecommendationNote(id, note, options) {
  const { analyst = "local-analyst", ...requestOptions } = options ?? {};
  return request(`/recommendations/${encodeURIComponent(id)}/notes`, {
    ...requestOptions,
    method: "POST",
    body: { schema_version: SCHEMA_VERSION, analyst, note },
  });
}

export function getEnforcementResults(findingId, options) {
  return request(`/enforcement-results${queryString({ finding_id: findingId })}`, options);
}
