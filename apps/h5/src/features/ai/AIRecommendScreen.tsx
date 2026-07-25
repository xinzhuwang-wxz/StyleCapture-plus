import { useEffect, useRef, useState } from "react";

import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";

type ChatMessage = {
  id: string;
  role: "ai" | "user";
  content: string;
};

interface AIRecommendScreenProps {
  onGoWardrobe: () => void;
  presetPrompt?: string | null;
}

const unavailableMessage: ChatMessage = {
  id: "ai-unavailable",
  role: "ai",
  content:
    "真实 AI 搭配推荐接口还没有接入当前 H5。这里不会生成固定或模拟穿搭；可以先继续收藏真实单品和整套穿搭，等后端推荐端点接入后再从衣橱数据生成结果。"
};

export function AIRecommendScreen({
  onGoWardrobe,
  presetPrompt
}: AIRecommendScreenProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([unavailableMessage]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (presetPrompt) setInput(presetPrompt);
  }, [presetPrompt]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  function sendMessage(content: string) {
    const trimmed = content.trim();
    if (!trimmed) return;
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
      {
        id: crypto.randomUUID(),
        role: "ai",
        content:
          "已收到你的穿搭意图，但当前版本没有真实推荐 API，不能返回模拟搭配。请先到数字衣橱查看已保存的真实单品/穿搭。"
      }
    ]);
    setInput("");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100dvh - 9.5rem)" }}>
      <PixelSectionHeader
        kicker="AI 穿搭闺蜜"
        title="真实推荐待接入"
        action={<span style={{ fontSize: "1.4rem" }} aria-hidden="true">◇</span>}
      />

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--px-3)",
          padding: "var(--px-2) 0 var(--px-3)"
        }}
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`pixel-chat-bubble pixel-chat-bubble--${msg.role}`}
          >
            {msg.role === "ai" ? "◇ " : ""}
            {msg.content}
          </div>
        ))}

        <section
          style={{
            padding: "var(--px-3)",
            background: "var(--pixel-surface)",
            border: "2px dashed var(--pixel-secondary)",
            borderRadius: "var(--pixel-border-radius)",
            color: "var(--pixel-text-muted)",
            fontSize: "0.75rem",
            lineHeight: 1.7
          }}
          role="status"
        >
          当前可用数据源：真实衣橱单品、真实 Feed 收藏穿搭、穿搭详情与来源回看。
          推荐生成端点接入前，本页只展示不可用状态。
        </section>
      </div>

      <div
        style={{
          padding: "var(--px-3)",
          borderRadius: "var(--pixel-border-radius)",
          border: "2px solid var(--pixel-border)",
          background: "var(--pixel-surface)",
          boxShadow: "var(--pixel-shadow)"
        }}
      >
        <div style={{ display: "flex", gap: "var(--px-2)", marginBottom: "var(--px-2)" }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") sendMessage(input);
            }}
            placeholder="记录想法；真实推荐接口接入后会使用"
            style={{
              flex: 1,
              minWidth: 0,
              padding: "var(--px-2) var(--px-3)",
              fontFamily: "var(--font-body)",
              fontSize: "0.85rem",
              background: "var(--pixel-bg-light)",
              border: "2px solid var(--pixel-border-light)",
              borderRadius: "999px",
              color: "var(--pixel-text)",
              outline: "none"
            }}
          />
          <PixelButton
            variant="primary"
            onClick={() => sendMessage(input)}
            disabled={!input.trim()}
            ariaLabel="发送"
          >
            ➤
          </PixelButton>
        </div>
        <PixelButton variant="ghost" onClick={onGoWardrobe}>
          打开真实衣橱
        </PixelButton>
      </div>
    </div>
  );
}
