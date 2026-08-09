import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ComponentProps } from "react";
import userEvent from "@testing-library/user-event";

import { AIRecommendScreen } from "../src/features/ai/AIRecommendScreen";
import { wardrobeApi } from "../src/api/client";

vi.mock("../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/client")>();
  return {
    ...actual,
    wardrobeApi: {
      ...actual.wardrobeApi,
      planOutfitsProgressively: vi.fn()
    }
  };
});

const api = vi.mocked(wardrobeApi);

function renderAI(props: Partial<ComponentProps<typeof AIRecommendScreen>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AIRecommendScreen
        onGoWardrobe={vi.fn()}
        onSavedLook={vi.fn()}
        onOpenLook={vi.fn()}
        {...props}
      />
    </QueryClientProvider>
  );
}

describe("AI recommendation recovery", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("lets users retry the same failed outfit request without retyping", async () => {
    const user = userEvent.setup();
    api.planOutfitsProgressively
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce({
        request_id: "request-1",
        trace_id: "trace-1",
        plans: [],
        degraded: false,
        degradation_reason: null,
        explanation_state: "llm_ranked"
      });

    renderAI();

    await user.type(
      screen.getByRole("textbox", { name: "穿搭需求" }),
      "明天路演想要松弛但专业"
    );
    await user.click(screen.getByRole("button", { name: "生成穿搭推荐" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "搭配请求暂时没有完成，请稍后再试。"
    );
    await user.click(screen.getByRole("button", { name: "重试当前需求" }));

    await waitFor(() => expect(api.planOutfitsProgressively).toHaveBeenCalledTimes(2));
    expect(api.planOutfitsProgressively).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scene: "明天路演想要松弛但专业"
      }),
      expect.any(Function)
    );
  });

  it("treats the preset chips as shortcuts into the box, not as send", async () => {
    const user = userEvent.setup();
    renderAI();

    // 点场景和条件都只是帮你少打字。以前点一下就直接开始生成，用户还没
    // 来得及选天气就拿到了方案。
    await user.click(screen.getByRole("button", { name: /通勤面试/ }));
    await user.click(screen.getByRole("button", { name: "温和" }));

    const box = screen.getByLabelText("穿搭需求") as HTMLInputElement;
    expect(box.value).toContain("通勤面试");
    expect(box.value).toContain("温和");
    expect(api.planOutfitsProgressively).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "生成穿搭推荐" }));
    expect(api.planOutfitsProgressively).toHaveBeenCalledTimes(1);
  });

  it("sends the selected outfit count through the progressive Product API", async () => {
    const user = userEvent.setup();
    api.planOutfitsProgressively.mockResolvedValue({
      request_id: "request-3-plans",
      trace_id: "trace-3-plans",
      plans: [],
      degraded: false,
      degradation_reason: null,
      explanation_state: "llm_ranked"
    } as never);
    renderAI();

    await user.click(screen.getByRole("button", { name: "3 套" }));
    await user.type(screen.getByRole("textbox", { name: "穿搭需求" }), "周五面试");
    await user.click(screen.getByRole("button", { name: "生成穿搭推荐" }));

    await waitFor(() => expect(api.planOutfitsProgressively).toHaveBeenCalledTimes(1));
    expect(api.planOutfitsProgressively).toHaveBeenCalledWith(
      expect.objectContaining({
        scene: "周五面试",
        outfitCount: 3
      }),
      expect.any(Function)
    );
  });

  it("opens item mode and waits for explicit confirmation before analyzing the wardrobe item", async () => {
    const user = userEvent.setup();
    api.planOutfitsProgressively.mockResolvedValue({
      request_id: "anchored-request",
      trace_id: "anchored-trace",
      plans: [],
      degraded: false,
      degradation_reason: null,
      explanation_state: "llm_ranked"
    } as never);

    renderAI({
      anchorItemId: "item-1",
      wardrobeItems: [
        {
          id: "item-1",
          status: "ready",
          ownership: "owned",
          display_image_url: "/item-1.png",
          pixel_image_url: null,
          attributes: { category: { value: "tops" } }
        } as never
      ]
    });

    expect(screen.getByRole("button", { name: "按单品搭配" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByText("必须出现在每套方案中")).toBeVisible();
    expect(api.planOutfitsProgressively).not.toHaveBeenCalled();
    const confirm = screen.getByRole("button", { name: "确定并推荐" });
    expect(confirm).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "温和" }));
    await user.click(screen.getByRole("button", { name: "日常得体" }));
    await user.click(screen.getByRole("button", { name: "方便走路" }));
    expect(confirm).toBeEnabled();

    await user.click(confirm);

    await waitFor(() => expect(api.planOutfitsProgressively).toHaveBeenCalledTimes(1));
    expect(api.planOutfitsProgressively).toHaveBeenCalledWith(
      expect.objectContaining({
        scene: "日常通用，围绕这件单品搭配",
        anchorItemId: "item-1",
        weather: "温和",
        formality: "日常得体",
        comfort: "方便走路"
      }),
      expect.any(Function)
    );
  });

  it("shows only six wardrobe anchors and sends More back to the wardrobe item tab", async () => {
    const user = userEvent.setup();
    const onGoWardrobeItems = vi.fn();
    renderAI({
      onGoWardrobeItems,
      wardrobeItems: Array.from({ length: 7 }, (_, index) => ({
        id: `item-${index + 1}`,
        status: "ready",
        ownership: "owned",
        display_image_url: `/item-${index + 1}.png`,
        pixel_image_url: null,
        attributes: { subcategory: { value: `单品${index + 1}` } }
      })) as never
    });

    await user.click(screen.getByRole("button", { name: "按单品搭配" }));

    expect(screen.getAllByRole("button", { name: /^选择/ })).toHaveLength(6);
    expect(screen.queryByRole("button", { name: "选择单品7" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "更多" }));
    expect(onGoWardrobeItems).toHaveBeenCalledTimes(1);
  });

  it("keeps the thread open so the next message can adjust the last answer", async () => {
    const user = userEvent.setup();
    api.planOutfitsProgressively
      .mockResolvedValueOnce({
        request_id: "r1",
        trace_id: "t1",
        plans: [
          {
            id: "plan-1",
            title: "第一轮方案",
            scene: "周五面试",
            slots: [],
            rationale: "第一轮推荐理由",
            style_match_score: 91,
            missing_count: 0
          }
        ],
        degraded: false,
        degradation_reason: null,
        explanation_state: "llm_ranked"
      } as never)
      .mockResolvedValueOnce({
        request_id: "r2",
        trace_id: "t2",
        plans: [
          {
            id: "plan-2",
            title: "第二轮方案",
            scene: "周五面试；鞋子换平底",
            slots: [],
            rationale: "第二轮推荐理由",
            style_match_score: 89,
            missing_count: 0
          }
        ],
        degraded: false,
        degradation_reason: null,
        explanation_state: "llm_ranked"
      } as never);
    renderAI();

    const box = screen.getByLabelText("穿搭需求");
    await user.type(box, "周五面试");
    await user.click(screen.getByRole("button", { name: "生成穿搭推荐" }));
    await screen.findByText("周五面试");

    // 发完输入框要空出来，否则没法说下一句——这正是用户说的「只能发一次」。
    expect((box as HTMLInputElement).value).toBe("");

    await user.type(box, "鞋子换平底");
    await user.click(screen.getByRole("button", { name: "生成穿搭推荐" }));
    await screen.findByText("鞋子换平底");
    expect(screen.getByText("第一轮方案")).toBeVisible();
    expect(screen.getByText("第二轮方案")).toBeVisible();

    // 第二句要带着第一句一起发，AI 才知道是在调整而不是重开。
    const lastCall = api.planOutfitsProgressively.mock.calls.at(-1);
    expect(lastCall?.[0].scene).toBe("周五面试；鞋子换平底");
  });
});
