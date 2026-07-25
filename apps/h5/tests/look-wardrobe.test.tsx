import { fireEvent, render, screen } from "@testing-library/react";

import type {
  Look,
  LookDetail as LookDetailData,
  RenderArtifact
} from "../src/api/client";
import { LookCard } from "../src/features/wardrobe/LookCard";
import { LookDetail } from "../src/features/wardrobe/LookDetail";

const pendingLook: Look = {
  id: "11111111-1111-4111-8111-111111111111",
  capture_id: "22222222-2222-4222-8222-222222222222",
  status: "processing",
  source: "feed_saved",
  display_image_url: null,
  source_image_url: "/v1/looks/11111111-1111-4111-8111-111111111111/source",
  display_ready: false,
  source_available: true,
  created_at: "2026-07-25T00:00:00Z",
  updated_at: "2026-07-25T00:00:00Z"
};

function partialDetail(sourceAvailable = true): LookDetailData {
  return {
    look: {
      ...pendingLook,
      status: "partial",
      source_available: sourceAvailable,
      source_image_url: sourceAvailable ? pendingLook.source_image_url : null
    },
    components: [],
    analysis: {
      capability_alias: "outfit_analysis",
      confidence: {
        color: 0.91,
        silhouette: 0.87,
        style: 0.92
      },
      model_version: "outfit-analysis-model-v1",
      prompt_version: "outfit-analysis-zh-v2",
      schema_version: "look-analysis-v1",
      taxonomy_version: "stylecapture-v1",
      values: {
        color: "黑底搭配银色花卉",
        silhouette: "修身连衣裙",
        style: "轻奢晚宴风"
      }
    },
    preferences: [],
    source_video_ref: "pexels-9512048",
    source_timestamp_ms: 2_300
  };
}

function readyDetail(): LookDetailData {
  return {
    ...partialDetail(),
    look: {
      ...pendingLook,
      status: "ready",
      display_ready: true,
      display_image_url: "/v1/looks/11111111-1111-4111-8111-111111111111/image"
    },
    components: [
      {
        component_key: "top",
        status: "ready",
        item_id: "44444444-4444-4444-8444-444444444444",
        item_image_url: "/v1/items/44444444-4444-4444-8444-444444444444/image",
        role: "tops",
        layer: "base",
        display_order: 0,
        confidence: 0.95
      }
    ]
  };
}

function renderArtifact(
  overrides: Partial<RenderArtifact> = {}
): RenderArtifact {
  return {
    id: "55555555-5555-4555-8555-555555555555",
    look_id: pendingLook.id,
    kind: "collage",
    status: "succeeded",
    presentation_label: "真实单品拼贴",
    personalized: false,
    output_image_url:
      "/v1/render-artifacts/55555555-5555-4555-8555-555555555555/image",
    fallback_artifact_id: null,
    failure_message: null,
    retryable: false,
    share_eligible: false,
    cache_hit: false,
    created_at: "2026-07-25T00:00:00Z",
    updated_at: "2026-07-25T00:00:00Z",
    ...overrides
  };
}

describe("Look wardrobe states", () => {
  it("shows an honest processing placeholder instead of the full source frame", () => {
    render(<LookCard look={pendingLook} onOpen={vi.fn()} />);

    expect(screen.queryByRole("img", { name: "收藏的整套穿搭" })).not.toBeInTheDocument();
    expect(screen.getByText("整套已保存，封面生成中")).toBeInTheDocument();
    expect(screen.getByText("正在拆解")).toBeInTheDocument();
  });

  it("uses a successful shareable pixel artifact as the wardrobe cover", () => {
    render(
      <LookCard
        look={{
          ...pendingLook,
          status: "ready",
          display_image_url: "/v1/looks/11111111-1111-4111-8111-111111111111/image"
        }}
        pixelCover={renderArtifact({
          kind: "pixel_cover",
          share_eligible: true
        })}
        onOpen={vi.fn()}
      />
    );

    expect(
      screen.getByRole("img", { name: "已生成的像素穿搭封面" })
    ).toHaveAttribute(
      "src",
      expect.stringContaining("55555555-5555-4555-8555-555555555555")
    );
    expect(screen.getByText("像素封面")).toBeInTheDocument();
  });

  it("keeps a partial Look retryable without losing its source evidence", () => {
    const onRetry = vi.fn();
    render(
      <LookDetail
        detail={partialDetail()}
        loading={false}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={onRetry}
        onSaveReason={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "重新解析" }));
    expect(onRetry).toHaveBeenCalledWith(pendingLook.id);
    expect(screen.getByRole("button", { name: "回看原视频 · 2.3s" })).toBeEnabled();
  });

  it("renders a deliberate source-deleted state and disables retry", () => {
    render(
      <LookDetail
        detail={partialDetail(false)}
        loading={false}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
      />
    );

    expect(screen.getByText("来源画面已删除")).toBeInTheDocument();
    expect(
      screen.getByText("原始画面已删除，穿搭关系和已拆出的单品仍保留。")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新解析" })).toBeDisabled();
  });

  it("keeps generated states honest and lets the user retry without hiding the real collage", () => {
    const onGenerate = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[
          renderArtifact(),
          renderArtifact({
            id: "66666666-6666-4666-8666-666666666666",
            kind: "pixel_cover",
            status: "degraded",
            presentation_label: "像素生成失败。展示真实拼贴",
            fallback_artifact_id: "55555555-5555-4555-8555-555555555555",
            failure_message: "像素生成暂不可用。展示真实单品拼贴",
            retryable: true,
            updated_at: "2026-07-25T00:01:00Z"
          })
        ]}
        rendersLoading={false}
        generatingKind={null}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
        onGenerate={onGenerate}
      />
    );

    fireEvent.click(screen.getByRole("tab", { name: "像素封面" }));

    const fallbackImage = screen.getByRole("img", {
      name: "像素生成失败。展示真实拼贴"
    });
    expect(fallbackImage).toHaveAttribute(
      "src",
      expect.stringContaining("55555555-5555-4555-8555-555555555555")
    );
    expect(
      screen.getAllByText("像素生成失败。展示真实拼贴")
    ).not.toHaveLength(0);
    expect(
      screen.getByText("像素图只作为衣橱封面和分享锚点，真实单品仍以原图为准。")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "生成像素封面" }));
    expect(onGenerate).toHaveBeenCalledWith(pendingLook.id, "pixel_cover");
    expect(
      screen.queryByRole("button", { name: "分享像素封面" })
    ).not.toBeInTheDocument();
  });

  it("localizes wardrobe taxonomy and outfit relationship labels for users", () => {
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[]}
        rendersLoading={false}
        generatingKind={null}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
      />
    );

    expect(screen.getByText("上装")).toBeInTheDocument();
    expect(screen.getByText("配色")).toBeInTheDocument();
    expect(screen.getByText("廓形")).toBeInTheDocument();
    expect(screen.getByText("整体风格")).toBeInTheDocument();
    expect(screen.getByText("黑底搭配银色花卉")).toBeInTheDocument();
    expect(screen.queryByText("tops")).not.toBeInTheDocument();
    expect(screen.queryByText("color")).not.toBeInTheDocument();
  });
});
