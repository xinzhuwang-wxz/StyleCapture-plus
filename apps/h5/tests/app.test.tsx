import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { App } from "../src/app/App";
import { type Item, wardrobeApi } from "../src/api/client";

vi.mock("../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/client")>();
  return {
    ...actual,
    wardrobeApi: {
      listItems: vi.fn(),
      listLooks: vi.fn(),
      getLook: vi.fn(),
      addLikingReason: vi.fn(),
      retryLook: vi.fn(),
      ingest: vi.fn(),
      ingestFeedFrame: vi.fn(),
      getJob: vi.fn(),
      retryJob: vi.fn(),
      retryItem: vi.fn(),
      updateItem: vi.fn(),
      deleteSource: vi.fn(),
      sourceImage: vi.fn()
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
  source_image_url: "/v1/items/44444444-4444-4444-8444-444444444444/source",
  source_available: true,
  attributes: {
    category: {
      value: "上装",
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

describe("StyleCapture garment ingest", () => {
  beforeEach(() => {
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

  it("keeps camera and gallery inputs distinct", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("button", { name: "数字衣橱" }));

    const camera = screen.getByLabelText("拍摄衣物照片");
    const gallery = screen.getByLabelText("选择衣物照片");

    expect(camera).toHaveAttribute("capture", "environment");
    expect(gallery).not.toHaveAttribute("capture");
    expect(camera).toHaveAttribute("accept", expect.stringContaining("image/heic"));
  });

  it("requires ownership before a real upload can enter the wardrobe", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("button", { name: "数字衣橱" }));
    const file = new File(["real-image"], "jacket.jpg", { type: "image/jpeg" });

    await user.upload(screen.getByLabelText("选择衣物照片"), file);

    const confirmation = screen.getByRole("dialog", { name: "确认加入衣橱" });
    expect(within(confirmation).getByRole("heading", { name: "确认加入衣橱" })).toBeInTheDocument();
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
    expect(screen.queryByRole("heading", { name: "确认加入衣橱" })).not.toBeInTheDocument();
    expect(screen.getByText("正在理解这件衣服")).toBeInTheDocument();
  });

  it("rejects a non-image locally without opening the confirmation surface", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("button", { name: "数字衣橱" }));
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
    await user.click(screen.getByRole("button", { name: "数字衣橱" }));

    await user.click(
      await screen.findByRole("button", {
        name: "米白色针织上衣 可搭配 上装 我的衣服"
      })
    );
    await user.click(screen.getByRole("button", { name: "删除原图" }));

    expect(api.deleteSource).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("删除后原图无法恢复");

    await user.click(screen.getByRole("button", { name: "确认删除原图" }));

    await waitFor(() =>
      expect(api.deleteSource).toHaveBeenCalledWith(
        "44444444-4444-4444-8444-444444444444"
      )
    );
    expect(screen.queryByLabelText("原图不可用")).not.toBeInTheDocument();
  });
});
