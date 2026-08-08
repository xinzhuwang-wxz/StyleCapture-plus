#!/usr/bin/env node
// Generate the two presentation assets for each Item in one workflow.
"use strict";

const { randomUUID } = require("node:crypto");

const DEFAULT_API_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 90_000;

function normalizeBaseUrl(value) {
  const normalized = String(value || "").trim().replace(/\/+$/, "");
  if (!normalized) throw new Error("StyleCapture Product API URL is required");
  return normalized;
}

function normalizeLookId(value) {
  const lookId = String(value || "").trim();
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(lookId)) {
    throw new TypeError("lookId must be a UUID");
  }
  return lookId;
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

function assertItemPresentation(presentation, expectedKind) {
  if (!presentation || typeof presentation !== "object" || typeof presentation.id !== "string") {
    throw new Error("Product API returned an invalid item presentation");
  }
  if (presentation.kind !== expectedKind) {
    throw new Error(`Product API returned ${presentation.kind || "an unknown kind"}, expected ${expectedKind}`);
  }
  return presentation;
}

async function ensureSession(baseUrl, options, signal) {
  const provided = String(options.sessionCookie || process.env.STYLECAPTURE_SESSION_COOKIE || "").trim();
  if (provided) return provided;
  const response = await fetch(`${baseUrl}/v1/session`, { method: "POST", signal });
  if (!response.ok) await productApiError(response, "无法建立私人会话");
  return sessionCookie(response);
}

async function requestItemPresentation(itemId, kind, context) {
  const slug = kind === "pixel_item" ? "pixel" : "flat-lay";
  const response = await fetch(`${context.baseUrl}/v1/items/${encodeURIComponent(itemId)}/presentations/${slug}`, {
    method: "POST",
    headers: { "idempotency-key": randomUUID(), cookie: context.cookie },
    signal: context.signal,
  });
  if (!response.ok) await productApiError(response, `${kind} creation failed`);
  const presentation = assertItemPresentation(await response.json(), kind);
  if (!context.wait) return presentation;
  while (!new Set(["succeeded", "failed"]).has(presentation.status)) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    const latest = await fetch(`${context.baseUrl}/v1/item-presentations/${encodeURIComponent(presentation.id)}`, {
      headers: { cookie: context.cookie }, signal: context.signal,
    });
    if (!latest.ok) await productApiError(latest, `${kind} status lookup failed`);
    Object.assign(presentation, assertItemPresentation(await latest.json(), kind));
  }
  return presentation;
}

async function renderItemAssets(lookId, options = {}) {
  const normalizedLookId = normalizeLookId(lookId);
  const baseUrl = normalizeBaseUrl(options.baseUrl || process.env.STYLECAPTURE_API_URL || DEFAULT_API_URL);
  const timeoutMs = Math.max(1, Math.min(Number(options.timeoutMs) || DEFAULT_TIMEOUT_MS, 180_000));
  const signal = AbortSignal.timeout(timeoutMs);
  const cookie = await ensureSession(baseUrl, options, signal);
  const detailResponse = await fetch(`${baseUrl}/v1/looks/${encodeURIComponent(normalizedLookId)}`, {
    headers: { cookie }, signal,
  });
  if (!detailResponse.ok) await productApiError(detailResponse, "无法读取穿搭中的真实单品");
  const detail = await detailResponse.json();
  const itemIds = [...new Set((detail?.components || []).map((component) => component?.item_id).filter((id) => typeof id === "string"))];
  const context = { baseUrl, cookie, signal, wait: options.wait };
  return Promise.all(itemIds.map(async (itemId) => {
    const [pixel, flatLay] = await Promise.all([
      requestItemPresentation(itemId, "pixel_item", context),
      requestItemPresentation(itemId, "flat_lay_item", context),
    ]);
    return { item_id: itemId, pixel, flat_lay: flatLay };
  }));
}

async function renderItemFlatLays(lookId, options = {}) {
  const assets = await renderItemAssets(lookId, options);
  return assets.map((entry) => entry.flat_lay);
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key === "--wait") { args.wait = true; continue; }
    const value = argv[index + 1];
    if (!key.startsWith("--") || !value || value.startsWith("--")) {
      throw new Error("Usage: node scripts/render.js --look-id <UUID> [--wait] [--api-base-url URL] [--timeout-ms 90000]");
    }
    args[key.slice(2)] = value;
    index += 1;
  }
  return args;
}

async function main(argv) {
  const args = parseArgs(argv);
  if (!args["look-id"]) throw new Error("--look-id is required");
  const output = await renderItemAssets(args["look-id"], {
    baseUrl: args["api-base-url"],
    sessionCookie: args["session-cookie"],
    timeoutMs: args["timeout-ms"],
    wait: args.wait,
  });
  process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}

module.exports = { normalizeLookId, renderItemAssets, renderItemFlatLays };
