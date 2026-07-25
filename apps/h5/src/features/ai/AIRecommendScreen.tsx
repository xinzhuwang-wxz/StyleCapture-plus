import { useEffect, useRef, useState } from "react";
import { PixelButton, PixelCard, PixelSectionHeader } from "../../components/PixelUI";
import { mockApi } from "../../mock/mockApi";

interface AIRecommendScreenProps {
  onOutfitClick: (outfitId: string) => void;
}

type Message = {
  id: string;
  role: "ai" | "user";
  content: string;
  options?: string[];
  outfits?: any[];
};

export function AIRecommendScreen({ onOutfitClick }: AIRecommendScreenProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function init() {
      const msgs = await mockApi.getAIMessages();
      setMessages(msgs as Message[]);
    }
    void init();
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async (content: string, style?: string) => {
    if (!content.trim() || loading) return;
    setLoading(true);
    setInput("");

    await mockApi.sendAIMessage(content, style);
    const newMessages = await mockApi.getAIMessages();
    setMessages(newMessages as Message[]);
    setLoading(false);
  };

  return (
    <div className="pixel-app" style={{ display: "flex", flexDirection: "column", height: "100dvh", paddingBottom: 0 }}>
      {/* Header */}
      <PixelSectionHeader
        kicker="AI 穿搭顾问"
        title="像素搭配师"
      />

      {/* Chat Area */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--px-3)",
          padding: "var(--px-3) 0",
          marginBottom: "var(--px-3)"
        }}
      >
        {messages.map((msg) => (
          <div key={msg.id} style={{ display: "flex", flexDirection: "column", gap: "var(--px-3)", alignItems: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div className={`pixel-chat-bubble pixel-chat-bubble--${msg.role}`}>
              {msg.content}
            </div>

            {/* Style Options */}
            {msg.options ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--px-2)", paddingLeft: msg.role === "ai" ? "var(--px-2)" : 0, paddingRight: msg.role === "user" ? "var(--px-2)" : 0 }}>
                {msg.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    className="pixel-tag"
                    onClick={() => sendMessage(`我想看${opt}风格`, opt)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ) : null}

            {/* Outfit Recommendations */}
            {msg.outfits ? (
              <div className="pixel-grid" style={{ width: "100%" }}>
                {msg.outfits.map((outfit) => (
                  <PixelCard
                    key={outfit.id}
                    onClick={() => onOutfitClick(outfit.id)}
                    ariaLabel={outfit.name}
                  >
                    <div style={{ position: "relative" }}>
                      <img
                        src={outfit.collageUrl}
                        alt={outfit.name}
                        style={{
                          width: "100%",
                          aspectRatio: "4/5",
                          objectFit: "cover"
                        }}
                      />
                    </div>
                    <div style={{ padding: "var(--px-3)" }}>
                      <strong
                        style={{
                          fontFamily: "var(--font-pixel)",
                          fontSize: "0.78rem",
                          color: "var(--pixel-text)"
                        }}
                      >
                        {outfit.name}
                      </strong>
                      <p
                        style={{
                          margin: "4px 0 0",
                          fontSize: "0.65rem",
                          color: "var(--pixel-text-dim)",
                          lineHeight: 1.4
                        }}
                      >
                        {outfit.description.slice(0, 30)}...
                      </p>
                    </div>
                  </PixelCard>
                ))}
              </div>
            ) : null}
          </div>
        ))}

        {loading ? (
          <div className="pixel-chat-bubble pixel-chat-bubble--ai" style={{ opacity: 0.7 }}>
            <span className="pixel-pulse">正在搭配中…</span>
          </div>
        ) : null}
      </div>

      {/* Input Area */}
      <div
        style={{
          padding: "var(--px-3) var(--px-4)",
          borderTop: "2px dashed var(--pixel-border)",
          background: "var(--pixel-bg)",
          margin: "0 calc(-1 * var(--px-4))",
          marginBottom: "5rem"
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
            placeholder="描述你想要的风格…"
            style={{
              flex: 1,
              padding: "var(--px-3) var(--px-4)",
              fontFamily: "var(--font-body)",
              fontSize: "0.85rem",
              background: "var(--pixel-surface-raised)",
              border: "2px solid var(--pixel-border)",
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
            📤
          </PixelButton>
        </div>
      </div>
    </div>
  );
}
