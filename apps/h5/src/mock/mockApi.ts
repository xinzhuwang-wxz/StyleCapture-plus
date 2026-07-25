/**
 * Mock API Layer — 前后端解耦
 * 当 VITE_USE_MOCK=true 时，所有 API 调用走 Mock
 */

import type {
  CaptureAccepted,
  FeedFrameContext,
  Item,
  Job,
  Ownership,
  SourceKind
} from "../api/client";

// Helper to create a proper field
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

// ─── Mock Data ─────────────────────────────────────────

const MOCK_ITEMS: Item[] = [
  {
    id: "item-001",
    capture_id: "cap-001",
    ownership: "owned",
    status: "ready",
    source_kind: "camera",
    source_available: true,
    attributes: {
      category: field("上装", 0.95),
      subcategory: field("卫衣", 0.88),
      description: field("灰色连帽卫衣，oversize版型", 0.82),
      color: field("灰色", 0.96)
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    model_metadata: {},
    source_image_url: ""
  },
  {
    id: "item-002",
    capture_id: "cap-002",
    ownership: "inspiration",
    status: "ready",
    source_kind: "upload",
    source_available: true,
    attributes: {
      category: field("下装", 0.92),
      subcategory: field("牛仔裤", 0.85),
      description: field("复古水洗直筒牛仔裤", 0.78),
      color: field("蓝色", 0.94)
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    model_metadata: {},
    source_image_url: ""
  },
  {
    id: "item-003",
    capture_id: "cap-003",
    ownership: "owned",
    status: "ready",
    source_kind: "camera",
    source_available: true,
    attributes: {
      category: field("鞋子", 0.97),
      subcategory: field("运动鞋", 0.91),
      description: field("白色空军一号", 0.89),
      color: field("白色", 0.98)
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    model_metadata: {},
    source_image_url: ""
  },
  {
    id: "item-004",
    capture_id: "cap-004",
    ownership: "inspiration",
    status: "ready",
    source_kind: "feed",
    source_available: true,
    attributes: {
      category: field("配饰", 0.88),
      subcategory: field("帽子", 0.84),
      description: field("黑色渔夫帽", 0.76),
      color: field("黑色", 0.95)
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    model_metadata: {},
    source_image_url: ""
  },
  {
    id: "item-005",
    capture_id: "cap-005",
    ownership: "owned",
    status: "ready",
    source_kind: "camera",
    source_available: true,
    attributes: {
      category: field("上装", 0.93),
      subcategory: field("T恤", 0.87),
      description: field("黑色印花T恤", 0.81),
      color: field("黑色", 0.96)
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    model_metadata: {},
    source_image_url: ""
  },
  {
    id: "item-006",
    capture_id: "cap-006",
    ownership: "inspiration",
    status: "partial",
    source_kind: "upload",
    source_available: true,
    attributes: {
      category: field("外套", 0.79),
      subcategory: field("风衣", 0.72),
      description: field("卡其色中长款风衣", 0.68)
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    model_metadata: {},
    source_image_url: ""
  }
];

const MOCK_JOBS: Record<string, Job> = {};

const MOCK_OUTFITS = [
  {
    id: "outfit-001",
    name: "街头休闲风",
    items: ["item-001", "item-002", "item-003"],
    collageUrl: "https://images.unsplash.com/photo-1552374196-1ab2a1c593e8?w=400&h=500&fit=crop",
    pixelAvatarUrl: "https://images.unsplash.com/photo-1552374196-1ab2a1c593e8?w=200&h=200&fit=crop",
    description: "oversize卫衣+直筒牛仔裤+小白鞋，经典街头风格"
  },
  {
    id: "outfit-002",
    name: "简约通勤风",
    items: ["item-005", "item-002", "item-003"],
    collageUrl: "https://images.unsplash.com/photo-1487222477894-8943e31ef7b2?w=400&h=500&fit=crop",
    pixelAvatarUrl: "https://images.unsplash.com/photo-1487222477894-8943e31ef7b2?w=200&h=200&fit=crop",
    description: "黑T恤+牛仔裤+小白鞋，简约不简单"
  },
  {
    id: "outfit-003",
    name: "复古日系风",
    items: ["item-001", "item-004", "item-003"],
    collageUrl: "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=400&h=500&fit=crop",
    pixelAvatarUrl: "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=200&h=200&fit=crop",
    description: "卫衣+渔夫帽+小白鞋，日系复古感"
  }
];

type AIMessage = {
  id: string;
  role: "ai" | "user";
  content: string;
  options?: string[];
  outfits?: typeof MOCK_OUTFITS;
};

const MOCK_AI_MESSAGES: AIMessage[] = [
  {
    id: "msg-001",
    role: "ai",
    content: "嗨！我是你的 AI 穿搭顾问 👾\n\n今天想尝试什么风格呢？",
    options: ["街头休闲", "简约通勤", "复古日系", "运动风", "自由发挥"]
  }
];

let mockItems = [...MOCK_ITEMS];
let mockMessages = [...MOCK_AI_MESSAGES];

// ─── Helpers ───────────────────────────────────────────

function delay(ms = 600): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

// ─── Mock API ──────────────────────────────────────────

export const mockApi = {
  async ingest(
    file: File,
    sourceKind: SourceKind,
    ownership: Ownership,
    _idempotencyKey: string
  ): Promise<CaptureAccepted> {
    await delay(800);
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

    // Simulate completion
    setTimeout(() => {
      MOCK_JOBS[jobId] = {
        job_id: jobId,
        capture_id: captureId,
        state: "ready",
        attempt: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        error_code: null,
        error_message: null
      };
      const idx = mockItems.findIndex((i) => i.id === itemId);
      if (idx >= 0) {
        mockItems[idx] = {
          ...mockItems[idx],
          status: "ready",
          attributes: {
            category: field("上装", 0.9),
            subcategory: field("未知分类", 0.7),
            description: field(
              `来自${sourceKind === "camera" ? "拍照" : "相册"}的新衣服`,
              0.8
            ),
            color: field("多色", 0.6)
          }
        };
      }
    }, 3000);

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
    await delay(400);
    return [...mockItems];
  },

  async getJob(jobId: string): Promise<Job> {
    await delay(200);
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

  async retryJob(jobId: string): Promise<Job> {
    await delay(500);
    MOCK_JOBS[jobId] = {
      job_id: jobId,
      capture_id: randomId("cap"),
      state: "processing",
      attempt: (MOCK_JOBS[jobId]?.attempt ?? 0) + 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      error_code: null,
      error_message: null
    };
    return MOCK_JOBS[jobId];
  },

  async retryItem(_itemId: string): Promise<void> {
    await delay(500);
    // In mock, we just simulate
  },

  async updateItem(
    itemId: string,
    changes: {
      ownership?: Ownership;
      corrections?: Record<string, string | string[]>;
    }
  ): Promise<Item> {
    await delay(400);
    const idx = mockItems.findIndex((i) => i.id === itemId);
    if (idx < 0) throw new Error("Item not found");

    const updated = { ...mockItems[idx] };
    if (changes.ownership) updated.ownership = changes.ownership;
    if (changes.corrections) {
      for (const [key, value] of Object.entries(changes.corrections)) {
        const val = Array.isArray(value) ? value[0] : value;
        updated.attributes = {
          ...updated.attributes,
          [key]: field(val, 1)
        };
      }
    }
    mockItems[idx] = updated;
    return updated;
  },

  async deleteSource(itemId: string): Promise<void> {
    await delay(300);
    const idx = mockItems.findIndex((i) => i.id === itemId);
    if (idx >= 0) {
      mockItems[idx] = { ...mockItems[idx], source_available: false };
    }
  },

  async sourceImage(itemId: string): Promise<string> {
    await delay(200);
    const hue =
      itemId.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
    const canvas = document.createElement("canvas");
    canvas.width = 300;
    canvas.height = 400;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = `hsl(${hue}, 50%, 30%)`;
    ctx.fillRect(0, 0, 300, 400);
    ctx.fillStyle = `hsl(${hue}, 70%, 60%)`;
    ctx.fillRect(20, 20, 260, 360);
    ctx.fillStyle = "#fff";
    ctx.font = "20px monospace";
    ctx.textAlign = "center";
    ctx.fillText(itemId, 150, 200);
    return canvas.toDataURL("image/png");
  },

  // ─── Outfit / AI APIs ────────────────────────────────

  async listOutfits() {
    await delay(300);
    return [...MOCK_OUTFITS];
  },

  async getOutfit(outfitId: string) {
    await delay(200);
    return MOCK_OUTFITS.find((o) => o.id === outfitId) ?? null;
  },

  async generateOutfits(style: string) {
    await delay(1500);
    return MOCK_OUTFITS.map((o) => ({
      ...o,
      id: randomId("outfit"),
      name: `${style}·${o.name}`,
      description: `基于${style}风格生成的${o.description}`
    }));
  },

  async getAIMessages() {
    await delay(200);
    return [...mockMessages];
  },

  async sendAIMessage(content: string, style?: string) {
    await delay(800);
    const userMsg: AIMessage = {
      id: randomId("msg"),
      role: "user",
      content
    };
    const outfits = style ? await this.generateOutfits(style) : undefined;
    const aiResponse: AIMessage = outfits
      ? {
          id: randomId("msg"),
          role: "ai",
          content: `收到！为你推荐「${style}」风格的穿搭方案 👇`,
          outfits
        }
      : {
          id: randomId("msg"),
          role: "ai",
          content: "好的！我来帮你看看怎么搭配最合适 ✨",
          options: ["街头休闲", "简约通勤", "复古日系", "运动风"]
        };

    mockMessages = [...mockMessages, userMsg, aiResponse];
    return aiResponse;
  },

  reset() {
    mockItems = [...MOCK_ITEMS];
    mockMessages = [...MOCK_AI_MESSAGES];
    Object.keys(MOCK_JOBS).forEach((k) => delete MOCK_JOBS[k]);
  }
};
