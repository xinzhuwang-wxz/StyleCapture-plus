"use strict";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 90_000;
const sessionCookies = new Map();

function env(value, fallback) {
  return String(value || "").trim() || fallback;
}

function hasInfraKey(value) {
  if (!value || typeof value !== "object") {
    return false;
  }
  if (Array.isArray(value)) {
    return value.some(hasInfraKey);
  }
  return Object.entries(value).some(([key, nested]) => {
    const lower = String(key).toLowerCase();
    return lower.includes("prompt") || lower.includes("media") || lower.includes("provider") || hasInfraKey(nested);
  });
}

function parseIntTimeout(raw) {
  const parsed = Number(raw);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }
  return DEFAULT_TIMEOUT_MS;
}

async function parseError(response) {
  const payload = await response.json().catch(() => null);
  return {
    status: response.status,
    code: payload?.error?.code,
    message: payload?.error?.message || `HTTP ${response.status}`,
  };
}

async function createSession(baseUrl, timeoutMs) {
  const signal = AbortSignal.timeout(timeoutMs);
  const response = await fetch(`${baseUrl}/v1/session`, {
    method: "POST",
    signal,
  });
  if (!response.ok) {
    const error = await parseError(response);
    throw new Error(`Create session failed: ${error.code || error.message}`);
  }
  const cookie = response.headers.get("set-cookie");
  if (!cookie) {
    throw new Error("Session response does not include Set-Cookie");
  }
  return cookie.split(";")[0].trim();
}

function formatRequest(vars) {
  const scene = typeof vars?.scene === "string" ? vars.scene.trim() : "";
  const style = typeof vars?.style === "string" ? vars.style.trim() : undefined;
  const weather = typeof vars?.weather === "string" ? vars.weather.trim() : undefined;
  const formality = typeof vars?.formality === "string" ? vars.formality.trim() : undefined;
  const comfort = typeof vars?.comfort === "string" ? vars.comfort.trim() : undefined;
  return {
    scene,
    style: style || undefined,
    weather: weather || undefined,
    formality: formality || undefined,
    comfort: comfort || undefined,
    anchor_item_id: undefined,
    must_include_item_ids: [],
    exclude_item_ids: [],
  };
}

async function callProductApi(context) {
  const testOpts = context?.test?.options || context?.options || {};
  const vars = context?.vars || {};
  const baseUrl = env(
    process.env.STYLECAPTURE_API_URL || context?.config?.baseUrl,
    DEFAULT_BASE_URL,
  ).replace(/\/$/, "");
  const timeoutMs = parseIntTimeout(context?.config?.requestTimeoutMs || process.env.STYLECAPTURE_REQUEST_TIMEOUT_MS);
  const expectedErrorCode = typeof vars.expect_error_code === "string" ? vars.expect_error_code.trim() : null;
  const expectFailure =
    testOpts.expectFailure === true ||
    testOpts.expectFailure === "true" ||
    Boolean(expectedErrorCode);

  const request = formatRequest(vars);

  const signal = AbortSignal.timeout(timeoutMs);
  let cookie = env(process.env.STYLECAPTURE_SESSION_COOKIE, null) || sessionCookies.get(baseUrl);
  if (!cookie) {
    cookie = await createSession(baseUrl, timeoutMs);
    sessionCookies.set(baseUrl, cookie);
  }

  const response = await fetch(`${baseUrl}/v1/outfit-plans`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      Cookie: cookie,
    },
    body: JSON.stringify(request),
    signal,
  });

  if (expectFailure) {
    if (response.ok) {
      throw new Error(`Expected failure, but got HTTP ${response.status}`);
    }
    const error = await parseError(response);
    if (expectedErrorCode && error.code !== expectedErrorCode) {
      throw new Error(`Expected error code ${expectedErrorCode}, got ${error.code || "<none>"}`);
    }
    return {
      output: JSON.stringify({
        scenario: request.scene,
        scenario_passed: false,
        expected: expectedErrorCode,
        actual_code: error.code,
        status: error.status,
        message: error.message,
      }),
    };
  }

  if (!response.ok) {
    const error = await parseError(response);
    throw new Error(`Scene matching failed (${error.status}): ${error.code || error.message}`);
  }

  const result = await response.json();
  if (!result || !Array.isArray(result.plans)) {
    throw new Error("Invalid /v1/outfit-plans response shape");
  }
  if (result.plans.length < 1) {
    throw new Error("Expected at least one outfit plan from smoke query");
  }
  if (typeof result.trace_id !== "string" || typeof result.request_id !== "string") {
    throw new Error("Missing trace/request identifiers in outfit response");
  }

  const traceResponse = await fetch(
    `${baseUrl}/v1/outfit-plans/traces/${encodeURIComponent(result.trace_id)}`,
    {
      headers: {
        Cookie: cookie,
      },
      signal,
    },
  );
  if (!traceResponse.ok) {
    const error = await parseError(traceResponse);
    throw new Error(`Trace fetch failed (${error.status}): ${error.code || error.message}`);
  }

  const workflowTrace = await traceResponse.json();
  const trace = workflowTrace;
  if (trace.trace_id !== result.trace_id) {
    throw new Error("Trace id mismatch in workflow trace response");
  }
  if (trace.request_id !== result.request_id) {
    throw new Error("Request id mismatch in workflow trace response");
  }
  if (typeof trace.plan_count !== "number" || trace.plan_count < 1) {
    throw new Error(`Invalid plan_count in workflow trace: ${trace.plan_count}`);
  }
  if (!Array.isArray(trace.steps) || trace.steps.length < 3) {
    throw new Error("Workflow trace should expose at least 3 steps");
  }
  if (hasInfraKey(trace)) {
    throw new Error("Workflow trace contains infrastructure-only fields");
  }

  return {
    output: JSON.stringify({
      scenario: request.scene,
      scenario_passed: true,
      request_id: result.request_id,
      trace_id: result.trace_id,
      plan_count: result.plans.length,
      trace_plan_count: trace.plan_count,
      trace_status: trace.status,
      explanation_state: trace.explanation_state,
      capability_alias: trace.capability_alias,
      model_version: trace.model_version,
    }),
  };
}

export default class StyleCaptureProductApiProvider {
  constructor(options = {}) {
    this.providerId = options.id || "stylecapture-product-api";
    this.config = options.config || {};
  }

  id() {
    return this.providerId;
  }

  async callApi(prompt, context) {
    try {
      return await callProductApi({
        ...context,
        config: {
          ...this.config,
          ...context?.config,
        },
      });
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : String(error),
        output: JSON.stringify({ scenario_failed: true, error: String(error) }),
      };
    }
  }
}
