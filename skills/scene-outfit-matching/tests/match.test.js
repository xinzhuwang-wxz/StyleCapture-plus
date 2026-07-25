const assert = require("node:assert/strict");
const { execFile } = require("node:child_process");
const { createServer } = require("node:http");
const { readFile } = require("node:fs/promises");
const path = require("node:path");
const { promisify } = require("node:util");
const test = require("node:test");

const {
  MAX_LLM_TIMEOUT_MS,
  matchOutfits,
  validateMatchResponse,
} = require("../scripts/match.js");
const { createPlaygroundServer } = require("../scripts/playground.js");

const execFileAsync = promisify(execFile);
const skillRoot = path.resolve(__dirname, "..");
const mockWardrobePath = path.join(skillRoot, "assets", "mock-wardrobe.json");

async function loadWardrobe() {
  return JSON.parse(await readFile(mockWardrobePath, "utf8"));
}

function assertPlanShape(response) {
  assert.equal(validateMatchResponse(response), true);
  assert.ok(response.outfitPlans.length >= 3);
  assert.ok(response.outfitPlans.length <= 4);
  for (const plan of response.outfitPlans) {
    assert.ok(plan.id);
    assert.ok(Array.isArray(plan.wardrobeItemIds));
    assert.ok(Array.isArray(plan.recommendedItems));
    assert.ok(plan.rationale.length > 8);
    assert.ok(plan.styleMatchScore >= 0 && plan.styleMatchScore <= 100);
    assert.equal(
      plan.isFullyFromWardrobe,
      plan.recommendedItems.length === 0,
    );
  }
}

test("scene input returns four structured interview plans", async () => {
  const wardrobe = await loadWardrobe();
  const response = await matchOutfits(
    wardrobe,
    { scene: "周五面试" },
    { llm: false },
  );

  assert.equal(response.triggerType, "scene");
  assert.equal(response.degraded, true);
  assert.equal(response.outfitPlans.length, 4);
  assertPlanShape(response);
});

test("style input returns three or four distinct French commute plans", async () => {
  const wardrobe = await loadWardrobe();
  const response = await matchOutfits(
    wardrobe,
    { style: "法式通勤" },
    { llm: false },
  );

  assert.equal(response.triggerType, "style");
  assertPlanShape(response);
  const combinations = response.outfitPlans.map((plan) =>
    [...plan.wardrobeItemIds].sort().join(","),
  );
  assert.equal(new Set(combinations).size, combinations.length);
});

test("target item input includes the unpurchased item and wardrobe matches", async () => {
  const wardrobe = await loadWardrobe();
  const targetItem = {
    id: "target-red-trench",
    name: "酒红色短款风衣",
    category: "外套",
    colors: ["酒红"],
    styleTags: ["法式", "通勤"],
    sceneTags: ["通勤", "约会"],
    source: "ecommerce",
    originalImageUrl: "https://example.invalid/target-red-trench.jpg",
    bbox: null,
    searchQuery: "酒红色短款风衣",
    buyLink: "https://s.taobao.com/search?q=%E9%85%92%E7%BA%A2%E8%89%B2%E7%9F%AD%E6%AC%BE%E9%A3%8E%E8%A1%A3",
    pixelUrl: null,
  };
  const response = await matchOutfits(
    wardrobe,
    {
      targetItem,
      question: "这件未购外套能不能和我的衣橱搭？",
    },
    { llm: false },
  );

  assert.equal(response.triggerType, "target_item");
  assertPlanShape(response);
  for (const plan of response.outfitPlans) {
    assert.ok(
      plan.recommendedItems.some((item) => item.id === targetItem.id),
      "every target-item plan must retain the target item",
    );
    assert.match(plan.rationale, /已将目标单品/);
    assert.doesNotMatch(plan.rationale, /衣橱暂缺外套/);
  }
});

test("target item image description is normalized into a consumable recommendation", async () => {
  const wardrobe = await loadWardrobe();
  const response = await matchOutfits(
    wardrobe,
    {
      targetItem: {
        imageDescription: "一件酒红色短款风衣，翻领，适合通勤",
        category: "外套",
        colors: ["酒红"],
        styleTags: ["法式", "通勤"],
      },
      question: "能不能和我的衣橱搭？",
    },
    { llm: false },
  );

  assert.equal(response.triggerType, "target_item");
  assertPlanShape(response);
  for (const plan of response.outfitPlans) {
    const target = plan.recommendedItems.find((item) =>
      item.name.includes("酒红色短款风衣"),
    );
    assert.ok(target);
    assert.match(target.id, /^target-[a-f0-9]{12}$/);
    assert.equal(target.source, "ecommerce");
    assert.ok(target.searchQuery.length > 0);
    assert.match(target.buyLink, /^https:\/\//);
  }
});

test("the deliberate missing-shoes wardrobe creates honest commerce completion", async () => {
  const wardrobe = await loadWardrobe();
  const response = await matchOutfits(
    wardrobe,
    { scene: "周五面试" },
    { llm: false },
  );

  for (const plan of response.outfitPlans) {
    assert.equal(plan.isFullyFromWardrobe, false);
    const shoes = plan.recommendedItems.find((item) => item.category === "鞋");
    assert.ok(shoes, "a missing-shoes plan must recommend shoes");
    assert.ok(shoes.searchQuery.length > 0);
    assert.match(shoes.buyLink, /^https:\/\//);
  }
});

test("a complete wardrobe stays fully wardrobe-backed", async () => {
  const wardrobe = await loadWardrobe();
  wardrobe.items.push({
    id: "own-black-loafers",
    name: "黑色通勤乐福鞋",
    category: "鞋",
    colors: ["黑色"],
    styleTags: ["通勤", "正式"],
    sceneTags: ["面试", "商务"],
    source: "own",
    originalImageUrl: "https://example.invalid/wardrobe/black-loafers.jpg",
    bbox: null,
    searchQuery: "",
    buyLink: "",
    pixelUrl: null,
  });
  const response = await matchOutfits(
    wardrobe,
    { scene: "周五面试" },
    { llm: false },
  );

  for (const plan of response.outfitPlans) {
    assert.equal(plan.isFullyFromWardrobe, true);
    assert.deepEqual(plan.recommendedItems, []);
  }
});

test("valid LLM ranking is accepted without degradation", async (t) => {
  const server = createServer(async (request, response) => {
    assert.equal(request.url, "/v1/chat/completions");
    let body = "";
    for await (const chunk of request) body += chunk;
    const payload = JSON.parse(body);
    const candidates = JSON.parse(
      payload.messages.find((message) => message.role === "user").content,
    ).candidates;
    const rankedPlans = candidates.map((candidate, index) => ({
      id: candidate.id,
      rationale: `模型复核：第 ${index + 1} 套在场景、配色与层次上协调。`,
      styleMatchScore: 92 - index,
    }));
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        choices: [
          {
            message: {
              content: JSON.stringify({ rankedPlans }),
            },
          },
        ],
      }),
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const address = server.address();
  const wardrobe = await loadWardrobe();
  const result = await matchOutfits(
    wardrobe,
    { style: "法式通勤" },
    {
      llm: {
        apiKey: "test-only",
        baseUrl: `http://127.0.0.1:${address.port}`,
        timeoutMs: 500,
      },
    },
  );

  assert.equal(result.degraded, false);
  assert.equal(result.degradationReason, null);
  assert.match(result.outfitPlans[0].rationale, /^模型复核/);
  assertPlanShape(result);
});

test("LLM timeout stays bounded and falls back with degraded true", async (t) => {
  const server = createServer((_request, response) => {
    setTimeout(() => {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ choices: [] }));
    }, 200);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const address = server.address();
  const wardrobe = await loadWardrobe();
  const started = Date.now();
  const result = await matchOutfits(
    wardrobe,
    { scene: "周五面试" },
    {
      llm: {
        apiKey: "test-only",
        baseUrl: `http://127.0.0.1:${address.port}`,
        timeoutMs: 25,
      },
    },
  );

  assert.ok(Date.now() - started < 1000);
  assert.equal(result.degraded, true);
  assert.match(result.degradationReason, /timeout/i);
  assertPlanShape(result);
  assert.equal(MAX_LLM_TIMEOUT_MS, 15_000);
});

test("unknown plan ids from the LLM are rejected and degraded", async (t) => {
  const server = createServer((_request, response) => {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        choices: [
          {
            message: {
              content: JSON.stringify({
                rankedPlans: [
                  {
                    id: "invented-plan",
                    rationale: "这不是候选中的方案，因此必须被拒绝。",
                    styleMatchScore: 99,
                  },
                  {
                    id: "also-invented",
                    rationale: "这同样不是候选中的方案。",
                    styleMatchScore: 98,
                  },
                  {
                    id: "still-invented",
                    rationale: "模型不得新增搭配。",
                    styleMatchScore: 97,
                  },
                ],
              }),
            },
          },
        ],
      }),
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => server.close());
  const address = server.address();
  const wardrobe = await loadWardrobe();
  const result = await matchOutfits(
    wardrobe,
    { style: "法式通勤" },
    {
      llm: {
        apiKey: "test-only",
        baseUrl: `http://127.0.0.1:${address.port}`,
        timeoutMs: 500,
      },
    },
  );

  assert.equal(result.degraded, true);
  assert.equal(result.degradationReason, "llm_response_plan_id_invalid");
  assertPlanShape(result);
});

test("strict response validation rejects unknown fields", async () => {
  const wardrobe = await loadWardrobe();
  const response = await matchOutfits(
    wardrobe,
    { scene: "周五面试" },
    { llm: false },
  );
  assert.equal(validateMatchResponse({ ...response, unexpected: true }), false);
  assert.equal(
    validateMatchResponse({
      ...response,
      outfitPlans: [
        { ...response.outfitPlans[0], unexpected: true },
        ...response.outfitPlans.slice(1),
      ],
    }),
    false,
  );
});

test("CLI reads the documented files and emits valid JSON", async () => {
  const request = JSON.stringify({ scene: "周五面试" });
  const { stdout } = await execFileAsync(
    process.execPath,
    [
      path.join(skillRoot, "scripts", "match.js"),
      "--wardrobe",
      mockWardrobePath,
      "--request",
      request,
      "--no-llm",
    ],
    { cwd: skillRoot },
  );
  const response = JSON.parse(stdout);
  assertPlanShape(response);
});

async function withPlayground(run) {
  const server = createPlaygroundServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;
  try {
    await run(baseUrl);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test("playground serves an interactive page and the mock wardrobe", async () => {
  await withPlayground(async (baseUrl) => {
    const pageResponse = await fetch(baseUrl);
    assert.equal(pageResponse.status, 200);
    const page = await pageResponse.text();
    assert.match(page, /场景搭配实验室/);
    assert.match(page, /生成 3–4 套搭配/);
    assert.match(page, /使用自己的衣橱 JSON/);

    const wardrobeResponse = await fetch(`${baseUrl}/api/mock-wardrobe`);
    assert.equal(wardrobeResponse.status, 200);
    const wardrobe = await wardrobeResponse.json();
    assert.equal(wardrobe.items.length, 16);
    assert.equal(
      wardrobe.items.some((item) => item.category === "鞋"),
      false,
    );
  });
});

test("playground API executes the same scene matching workflow", async () => {
  const wardrobe = await loadWardrobe();
  await withPlayground(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/match`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        wardrobe,
        request: { scene: "周五面试" },
        useLlm: false,
      }),
    });
    assert.equal(response.status, 200);
    const result = await response.json();
    assert.equal(result.triggerType, "scene");
    assert.equal(result.degraded, true);
    assertPlanShape(result);
    assert.ok(
      result.outfitPlans.every((plan) =>
        plan.recommendedItems.some((item) => item.category === "鞋"),
      ),
    );
  });
});

test("playground API accepts a lightweight target-item description", async () => {
  const wardrobe = await loadWardrobe();
  await withPlayground(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/match`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        wardrobe,
        request: {
          targetItem: {
            imageDescription: "一件酒红色短款风衣，翻领，适合通勤",
            category: "外套",
            colors: ["酒红"],
          },
          question: "能不能和我的衣橱搭？",
        },
        useLlm: false,
      }),
    });
    assert.equal(response.status, 200);
    const result = await response.json();
    assert.equal(result.triggerType, "target_item");
    assertPlanShape(result);
  });
});
