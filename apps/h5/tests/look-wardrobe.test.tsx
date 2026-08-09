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
  fixed_presentation: false,
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
    current: true,
    presentation_label: "真实单品拼贴",
    subject_attached: false,
    personalized: false,
    output_image_url:
      "/v1/render-artifacts/55555555-5555-4555-8555-555555555555/image",
    fallback_artifact_id: null,
    failure_code: null,
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

    expect(
      screen.getByRole("img", { name: "单品拼贴封面占位" })
    ).toHaveAttribute("data-image-kind", "look-source-placeholder");
    expect(screen.getByText("解析中")).toBeInTheDocument();
    expect(screen.getByText("穿搭已保存 · 正在整理")).toBeInTheDocument();
  });

  it("uses a blurred real collage while no pixel cover is selected", () => {
    render(
      <LookCard
        look={{ ...pendingLook, status: "ready" }}
        collageCover={renderArtifact()}
        onOpen={vi.fn()}
      />
    );

    const fallback = screen.getByRole("img", { name: "单品拼贴封面占位" });
    expect(fallback).toHaveAttribute("data-image-kind", "look-collage-placeholder");
    expect(fallback).toHaveClass("look-card__fallback-cover");
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
    expect(screen.getByText("已解析")).toBeInTheDocument();
    expect(screen.getByText("穿搭灵感 · 已收藏")).toBeInTheDocument();
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

    expect(
      screen.getByText("原始画面已删除，穿搭关系和已拆出的单品仍保留。")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新解析" })).toBeDisabled();
  });

  it("renders an AI-created Look as a component flatlay without a deleted-source warning", () => {
    const detail = readyDetail();
    detail.look = {
      ...detail.look,
      capture_id: null,
      source: "ai_generated",
      display_image_url: null,
      source_image_url: null,
      source_available: false
    };

    render(
      <LookDetail
        detail={detail}
        loading={false}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
      />
    );

    expect(screen.getByLabelText("套装单品平面拼贴")).toBeInTheDocument();
    expect(
      screen.queryByText("原始画面已删除，穿搭关系和已拆出的单品仍保留。")
    ).not.toBeInTheDocument();
  });

  it("labels an errored Look as failed instead of still processing", () => {
    const detail = partialDetail();
    detail.look = {
      ...detail.look,
      status: "error"
    };

    render(
      <LookDetail
        detail={detail}
        loading={false}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
      />
    );

    expect(screen.getByText("这次还没解析成功")).toBeInTheDocument();
    expect(screen.queryByText("后台处理中")).not.toBeInTheDocument();
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

    fireEvent.click(screen.getByRole("button", { name: "重新生成像素封面" }));
    expect(onGenerate).toHaveBeenCalledWith(pendingLook.id, "pixel_cover");
    expect(
      screen.queryByRole("button", { name: "分享像素封面" })
    ).not.toBeInTheDocument();
  });

  it("keeps the last successful pixel visible while a refresh is running", () => {
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[
          renderArtifact(),
          renderArtifact({
            id: "77777777-7777-4777-8777-777777777777",
            kind: "pixel_cover",
            presentation_label: "像素穿搭封面",
            share_eligible: true,
            output_image_url:
              "/v1/render-artifacts/77777777-7777-4777-8777-777777777777/image",
            updated_at: "2026-07-25T00:01:00Z"
          }),
          renderArtifact({
            id: "88888888-8888-4888-8888-888888888888",
            kind: "pixel_cover",
            status: "running",
            presentation_label: "像素穿搭封面",
            output_image_url: null,
            updated_at: "2026-07-25T00:02:00Z"
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
      />
    );

    fireEvent.click(screen.getByRole("tab", { name: "像素封面" }));

    expect(
      screen.getByRole("img", { name: "像素穿搭封面" })
    ).toHaveAttribute(
      "src",
      expect.stringContaining("77777777-7777-4777-8777-777777777777")
    );
    expect(screen.getByText("后台生成中…")).toBeInTheDocument();
  });

  it("uses a successful collage render as the Look detail hero and removes the collage tab", () => {
    const onGenerate = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[renderArtifact()]}
        rendersLoading={false}
        generatingKind={null}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
        onGenerate={onGenerate}
        onTryOn={vi.fn()}
      />
    );

    expect(
      screen.getByRole("img", { name: "真实单品拼贴" })
    ).toHaveAttribute(
      "src",
      expect.stringContaining("55555555-5555-4555-8555-555555555555")
    );
    expect(screen.queryByRole("tab", { name: "真实拼贴" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "真人试穿" }));
    expect(document.querySelector('input[capture="user"]')).not.toBeNull();
    expect(
      document.querySelector('.render-studio__preview img[alt="真实单品拼贴"]')
    ).toBeNull();
    expect(
      screen.getByText(
        "上传或拍摄一张正面全身照，AI 会把这套已保存穿搭换到你身上。"
      )
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "拍照或上传全身照" })
    ).toBeEnabled();

    fireEvent.click(screen.getByRole("tab", { name: "像素封面" }));
    expect(
      document.querySelector('.render-studio__preview img[alt="真实单品拼贴"]')
    ).toBeNull();
    expect(
      screen.getByText(
        "像素图只作为衣橱封面和分享锚点，真实单品仍以原图为准。"
      )
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "生成像素封面" }));
    expect(onGenerate).toHaveBeenCalledWith(pendingLook.id, "pixel_cover");
  });

  it("shows an explicit hero placeholder while the collage render is queued", () => {
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[
          renderArtifact({
            status: "queued",
            output_image_url: null,
            presentation_label: "真实单品拼贴排队中"
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
      />
    );

    expect(
      screen.getByRole("img", { name: "真实单品拼贴生成中" })
    ).toBeInTheDocument();
    expect(screen.getByText("正在生成整套拼贴")).toBeInTheDocument();
    expect(
      screen.queryByRole("img", { name: "收藏的真实整套穿搭" })
    ).not.toBeInTheDocument();
  });

  it("shows real item-image progress on the hero and each pending component", () => {
    const detail = readyDetail();
    detail.components = [
      {
        ...detail.components[0],
        item_image_status: "running"
      },
      {
        component_key: "bottom",
        status: "ready",
        item_id: "66666666-6666-4666-8666-666666666666",
        item_image_url: "/v1/item-presentations/66666666-6666-4666-8666-666666666666/image",
        item_image_status: "succeeded",
        role: "bottoms",
        layer: "base",
        display_order: 1,
        confidence: 0.91
      }
    ];

    render(
      <LookDetail
        detail={detail}
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

    expect(screen.getByText("正在生成单品图 1/2")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "单品图生成进度" })).toHaveAttribute(
      "value",
      "1"
    );
    expect(
      screen.getByRole("status", { name: "上装白底单品图生成中" })
    ).toBeInTheDocument();
    expect(screen.getByText("正在生成白底单品图")).toBeInTheDocument();
  });

  it("builds the hero flatlay from component images when no collage render is available", () => {
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

    const flatlay = screen.getByLabelText("套装单品平面拼贴");
    expect(flatlay.querySelector('img[alt="上装"]')).toHaveAttribute(
      "src",
      "/v1/items/44444444-4444-4444-8444-444444444444/image"
    );
  });

  it("rejects invalid try-on files before creating a pending generation", () => {
    const onTryOn = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[renderArtifact()]}
        rendersLoading={false}
        generatingKind={null}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
        onTryOn={onTryOn}
      />
    );

    fireEvent.click(screen.getByRole("tab", { name: "真人试穿" }));
    const input = document.querySelector('input[capture="user"]');
    expect(input).not.toBeNull();
    fireEvent.change(input!, {
      target: {
        files: [new File(["not an image"], "notes.txt", { type: "text/plain" })]
      }
    });

    expect(
      screen.getByText("请选择 JPG、PNG、WebP 或 HEIC 图片")
    ).toBeInTheDocument();
    expect(
      screen.queryByAltText("待确认的试穿全身照")
    ).not.toBeInTheDocument();
    expect(onTryOn).not.toHaveBeenCalled();
  });

  it("deletes only the original Look photo after an explicit confirmation", () => {
    const onDeleteSource = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
        onDeleteSource={onDeleteSource}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "删除整套原图" }));
    expect(
      screen.getByText("已拆出的单品、搭配关系和生成结果都会保留；删除后不能重新解析原图。")
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认删除原图" }));
    expect(onDeleteSource).toHaveBeenCalledWith(pendingLook.id);
  });

  it("closes the Look detail with Escape", () => {
    const onClose = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        retrying={false}
        saving={false}
        onClose={onClose}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
      />
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
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

  it("labels curated and human-reviewed relationship analysis as manual", () => {
    const detail = readyDetail();
    detail.analysis = {
      ...detail.analysis!,
      capability_alias: "curated_seed",
      model_version: "human_reviewed"
    };

    render(
      <LookDetail
        detail={detail}
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

    expect(screen.getByText("人工整理 · 示例搭配解析")).toBeInTheDocument();
    expect(screen.queryByText("AI 理解")).not.toBeInTheDocument();
  });

  it("keeps a curated example's component flatlay visible despite a stale queued collage", () => {
    const detail = readyDetail();
    detail.look.fixed_presentation = true;
    detail.analysis = {
      ...detail.analysis!,
      capability_alias: "curated_seed",
      model_version: "human_reviewed"
    };

    render(
      <LookDetail
        detail={detail}
        loading={false}
        renders={[
          renderArtifact({
            status: "queued",
            output_image_url: null
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
      />
    );

    expect(screen.queryByText("单品图生成中，请稍后")).not.toBeInTheDocument();
    const flatlay = screen.getByLabelText("套装单品平面拼贴");
    expect(flatlay.querySelector('img[alt="上装"]')).toHaveAttribute(
      "src",
      "/v1/items/44444444-4444-4444-8444-444444444444/image"
    );
  });

  it("offers a manual retry when a generated look collage fails", () => {
    const onGenerate = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[
          renderArtifact({
            status: "failed",
            output_image_url: null,
            retryable: true,
            failure_code: "provider_timeout",
            failure_message: "生成超时"
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

    expect(screen.getByText("真实单品拼贴暂未生成")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重新生成真实拼贴" }));
    expect(onGenerate).toHaveBeenCalledWith(pendingLook.id, "collage");
  });

  it("keeps the AI label for real model relationship analysis", () => {
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

    expect(screen.getByText("AI 理解")).toBeInTheDocument();
    expect(
      screen.queryByText("人工整理 · 示例搭配解析")
    ).not.toBeInTheDocument();
  });

  it("shows and advances missing purchase demands", () => {
    const onAdvancePurchaseDemand = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[]}
        purchaseDemands={[
          {
            id: "99999999-9999-4999-8999-999999999999",
            look_id: readyDetail().look.id,
            item_id: null,
            role: "shoes",
            search_query: "黑色乐福鞋",
            search_url: "https://www.douyin.com/search/黑色乐福鞋",
            status: "wanted",
            can_mark_owned: false
          }
        ]}
        purchaseDemandsLoading={false}
        generatingKind={null}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
        onAdvancePurchaseDemand={onAdvancePurchaseDemand}
      />
    );

    expect(screen.getByRole("heading", { name: "补齐这套" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "标记已下单" }));
    expect(onAdvancePurchaseDemand).toHaveBeenCalledWith(
      "99999999-9999-4999-8999-999999999999",
      "purchased_pending"
    );
  });

  it("never calls an unlinked purchase demand owned before photo intake", () => {
    const onAdvancePurchaseDemand = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[]}
        purchaseDemands={[
          {
            id: "99999999-9999-4999-8999-999999999999",
            look_id: readyDetail().look.id,
            item_id: null,
            role: "shoes",
            search_query: "黑色乐福鞋",
            search_url: "https://www.douyin.com/search/黑色乐福鞋",
            status: "purchased_pending",
            can_mark_owned: false
          }
        ]}
        purchaseDemandsLoading={false}
        generatingKind={null}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
        onAdvancePurchaseDemand={onAdvancePurchaseDemand}
      />
    );

    expect(screen.getByText("已下单，收到后需拍照入库")).toBeInTheDocument();
    expect(
      screen.getByText(
        "收到后请拍照上传；完成识别入库后才会成为「已拥有」。"
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "确认已收到" })
    ).not.toBeInTheDocument();
    expect(onAdvancePurchaseDemand).not.toHaveBeenCalled();
  });

  it("lets a linked inspiration item become owned when received", () => {
    const onAdvancePurchaseDemand = vi.fn();
    render(
      <LookDetail
        detail={readyDetail()}
        loading={false}
        renders={[]}
        purchaseDemands={[
          {
            id: "99999999-9999-4999-8999-999999999999",
            look_id: readyDetail().look.id,
            item_id: "44444444-4444-4444-8444-444444444444",
            role: "shoes",
            search_query: "黑色乐福鞋",
            search_url: "https://www.douyin.com/search/黑色乐福鞋",
            status: "purchased_pending",
            can_mark_owned: true
          }
        ]}
        purchaseDemandsLoading={false}
        generatingKind={null}
        retrying={false}
        saving={false}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
        onAdvancePurchaseDemand={onAdvancePurchaseDemand}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "确认已收到" }));
    expect(onAdvancePurchaseDemand).toHaveBeenCalledWith(
      "99999999-9999-4999-8999-999999999999",
      "owned"
    );
  });

  it("sends owned and missing components to the same backend-aware action flow", () => {
    const onOpenItem = vi.fn();
    const detail = readyDetail();
    detail.components = [
      ...detail.components,
      {
        component_key: "shoes",
        status: "ready",
        item_id: null,
        item_image_url: null,
        role: "shoes",
        layer: "base",
        display_order: 1,
        confidence: 0.9
      }
    ];
    render(
      <LookDetail
        detail={detail}
        loading={false}
        retrying={false}
        saving={false}
        onOpenItem={onOpenItem}
        purchaseDemands={[
          {
            id: "d1",
            look_id: detail.look.id,
            item_id: null,
            role: "shoes",
            status: "wanted",
            can_mark_owned: true,
            search_query: "白色小星板鞋",
            search_url: "https://www.douyin.com/search/%E7%99%BD%E8%89%B2"
          }
        ]}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: "查看单品操作：上装" })
    );
    expect(onOpenItem).toHaveBeenLastCalledWith({
      itemId: "44444444-4444-4444-8444-444444444444",
      label: "上装",
      imageUrl: "/v1/items/44444444-4444-4444-8444-444444444444/image",
      ownership: "inspiration",
      purchaseSearchUrl: null
    });

    fireEvent.click(
      screen.getByRole("button", { name: "查看单品操作：鞋履" })
    );
    expect(onOpenItem).toHaveBeenLastCalledWith({
      itemId: null,
      label: "鞋履",
      imageUrl: null,
      ownership: "inspiration",
      purchaseSearchUrl: "https://www.douyin.com/search/%E7%99%BD%E8%89%B2"
    });
  });

  it("leaves a missing item unclickable when there is no real query for it", () => {
    const detail = readyDetail();
    detail.components = [
      {
        component_key: "shoes",
        status: "ready",
        item_id: null,
        item_image_url: null,
        role: "shoes",
        layer: "base",
        display_order: 0,
        confidence: 0.9
      }
    ];
    render(
      <LookDetail
        detail={detail}
        loading={false}
        retrying={false}
        saving={false}
        onOpenItem={vi.fn()}
        onClose={vi.fn()}
        onReturnToSource={vi.fn()}
        onRetry={vi.fn()}
        onSaveReason={vi.fn()}
      />
    );

    // 没有搜索词时不给出口：一个点了搜不到东西的按钮比不给更糟。
    expect(screen.queryByRole("link", { name: /抖音/ })).not.toBeInTheDocument();
    expect(screen.getByText("保留中，等待补全")).toBeInTheDocument();
  });
});
