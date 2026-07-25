/**
 * Mock API Layer — 前后端解耦
 * USE_MOCK=true 时，所有 API 调用走 Mock。
 * 后端联调时只需把 App 里的 api 换成 wardrobeApi。
 */

import type {
  CaptureAccepted,
  FeedFrameContext,
  Item,
  Job,
  Ownership,
  SourceKind
} from "../api/client";

type ItemField = {
  value: unknown;
  confidence: number;
  locked: boolean;
  model_version: string | null;
  provenance: "user" | "model" | "curated_seed";
};

function field(value: unknown, confidence = 1): ItemField {
  return {
    value,
    confidence,
    locked: false,
    model_version: null,
    provenance: "model"
  };
}

// ─── Types ─────────────────────────────────────────────

export type OutfitSlot = {
  name: string;
  category: string;
  owned: boolean;
  itemId?: string;
  price?: number;
};

export type MockOutfit = {
  id: string;
  name: string;
  style: string;
  scene: string;
  seed: string;
  description: string;
  slots: OutfitSlot[];
  /** 用户收藏（右上角黄色小星星） */
  favorited?: boolean;
};

export type AIMessage = {
  id: string;
  role: "ai" | "user";
  content: string;
  options?: string[];
  outfits?: MockOutfit[];
};

// ─── Mock Wardrobe Items ───────────────────────────────

function mockItem(
  id: string,
  ownership: Ownership,
  category: string,
  subcategory: string,
  description: string,
  color: string,
  sourceKind: SourceKind
): Item {
  return {
    id,
    capture_id: `cap-${id}`,
    ownership,
    status: "ready",
    source_kind: sourceKind,
    source_available: true,
    attributes: {
      category: field(category, 0.93),
      subcategory: field(subcategory, 0.87),
      description: field(description, 0.8),
      color: field(color, 0.9)
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    model_metadata: {},
    source_image_url: ""
  };
}

const MOCK_ITEMS: Item[] = [
  mockItem("item-001", "owned", "上装", "针织开衫", "粉色短款针织开衫，软软糯糯", "粉色", "camera"),
  mockItem("item-002", "owned", "下装", "白色阔腿裤", "高腰垂感白色阔腿裤", "白色", "camera"),
  mockItem("item-003", "owned", "鞋子", "粉色帆布鞋", "奶油粉低帮帆布鞋", "粉色", "upload"),
  mockItem("item-004", "owned", "配饰", "粉色棒球帽", "灯芯绒粉色棒球帽", "粉色", "camera"),
  mockItem("item-005", "inspiration", "上装", "娃娃领衬衫", "白色娃娃领雪纺衬衫", "白色", "feed"),
  mockItem("item-006", "inspiration", "下装", "牛仔A字裙", "复古浅蓝牛仔A字短裙", "蓝色", "feed"),
  mockItem("item-007", "inspiration", "包包", "菱格链条包", "奶白菱格链条小包", "白色", "feed"),
  mockItem("item-008", "owned", "外套", "奶油牛仔外套", " oversize 奶油白牛仔外套", "白色", "camera"),
  mockItem("item-009", "inspiration", "鞋子", "玛丽珍鞋", "黑色漆皮玛丽珍鞋", "黑色", "feed"),
  mockItem("item-010", "owned", "配饰", "珍珠发夹", "法式珍珠一字发夹", "白色", "upload")
];

const MOCK_JOBS: Record<string, Job> = {};

// ─── Mock Outfits ──────────────────────────────────────

function slots(...list: OutfitSlot[]): OutfitSlot[] {
  return list;
}

const MOCK_OUTFITS: MockOutfit[] = [
  {
    id: "outfit-001",
    name: "草莓牛奶约会装",
    style: "甜美",
    scene: "约会",
    seed: "outfit-strawberry",
    description: "粉色针织开衫 + 白色阔腿裤，甜度刚好的约会搭配。",
    slots: slots(
      { name: "粉色针织开衫", category: "上装", owned: true, itemId: "item-001", price: 129 },
      { name: "白色阔腿裤", category: "下装", owned: true, itemId: "item-002", price: 149 },
      { name: "粉色帆布鞋", category: "鞋子", owned: true, itemId: "item-003", price: 199 },
      { name: "粉色棒球帽", category: "配饰", owned: true, itemId: "item-004", price: 59 }
    )
  },
  {
    id: "outfit-002",
    name: "云朵通勤装",
    style: "简约",
    scene: "通勤",
    seed: "outfit-cloud",
    description: "娃娃领衬衫配牛仔裙，清清爽爽的上班Look。",
    slots: slots(
      { name: "娃娃领衬衫", category: "上装", owned: false, itemId: "item-005", price: 99 },
      { name: "牛仔A字裙", category: "下装", owned: false, itemId: "item-006", price: 139 },
      { name: "玛丽珍鞋", category: "鞋子", owned: false, itemId: "item-009", price: 259 },
      { name: "珍珠发夹", category: "配饰", owned: true, itemId: "item-010", price: 29 }
    )
  },
  {
    id: "outfit-003",
    name: "奶油周末出游装",
    style: "休闲",
    scene: "出游",
    seed: "outfit-cream",
    description: "奶油牛仔外套叠穿，随手一拍都很出片。",
    slots: slots(
      { name: "奶油牛仔外套", category: "外套", owned: true, itemId: "item-008", price: 229 },
      { name: "粉色针织开衫", category: "上装", owned: true, itemId: "item-001", price: 129 },
      { name: "牛仔A字裙", category: "下装", owned: false, itemId: "item-006", price: 139 },
      { name: "菱格链条包", category: "包包", owned: false, itemId: "item-007", price: 179 }
    )
  }
];

const AI_SCENES = ["约会", "通勤", "出游", "校园"];
const AI_STYLES = ["甜美", "简约", "休闲", "复古"];

const GREETING: AIMessage = {
  id: "msg-001",
  role: "ai",
  content: "嗨嗨！我是你的穿搭闺蜜 💜\n今天想听我分享什么呢？",
  options: ["今天约会穿哪套好呢？", "帮我搭一套通勤装", "周末出游怎么穿？", "来一套校园风"]
};

let mockItems = [...MOCK_ITEMS];
let mockMessages: AIMessage[] = [GREETING];
let wardrobeOutfits = [...MOCK_OUTFITS];
const favoriteOutfits = new Set<string>(["outfit-001"]);
const outfitPool: Record<string, MockOutfit> = {};
MOCK_OUTFITS.forEach((o) => { outfitPool[o.id] = o; });

function withFavorite<T extends MockOutfit>(outfit: T): T {
  return { ...outfit, favorited: favoriteOutfits.has(outfit.id) };
}

// ─── Helpers ───────────────────────────────────────────

function delay(ms = 600): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

export function douyinShopUrl(keyword: string): string {
  return `https://www.douyin.com/search/${encodeURIComponent(keyword)}`;
}

// ─── Mock API ──────────────────────────────────────────

export const mockApi = {
  async ingest(
    file: File,
    sourceKind: SourceKind,
    ownership: Ownership,
    _idempotencyKey: string
  ): Promise<CaptureAccepted> {
    await delay(600);
    const captureId = randomId("cap");
    const jobId = randomId("job");
    const itemId = randomId("item");

    const newItem: Item = {
      id: itemId,
      capture_id: captureId,
      ownership,
      status: "processing",
      source_kind: sourceKind,
      source_available: true,
      attributes: {
        category: field("正在识别…", 0),
        description: field(file.name, 0)
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      model_metadata: {},
      source_image_url: ""
    };

    mockItems = [newItem, ...mockItems];

    MOCK_JOBS[jobId] = {
      job_id: jobId,
      capture_id: captureId,
      state: "processing",
      attempt: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      error_code: null,
      error_message: null
    };

    setTimeout(() => {
      MOCK_JOBS[jobId] = { ...MOCK_JOBS[jobId], state: "ready", updated_at: new Date().toISOString() };
      const idx = mockItems.findIndex((i) => i.id === itemId);
      if (idx >= 0) {
        mockItems[idx] = {
          ...mockItems[idx],
          status: "ready",
          attributes: {
            category: field("上装", 0.9),
            subcategory: field("新收藏单品", 0.7),
            description: field(
              sourceKind === "feed" ? "从穿搭视频里圈选收藏" : "新加入衣橱的衣服",
              0.8
            ),
            color: field("多色", 0.6)
          }
        };
      }
    }, 2500);

    return {
      capture_id: captureId,
      job_id: jobId,
      state: "processing",
      events_url: `/v1/jobs/${jobId}/events`,
      status_url: `/v1/jobs/${jobId}`
    };
  },

  async ingestFeedFrame(
    file: File,
    _feedContext: FeedFrameContext,
    idempotencyKey: string
  ): Promise<CaptureAccepted> {
    return this.ingest(file, "feed", "inspiration", idempotencyKey);
  },

  async listItems(): Promise<Item[]> {
    await delay(300);
    return [...mockItems];
  },

  async getJob(jobId: string): Promise<Job> {
    await delay(150);
    return (
      MOCK_JOBS[jobId] ?? {
        job_id: jobId,
        capture_id: randomId("cap"),
        state: "ready",
        attempt: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        error_code: null,
        error_message: null
      }
    );
  },

  async retryItem(_itemId: string): Promise<void> {
    await delay(400);
  },

  async updateItem(
    itemId: string,
    changes: {
      ownership?: Ownership;
      corrections?: Record<string, string | string[]>;
    }
  ): Promise<Item> {
    await delay(300);
    const idx = mockItems.findIndex((i) => i.id === itemId);
    if (idx < 0) throw new Error("Item not found");

    const updated = { ...mockItems[idx] };
    if (changes.ownership) updated.ownership = changes.ownership;
    if (changes.corrections) {
      for (const [key, value] of Object.entries(changes.corrections)) {
        const val = Array.isArray(value) ? value[0] : value;
        updated.attributes = { ...updated.attributes, [key]: field(val, 1) };
      }
    }
    mockItems[idx] = updated;
    return updated;
  },

  async deleteSource(itemId: string): Promise<void> {
    await delay(250);
    const idx = mockItems.findIndex((i) => i.id === itemId);
    if (idx >= 0) {
      mockItems[idx] = { ...mockItems[idx], source_available: false };
    }
  },

  /** 写实风格单品图（占位：渐变 + 大字标签，联调后换成真实抠图） */
  async sourceImage(itemId: string): Promise<string> {
    await delay(120);
    const item = mockItems.find((i) => i.id === itemId);
    const hue = itemId.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
    const canvas = document.createElement("canvas");
    canvas.width = 480;
    canvas.height = 600;
    const ctx = canvas.getContext("2d")!;
    const grad = ctx.createLinearGradient(0, 0, 480, 600);
    grad.addColorStop(0, `hsl(${hue}, 65%, 88%)`);
    grad.addColorStop(1, `hsl(${(hue + 40) % 360}, 55%, 78%)`);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 480, 600);
    ctx.fillStyle = `hsl(${hue}, 45%, 55%)`;
    ctx.beginPath();
    ctx.roundRect(90, 140, 300, 320, 24);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.font = "bold 30px 'PingFang SC', sans-serif";
    ctx.textAlign = "center";
    const label = String(
      item?.attributes.subcategory?.value ?? item?.attributes.category?.value ?? "单品"
    );
    ctx.fillText(label, 240, 310);
    ctx.font = "18px 'PingFang SC', sans-serif";
    ctx.fillText("实物图 · 联调后替换", 240, 345);
    return canvas.toDataURL("image/png");
  },

  // ─── Outfit APIs ─────────────────────────────────────

  async listWardrobeOutfits(): Promise<MockOutfit[]> {
    await delay(250);
    return wardrobeOutfits.map(withFavorite);
  },

  async getOutfit(outfitId: string): Promise<MockOutfit | null> {
    await delay(150);
    const outfit = outfitPool[outfitId];
    return outfit ? withFavorite(outfit) : null;
  },

  /** 小红书式收藏：切换后返回最新收藏状态 */
  async toggleFavoriteOutfit(outfitId: string): Promise<boolean> {
    await delay(120);
    if (favoriteOutfits.has(outfitId)) {
      favoriteOutfits.delete(outfitId);
      return false;
    }
    favoriteOutfits.add(outfitId);
    return true;
  },

  async countFavorites(): Promise<number> {
    return favoriteOutfits.size;
  },

  async generateOutfits(theme: string): Promise<MockOutfit[]> {
    await delay(1200);
    return MOCK_OUTFITS.map((o) => {
      const generated: MockOutfit = {
        ...o,
        id: randomId("outfit"),
        name: `${theme} · ${o.name}`,
        description: `按「${theme}」为你重新搭配的 ${o.description}`
      };
      outfitPool[generated.id] = generated;
      return generated;
    });
  },

  async saveOutfit(outfitId: string): Promise<void> {
    await delay(250);
    const outfit = outfitPool[outfitId];
    if (outfit && !wardrobeOutfits.some((o) => o.id === outfitId)) {
      wardrobeOutfits = [outfit, ...wardrobeOutfits];
    }
  },

  async getAIScenes(): Promise<{ scenes: string[]; styles: string[] }> {
    return { scenes: [...AI_SCENES], styles: [...AI_STYLES] };
  },

  async getAIMessages(): Promise<AIMessage[]> {
    await delay(120);
    return [...mockMessages];
  },

  async sendAIMessage(content: string, theme?: string): Promise<AIMessage> {
    await delay(700);
    const userMsg: AIMessage = { id: randomId("msg"), role: "user", content };
    const wantsOutfits = Boolean(theme) || /约会|通勤|出游|校园|搭|穿/.test(content);
    let aiResponse: AIMessage;
    if (wantsOutfits) {
      const outfits = await this.generateOutfits(theme ?? content.slice(0, 6));
      aiResponse = {
        id: randomId("msg"),
        role: "ai",
        content: `收到！按你的想法搭了三套，点图片看详情，喜欢就存进穿搭图鉴吧 ✨`,
        outfits
      };
    } else {
      aiResponse = {
        id: randomId("msg"),
        role: "ai",
        content: "好呀～告诉我今天的场合或者想要的风格，我就能帮你搭三套出来 💜",
        options: ["今天约会穿哪套好呢？", "帮我搭一套通勤装", "周末出游怎么穿？", "来一套校园风"]
      };
    }
    mockMessages = [...mockMessages, userMsg, aiResponse];
    return aiResponse;
  },

  reset() {
    mockItems = [...MOCK_ITEMS];
    mockMessages = [GREETING];
    wardrobeOutfits = [...MOCK_OUTFITS];
    favoriteOutfits.clear();
    favoriteOutfits.add("outfit-001");
    Object.keys(MOCK_JOBS).forEach((k) => delete MOCK_JOBS[k]);
  }
};
