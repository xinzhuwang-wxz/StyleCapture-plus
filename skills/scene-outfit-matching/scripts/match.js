#!/usr/bin/env node
"use strict";

const { createHash, randomUUID } = require("node:crypto");
const { readFile } = require("node:fs/promises");
const path = require("node:path");

const SCHEMA_VERSION = "scene-outfit-matching.v1";
const MAX_LLM_TIMEOUT_MS = 15_000;
const DEFAULT_LLM_TIMEOUT_MS = 12_000;
const VALID_SOURCES = new Set(["own", "collected", "ecommerce"]);
const CATEGORIES = new Set(["上衣", "下装", "连衣裙", "外套", "鞋", "配饰"]);

const CATEGORY_ALIASES = new Map([
  ["tops", "上衣"],
  ["top", "上衣"],
  ["bottoms", "下装"],
  ["bottom", "下装"],
  ["dresses", "连衣裙"],
  ["dress", "连衣裙"],
  ["outerwear", "外套"],
  ["shoes", "鞋"],
  ["shoe", "鞋"],
  ["bags", "配饰"],
  ["headwear", "配饰"],
  ["accessories", "配饰"],
]);

const FALLBACK_TEMPLATES = [
  ["上衣", "下装", "外套", "鞋", "配饰"],
  ["连衣裙", "外套", "鞋", "配饰"],
  ["上衣", "下装", "鞋", "配饰"],
  ["上衣", "下装", "外套", "鞋"],
];

const COMMERCE_SEARCHES = {
  上衣: ["通勤衬衫", "法式针织上衣", "极简通勤上衣", "面试白衬衫"],
  下装: ["高腰通勤西裤", "法式直筒裤", "通勤半身裙", "面试西装裤"],
  连衣裙: ["通勤衬衫连衣裙", "法式中长连衣裙", "面试连衣裙", "极简连衣裙"],
  外套: ["通勤西装外套", "法式风衣", "面试西装", "极简羊毛外套"],
  鞋: ["黑色通勤乐福鞋", "低跟通勤鞋", "简洁白色皮鞋", "法式芭蕾鞋"],
  配饰: ["通勤结构感托特包", "法式丝巾", "极简皮带", "通勤手提包"],
};

function asTrimmedString(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeCategory(value) {
  const category = asTrimmedString(value);
  return CATEGORIES.has(category)
    ? category
    : CATEGORY_ALIASES.get(category.toLowerCase()) || category;
}

function normalizeStringArray(value) {
  return Array.isArray(value)
    ? value.map(asTrimmedString).filter(Boolean)
    : [];
}

function normalizeItem(raw, index) {
  if (!raw || typeof raw !== "object") {
    throw new TypeError(`wardrobe item ${index} must be an object`);
  }
  const id = asTrimmedString(raw.id);
  const name = asTrimmedString(raw.name);
  const category = normalizeCategory(raw.category);
  const source = asTrimmedString(raw.source);
  if (!id || !name) {
    throw new TypeError(`wardrobe item ${index} requires id and name`);
  }
  if (!CATEGORIES.has(category)) {
    throw new TypeError(`wardrobe item ${id} has unsupported category ${category}`);
  }
  if (!VALID_SOURCES.has(source)) {
    throw new TypeError(`wardrobe item ${id} has unsupported source ${source}`);
  }
  return {
    id,
    name,
    category,
    colors: normalizeStringArray(raw.colors),
    styleTags: normalizeStringArray(raw.styleTags),
    sceneTags: normalizeStringArray(raw.sceneTags),
    source,
    originalImageUrl: asTrimmedString(raw.originalImageUrl) || null,
    bbox: Array.isArray(raw.bbox) ? raw.bbox : null,
    searchQuery: asTrimmedString(raw.searchQuery),
    buyLink: asTrimmedString(raw.buyLink),
    pixelUrl: asTrimmedString(raw.pixelUrl) || null,
  };
}

function normalizeWardrobe(raw) {
  const items = Array.isArray(raw) ? raw : raw && raw.items;
  if (!Array.isArray(items) || items.length === 0) {
    throw new TypeError("wardrobe must contain at least one item");
  }
  const normalized = items.map(normalizeItem);
  if (new Set(normalized.map((item) => item.id)).size !== normalized.length) {
    throw new TypeError("wardrobe item ids must be unique");
  }
  return normalized;
}

function inferTargetCategory(rawCategory, description) {
  const normalized = normalizeCategory(rawCategory);
  if (CATEGORIES.has(normalized)) return normalized;
  const text = asTrimmedString(description).toLowerCase();
  const rules = [
    ["连衣裙", ["连衣裙", "dress"]],
    ["外套", ["外套", "风衣", "大衣", "夹克", "西装", "coat", "jacket", "blazer"]],
    ["鞋", ["鞋", "靴", "乐福", "loafer", "shoe", "boot", "sneaker"]],
    ["下装", ["裤", "半身裙", "牛仔", "trouser", "pants", "skirt", "jeans"]],
    ["配饰", ["包", "帽", "围巾", "丝巾", "皮带", "bag", "hat", "scarf", "belt"]],
    ["上衣", ["上衣", "衬衫", "针织", "毛衣", "t恤", "shirt", "blouse", "sweater", "top"]],
  ];
  return rules.find(([, terms]) => terms.some((term) => text.includes(term)))?.[0] || "";
}

function normalizeTargetItem(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new TypeError("targetItem must be an object");
  }
  const description =
    asTrimmedString(raw.description) || asTrimmedString(raw.imageDescription);
  const name = asTrimmedString(raw.name) || description;
  const category = inferTargetCategory(raw.category, `${name} ${description}`);
  if (!name) {
    throw new TypeError("targetItem requires name, description, or imageDescription");
  }
  if (!category) {
    throw new TypeError("targetItem requires a supported category or recognizable description");
  }
  const id =
    asTrimmedString(raw.id) ||
    `target-${createHash("sha256")
      .update(`${category}:${name}`)
      .digest("hex")
      .slice(0, 12)}`;
  const searchQuery = asTrimmedString(raw.searchQuery) || name;
  const buyLink =
    asTrimmedString(raw.buyLink) ||
    `https://search.jd.com/Search?keyword=${encodeURIComponent(searchQuery)}`;
  return normalizeItem(
    {
      ...raw,
      id,
      name,
      category,
      source: "ecommerce",
      searchQuery,
      buyLink,
    },
    "targetItem",
  );
}

function normalizeRequest(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new TypeError("request must be a JSON object");
  }
  const scene = asTrimmedString(raw.scene);
  const style = asTrimmedString(raw.style);
  const question = asTrimmedString(raw.question);
  const targetItem = raw.targetItem ? normalizeTargetItem(raw.targetItem) : null;
  if (!scene && !style && !targetItem) {
    throw new TypeError("request requires scene, style, or targetItem");
  }
  return {
    triggerType: targetItem ? "target_item" : scene ? "scene" : "style",
    scene,
    style,
    question,
    targetItem,
  };
}

function containsText(value, query) {
  return asTrimmedString(value).toLowerCase().includes(query.toLowerCase());
}

function itemRelevance(item, request) {
  let score = item.source === "own" ? 8 : item.source === "collected" ? 5 : 0;
  const sceneTokens = [request.scene, request.question].filter(Boolean);
  const styleTokens = [request.style].filter(Boolean);
  for (const tag of item.sceneTags) {
    if (sceneTokens.some((token) => containsText(token, tag) || containsText(tag, token))) {
      score += 5;
    }
  }
  for (const tag of item.styleTags) {
    if (styleTokens.some((token) => containsText(token, tag) || containsText(tag, token))) {
      score += 4;
    }
    if (containsText(request.scene, tag) || containsText(request.question, tag)) {
      score += 2;
    }
  }
  if (
    containsText(request.scene, "面试") &&
    (item.styleTags.includes("正式") || item.sceneTags.includes("面试"))
  ) {
    score += 6;
  }
  return score;
}

function groupCandidates(items, request) {
  const grouped = Object.fromEntries([...CATEGORIES].map((category) => [category, []]));
  for (const item of items) grouped[item.category].push(item);
  for (const category of CATEGORIES) {
    grouped[category].sort(
      (left, right) =>
        itemRelevance(right, request) - itemRelevance(left, request) ||
        left.id.localeCompare(right.id),
    );
  }
  return grouped;
}

function targetTemplate(targetCategory) {
  if (targetCategory === "连衣裙") return ["连衣裙", "外套", "鞋", "配饰"];
  if (targetCategory === "上衣") return ["上衣", "下装", "外套", "鞋", "配饰"];
  if (targetCategory === "下装") return ["上衣", "下装", "外套", "鞋", "配饰"];
  if (targetCategory === "外套") return ["上衣", "下装", "外套", "鞋", "配饰"];
  if (targetCategory === "鞋") return ["上衣", "下装", "外套", "鞋", "配饰"];
  return ["上衣", "下装", "鞋", "配饰"];
}

function selectWardrobeItem(grouped, category, planIndex, usedIds) {
  const candidates = grouped[category];
  if (!candidates || candidates.length === 0) return null;
  for (let offset = 0; offset < candidates.length; offset += 1) {
    const candidate = candidates[(planIndex + offset) % candidates.length];
    if (!usedIds.has(candidate.id)) return candidate;
  }
  return candidates[planIndex % candidates.length];
}

function commerceSearchItem(category, request, planIndex) {
  const searches = COMMERCE_SEARCHES[category];
  const queryBase = searches[planIndex % searches.length];
  const context = request.style || request.scene || "日常搭配";
  const searchQuery = `${context} ${queryBase}`.trim();
  const slug = createHash("sha256")
    .update(`${category}:${searchQuery}`)
    .digest("hex")
    .slice(0, 12);
  return {
    id: `commerce-search-${slug}`,
    name: `${queryBase}（搜索推荐）`,
    category,
    colors: [],
    styleTags: normalizeStringArray([request.style]),
    sceneTags: normalizeStringArray([request.scene]),
    source: "ecommerce",
    originalImageUrl: null,
    bbox: null,
    searchQuery,
    buyLink: `https://search.jd.com/Search?keyword=${encodeURIComponent(searchQuery)}`,
    pixelUrl: null,
  };
}

function planScore(items, request, planIndex) {
  if (items.length === 0) return Math.max(55, 70 - planIndex * 2);
  const raw =
    66 +
    Math.round(
      items.reduce((sum, item) => sum + itemRelevance(item, request), 0) /
        Math.max(items.length, 1),
    ) -
    planIndex;
  return Math.max(55, Math.min(96, raw));
}

function fallbackRationale(items, recommended, request) {
  const wardrobeNames = items.map((item) => item.name).join("、");
  const requestLabel =
    request.scene || request.style || request.targetItem?.name || "当前搭配需求";
  const targetItem = request.targetItem;
  const targetIncluded = Boolean(
    targetItem && recommended.some((item) => item.id === targetItem.id),
  );
  const missingItems = recommended.filter((item) => item.id !== targetItem?.id);
  const targetStatement = targetIncluded
    ? `已将目标单品“${targetItem.name}”纳入方案。`
    : "";
  const completion = missingItems.length
    ? `衣橱另缺${[...new Set(missingItems.map((item) => item.category))].join("、")}，已给出明确搜索需求。`
    : recommended.length
      ? "除目标单品外，其余单品均来自现有衣橱。"
      : "全部单品均来自现有衣橱。";
  return `${requestLabel}：以${wardrobeNames || "现有衣橱单品"}建立主色与层次，兼顾场景正式度和风格一致性。${targetStatement}${completion}`;
}

function buildFallbackCandidates(items, request) {
  const grouped = groupCandidates(items, request);
  const templates = request.targetItem
    ? [
        targetTemplate(request.targetItem.category),
        ...FALLBACK_TEMPLATES.filter(
          (template) => !template.includes(request.targetItem.category),
        ),
        ...FALLBACK_TEMPLATES,
      ]
    : FALLBACK_TEMPLATES;
  const plans = [];
  const signatures = new Set();
  for (let attempt = 0; attempt < 16 && plans.length < 4; attempt += 1) {
    const template = templates[attempt % templates.length];
    const usedIds = new Set();
    const selected = [];
    const recommended = [];
    let targetAdded = false;
    for (const category of template) {
      if (
        request.targetItem &&
        request.targetItem.category === category &&
        !targetAdded
      ) {
        recommended.push(request.targetItem);
        targetAdded = true;
        continue;
      }
      const item = selectWardrobeItem(grouped, category, attempt, usedIds);
      if (item) {
        selected.push(item);
        usedIds.add(item.id);
      } else {
        recommended.push(commerceSearchItem(category, request, attempt));
      }
    }
    if (request.targetItem && !targetAdded) {
      recommended.unshift(request.targetItem);
    }
    const signature = [
      ...selected.map((item) => item.id).sort(),
      ...recommended.map((item) => item.id).sort(),
    ].join("|");
    if (signatures.has(signature)) continue;
    signatures.add(signature);
    plans.push({
      id: `plan-${createHash("sha256").update(signature).digest("hex").slice(0, 12)}`,
      scene: request.scene || request.style || request.question || "目标单品搭配",
      wardrobeItemIds: selected.map((item) => item.id),
      recommendedItems: recommended,
      isFullyFromWardrobe: recommended.length === 0,
      rationale: fallbackRationale(selected, recommended, request),
      styleMatchScore: planScore(selected, request, plans.length),
      tryOnImageUrl: null,
      pixelCardUrl: null,
    });
  }
  if (plans.length < 3) {
    throw new Error("wardrobe does not contain enough distinct items for three plans");
  }
  return plans;
}

function normalizeBaseUrl(value) {
  return asTrimmedString(value).replace(/\/+$/, "");
}

function llmConfigFromEnvironment() {
  const baseUrl = normalizeBaseUrl(
    process.env.STYLECAPTURE_LITELLM_URL || process.env.LITELLM_BASE_URL,
  );
  const apiKey =
    asTrimmedString(process.env.STYLECAPTURE_LITELLM_API_KEY) ||
    asTrimmedString(process.env.LITELLM_MASTER_KEY);
  return baseUrl && apiKey
    ? { baseUrl, apiKey, timeoutMs: DEFAULT_LLM_TIMEOUT_MS }
    : null;
}

function llmEndpoint(baseUrl) {
  const normalized = normalizeBaseUrl(baseUrl);
  return normalized.endsWith("/v1")
    ? `${normalized}/chat/completions`
    : `${normalized}/v1/chat/completions`;
}

function parseLlmContent(payload) {
  const content = payload?.choices?.[0]?.message?.content;
  if (typeof content !== "string") {
    throw new Error("llm_response_missing_content");
  }
  return JSON.parse(content);
}

function applyLlmRanking(candidates, rawRanking) {
  if (!rawRanking || !Array.isArray(rawRanking.rankedPlans)) {
    throw new Error("llm_response_schema_invalid");
  }
  if (
    rawRanking.rankedPlans.length < 3 ||
    rawRanking.rankedPlans.length > 4
  ) {
    throw new Error("llm_response_plan_count_invalid");
  }
  const byId = new Map(candidates.map((plan) => [plan.id, plan]));
  const seen = new Set();
  const ranked = rawRanking.rankedPlans.map((ranking) => {
    const id = asTrimmedString(ranking.id);
    const candidate = byId.get(id);
    const rationale = asTrimmedString(ranking.rationale);
    const score = Number(ranking.styleMatchScore);
    if (!candidate || seen.has(id)) {
      throw new Error("llm_response_plan_id_invalid");
    }
    if (!rationale || !Number.isFinite(score) || score < 0 || score > 100) {
      throw new Error("llm_response_plan_fields_invalid");
    }
    seen.add(id);
    return {
      ...candidate,
      rationale,
      styleMatchScore: Math.round(score),
    };
  });
  return ranked;
}

async function rerankWithLlm(candidates, request, config) {
  const timeoutMs = Math.max(
    1,
    Math.min(Number(config.timeoutMs) || DEFAULT_LLM_TIMEOUT_MS, MAX_LLM_TIMEOUT_MS),
  );
  const payload = {
    model: "reasoning",
    temperature: 0.2,
    response_format: { type: "json_object" },
    messages: [
      {
        role: "system",
        content:
          "你是穿搭审美重排器。只能重排给定候选并改写解释，不能添加、删除或替换单品。返回严格 JSON：{\"rankedPlans\":[{\"id\":string,\"rationale\":string,\"styleMatchScore\":0..100}]}。",
      },
      {
        role: "user",
        content: JSON.stringify({
          request: {
            scene: request.scene,
            style: request.style,
            question: request.question,
            targetItem: request.targetItem,
          },
          candidates,
        }),
      },
    ],
  };
  try {
    const response = await fetch(llmEndpoint(config.baseUrl), {
      method: "POST",
      headers: {
        authorization: `Bearer ${config.apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!response.ok) {
      throw new Error(`llm_http_${response.status}`);
    }
    const ranking = parseLlmContent(await response.json());
    return applyLlmRanking(candidates, ranking);
  } catch (error) {
    if (error && (error.name === "TimeoutError" || error.name === "AbortError")) {
      throw new Error("llm_timeout");
    }
    throw error;
  }
}

function validateRecommendedItem(item) {
  const keys = [
    "bbox",
    "buyLink",
    "category",
    "colors",
    "id",
    "name",
    "originalImageUrl",
    "pixelUrl",
    "sceneTags",
    "searchQuery",
    "source",
    "styleTags",
  ];
  return Boolean(
    item &&
      hasExactKeys(item, keys) &&
      typeof item.id === "string" &&
      typeof item.name === "string" &&
      CATEGORIES.has(item.category) &&
      VALID_SOURCES.has(item.source) &&
      Array.isArray(item.colors) &&
      Array.isArray(item.styleTags) &&
      Array.isArray(item.sceneTags) &&
      (item.originalImageUrl === null ||
        typeof item.originalImageUrl === "string") &&
      (item.bbox === null ||
        (Array.isArray(item.bbox) &&
          item.bbox.length === 4 &&
          item.bbox.every(Number.isFinite))) &&
      typeof item.searchQuery === "string" &&
      item.searchQuery.length > 0 &&
      typeof item.buyLink === "string" &&
      item.buyLink.startsWith("https://") &&
      (item.pixelUrl === null || typeof item.pixelUrl === "string"),
  );
}

function hasExactKeys(value, expectedKeys) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  const expected = [...expectedKeys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function validateMatchResponse(response) {
  if (
    !response ||
    !hasExactKeys(response, [
      "degradationReason",
      "degraded",
      "outfitPlans",
      "requestId",
      "schemaVersion",
      "triggerType",
    ]) ||
    response.schemaVersion !== SCHEMA_VERSION ||
    typeof response.requestId !== "string" ||
    !["scene", "style", "target_item"].includes(response.triggerType) ||
    typeof response.degraded !== "boolean" ||
    !(
      response.degradationReason === null ||
      typeof response.degradationReason === "string"
    ) ||
    !Array.isArray(response.outfitPlans) ||
    response.outfitPlans.length < 3 ||
    response.outfitPlans.length > 4
  ) {
    return false;
  }
  const ids = new Set();
  for (const plan of response.outfitPlans) {
    if (
      !plan ||
      !hasExactKeys(plan, [
        "id",
        "isFullyFromWardrobe",
        "pixelCardUrl",
        "rationale",
        "recommendedItems",
        "scene",
        "styleMatchScore",
        "tryOnImageUrl",
        "wardrobeItemIds",
      ]) ||
      typeof plan.id !== "string" ||
      ids.has(plan.id) ||
      typeof plan.scene !== "string" ||
      !Array.isArray(plan.wardrobeItemIds) ||
      !plan.wardrobeItemIds.every((id) => typeof id === "string") ||
      new Set(plan.wardrobeItemIds).size !== plan.wardrobeItemIds.length ||
      !Array.isArray(plan.recommendedItems) ||
      !plan.recommendedItems.every(validateRecommendedItem) ||
      typeof plan.isFullyFromWardrobe !== "boolean" ||
      plan.isFullyFromWardrobe !== (plan.recommendedItems.length === 0) ||
      typeof plan.rationale !== "string" ||
      plan.rationale.length < 8 ||
      !Number.isInteger(plan.styleMatchScore) ||
      plan.styleMatchScore < 0 ||
      plan.styleMatchScore > 100 ||
      plan.tryOnImageUrl !== null ||
      plan.pixelCardUrl !== null
    ) {
      return false;
    }
    ids.add(plan.id);
  }
  return true;
}

async function matchOutfits(rawWardrobe, rawRequest, options = {}) {
  const items = normalizeWardrobe(rawWardrobe);
  const request = normalizeRequest(rawRequest);
  const fallbackPlans = buildFallbackCandidates(items, request);
  let outfitPlans = fallbackPlans;
  let degraded = true;
  let degradationReason = "llm_not_configured";
  const configuredLlm =
    options.llm === false ? null : options.llm || llmConfigFromEnvironment();
  if (options.llm === false) {
    degradationReason = "llm_disabled";
  } else if (configuredLlm) {
    try {
      outfitPlans = await rerankWithLlm(fallbackPlans, request, configuredLlm);
      degraded = false;
      degradationReason = null;
    } catch (error) {
      degradationReason =
        error instanceof Error ? error.message : "llm_rerank_failed";
    }
  }
  const response = {
    schemaVersion: SCHEMA_VERSION,
    requestId: randomUUID(),
    triggerType: request.triggerType,
    degraded,
    degradationReason,
    outfitPlans,
  };
  if (!validateMatchResponse(response)) {
    throw new Error("generated response does not match the OutfitPlan schema");
  }
  return response;
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === "--no-llm") {
      args.noLlm = true;
      continue;
    }
    if (!current.startsWith("--")) {
      throw new Error(`unexpected argument: ${current}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`${current} requires a value`);
    }
    args[current.slice(2)] = value;
    index += 1;
  }
  return args;
}

async function readJsonArgument(value) {
  const trimmed = asTrimmedString(value);
  if (!trimmed) throw new Error("JSON argument must not be empty");
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    return JSON.parse(trimmed);
  }
  return JSON.parse(await readFile(path.resolve(trimmed), "utf8"));
}

function usage() {
  return [
    "Usage:",
    "  node scripts/match.js --wardrobe <file> --request '<json-or-file>' [options]",
    "",
    "Options:",
    "  --no-llm                 Use deterministic fallback and mark degraded=true",
    "  --llm-base-url <url>     LiteLLM base URL",
    "  --timeout-ms <1..15000>  Per-call LLM timeout (default 12000)",
  ].join("\n");
}

async function main(argv) {
  const args = parseArgs(argv);
  if (!args.wardrobe || !args.request) {
    throw new Error(usage());
  }
  const wardrobe = await readJsonArgument(args.wardrobe);
  const request = await readJsonArgument(args.request);
  let llm;
  if (args.noLlm) {
    llm = false;
  } else if (args["llm-base-url"]) {
    const apiKey =
      asTrimmedString(process.env.STYLECAPTURE_LITELLM_API_KEY) ||
      asTrimmedString(process.env.LITELLM_MASTER_KEY);
    if (!apiKey) {
      throw new Error(
        "STYLECAPTURE_LITELLM_API_KEY or LITELLM_MASTER_KEY is required",
      );
    }
    llm = {
      baseUrl: args["llm-base-url"],
      apiKey,
      timeoutMs: Number(args["timeout-ms"]) || DEFAULT_LLM_TIMEOUT_MS,
    };
  }
  const result = await matchOutfits(wardrobe, request, { llm });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}

module.exports = {
  MAX_LLM_TIMEOUT_MS,
  SCHEMA_VERSION,
  matchOutfits,
  normalizeRequest,
  normalizeWardrobe,
  validateMatchResponse,
};
