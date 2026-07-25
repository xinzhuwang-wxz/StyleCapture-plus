import { fireEvent, render, screen } from "@testing-library/react";

import type { Look, LookDetail as LookDetailData } from "../src/api/client";
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
    analysis: null,
    preferences: [],
    source_video_ref: "pexels-9512048",
    source_timestamp_ms: 2_300
  };
}

describe("Look wardrobe states", () => {
  it("shows an honest processing placeholder instead of the full source frame", () => {
    render(<LookCard look={pendingLook} onOpen={vi.fn()} />);

    expect(screen.queryByRole("img", { name: "收藏的整套穿搭" })).not.toBeInTheDocument();
    expect(screen.getByText("整套已保存，封面生成中")).toBeInTheDocument();
    expect(screen.getByText("正在拆解")).toBeInTheDocument();
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
});
