const assert = require("node:assert/strict");
const { createServer } = require("node:http");
const test = require("node:test");

const { normalizeLookId, renderItemFlatLays } = require("../scripts/render.js");

test("validates a Look UUID", () => {
  assert.equal(normalizeLookId("11111111-1111-4111-8111-111111111111"), "11111111-1111-4111-8111-111111111111");
  assert.throws(() => normalizeLookId("not-a-look"), /UUID/);
});

test("requests each item presentation directly without creating a collage", async (t) => {
  const lookId = "11111111-1111-4111-8111-111111111111";
  const itemId = "22222222-2222-4222-8222-222222222222";
  const assetId = "33333333-3333-4333-8333-333333333333";
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
    if (request.method === "POST" && request.url === `/v1/items/${itemId}/presentations/flat-lay`) {
      response.writeHead(202, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: assetId, kind: "flat_lay_item", status: "queued" }));
      return;
    }
    if (request.url === `/v1/item-presentations/${assetId}`) {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: assetId, kind: "flat_lay_item", status: "succeeded", output_image_url: `/v1/item-presentations/${assetId}/image` }));
      return;
    }
    response.writeHead(404);
    response.end();
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const { port } = server.address();
  const presentations = await renderItemFlatLays(lookId, { baseUrl: `http://127.0.0.1:${port}`, wait: true });
  assert.equal(presentations[0].status, "succeeded");
  assert.equal(requests[1].url, `/v1/looks/${lookId}`);
  assert.equal(requests[2].url, `/v1/items/${itemId}/presentations/flat-lay`);
  assert.equal(requests[2].headers.cookie, "stylecapture_session=signed");
  assert.ok(requests[2].headers["idempotency-key"]);
  assert.equal(requests.some((request) => request.url.endsWith("/renders")), false);
});
