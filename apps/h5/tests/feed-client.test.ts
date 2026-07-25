import { vi } from "vitest";

import { wardrobeApi } from "../src/api/client";

describe("Feed capture client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uploads the real paused frame before submitting its normalized selection batch", async () => {
    const requests: Request[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const request =
          input instanceof Request
            ? input
            : new Request(
                typeof input === "string"
                  ? new URL(input, "http://localhost")
                  : input,
                init?.body instanceof File ? { ...init, body: undefined } : init
              );
        requests.push(request);
        if (request.url.endsWith("/v1/session")) {
          return new Response(null, { status: 204 });
        }
        if (request.url.endsWith("/v1/uploads/prepare")) {
          return Response.json({
            upload_url: "/v1/uploads/feed-token",
            upload_token: "feed-token",
            object_key: "capture/feed/frame.png",
            expires_at: "2026-07-25T10:00:00Z"
          });
        }
        if (request.url.endsWith("/v1/uploads/feed-token")) {
          return Response.json({
            object_key: "capture/feed/frame.png",
            content_type: "image/png",
            byte_size: 5,
            sha256: "0".repeat(64),
            width: 480,
            height: 854
          });
        }
        if (request.url.endsWith("/v1/captures")) {
          return Response.json(
            {
              capture_id: "22222222-2222-4222-8222-222222222222",
              job_id: "33333333-3333-4333-8333-333333333333",
              state: "queued",
              status_url: "/v1/jobs/33333333-3333-4333-8333-333333333333",
              events_url:
                "/v1/jobs/33333333-3333-4333-8333-333333333333/events"
            },
            { status: 202 }
          );
        }
        return new Response(null, { status: 404 });
      })
    );

    const frame = new File(["frame"], "frame.png", { type: "image/png" });
    Object.defineProperty(frame, "arrayBuffer", {
      value: async () => new TextEncoder().encode("frame").buffer
    });

    const accepted = await wardrobeApi.ingestFeedFrame(
      frame,
      {
        video_ref: "pexels-19862866",
        timestamp_ms: 2400,
        frame_width: 480,
        frame_height: 854,
        selections: [
          {
            selection_key: "selection-1",
            polygon: [
              { x: 0.1, y: 0.1 },
              { x: 0.7, y: 0.1 },
              { x: 0.7, y: 0.8 },
              { x: 0.1, y: 0.1 }
            ]
          }
        ]
      },
      "feed-batch-1"
    );

    expect(accepted.state).toBe("queued");
    const submit = requests.find((request) => request.url.endsWith("/v1/captures"));
    expect(submit).toBeDefined();
    expect(submit?.headers.get("Idempotency-Key")).toBe("feed-batch-1");
    await expect(submit?.json()).resolves.toMatchObject({
      source_kind: "feed",
      ownership: "inspiration",
      feed_context: {
        video_ref: "pexels-19862866",
        selections: [{ selection_key: "selection-1" }]
      }
    });
  });
});
