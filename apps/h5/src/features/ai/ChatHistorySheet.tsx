import { PixelButton } from "../../components/PixelUI";
import { displayDate, type ChatRecord } from "./chatHistory";

type ChatHistorySheetProps = {
  records: readonly ChatRecord[];
  /** 回到当时说过的话。 */
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
  onReopen,
  onClose
}: ChatHistorySheetProps) {
  return (
    <section className="profile-page chat-history-page" aria-label="对话记录">
      <header className="chat-history-page__header">
        <PixelButton variant="ghost" onClick={onClose}>
          ‹ 返回
        </PixelButton>
        <h1>对话记录</h1>
      </header>

      <p className="chat-history-page__count">
        {records.length ? `和 AI 聊过的 ${records.length} 次` : "还没有记录"}
      </p>
      <h2 className="chat-history-page__title">聊过什么，最后穿了什么</h2>

      {records.length === 0 ? (
        <p className="profile__summary">
          和 AI 聊过之后，每次的主题和最终选定的搭配会记在这里，只存在这台设备上。
        </p>
      ) : (
        <ul className="chat-history">
          {records.map((record) => (
            <li key={record.id}>
              <button
                type="button"
                className="chat-history__row"
                aria-label={`回看 ${displayDate(record.date)} 的对话：${record.theme}`}
                onClick={() => onReopen(record)}
              >
                <time className="chat-history__date" dateTime={record.date}>
                  {displayDate(record.date)}
                </time>
                <span className="chat-history__body">
                  <strong>{record.theme}</strong>
                  {record.last ? (
                    <span className="chat-history__last">{record.last}</span>
                  ) : null}
                  {record.outfitTitle ? (
                    <span className="chat-history__outfit">
                      最后穿了：{record.outfitTitle}
                    </span>
                  ) : null}
                  <span className="chat-history__link">回看聊了什么 ›</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
