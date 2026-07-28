import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { displayDate, type ChatRecord } from "./chatHistory";

type ChatHistorySheetProps = {
  records: readonly ChatRecord[];
  /** 打开那次最终存进衣橱的穿搭。没存过的那几条没有这个出口。 */
  onOpenLook: (lookId: string) => void;
  onClose: () => void;
};

/**
 * 「对话记录」。每条是一次和 AI 聊过的：哪天、聊的什么、它最后说了什么、
 * 最终选定了哪套。
 *
 * 只读本机。没聊过就是空的——这里不摆样例对话，那会让人以为自己聊过。
 */
export function ChatHistorySheet({
  records,
  onOpenLook,
  onClose
}: ChatHistorySheetProps) {
  return (
    <section className="profile-page" aria-label="对话记录">
      <div className="subpage__header">
        <PixelButton variant="ghost" onClick={onClose}>
          ‹ 返回
        </PixelButton>
        <h2>对话记录</h2>
      </div>

      <PixelSectionHeader
        kicker={
          records.length ? `和闺蜜聊过的 ${records.length} 次` : "还没有记录"
        }
        title="聊过什么，最后穿了什么"
      />

      {records.length === 0 ? (
        <p className="profile__summary">
          和 AI 闺蜜聊过之后，每次的主题和最终选定的搭配会记在这里，只存在这台设备上。
        </p>
      ) : (
        <ul className="chat-history">
          {records.map((record) => (
            <li key={record.id}>
              <div className="chat-history__head">
                <span className="chat-history__date">
                  {displayDate(record.date)}
                </span>
                <strong>{record.theme}</strong>
              </div>
              {record.last ? (
                <p className="chat-history__last">{record.last}</p>
              ) : null}
              {record.outfitLookId && record.outfitTitle ? (
                <button
                  type="button"
                  className="chat-history__outfit"
                  onClick={() => onOpenLook(record.outfitLookId as string)}
                >
                  最终选定：{record.outfitTitle} ›
                </button>
              ) : (
                <p className="chat-history__outfit chat-history__outfit--none">
                  这次没有存下搭配
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
