#!/usr/bin/env node
"use strict";

const { createServer } = require("node:http");
const { readFile } = require("node:fs/promises");
const path = require("node:path");

const { matchOutfits } = require("./match.js");

const SKILL_ROOT = path.resolve(__dirname, "..");
const PLAYGROUND_PATH = path.join(SKILL_ROOT, "assets", "playground.html");
const MOCK_WARDROBE_PATH = path.join(SKILL_ROOT, "assets", "mock-wardrobe.json");
const MAX_BODY_BYTES = 2 * 1024 * 1024;

function sendJson(response, statusCode, value) {
  const body = JSON.stringify(value);
  response.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
  });
  response.end(body);
}

function sendHtml(response, body) {
  response.writeHead(200, {
    "content-type": "text/html; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
    "content-security-policy":
      "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'; base-uri 'none'; form-action 'self'",
    "x-content-type-options": "nosniff",
  });
  response.end(body);
}

async function readJsonBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      const error = new Error("request_body_too_large");
      error.statusCode = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  if (chunks.length === 0) {
    const error = new Error("request_body_required");
    error.statusCode = 400;
    throw error;
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    const error = new Error("request_body_invalid_json");
    error.statusCode = 400;
    throw error;
  }
}

function createPlaygroundServer(options = {}) {
  const match = options.match || matchOutfits;
  const readAsset = options.readAsset || readFile;

  return createServer(async (request, response) => {
    const url = new URL(request.url || "/", "http://127.0.0.1");
    try {
      if (request.method === "GET" && url.pathname === "/") {
        sendHtml(response, await readAsset(PLAYGROUND_PATH, "utf8"));
        return;
      }
      if (request.method === "GET" && url.pathname === "/health") {
        sendJson(response, 200, {
          status: "ok",
          skill: "scene-outfit-matching",
        });
        return;
      }
      if (request.method === "GET" && url.pathname === "/favicon.ico") {
        response.writeHead(204, { "cache-control": "public, max-age=86400" });
        response.end();
        return;
      }
      if (request.method === "GET" && url.pathname === "/api/mock-wardrobe") {
        sendJson(
          response,
          200,
          JSON.parse(await readAsset(MOCK_WARDROBE_PATH, "utf8")),
        );
        return;
      }
      if (request.method === "POST" && url.pathname === "/api/match") {
        const payload = await readJsonBody(request);
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
          const error = new Error("request_payload_must_be_object");
          error.statusCode = 400;
          throw error;
        }
        const result = await match(payload.wardrobe, payload.request, {
          llm: payload.useLlm === true ? undefined : false,
        });
        sendJson(response, 200, result);
        return;
      }
      sendJson(response, 404, { error: "not_found" });
    } catch (error) {
      sendJson(response, Number(error.statusCode) || 422, {
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });
}

function parseArgs(argv) {
  const options = { host: "127.0.0.1", port: 4174 };
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    const value = argv[index + 1];
    if (!["--host", "--port"].includes(current) || !value) {
      throw new Error(
        "Usage: node scripts/playground.js [--host 127.0.0.1] [--port 4174]",
      );
    }
    if (current === "--host") options.host = value;
    if (current === "--port") options.port = Number(value);
    index += 1;
  }
  if (!["127.0.0.1", "localhost"].includes(options.host)) {
    throw new Error("playground host must be 127.0.0.1 or localhost");
  }
  if (
    !Number.isInteger(options.port) ||
    options.port < 0 ||
    options.port > 65_535
  ) {
    throw new Error("playground port must be an integer from 0 to 65535");
  }
  return options;
}

async function main(argv) {
  const options = parseArgs(argv);
  const server = createPlaygroundServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(options.port, options.host, resolve);
  });
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : options.port;
  process.stdout.write(`Scene Outfit Matching Playground: http://${options.host}:${port}\n`);
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}

module.exports = {
  createPlaygroundServer,
  parseArgs,
};
