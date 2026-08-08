// Contract tests for the combined pixel-card and white-detail workflow.
const assert = require("node:assert/strict");
const { createServer } = require("node:http");
const test = require("node:test");

const { normalizeLookId, renderItemAssets } = require("../scripts/render.js");

test("validates a Look UUID", () => {
  assert.equal(normalizeLookId("11111111-1111-4111-8111-111111111111"), "11111111-1111-4111-8111-111111111111");
  assert.throws(() => normalizeLookId("not-a-look"), /UUID/);
});

test("requests both item assets directly without creating a collage", async (t) => {
  const lookId = "11111111-1111-4111-8111-111111111111";
  const itemId = "22222222-2222-4222-8222-222222222222";
  const pixelAssetId = "33333333-3333-4333-8333-333333333333";
  const flatLayAssetId = "44444444-4444-4444-8444-444444444444";
  const requests = [];
  const server = createServer(async (request, response) => {
    let body = "";
    for await (const chunk of request) body += chunk;
    requests.push({ url: request.url, method: request.method, body, headers: request.headers });
    if (request.url === "/v1/session") {
      response.writeHead(201, { "set-cookie": "stylecapture_session=signed; HttpOnly" });
      response.end("{}");
      return;
    }
    if (request.url === `/v1/looks/${lookId}`) {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ components: [{ item_id: itemId }] }));
      return;
    }
    if (request.method === "POST" && request.url === `/v1/items/${itemId}/presentations/pixel`) {
      response.writeHead(202, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: pixelAssetId, kind: "pixel_item", status: "queued" }));
      return;
    }
    if (request.method === "POST" && request.url === `/v1/items/${itemId}/presentations/flat-lay`) {
      response.writeHead(202, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: flatLayAssetId, kind: "flat_lay_item", status: "queued" }));
      return;
    }
    if (request.url === `/v1/item-presentations/${pixelAssetId}`) {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: pixelAssetId, kind: "pixel_item", status: "succeeded", output_image_url: `/v1/item-presentations/${pixelAssetId}/image` }));
      return;
    }
    if (request.url === `/v1/item-presentations/${flatLayAssetId}`) {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: flatLayAssetId, kind: "flat_lay_item", status: "succeeded", output_image_url: `/v1/item-presentations/${flatLayAssetId}/image` }));
      return;
    }
    response.writeHead(404);
    response.end();
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const { port } = server.address();
  const assets = await renderItemAssets(lookId, { baseUrl: `http://127.0.0.1:${port}`, wait: true });
  assert.equal(assets[0].pixel.status, "succeeded");
  assert.equal(assets[0].flat_lay.status, "succeeded");
  assert.equal(requests[1].url, `/v1/looks/${lookId}`);
  const creates = requests.filter((request) => request.method === "POST" && request.url.includes("/presentations/"));
  assert.deepEqual(new Set(creates.map((request) => request.url)), new Set([
    `/v1/items/${itemId}/presentations/pixel`,
    `/v1/items/${itemId}/presentations/flat-lay`,
  ]));
  assert.equal(creates[0].headers.cookie, "stylecapture_session=signed");
  assert.ok(creates.every((request) => request.headers["idempotency-key"]));
  assert.equal(requests.some((request) => request.url.endsWith("/renders")), false);
});
