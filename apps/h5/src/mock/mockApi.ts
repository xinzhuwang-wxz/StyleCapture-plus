/**
 * Mock API Layer — 前后端解耦
 *
 * USE_MOCK=true 时衣橱/穿搭数据走这里；接后端时把 App 里的 api 换成 wardrobeApi。
 * 数据本体在 `features/wardrobe/catalog.ts`，这一层只负责模拟接口形状与时延。
 *
 * 注意：Look 的拼贴、真人试穿和像素封面**不**由这里编造，它们走
 * `features/render` 的 RenderPort（Issue #5 的统一 RenderArtifact 链）。
 */

import {
  CAPTURED_ITEM,
  CATALOG_ITEMS,
  CATALOG_OUTFITS,
  type CatalogItem
} from "../features/wardrobe/catalog";
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

function field(
  value: unknown,
  confidence = 1,
  provenance: ItemField["provenance"] = "curated_seed"
): ItemField {
  return { value, confidence, locked: false, model_version: null, provenance };
}

// ─── Types ─────────────────────────────────────────────

export type OutfitSlot = {
  itemId: string;
  name: string;
  category: string;
  owned: boolean;
  price: number;
  /** 1:1 像素单品图 */
  imageUrl: string;
};

export type MockOutfit = {
  id: string;
  name: string;
  style: string;
  scene: string;
  description: string;
  slots: OutfitSlot[];
  /** 人工审核的 3:4 像素封面；用户自由组合出来的穿搭没有，为 null */
  pixelCoverUrl: string | null;
  /** 人工审核的模特参考照；同上 */
  modelPhotoUrl: string | null;
  /** 用户收藏（左上角黄色小星星） */
  favorited?: boolean;
  /** true = 用户在「按单品」里自由组合保存的 */
  custom?: boolean;
};

export type AIMessage = {
  id: string;
  role: "ai" | "user";
  content: string;
  options?: string[];
  outfits?: MockOutfit[];
};

// ─── Catalog → API 形状 ─────────────────────────────────

function toItem(entry: CatalogItem): Item {
  return {
    id: entry.id,
    capture_id: `cap-${entry.id}`,
    ownership: entry.owned ? "owned" : "inspiration",
    status: "ready",
    // Product API 的 CaptureSourceKind 只有 upload/camera/feed；这些条目是
    // 人工审核的演示素材，来源类别记在字段级 provenance 上。
    source_kind: "upload",
    source_available: true,
    attributes: {
      category: field(entry.category),
      subcategory: field(entry.name),
      description: field(entry.description),
      price: field(entry.price)
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    model_metadata: {},
    source_image_url: entry.imageUrl
  };
}

function toSlot(entry: CatalogItem): OutfitSlot {
  return {
    itemId: entry.id,
    name: entry.name,
    category: entry.category,
    owned: entry.owned,
    price: entry.price,
    imageUrl: entry.imageUrl
  };
}

function catalogById(id: string): CatalogItem | undefined {
  return [...CATALOG_ITEMS, CAPTURED_ITEM].find((entry) => entry.id === id);
}

const SEED_OUTFITS: MockOutfit[] = CATALOG_OUTFITS.map((outfit) => ({
  id: outfit.id,
  name: outfit.name,
  style: outfit.style,
  scene: outfit.scene,
  description: outfit.description,
  pixelCoverUrl: outfit.pixelCoverUrl,
  modelPhotoUrl: outfit.modelPhotoUrl,
  slots: outfit.itemIds
    .map(catalogById)
    .filter((entry): entry is CatalogItem => Boolean(entry))
    .map(toSlot)
}));

const SEED_ITEMS: Item[] = CATALOG_ITEMS.map(toItem);

const MOCK_JOBS: Record<string, Job> = {};

const AI_SCENES = ["上班通勤", "周末约会", "旅行拍照", "校园日常", "见家长"];
const AI_STYLES = ["甜美", "复古", "简约", "辣妹", "美拉德"];
const AI_WEATHER = ["30℃ 很热", "降温 10℃", "梅雨天", "初秋微凉", "有风"];

const GREETING: AIMessage = {
  id: "msg-001",
  role: "ai",
  content: "嗨嗨！我是你的穿搭闺蜜 💜\n今天想去哪儿、想穿成什么样？"
};

let mockItems = [...SEED_ITEMS];
let mockMessages: AIMessage[] = [GREETING];
let wardrobeOutfits = [...SEED_OUTFITS];
const favoriteOutfits = new Set<string>([SEED_OUTFITS[0]?.id].filter(Boolean) as string[]);
const outfitPool: Record<string, MockOutfit> = {};
SEED_OUTFITS.forEach((outfit) => {
  outfitPool[outfit.id] = outfit;
});

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

export { douyinShopUrl } from "../features/wardrobe/catalog";

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
        category: field("正在识别…", 0, "model"),
        description: field(file.name, 0, "model")
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
      MOCK_JOBS[jobId] = {
        ...MOCK_JOBS[jobId],
        state: "ready",
        updated_at: new Date().toISOString()
      };
      const index = mockItems.findIndex((item) => item.id === itemId);
      if (index >= 0) {
        mockItems[index] = { ...toItem(CAPTURED_ITEM), id: itemId, capture_id: captureId };
      }
    }, 2300);

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
    const index = mockItems.findIndex((item) => item.id === itemId);
    if (index < 0) throw new Error("Item not found");

    const updated = { ...mockItems[index] };
    if (changes.ownership) updated.ownership = changes.ownership;
    if (changes.corrections) {
      for (const [key, value] of Object.entries(changes.corrections)) {
        const single = Array.isArray(value) ? value[0] : value;
        // 人工值优先于后续自动补全（CONTEXT.md 不变量）。
        updated.attributes = { ...updated.attributes, [key]: field(single, 1, "user") };
      }
    }
    mockItems[index] = updated;
    return updated;
  },

  async deleteSource(itemId: string): Promise<void> {
    await delay(250);
    const index = mockItems.findIndex((item) => item.id === itemId);
    if (index >= 0) {
      mockItems[index] = { ...mockItems[index], source_available: false };
    }
  },

  /** 单品原图地址。目录条目直接返回真实素材。 */
  async sourceImage(itemId: string): Promise<string> {
    await delay(120);
    return catalogById(itemId)?.imageUrl ?? CAPTURED_ITEM.imageUrl;
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

  /**
   * 保存用户在「按单品」里自由组合的新穿搭。
   *
   * 它没有 curated 素材，封面与试穿都交给 RenderPort 处理，
   * 因此 pixelCoverUrl / modelPhotoUrl 为 null。
   */
  async saveCustomOutfit(itemIds: readonly string[]): Promise<MockOutfit> {
    await delay(200);
    const entries = itemIds
      .map(catalogById)
      .filter((entry): entry is CatalogItem => Boolean(entry));
    const index = wardrobeOutfits.filter((outfit) => outfit.custom).length + 1;
    const outfit: MockOutfit = {
      id: randomId("look-custom"),
      name: `我的自由搭 ${index}`,
      style: "自由",
      scene: "自定义",
      description: `你自己挑的 ${entries.length} 件：${entries
        .map((entry) => entry.name)
        .join(" + ")}。AI 检查过品类没有冲突，可以直接穿出门。`,
      slots: entries.map(toSlot),
      pixelCoverUrl: null,
      modelPhotoUrl: null,
      custom: true
    };
    outfitPool[outfit.id] = outfit;
    wardrobeOutfits = [outfit, ...wardrobeOutfits];
    return outfit;
  },

  async saveOutfit(outfitId: string): Promise<void> {
    await delay(250);
    const outfit = outfitPool[outfitId];
    if (outfit && !wardrobeOutfits.some((candidate) => candidate.id === outfitId)) {
      wardrobeOutfits = [outfit, ...wardrobeOutfits];
    }
  },

  async getAIScenes(): Promise<{ scenes: string[]; styles: string[]; weather: string[] }> {
    return { scenes: [...AI_SCENES], styles: [...AI_STYLES], weather: [...AI_WEATHER] };
  },

  async getAIMessages(): Promise<AIMessage[]> {
    await delay(120);
    return [...mockMessages];
  },

  async sendAIMessage(content: string, theme?: string): Promise<AIMessage> {
    await delay(700);
    const userMessage: AIMessage = { id: randomId("msg"), role: "user", content };
    const response: AIMessage = {
      id: randomId("msg"),
      role: "ai",
      content: `收到「${content}」～我按这个方向从你衣橱里挑单品，这两套先看看 ✨`,
      outfits: [SEED_OUTFITS[0], SEED_OUTFITS[2]].filter(Boolean).map(withFavorite)
    };
    mockMessages = [...mockMessages, userMessage, response];
    return theme ? { ...response } : response;
  },

  reset() {
    mockItems = [...SEED_ITEMS];
    mockMessages = [GREETING];
    wardrobeOutfits = [...SEED_OUTFITS];
    favoriteOutfits.clear();
    if (SEED_OUTFITS[0]) favoriteOutfits.add(SEED_OUTFITS[0].id);
    Object.keys(outfitPool).forEach((key) => delete outfitPool[key]);
    SEED_OUTFITS.forEach((outfit) => {
      outfitPool[outfit.id] = outfit;
    });
    Object.keys(MOCK_JOBS).forEach((key) => delete MOCK_JOBS[key]);
  }
};
