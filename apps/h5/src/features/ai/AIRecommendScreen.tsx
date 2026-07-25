import { useEffect, useRef, useState } from "react";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { mockApi, type AIMessage, type MockOutfit } from "../../mock/mockApi";
import { pixelAvatarDataUrl } from "../../utils/pixelAvatar";

interface AIRecommendScreenProps {
  onOutfitClick: (outfitId: string) => void;
  /** 从 Feed「查看 AI 搭配」跳入时的预填内容 */
  presetPrompt?: string | null;
}

export function AIRecommendScreen({ onOutfitClick, presetPrompt }: AIRecommendScreenProps) {
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void mockApi.getAIMessages().then(setMessages);
  }, []);

  useEffect(() => {
    if (presetPrompt) setInput(presetPrompt);
  }, [presetPrompt]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async (content: string, theme?: string) => {
    if (!content.trim() || loading) return;
    setLoading(true);
    setInput("");
    await mockApi.sendAIMessage(content, theme);
    const newMessages = await mockApi.getAIMessages();
    setMessages(newMessages);
    setLoading(false);
  };

  const saveOutfit = async (outfit: MockOutfit) => {
    await mockApi.saveOutfit(outfit.id);
    setSavedIds((prev) => new Set(prev).add(outfit.id));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100dvh - 9.5rem)" }}>
      <PixelSectionHeader
        kicker="AI 穿搭闺蜜"
        title="今天想穿什么？"
        action={<span style={{ fontSize: "1.4rem" }} aria-hidden="true">💜</span>}
      />

      {/* 聊天区 */}
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
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--px-3)",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start"
            }}
          >
            <div className={`pixel-chat-bubble pixel-chat-bubble--${msg.role}`}>
              {msg.role === "ai" ? "👾 " : ""}
              {msg.content}
            </div>

            {/* 场景 / 风格选项 */}
            {msg.options ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--px-2)" }}>
                {msg.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    className="pixel-tag"
                    onClick={() => void sendMessage(opt, opt.replace(/[今天帮我来一套怎么穿好呢？]/g, ""))}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ) : null}

            {/* 三套拼贴穿搭 */}
            {msg.outfits ? (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: "var(--px-2)",
                  width: "100%"
                }}
              >
                {msg.outfits.map((outfit) => (
                  <div
                    key={outfit.id}
                    style={{
                      background: "var(--pixel-surface)",
                      border: "2px solid var(--pixel-border)",
                      borderRadius: "var(--pixel-radius-sm)",
                      boxShadow: "var(--pixel-shadow)",
                      overflow: "hidden"
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => onOutfitClick(outfit.id)}
                      style={{ padding: 0, border: "none", background: "none", width: "100%" }}
                      aria-label={`查看 ${outfit.name} 详情`}
                    >
                      <img
                        src={pixelAvatarDataUrl(outfit.seed, { size: 180 })}
                        alt={outfit.name}
                        data-pixel="true"
                        style={{ width: "100%" }}
                      />
                    </button>
                    <div style={{ padding: "var(--px-2)", textAlign: "center" }}>
                      <strong
                        style={{
                          fontFamily: "var(--font-pixel)",
                          fontSize: "0.62rem",
                          color: "var(--pixel-text)",
                          display: "block",
                          lineHeight: 1.4
                        }}
                      >
                        {outfit.name}
                      </strong>
                      <button
                        type="button"
                        className="pixel-tag"
                        style={{ marginTop: "4px", fontSize: "0.6rem" }}
                        disabled={savedIds.has(outfit.id)}
                        onClick={() => void saveOutfit(outfit)}
                      >
                        {savedIds.has(outfit.id) ? "✓ 已存衣橱" : "💜 存衣橱"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ))}

        {loading ? (
          <div className="pixel-chat-bubble pixel-chat-bubble--ai" style={{ opacity: 0.75 }}>
            <span className="pixel-pulse">👾 正在翻你的衣橱…</span>
          </div>
        ) : null}
      </div>

      {/* 输入区 */}
      <div
        style={{
          padding: "var(--px-3)",
          borderRadius: "var(--pixel-border-radius)",
          border: "2px solid var(--pixel-border)",
          background: "var(--pixel-surface)",
          boxShadow: "var(--pixel-shadow)"
        }}
      >
        <div style={{ display: "flex", gap: "var(--px-2)" }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void sendMessage(input);
            }}
            placeholder="和闺蜜聊聊穿搭吧～"
            style={{
              flex: 1,
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
            onClick={() => void sendMessage(input)}
            disabled={!input.trim() || loading}
            ariaLabel="发送"
          >
            ➤
          </PixelButton>
        </div>
      </div>
    </div>
  );
}
