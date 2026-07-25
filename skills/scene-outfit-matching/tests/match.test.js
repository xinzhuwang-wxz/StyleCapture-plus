const assert = require("node:assert/strict");
const { createServer } = require("node:http");
const test = require("node:test");

const {
  matchOutfits,
  normalizeRequest,
  validateWorkflowTrace,
} = require("../scripts/match.js");

test("normalizes only the Product API request contract", () => {
  assert.deepEqual(
    normalizeRequest({
      scene: " 周五面试 ",
      style: " 简洁正式 ",
      formality: " 正式商务 ",
      mustIncludeItemIds: ["22222222-2222-4222-8222-222222222222"],
      exclude_item_ids: ["33333333-3333-4333-8333-333333333333"],
      anchorItemId: "11111111-1111-4111-8111-111111111111",
    }),
    {
      scene: "周五面试",
      style: "简洁正式",
      weather: undefined,
      formality: "正式商务",
      comfort: undefined,
      anchor_item_id: "11111111-1111-4111-8111-111111111111",
      must_include_item_ids: ["22222222-2222-4222-8222-222222222222"],
      exclude_item_ids: ["33333333-3333-4333-8333-333333333333"],
    },
  );
  assert.throws(() => normalizeRequest({ style: "通勤" }), /scene/);
});

test("uses session and outfit Product APIs without implementing matching", async (t) => {
  const requests = [];
  const expected = {
    request_id: "11111111-1111-4111-8111-111111111111",
    trace_id: "44444444-4444-4444-8444-444444444444",
    plans: [{ id: "22222222-2222-4222-8222-222222222222" }],
    degraded: false,
    degradation_reason: null,
    explanation_state: "llm_ranked",
  };
  const expectedTrace = {
    trace_id: expected.trace_id,
    request_id: expected.request_id,
    status: "completed",
    explanation_state: "llm_ranked",
    plan_count: 1,
    capability_alias: "reasoning",
    model_version: "outfit-rerank-model-v1",
    steps: [
      {
        name: "reasoning_rerank",
        label: "搭配理解与重排",
        status: "completed",
      },
    ],
    created_at: "2026-07-26T00:00:00Z",
    updated_at: "2026-07-26T00:00:01Z",
  };
  const server = createServer(async (request, response) => {
    let body = "";
    for await (const chunk of request) body += chunk;
    requests.push({
      method: request.method,
      url: request.url,
      cookie: request.headers.cookie,
      body,
    });
    if (request.url === "/v1/session") {
      response.writeHead(201, {
        "content-type": "application/json",
        "set-cookie": "stylecapture_session=signed; HttpOnly; SameSite=Strict",
      });
      response.end('{"user_id":"11111111-1111-4111-8111-111111111111"}');
      return;
    }
    if (request.url === `/v1/outfit-plans/traces/${expected.trace_id}`) {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify(expectedTrace));
      return;
    }
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(expected));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const address = server.address();

  const result = await matchOutfits(
    { scene: "客户提案", style: "简洁正式" },
    { baseUrl: `http://127.0.0.1:${address.port}` },
  );

  assert.deepEqual(result, { ...expected, workflow_trace: expectedTrace });
  assert.equal(requests.length, 3);
  assert.equal(requests[1].url, "/v1/outfit-plans");
  assert.equal(requests[1].cookie, "stylecapture_session=signed");
  assert.deepEqual(JSON.parse(requests[1].body), {
    scene: "客户提案",
    style: "简洁正式",
    must_include_item_ids: [],
    exclude_item_ids: [],
  });
  assert.equal(
    requests[2].url,
    `/v1/outfit-plans/traces/${expected.trace_id}`,
  );
  assert.equal(requests[2].cookie, "stylecapture_session=signed");
});

test("rejects mismatched or infrastructure-leaking workflow traces", () => {
  const result = {
    request_id: "11111111-1111-4111-8111-111111111111",
    trace_id: "44444444-4444-4444-8444-444444444444",
  };
  const valid = {
    trace_id: result.trace_id,
    request_id: result.request_id,
    status: "completed",
    explanation_state: "llm_ranked",
    plan_count: 4,
    steps: [],
  };

  assert.equal(validateWorkflowTrace(valid, result), valid);
  assert.throws(
    () => validateWorkflowTrace({ ...valid, request_id: "wrong" }, result),
    /mismatched/,
  );
  assert.throws(
    () =>
      validateWorkflowTrace(
        { ...valid, steps: [{ provider_payload: "hidden" }] },
        result,
      ),
    /infrastructure-only/,
  );
});

test("does not hide Product API errors behind fixed results", async (t) => {
  const server = createServer((request, response) => {
    if (request.url === "/v1/session") {
      response.writeHead(201, {
        "set-cookie": "stylecapture_session=signed; HttpOnly",
      });
      response.end("{}");
      return;
    }
    response.writeHead(422, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        error: {
          code: "outfit_wardrobe_empty",
          message: "请先保存至少一件已识别的真实衣服",
        },
      }),
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const address = server.address();

  await assert.rejects(
    matchOutfits(
      { scene: "周五面试" },
      { baseUrl: `http://127.0.0.1:${address.port}` },
    ),
    /outfit_wardrobe_empty/,
  );
});
