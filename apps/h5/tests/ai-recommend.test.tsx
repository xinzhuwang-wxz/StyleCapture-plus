import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

function renderAI() {
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
});
