import { useCallback, useEffect, useState } from "react";

import { mockApi, type AIMessage, type MockOutfit } from "../../mock/mockApi";
import "./ai.css";

interface AIRecommendScreenProps {
  /** 从 Feed「查看 AI 搭配」跳入时的预填内容 */
  presetPrompt?: string | null;
  onOutfitClick: (outfitId: string) => void;
  onOpenHistory: () => void;
}

/** 提词模板：点标签把词拼进输入框，而不是直接发送，方便叠加。 */
const PROMPT_ROWS: readonly {
  readonly key: string;
  readonly label: string;
  readonly tone: "scene" | "style" | "weather";
  readonly options: readonly string[];
}[] = [
  {
    key: "scene",
    label: "场景",
    tone: "scene",
    options: ["上班通勤", "周末约会", "旅行拍照", "校园日常", "见家长"]
  },
  {
    key: "style",
    label: "风格",
    tone: "style",
    options: ["甜美", "复古", "简约", "辣妹", "美拉德"]
  },
  {
    key: "weather",
    label: "天气",
    tone: "weather",
    options: ["30℃ 很热", "降温 10℃", "梅雨天", "初秋微凉", "有风"]
  }
];

export function AIRecommendScreen({
  presetPrompt,
  onOutfitClick,
  onOpenHistory
}: AIRecommendScreenProps) {
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    void mockApi.getAIMessages().then(setMessages);
  }, []);

  useEffect(() => {
    if (presetPrompt) setDraft(presetPrompt);
  }, [presetPrompt]);

  const appendPrompt = useCallback((label: string) => {
    setDraft((current) => {
      const trimmed = current.trim();
      return trimmed ? `${trimmed} · ${label}` : label;
    });
  }, []);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setDraft("");
    // 先挂上用户气泡，不等接口返回，避免输入框「按了没反应」。
    setMessages((current) => [
      ...current,
      { id: `local-${Date.now()}`, role: "user", content: text }
    ]);
    try {
      const reply = await mockApi.sendAIMessage(text);
      setMessages((current) => [...current, reply]);
    } finally {
      setSending(false);
    }
  }, [draft, sending]);

  return (
    <>
      <div className="ai-screen__header">
        <h1 className="pixel-title ai-screen__title">🤖 AI 闺蜜</h1>
        <button type="button" className="pixel-tag" onClick={onOpenHistory}>
          对话记录 ›
        </button>
      </div>

      <div className="ai-screen__thread">
        {messages.map((message) => (
          <div key={message.id} className="ai-screen__turn">
            <div
              className={`pixel-chat-bubble pixel-chat-bubble--${
                message.role === "user" ? "user" : "ai"
              }`}
            >
              {message.content}
            </div>
            {message.outfits?.length ? (
              <div className="ai-screen__cards">
                {message.outfits.map((outfit: MockOutfit) => (
                  <article
                    key={outfit.id}
                    className="pixel-card ai-screen__card"
                    onClick={() => onOutfitClick(outfit.id)}
                  >
                    <div className="ai-screen__card-cover">
                      {outfit.pixelCoverUrl ? (
                        <img src={outfit.pixelCoverUrl} alt={outfit.name} data-pixel="true" />
                      ) : null}
                    </div>
                    <div className="ai-screen__card-name">{outfit.name}</div>
                  </article>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {sending ? (
          <div className="pixel-chat-bubble pixel-chat-bubble--ai" role="status">
            正在从你的衣橱里挑单品…
          </div>
        ) : null}
      </div>

      {/* 输入区固定在导航栏上方 */}
      <div className="ai-composer">
        {PROMPT_ROWS.map((row) => (
          <div key={row.key} className="ai-composer__row">
            <span className="ai-composer__row-label">{row.label}</span>
            {row.options.map((option) => (
              <button
                key={option}
                type="button"
                className="ai-composer__chip"
                data-tone={row.tone}
                onClick={() => appendPrompt(option)}
              >
                {option}
              </button>
            ))}
          </div>
        ))}

        <form
          className="ai-composer__input"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <input
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="和闺蜜聊聊穿搭吧～"
            aria-label="和 AI 闺蜜说点什么"
          />
          <button type="submit" aria-label="发送" disabled={!draft.trim() || sending}>
            ➤
          </button>
        </form>
      </div>
    </>
  );
}
