import { fireEvent, render, screen } from "@testing-library/react";

import { ChatHistorySheet } from "../src/features/ai/ChatHistorySheet";
import type { ChatRecord } from "../src/features/ai/chatHistory";

const record: ChatRecord = {
  id: "conversation-1",
  date: "2026-08-10T09:30:00.000Z",
  theme: "通勤面试，利落但不刻板",
  last: "围绕面试通勤挑了四套，优先使用已有衣服。",
  outfitTitle: "衣橱优先方案 1",
  outfitLookId: "look-1",
  messages: [
    { role: "user", text: "明天面试穿什么？" },
    { role: "ai", text: "先从你的衣橱里搭四套。" }
  ]
};

describe("ChatHistorySheet", () => {
  it("uses an unboxed timeline row and reopens the conversation when clicked", () => {
    const onReopen = vi.fn();
    render(
      <ChatHistorySheet
        records={[record]}
        onReopen={onReopen}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("和 AI 聊过的 1 次")).toBeInTheDocument();
    expect(screen.getByText("最后穿了：衣橱优先方案 1")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "回看 08-10 的对话：通勤面试，利落但不刻板" })
    );
    expect(onReopen).toHaveBeenCalledWith(record);
  });
});
