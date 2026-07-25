import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { App } from "../src/app/App";
import type { Item } from "../src/api/client";

/**
 * 重构后 App 默认走 mockApi（前后端解耦），
 * 测试直接 mock mock 层，验证从 Feed 入口 → 小程序 → 入库的完整链路。
 */
vi.mock("../src/mock/mockApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/mock/mockApi")>();
  return {
    ...actual,
    mockApi: {
      ...actual.mockApi,
      listItems: vi.fn(),
      listWardrobeOutfits: vi.fn(),
      ingest: vi.fn(),
      ingestFeedFrame: vi.fn(),
      getJob: vi.fn(),
      retryItem: vi.fn(),
      updateItem: vi.fn(),
      deleteSource: vi.fn(),
      sourceImage: vi.fn()
    }
  };
});

const { mockApi } = await import("../src/mock/mockApi");
const api = vi.mocked(mockApi);

const wardrobeItem: Item = {
  id: "44444444-4444-4444-8444-444444444444",
  capture_id: "22222222-2222-4222-8222-222222222222",
  status: "ready",
  ownership: "owned",
  source_kind: "upload",
  source_image_url: "/v1/items/44444444-4444-4444-8444-444444444444/image",
  source_available: true,
  attributes: {
    category: {
      value: "上装",
      provenance: "model",
      confidence: 0.9,
      model_version: "test-model",
      locked: false
    },
    subcategory: {
      value: "米白针织衫",
      provenance: "model",
      confidence: 0.9,
      model_version: "test-model",
      locked: false
    },
    description: {
      value: "米白色针织上衣",
      provenance: "model",
      confidence: 0.9,
      model_version: "test-model",
      locked: false
    }
  },
  model_metadata: {},
  created_at: "2026-07-25T00:00:00Z",
  updated_at: "2026-07-25T00:00:00Z"
};

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
      mutations: { retry: false }
    }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

/** App 初始是独立 Feed 模式；空 Feed 时提供「直接进入小程序」入口 */
async function enterMini(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    await screen.findByRole("button", { name: "直接进入小程序" })
  );
}

describe("StyleCapture mini-program", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ schema_version: 1, assets: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
    );
    api.listItems.mockResolvedValue([]);
    api.listWardrobeOutfits.mockResolvedValue([]);
    api.ingest.mockResolvedValue({
      capture_id: "22222222-2222-4222-8222-222222222222",
      job_id: "33333333-3333-4333-8333-333333333333",
      state: "queued",
      status_url: "/v1/jobs/33333333-3333-4333-8333-333333333333",
      events_url: "/v1/jobs/33333333-3333-4333-8333-333333333333/events"
    });
    api.sourceImage.mockResolvedValue("blob:item");
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("starts in the standalone Feed mode and enters the mini-program", async () => {
    const user = userEvent.setup();
    renderApp();

    // Feed 空素材时的诚实空态 + 小程序入口
    expect(
      await screen.findByText("暂时没有可播放的穿搭素材")
    ).toBeInTheDocument();

    await enterMini(user);

    // 小程序四 Tab：数字衣橱 / AI推荐 / 穿搭分析 / 我的
    expect(screen.getByRole("button", { name: /数字衣橱/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AI推荐/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /穿搭分析/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /我的/ })).toBeInTheDocument();
  });

  it("keeps camera and gallery inputs distinct", async () => {
    const user = userEvent.setup();
    renderApp();
    await enterMini(user);

    const camera = screen.getByLabelText("拍摄衣物照片");
    const gallery = screen.getByLabelText("选择衣物照片");

    expect(camera).toHaveAttribute("capture", "environment");
    expect(gallery).not.toHaveAttribute("capture");
    expect(camera).toHaveAttribute("accept", expect.stringContaining("image/heic"));
  });

  it("requires ownership before a real upload can enter the wardrobe", async () => {
    const user = userEvent.setup();
    renderApp();
    await enterMini(user);
    const file = new File(["real-image"], "jacket.jpg", { type: "image/jpeg" });

    await user.upload(screen.getByLabelText("选择衣物照片"), file);

    const confirmation = screen.getByRole("dialog", { name: "确认加入衣橱" });
    expect(
      within(confirmation).getByRole("heading", { name: "确认加入衣橱" })
    ).toBeInTheDocument();
    const submit = within(confirmation).getByRole("button", { name: /加入衣橱/ });
    expect(submit).toBeDisabled();

    await user.click(within(confirmation).getByRole("button", { name: /穿搭灵感/ }));
    await user.click(submit);

    await waitFor(() =>
      expect(api.ingest).toHaveBeenCalledWith(
        file,
        "upload",
        "inspiration",
        expect.any(String)
      )
    );
    expect(
      screen.queryByRole("heading", { name: "确认加入衣橱" })
    ).not.toBeInTheDocument();

    // 入库处理中的卡片在「按单品」子页签里
    await user.click(screen.getByRole("tab", { name: /按单品/ }));
    expect(screen.getByText(/正在理解这件衣服/)).toBeInTheDocument();
  });

  it("rejects a non-image locally without opening the confirmation surface", async () => {
    const user = userEvent.setup();
    renderApp();
    await enterMini(user);
    const file = new File(["not-an-image"], "notes.pdf", { type: "application/pdf" });

    fireEvent.change(screen.getByLabelText("选择衣物照片"), {
      target: { files: [file] }
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "请选择 JPG、PNG、WebP 或 HEIC"
    );
    expect(
      screen.queryByRole("heading", { name: "确认加入衣橱" })
    ).not.toBeInTheDocument();
    expect(api.ingest).not.toBeCalled();
  });

  it("shows wardrobe items with ownership badges in the item sub-tab", async () => {
    const user = userEvent.setup();
    api.listItems.mockResolvedValue([wardrobeItem]);
    renderApp();
    await enterMini(user);

    await user.click(screen.getByRole("tab", { name: /按单品/ }));

    // 像素单品卡片 + ⭐ 已有角标（筛选器与卡片角标各出现一次）
    expect(await screen.findByText("米白针织衫")).toBeInTheDocument();
    expect(screen.getAllByText("⭐ 已有").length).toBeGreaterThanOrEqual(2);
  });
});
