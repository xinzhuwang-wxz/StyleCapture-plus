import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { App } from "../src/app/App";
import {
  type CaptureAccepted,
  type Item,
  ProductApiError,
  type RenderArtifact,
  wardrobeApi
} from "../src/api/client";

vi.mock("../src/features/feed/FeedScreen", () => ({
  FeedScreen: ({
    onAccepted
  }: {
    onAccepted: (accepted: CaptureAccepted, file: File) => void;
  }) => (
    <button
      type="button"
      onClick={() =>
        onAccepted(
          {
            capture_id: "capture-feed-look",
            job_id: "job-feed-look",
            look_id: "look-feed-liked",
            state: "queued",
            status_url: "/v1/jobs/job-feed-look",
            events_url: "/v1/jobs/job-feed-look/events"
          },
          new File(["feed-frame"], "feed-frame.png", { type: "image/png" })
        )
      }
    >
      测试保存整套
    </button>
  )
}));

vi.mock("../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/client")>();
  return {
    ...actual,
    wardrobeApi: {
      listItems: vi.fn(),
      listLooks: vi.fn(),
      getLook: vi.fn(),
      listRenders: vi.fn(),
      createRender: vi.fn(),
      listPurchaseDemands: vi.fn(),
      addLikingReason: vi.fn(),
      retryLook: vi.fn(),
      ingest: vi.fn(),
      ingestFeedFrame: vi.fn(),
      getJob: vi.fn(),
      retryJob: vi.fn(),
      retryItem: vi.fn(),
      updateItem: vi.fn(),
      deleteSource: vi.fn(),
      displayImage: vi.fn(),
      createPixelTrial: vi.fn(),
      getPixelTrial: vi.fn(),
      deletePixelTrial: vi.fn()
    }
  };
});

const api = vi.mocked(wardrobeApi);
const wardrobeItem: Item = {
  id: "44444444-4444-4444-8444-444444444444",
  capture_id: "22222222-2222-4222-8222-222222222222",
  status: "ready",
  ownership: "owned",
  source_kind: "upload",
  display_image_url: "/v1/items/44444444-4444-4444-8444-444444444444/image",
  display_image_kind: "derived_garment",
  source_image_url: "/v1/items/44444444-4444-4444-8444-444444444444/source",
  source_available: true,
  attributes: {
    category: {
      value: "tops",
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

const collageRender: RenderArtifact = {
  id: "55555555-5555-4555-8555-555555555555",
  look_id: "11111111-1111-4111-8111-111111111111",
  kind: "collage",
  status: "queued",
  presentation_label: "真实单品拼贴",
  subject_attached: false,
  personalized: false,
  output_image_url: null,
  fallback_artifact_id: null,
  failure_code: null,
  failure_message: null,
  retryable: false,
  share_eligible: false,
  cache_hit: false,
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

describe("StyleCapture garment ingest", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ schema_version: 1, assets: [] }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" }
          }
        )
      )
    );
    api.listItems.mockResolvedValue([]);
    api.listLooks.mockResolvedValue([]);
    api.listRenders.mockResolvedValue([]);
    api.createRender.mockResolvedValue(collageRender);
    api.listPurchaseDemands.mockResolvedValue([]);
    api.addLikingReason.mockResolvedValue(undefined);
    api.ingest.mockResolvedValue({
      capture_id: "22222222-2222-4222-8222-222222222222",
      job_id: "33333333-3333-4333-8333-333333333333",
      state: "queued",
      status_url: "/v1/jobs/33333333-3333-4333-8333-333333333333",
      events_url: "/v1/jobs/33333333-3333-4333-8333-333333333333/events"
    });
    api.displayImage.mockResolvedValue("blob:item");
    api.createPixelTrial.mockResolvedValue({
      id: "77777777-7777-4777-8777-777777777777",
      status: "queued",
      output_image_url: null,
      failure_code: null,
      failure_message: null,
      retryable: true,
      subject_attached: true,
      created_at: "2026-07-25T00:00:00Z",
      updated_at: "2026-07-25T00:00:00Z"
    });
    api.getPixelTrial.mockResolvedValue({
      id: "77777777-7777-4777-8777-777777777777",
      status: "queued",
      output_image_url: null,
      failure_code: null,
      failure_message: null,
      retryable: true,
      subject_attached: true,
      created_at: "2026-07-25T00:00:00Z",
      updated_at: "2026-07-25T00:00:00Z"
    });
    api.deletePixelTrial.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads the wardrobe on entry and keeps it cached while users visit Feed", async () => {
    renderApp();

    await waitFor(() => {
      expect(api.listItems).toHaveBeenCalledTimes(1);
      expect(api.listLooks).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "刷灵感 Feed" }));
    fireEvent.click(screen.getByRole("button", { name: "数字衣橱" }));

    expect(api.listItems).toHaveBeenCalledTimes(1);
    expect(api.listLooks).toHaveBeenCalledTimes(1);
  });

  it("opens to the digital wardrobe first and lets users enter Feed from there", async () => {
    renderApp();

    expect(
      await screen.findByRole("heading", { name: "我的衣橱" })
    ).toBeVisible();
    expect(screen.getByRole("navigation", { name: "主要功能" })).toBeVisible();
    expect(screen.getByRole("button", { name: "刷灵感 Feed" })).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "刷灵感 Feed" }));

    expect(screen.getByLabelText("穿搭灵感")).toBeVisible();
    expect(screen.getByRole("button", { name: "数字衣橱" })).toBeVisible();
    expect(screen.queryByRole("navigation", { name: "主要功能" })).not.toBeInTheDocument();
  });

  it("opens the pixel world from the first-level navigation and returns to the wardrobe", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(await screen.findByRole("button", { name: "像素世界" }));

    expect(screen.getByLabelText("像素世界")).toBeVisible();
    expect(
      await screen.findByText(/预设角色非真人 · 非实时社区/)
    ).toBeVisible();
    expect(screen.queryByRole("navigation", { name: "主要功能" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "返回数字衣橱" }));

    expect(await screen.findByRole("heading", { name: "我的衣橱" })).toBeVisible();
    expect(screen.getByRole("navigation", { name: "主要功能" })).toBeVisible();
  });

  it("keeps optional Look feedback visible in Feed and dismisses it after saving", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("button", { name: "刷灵感 Feed" }));
    await user.click(screen.getByRole("button", { name: "测试保存整套" }));

    const prompt = await screen.findByRole("complementary", {
      name: "可选补充喜欢原因"
    });
    expect(within(prompt).getByText("顺手记一下喜欢它哪里？")).toBeVisible();

    await user.click(within(prompt).getByRole("button", { name: "层次感" }));

    await waitFor(() =>
      expect(api.addLikingReason).toHaveBeenCalledWith(
        "look-feed-liked",
        "层次感",
        expect.any(String)
      )
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("complementary", { name: "可选补充喜欢原因" })
      ).not.toBeInTheDocument()
    );
    expect(screen.getByLabelText("穿搭灵感")).toBeVisible();
  });

  it("removes a restored processing card when its backend job no longer exists", async () => {
    window.sessionStorage.setItem(
      "stylecapture:pending-items:v1",
      JSON.stringify([
        {
          captureId: "deleted-test-capture",
          jobId: "deleted-test-job",
          ownership: "owned",
          state: "processing"
        }
      ])
    );
    api.getJob.mockRejectedValue(
      new ProductApiError("job_not_found", "处理任务不存在")
    );
    renderApp();

    expect(screen.getByText("正在理解这件衣服")).toBeInTheDocument();

    await waitFor(
      () => expect(screen.queryByText("正在理解这件衣服")).not.toBeInTheDocument(),
      { timeout: 3_000 }
    );
    expect(window.sessionStorage.getItem("stylecapture:pending-items:v1")).toBeNull();
  });

  it("restores an opened Look after a page refresh without changing the wardrobe default", async () => {
    const lookId = "11111111-1111-4111-8111-111111111111";
    window.sessionStorage.setItem("stylecapture:selected-look:v1", lookId);
    api.getLook.mockResolvedValue({
      look: {
        id: lookId,
        capture_id: null,
        status: "ready",
        source: "ai_generated",
        display_image_url: null,
        source_image_url: null,
        display_ready: false,
        source_available: false,
        created_at: "2026-07-25T00:00:00Z",
        updated_at: "2026-07-25T00:00:00Z"
      },
      components: [],
      analysis: null,
      preferences: [],
      source_video_ref: null,
      source_timestamp_ms: null
    });

    renderApp();

    expect(await screen.findByRole("dialog", { name: "穿搭详情" })).toBeVisible();
    expect(screen.getByText("由衣橱真实单品组成")).toBeInTheDocument();
    expect(screen.queryByText("原始画面已删除")).not.toBeInTheDocument();
  });

  it("requests a real collage when opening a user-uploaded outfit with extracted items", async () => {
    const lookId = "11111111-1111-4111-8111-111111111111";
    window.sessionStorage.setItem("stylecapture:selected-look:v1", lookId);
    api.getLook.mockResolvedValue({
      look: {
        id: lookId,
        capture_id: null,
        status: "ready",
        source: "user_created",
        display_image_url: "/v1/looks/11111111-1111-4111-8111-111111111111/image",
        source_image_url: "/v1/looks/11111111-1111-4111-8111-111111111111/source",
        display_ready: true,
        source_available: true,
        created_at: "2026-07-25T00:00:00Z",
        updated_at: "2026-07-25T00:01:00Z"
      },
      components: [
        {
          component_key: "top",
          status: "ready",
          item_id: wardrobeItem.id,
          item_image_url: wardrobeItem.display_image_url,
          role: "tops",
          layer: "base",
          display_order: 0,
          confidence: 0.95
        }
      ],
      analysis: null,
      preferences: [],
      source_video_ref: null,
      source_timestamp_ms: null
    });

    renderApp();

    expect(await screen.findByRole("dialog", { name: "穿搭详情" })).toBeVisible();
    await waitFor(() =>
      expect(api.createRender).toHaveBeenCalledWith(
        lookId,
        "collage",
        "auto-collage:11111111-1111-4111-8111-111111111111:2026-07-25T00:01:00Z"
      )
    );
  });

  it("resets the wardrobe scroll position when switching primary destinations", async () => {
    const user = userEvent.setup();
    renderApp();
    const scrollContainer = document.querySelector<HTMLElement>(".pixel-app");
    expect(scrollContainer).not.toBeNull();
    scrollContainer!.scrollTop = 640;

    await user.click(screen.getByRole("button", { name: "分析" }));

    await waitFor(() => expect(scrollContainer!.scrollTop).toBe(0));
  });

  it("keeps camera and gallery inputs distinct", async () => {
    renderApp();

    const camera = screen.getByLabelText("拍摄衣物照片");
    const gallery = screen.getByLabelText("选择衣物照片");

    expect(camera).toHaveAttribute("capture", "environment");
    expect(gallery).not.toHaveAttribute("capture");
    expect(camera).toHaveAttribute("accept", expect.stringContaining("image/heic"));
    expect(gallery).toHaveAttribute("accept", expect.stringContaining(".heic"));
  });

  it("resets the non-Feed viewport scroll when switching primary tabs", async () => {
    const user = userEvent.setup();
    const scrollTo = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollTo", {
      configurable: true,
      value: scrollTo
    });
    const { container } = renderApp();

    const wardrobeViewport = container.querySelector(".product-view--wardrobe");
    expect(wardrobeViewport).toBeInstanceOf(HTMLElement);
    (wardrobeViewport as HTMLElement).scrollTop = 720;

    await user.click(screen.getByRole("button", { name: "我的" }));

    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: "auto" });

    delete (HTMLElement.prototype as { scrollTo?: unknown }).scrollTo;
  });

  it("requires an asset type and ownership before a real upload can enter the wardrobe", async () => {
    const user = userEvent.setup();
    renderApp();
    const file = new File(["real-image"], "jacket.jpg", { type: "image/jpeg" });

    await user.upload(screen.getByLabelText("选择衣物照片"), file);

    const confirmation = await screen.findByRole("dialog", {
      name: "确认加入衣橱"
    });
    expect(within(confirmation).getByRole("heading", { name: "确认加入衣橱" })).toBeInTheDocument();
    const submit = within(confirmation).getByRole("button", {
      name: "请选择保存类型"
    });
    expect(submit).toBeDisabled();

    await user.click(within(confirmation).getByRole("button", { name: /单件衣服/ }));
    const itemSubmit = within(confirmation).getByRole("button", {
      name: /加入单品衣橱/
    });
    expect(itemSubmit).toBeDisabled();
    await user.click(within(confirmation).getByRole("button", { name: /穿搭灵感/ }));
    await user.click(itemSubmit);

    await waitFor(() =>
      expect(api.ingest).toHaveBeenCalledWith(
        file,
        "upload",
        "inspiration",
        expect.any(String),
        "item"
      )
    );
    expect(screen.queryByRole("heading", { name: "确认加入衣橱" })).not.toBeInTheDocument();
    expect(screen.getByText("正在理解这件衣服")).toBeInTheDocument();
  });

  it("keeps HEIC upload usable without rendering a broken browser preview", async () => {
    const user = userEvent.setup();
    renderApp();
    const file = new File(["heic-bytes"], "wardrobe.HEIC", { type: "image/heic" });

    await user.upload(screen.getByLabelText("选择衣物照片"), file);

    const confirmation = await screen.findByRole("dialog", {
      name: "确认加入衣橱"
    });
    expect(within(confirmation).getByRole("status")).toHaveTextContent(
      "iPhone 照片已选中"
    );
    expect(
      within(confirmation).queryByRole("img", { name: "待加入衣橱的衣服" })
    ).not.toBeInTheDocument();

    await user.click(within(confirmation).getByRole("button", { name: /单件衣服/ }));
    await user.click(within(confirmation).getByRole("button", { name: /我的衣服/ }));
    await user.click(
      within(confirmation).getByRole("button", { name: /加入单品衣橱/ })
    );

    expect(screen.getByText("正在转换 iPhone 照片")).toBeInTheDocument();
  });

  it("submits a full-body upload as one Look for decomposition and pixel rendering", async () => {
    const user = userEvent.setup();
    api.ingest.mockResolvedValueOnce({
      capture_id: "capture-full-body",
      job_id: "job-full-body",
      look_id: "look-full-body",
      state: "queued",
      status_url: "/v1/jobs/job-full-body",
      events_url: "/v1/jobs/job-full-body/events"
    });
    renderApp();
    const file = new File(["full-body"], "full-body.jpg", { type: "image/jpeg" });

    await user.upload(screen.getByLabelText("选择衣物照片"), file);

    const confirmation = await screen.findByRole("dialog", {
      name: "确认加入衣橱"
    });
    await user.click(within(confirmation).getByRole("button", { name: /整套穿搭/ }));
    await user.click(within(confirmation).getByRole("button", { name: /我的衣服/ }));
    await user.click(
      within(confirmation).getByRole("button", {
        name: /保存整套并生成像素小人/
      })
    );

    await waitFor(() =>
      expect(api.ingest).toHaveBeenCalledWith(
        file,
        "upload",
        "owned",
        expect.any(String),
        "whole_outfit"
      )
    );
    expect(
      await screen.findByText("整套已保存，AI 正在拆解单品并准备像素小人")
    ).toBeInTheDocument();
  });

  it("rejects a non-image locally without opening the confirmation surface", async () => {
    renderApp();
    const file = new File(["not-an-image"], "notes.pdf", { type: "application/pdf" });

    fireEvent.change(screen.getByLabelText("选择衣物照片"), {
      target: { files: [file] }
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("请选择 JPG、PNG、WebP 或 HEIC");
    expect(screen.queryByRole("heading", { name: "确认加入衣橱" })).not.toBeInTheDocument();
    expect(api.ingest).not.toHaveBeenCalled();
  });

  it("requires an inline second confirmation before deleting a source image", async () => {
    const user = userEvent.setup();
    api.listItems.mockResolvedValue([wardrobeItem]);
    renderApp();

    await user.click(
      await screen.findByRole("button", {
        name: "米白色针织上衣 可搭配 上装 我的衣服"
      })
    );
    await user.click(
      await screen.findByRole("button", { name: "删除原图" })
    );

    expect(api.deleteSource).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "删除后原始上传图无法恢复"
    );

    await user.click(screen.getByRole("button", { name: "确认删除原图" }));

    await waitFor(() =>
      expect(api.deleteSource).toHaveBeenCalledWith(
        "44444444-4444-4444-8444-444444444444"
      )
    );
    expect(screen.queryByLabelText("原图不可用")).not.toBeInTheDocument();
  });

  it("shows category choices in Chinese while saving stable taxonomy ids", async () => {
    const user = userEvent.setup();
    api.listItems.mockResolvedValue([wardrobeItem]);
    api.updateItem.mockResolvedValue({
      ...wardrobeItem,
      attributes: {
        ...wardrobeItem.attributes,
        category: {
          ...wardrobeItem.attributes.category!,
          value: "dresses"
        }
      }
    });
    renderApp();

    await user.click(
      await screen.findByRole("button", {
        name: "米白色针织上衣 可搭配 上装 我的衣服"
      })
    );

    const category = screen.getByRole("combobox", { name: "分类" });
    expect(category).toHaveValue("tops");
    expect(screen.getByRole("option", { name: "上装" })).toHaveValue("tops");

    await user.selectOptions(category, "dresses");
    await user.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() =>
      expect(api.updateItem).toHaveBeenCalledWith(
        wardrobeItem.id,
        expect.objectContaining({
          corrections: expect.objectContaining({ category: "dresses" })
        })
      )
    );
  });

  it("uses a pixel first-level card and keeps the real display asset in item detail", async () => {
    api.listItems.mockResolvedValue([wardrobeItem]);
    renderApp();

    const pixelCard = await screen.findByRole("img", {
      name: "上装的像素图标"
    });
    expect(pixelCard).toHaveAttribute(
      "data-image-kind",
      "wardrobe-pixel-fallback"
    );
    expect(api.displayImage).not.toHaveBeenCalled();

    await userEvent.click(
      screen.getByRole("button", {
        name: "米白色针织上衣 可搭配 上装 我的衣服"
      })
    );
    await waitFor(() =>
      expect(api.displayImage).toHaveBeenCalledWith(wardrobeItem.id)
    );
    expect(
      await screen.findByRole("img", { name: "米白色针织上衣" })
    ).toHaveAttribute("data-image-kind", "wardrobe-display");
    expect(screen.getByRole("status")).toHaveTextContent(
      "当前展示已标准化的单品实物图；像素图只用于衣橱封面。"
    );
  });

  it("keeps wardrobe load errors distinct from an empty wardrobe and allows retry", async () => {
    const user = userEvent.setup();
    api.listItems
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce([wardrobeItem]);
    api.listLooks.mockResolvedValue([]);
    renderApp();

    await user.click(screen.getByRole("tab", { name: "按单品" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "衣橱暂时未加载，已有数据没有丢失"
    );
    expect(
      screen.queryByText("衣橱正在等第一件单品")
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重新加载" }));

    expect(
      await screen.findByRole("button", {
        name: "米白色针织上衣 可搭配 上装 我的衣服"
      })
    ).toBeInTheDocument();
  });

  it("focuses item detail on open and lets keyboard users close it with Escape", async () => {
    const user = userEvent.setup();
    api.listItems.mockResolvedValue([wardrobeItem]);
    renderApp();

    await user.click(
      await screen.findByRole("button", {
        name: "米白色针织上衣 可搭配 上装 我的衣服"
      })
    );

    const closeButton = await screen.findByRole("button", { name: "返回衣橱" });
    await waitFor(() => expect(closeButton).toHaveFocus());

    await user.keyboard("{Escape}");

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "单品详情" })).not.toBeInTheDocument()
    );
  });

  it("explains an ambiguous multi-garment upload instead of pretending the source is extracted", async () => {
    api.listItems.mockResolvedValue([
      {
        ...wardrobeItem,
        display_image_kind: "source_capture",
        display_image_issue: "multiple_garments"
      }
    ]);
    renderApp();

    await userEvent.click(
      await screen.findByRole("button", {
        name: "米白色针织上衣 可搭配 上装 我的衣服"
      })
    );

    expect(
      await screen.findByRole("img", { name: "米白色针织上衣" })
    ).toHaveAttribute("data-image-kind", "wardrobe-source-fallback");
    expect(screen.getByRole("status")).toHaveTextContent(
      "照片里识别到多件衣服。为避免抠错，当前保留原图"
    );
  });

  it("keeps profile pixel-trial uploads visible when status polling fails", async () => {
    const user = userEvent.setup();
    api.getPixelTrial.mockRejectedValueOnce(new Error("status unavailable"));
    renderApp();

    await user.click(await screen.findByRole("button", { name: "我的" }));
    const file = new File(["full-body"], "me.jpg", { type: "image/jpeg" });
    await user.upload(screen.getByLabelText("选择全身照生成像素形象"), file);

    const unavailableMessage = await screen.findByText(
      "像素形象状态暂时无法更新，已上传的照片不会丢失。"
    );
    expect(unavailableMessage).toBeInTheDocument();
    expect(screen.getByText("状态待恢复")).toBeInTheDocument();
    expect(screen.queryByText("未上传")).not.toBeInTheDocument();

    api.getPixelTrial.mockResolvedValueOnce({
      id: "77777777-7777-4777-8777-777777777777",
      status: "succeeded",
      output_image_url: "/v1/pixel-trials/77777777-7777-4777-8777-777777777777/image",
      failure_code: null,
      failure_message: null,
      retryable: false,
      subject_attached: true,
      created_at: "2026-07-25T00:00:00Z",
      updated_at: "2026-07-25T00:00:30Z"
    });
    await user.click(screen.getByRole("button", { name: "重试状态" }));

    expect(await screen.findByText("生成完成")).toBeInTheDocument();
  });
});
