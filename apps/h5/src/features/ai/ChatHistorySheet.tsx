import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { displayDate, type ChatRecord } from "./chatHistory";

type ChatHistorySheetProps = {
  records: readonly ChatRecord[];
  /** 打开那次最终存进衣橱的穿搭。 */
  onOpenLook: (lookId: string) => void;
  /** 没存下搭配的那几次，回到当时说过的话。 */
  onReopen: (record: ChatRecord) => void;
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
  onReopen,
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
              {/*
                看历史的目的就是「那天穿了什么」，所以整行可点：存过搭配就
                直接开那套，没存就回到当时说过的话。只有一个小按钮可点等于
                大部分行点不动。
              */}
              <button
                type="button"
                className="chat-history__row"
                aria-label={
                  record.outfitLookId
                    ? `打开 ${displayDate(record.date)} 选定的搭配：${record.outfitTitle}`
                    : `回看 ${displayDate(record.date)} 的对话：${record.theme}`
                }
                onClick={() =>
                  record.outfitLookId
                    ? onOpenLook(record.outfitLookId)
                    : onReopen(record)
                }
              >
                <span className="chat-history__head">
                  <span className="chat-history__date">
                    {displayDate(record.date)}
                  </span>
                  <strong>{record.theme}</strong>
                </span>
                {record.last ? (
                  <span className="chat-history__last">{record.last}</span>
                ) : null}
                <span className="chat-history__outfit">
                  {record.outfitTitle
                    ? `最终选定：${record.outfitTitle} ›`
                    : "这次没存下搭配 · 回看聊了什么 ›"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
