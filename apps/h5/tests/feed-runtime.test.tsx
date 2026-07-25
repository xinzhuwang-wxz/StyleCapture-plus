import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor
} from "@testing-library/react";
import { vi } from "vitest";

import { type CaptureAccepted, wardrobeApi } from "../src/api/client";
import { FeedScreen } from "../src/features/feed/FeedScreen";
import { captureVideoFrame } from "../src/features/feed/frameCapture";
import * as frameCaptureModule from "../src/features/feed/frameCapture";
import {
  feedMediaUrl,
  loadFeedManifest
} from "../src/features/feed/manifest";

vi.mock("../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/client")>();
  return {
    ...actual,
    wardrobeApi: {
      ...actual.wardrobeApi,
      ingestFeedFrame: vi.fn()
    }
  };
});

const api = vi.mocked(wardrobeApi);
const accepted: CaptureAccepted = {
  capture_id: "22222222-2222-4222-8222-222222222222",
  job_id: "33333333-3333-4333-8333-333333333333",
  state: "queued",
  status_url: "/v1/jobs/33333333-3333-4333-8333-333333333333",
  events_url: "/v1/jobs/33333333-3333-4333-8333-333333333333/events"
};
const manifest = {
  schema_version: 1,
  assets: [
    {
      asset_id: "look-01",
      source_page_url: "https://example.test/look-01",
      source_platform: "Pexels",
      creator_name: "Demo creator",
      license_name: "Pexels License",
      license_url: "https://example.test/license",
      local_path: "media/look-01.mp4",
      content_type: "video",
      category_bucket: "layering",
      orientation: "portrait",
      sha256: "abc",
      replacement_note: "replaceable public demo asset",
      fixed_regression: true,
      annotation_provenance: "curated_seed",
      curated_seed_reason: "corpus coverage"
    },
    {
      asset_id: "look-02",
      source_page_url: "https://example.test/look-02",
      source_platform: "Pexels",
      creator_name: "Second creator",
      license_name: "Pexels License",
      license_url: "https://example.test/license",
      local_path: "media/look-02.mp4",
      content_type: "video",
      category_bucket: "accessories",
      orientation: "portrait",
      sha256: "def",
      replacement_note: "replaceable public demo asset",
      fixed_regression: false,
      annotation_provenance: "curated_seed",
      curated_seed_reason: "corpus coverage"
    }
  ]
} as const;

class BrowserLikePointerEvent extends MouseEvent {
  readonly pointerId: number;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
  }
}

function firePointer(
  target: HTMLElement,
  type: "pointerdown" | "pointermove" | "pointerup",
  init: PointerEventInit
) {
  fireEvent(
    target,
    new BrowserLikePointerEvent(type, {
      bubbles: true,
      cancelable: true,
      ...init
    })
  );
}

function renderFeed(onAccepted = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <FeedScreen
        api={{ ingestFeedFrame: api.ingestFeedFrame }}
        onAccepted={onAccepted}
        onEnterMini={vi.fn()}
        onViewAI={vi.fn()}
      />
    </QueryClientProvider>
  );
}

function installMediaAndCanvasDoubles() {
  const play = vi
    .spyOn(HTMLMediaElement.prototype, "play")
    .mockResolvedValue(undefined);
  const pause = vi
    .spyOn(HTMLMediaElement.prototype, "pause")
    .mockImplementation(() => undefined);
  const drawImage = vi.fn();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    drawImage
  } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(
    (callback) => callback(new Blob(["captured-frame"], { type: "image/png" }))
  );
  return { drawImage, pause, play };
}

function prepareVideo(video: HTMLVideoElement, timestampSeconds = 2.4) {
  Object.defineProperties(video, {
    videoWidth: { configurable: true, value: 1080 },
    videoHeight: { configurable: true, value: 2160 },
    currentTime: {
      configurable: true,
      value: timestampSeconds,
      writable: true
    }
  });
}

function stubCapturedFrame() {
  const file = new File(["captured-frame"], "look-01-2400.png", {
    type: "image/png"
  });
  return vi.spyOn(frameCaptureModule, "captureVideoFrame").mockResolvedValue({
    file,
    width: 1080,
    height: 2160,
    timestampMs: 2400
  });
}

async function drawAndConfirm() {
  const overlay = await screen.findByRole("application", {
    name: "圈选穿搭"
  });
  vi.spyOn(overlay, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 400,
    bottom: 800,
    width: 400,
    height: 800,
    toJSON: () => ({})
  });
  firePointer(overlay, "pointerdown", {
    pointerId: 1,
    clientX: 40,
    clientY: 80
  });
  firePointer(overlay, "pointermove", {
    pointerId: 1,
    clientX: 180,
    clientY: 80
  });
  firePointer(overlay, "pointermove", {
    pointerId: 1,
    clientX: 180,
    clientY: 300
  });
  firePointer(overlay, "pointerup", {
    pointerId: 1,
    clientX: 40,
    clientY: 80
  });
  await act(async () => {
    await new Promise((resolve) => window.setTimeout(resolve, 710));
  });
  await act(async () => {
    fireEvent.click(
      screen.getByRole("button", { name: "保存圈选到数字衣橱" })
    );
    await Promise.resolve();
  });
}

describe("Feed runtime", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
    );
    api.ingestFeedFrame.mockResolvedValue(accepted);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads only safe local video entries from the provenance manifest", async () => {
    await expect(loadFeedManifest()).resolves.toHaveLength(2);
    expect(feedMediaUrl("media/look-01.mp4")).toBe(
      "/feed/media/look-01.mp4"
    );
    expect(() => feedMediaUrl("../private.mp4")).toThrow(
      "Feed 素材路径无效"
    );
  });

  it("captures the decoded video frame as a real PNG File", async () => {
    const { drawImage } = installMediaAndCanvasDoubles();
    const video = document.createElement("video");
    prepareVideo(video, 1.275);

    const frame = await captureVideoFrame(video, "look-01");

    expect(drawImage).toHaveBeenCalledWith(video, 0, 0, 1080, 2160);
    expect(frame.file).toEqual(
      expect.objectContaining({
        name: "look-01-1275.png",
        type: "image/png"
      })
    );
    expect(frame).toMatchObject({
      width: 1080,
      height: 2160,
      timestampMs: 1275
    });
  });

  it("plays only the visible Feed video after a vertical snap", async () => {
    const { pause, play } = installMediaAndCanvasDoubles();
    renderFeed();

    const videos = (await screen.findAllByLabelText(
      /的穿搭视频$/
    )) as HTMLVideoElement[];
    videos.forEach((video) => {
      prepareVideo(video);
      fireEvent.canPlay(video);
    });
    await waitFor(() => expect(play).toHaveBeenCalled());
    pause.mockClear();
    play.mockClear();

    const feed = screen.getByTestId("feed");
    Object.defineProperties(feed, {
      clientHeight: { configurable: true, value: 800 },
      scrollTop: { configurable: true, value: 800, writable: true }
    });
    fireEvent.scroll(feed);

    await waitFor(() => {
      expect(pause.mock.instances).toContain(videos[0]);
      expect(play.mock.instances).toContain(videos[1]);
    });
  });

  it("submits normalized selections from the captured frame and resumes", async () => {
    const onAccepted = vi.fn();
    const { pause, play } = installMediaAndCanvasDoubles();
    const frameCapture = stubCapturedFrame();
    renderFeed(onAccepted);

    const initialVideo = await screen.findByLabelText("Demo creator 的穿搭视频");
    prepareVideo(initialVideo as HTMLVideoElement);
    fireEvent.canPlay(initialVideo);
    const video = screen.getByLabelText("Demo creator 的穿搭视频");
    prepareVideo(video as HTMLVideoElement);
    const selectButton = screen.getAllByRole("button", {
      name: "暂停并圈选"
    })[0]!;
    await waitFor(() => expect(selectButton).toBeEnabled());
    const pauseCount = pause.mock.calls.length;
    await act(async () => {
      fireEvent.click(selectButton);
      await Promise.resolve();
    });
    expect(pause.mock.calls.length).toBeGreaterThan(pauseCount);
    await waitFor(() =>
      expect(frameCapture).toHaveBeenCalledWith(video, "look-01")
    );

    await drawAndConfirm();

    // 圈选完成 → 弹出卡片，点击「存入衣橱」才真正保存
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /存入衣橱/ }));
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(api.ingestFeedFrame).toHaveBeenCalledWith(
        expect.objectContaining({ type: "image/png" }),
        {
          video_ref: "look-01",
          timestamp_ms: 2400,
          frame_width: 1080,
          frame_height: 2160,
          selections: [
            {
              selection_key: "selection-1",
              polygon: expect.arrayContaining([
                expect.objectContaining({
                  x: expect.any(Number),
                  y: expect.any(Number)
                })
              ])
            }
          ]
        },
        expect.any(String)
      )
    );
    expect(onAccepted).toHaveBeenCalledWith(accepted, expect.any(File));
    expect(await screen.findByText("已存入数字衣橱！")).toBeInTheDocument();

    // 点「继续刷」回到视频并恢复播放
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "继续刷" }));
      await Promise.resolve();
    });
    expect(play).toHaveBeenCalled();
  });

  it("keeps a failed decision for an idempotent retry", async () => {
    installMediaAndCanvasDoubles();
    stubCapturedFrame();
    api.ingestFeedFrame
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce(accepted);
    renderFeed();

    const initialVideo = await screen.findByLabelText("Demo creator 的穿搭视频");
    prepareVideo(initialVideo as HTMLVideoElement);
    fireEvent.canPlay(initialVideo);
    const video = screen.getByLabelText("Demo creator 的穿搭视频");
    prepareVideo(video as HTMLVideoElement);
    const selectButton = screen.getAllByRole("button", {
      name: "暂停并圈选"
    })[0]!;
    await waitFor(() => expect(selectButton).toBeEnabled());
    await act(async () => {
      fireEvent.click(selectButton);
      await Promise.resolve();
    });
    await drawAndConfirm();

    // 弹出卡片后点击保存，第一次失败 → 卡片进入错误态，幂等键保留
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /存入衣橱/ }));
      await Promise.resolve();
    });

    expect(await screen.findByText("😵 这次没存进去")).toBeInTheDocument();
    const firstKey = api.ingestFeedFrame.mock.calls[0]?.[2];
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "重试" }));
      await Promise.resolve();
    });
    await waitFor(() => expect(api.ingestFeedFrame).toHaveBeenCalledTimes(2));
    expect(api.ingestFeedFrame.mock.calls[1]?.[2]).toBe(firstKey);
  });

  it("shows an honest empty state when the corpus has no playable videos", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ schema_version: 1, assets: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    renderFeed();

    expect(
      await screen.findByText("暂时没有可播放的穿搭素材")
    ).toBeInTheDocument();
  });
});
