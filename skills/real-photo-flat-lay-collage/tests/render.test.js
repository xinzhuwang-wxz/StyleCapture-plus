const assert = require("node:assert/strict");
const { createServer } = require("node:http");
const test = require("node:test");

const { normalizeLookId, renderFlatLay } = require("../scripts/render.js");

test("validates a Look UUID", () => {
  assert.equal(normalizeLookId("11111111-1111-4111-8111-111111111111"), "11111111-1111-4111-8111-111111111111");
  assert.throws(() => normalizeLookId("not-a-look"), /UUID/);
});

test("requests and polls the Product API collage artifact without image synthesis", async (t) => {
  const lookId = "11111111-1111-4111-8111-111111111111";
  const artifactId = "22222222-2222-4222-8222-222222222222";
  const requests = [];
  let polls = 0;
  const server = createServer(async (request, response) => {
    let body = "";
    for await (const chunk of request) body += chunk;
    requests.push({ url: request.url, method: request.method, body, headers: request.headers });
    if (request.url === "/v1/session") {
      response.writeHead(201, { "set-cookie": "stylecapture_session=signed; HttpOnly" });
      response.end("{}");
      return;
    }
    if (request.method === "POST") {
      response.writeHead(202, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: artifactId, kind: "collage", status: "queued" }));
      return;
    }
    polls += 1;
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ id: artifactId, kind: "collage", status: polls === 1 ? "running" : "succeeded", output_image_url: `/v1/render-artifacts/${artifactId}/image` }));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const { port } = server.address();
  const artifact = await renderFlatLay(lookId, { baseUrl: `http://127.0.0.1:${port}`, wait: true });
  assert.equal(artifact.status, "succeeded");
  assert.equal(requests[1].url, `/v1/looks/${lookId}/renders`);
  assert.deepEqual(JSON.parse(requests[1].body), { kind: "collage" });
  assert.equal(requests[1].headers.cookie, "stylecapture_session=signed");
  assert.ok(requests[1].headers["idempotency-key"]);
});
