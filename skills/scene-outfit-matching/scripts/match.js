#!/usr/bin/env node
"use strict";

const DEFAULT_API_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 90_000;

function normalizeBaseUrl(value) {
  const normalized = String(value || "").trim().replace(/\/+$/, "");
  if (!normalized) throw new Error("StyleCapture Product API URL is required");
  return normalized;
}

function normalizeRequest(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("request must be a JSON object");
  }
  const scene = typeof value.scene === "string" ? value.scene.trim() : "";
  const style = typeof value.style === "string" ? value.style.trim() : "";
  const weather = typeof value.weather === "string" ? value.weather.trim() : "";
  const formality =
    typeof value.formality === "string" ? value.formality.trim() : "";
  const comfort = typeof value.comfort === "string" ? value.comfort.trim() : "";
  const normalizeIds = (snakeName, camelName) => {
    const candidate = value[snakeName] ?? value[camelName] ?? [];
    if (!Array.isArray(candidate) || candidate.some((id) => typeof id !== "string")) {
      throw new TypeError(`request.${snakeName} must be an array of item ids`);
    }
    return candidate.map((id) => id.trim()).filter(Boolean);
  };
  const mustIncludeItemIds = normalizeIds(
    "must_include_item_ids",
    "mustIncludeItemIds",
  );
  const excludeItemIds = normalizeIds("exclude_item_ids", "excludeItemIds");
  const anchorItemId =
    typeof value.anchor_item_id === "string"
      ? value.anchor_item_id.trim()
      : typeof value.anchorItemId === "string"
        ? value.anchorItemId.trim()
        : "";
  if (!scene) {
    throw new TypeError("request.scene is required by the Product API");
  }
  return {
    scene,
    style: style || undefined,
    weather: weather || undefined,
    formality: formality || undefined,
    comfort: comfort || undefined,
    anchor_item_id: anchorItemId || undefined,
    must_include_item_ids: mustIncludeItemIds,
    exclude_item_ids: excludeItemIds,
  };
}

function sessionCookie(response) {
  const setCookie = response.headers.get("set-cookie") || "";
  const cookie = setCookie.split(";", 1)[0].trim();
  if (!cookie.includes("=")) throw new Error("Product API did not issue a session cookie");
  return cookie;
}

async function productApiError(response, fallback) {
  const payload = await response.json().catch(() => null);
  const message = payload?.error?.message;
  const code = payload?.error?.code;
  throw new Error(code ? `${code}: ${message || fallback}` : message || fallback);
}

function validateWorkflowTrace(trace, result) {
  if (!trace || typeof trace !== "object" || Array.isArray(trace)) {
    throw new Error("Product API returned an invalid outfit workflow trace");
  }
  if (
    typeof result.trace_id !== "string" ||
    trace.trace_id !== result.trace_id ||
    trace.request_id !== result.request_id
  ) {
    throw new Error("Product API returned a mismatched outfit workflow trace");
  }
  if (
    typeof trace.status !== "string" ||
    typeof trace.explanation_state !== "string" ||
    !Number.isInteger(trace.plan_count) ||
    !Array.isArray(trace.steps)
  ) {
    throw new Error("Product API returned an incomplete outfit workflow trace");
  }
  const hasInfrastructureKey = (value) => {
    if (!value || typeof value !== "object") return false;
    return Object.entries(value).some(([key, nested]) => {
      const normalized = key.toLowerCase();
      return (
        normalized.includes("prompt") ||
        normalized.includes("media") ||
        normalized.includes("provider") ||
        hasInfrastructureKey(nested)
      );
    });
  };
  if (hasInfrastructureKey(trace)) {
    throw new Error("Product API trace exposed infrastructure-only fields");
  }
  return trace;
}

async function matchOutfits(rawRequest, options = {}) {
  const request = normalizeRequest(rawRequest);
  const baseUrl = normalizeBaseUrl(
    options.baseUrl || process.env.STYLECAPTURE_API_URL || DEFAULT_API_URL,
  );
  const timeoutMs = Number(options.timeoutMs) || DEFAULT_TIMEOUT_MS;
  const signal = AbortSignal.timeout(Math.max(1, Math.min(timeoutMs, 180_000)));
  let cookie =
    String(options.sessionCookie || process.env.STYLECAPTURE_SESSION_COOKIE || "").trim();
  if (!cookie) {
    const session = await fetch(`${baseUrl}/v1/session`, {
      method: "POST",
      signal,
    });
    if (!session.ok) await productApiError(session, "无法建立私人衣橱会话");
    cookie = sessionCookie(session);
  }
  const response = await fetch(`${baseUrl}/v1/outfit-plans`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      cookie,
    },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok) await productApiError(response, "穿搭方案生成失败");
  const result = await response.json();
  if (!result || !Array.isArray(result.plans)) {
    throw new Error("Product API returned an invalid outfit response");
  }
  if (typeof result.trace_id !== "string" || typeof result.request_id !== "string") {
    throw new Error("Product API did not return a queryable workflow trace");
  }
  const traceResponse = await fetch(
    `${baseUrl}/v1/outfit-plans/traces/${encodeURIComponent(result.trace_id)}`,
    {
      headers: { cookie },
      signal,
    },
  );
  if (!traceResponse.ok) {
    await productApiError(traceResponse, "穿搭工作流记录查询失败");
  }
  const workflowTrace = validateWorkflowTrace(await traceResponse.json(), result);
  return { ...result, workflow_trace: workflowTrace };
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key.startsWith("--") || !value || value.startsWith("--")) {
      throw new Error(
        "Usage: node scripts/match.js --request '<json>' [--api-base-url URL] [--timeout-ms 90000]",
      );
    }
    args[key.slice(2)] = value;
    index += 1;
  }
  return args;
}

async function main(argv) {
  const args = parseArgs(argv);
  if (!args.request) throw new Error("--request is required");
  const result = await matchOutfits(JSON.parse(args.request), {
    baseUrl: args["api-base-url"],
    timeoutMs: args["timeout-ms"],
  });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}

module.exports = {
  DEFAULT_TIMEOUT_MS,
  matchOutfits,
  normalizeRequest,
  validateWorkflowTrace,
};
