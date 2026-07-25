import { PixelButton } from "../../components/PixelUI";
import { CATALOG_OUTFITS } from "../wardrobe/catalog";
import "./ai.css";

/**
 * 过去的对话记录。没有真实后端会话时用这组人工写的演示记录，
 * 每条都指向衣橱里真实存在的那套穿搭。
 */
const HISTORY = [
  {
    date: "07-21",
    theme: "上班通勤 · 想显气质",
    last: "那就用棕黄这套，尖头鞋会更利落～",
    outfitId: CATALOG_OUTFITS[0].id
  },
  {
    date: "07-14",
    theme: "周末约会 · 甜一点",
    last: "抹茶开衫压住粉色，不会太腻 💜",
    outfitId: CATALOG_OUTFITS[1].id
  },
  {
    date: "07-06",
    theme: "逛街 · 要能走一天",
    last: "工装裤配板鞋，舒服又有型！",
    outfitId: CATALOG_OUTFITS[2].id
  },
  {
    date: "06-28",
    theme: "梅雨天 · 怕湿鞋",
    last: "先避开高跟，换成板鞋更稳妥。",
    outfitId: CATALOG_OUTFITS[2].id
  }
] as const;

export function ChatHistoryScreen({
  onBack,
  onOpenOutfit
}: {
  onBack: () => void;
  onOpenOutfit: (outfitId: string) => void;
}) {
  return (
    <div className="pixel-subpage">
      <div className="subpage__header">
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: 0 }}>
            和闺蜜聊过的 {HISTORY.length} 次
          </p>
          <h1 className="pixel-title" style={{ margin: 0, fontSize: "1.18rem" }}>
            对话记录
          </h1>
        </div>
      </div>

      <div className="chat-history">
        {HISTORY.map((entry) => {
          const outfit = CATALOG_OUTFITS.find((candidate) => candidate.id === entry.outfitId);
          return (
            <button
              key={`${entry.date}-${entry.theme}`}
              type="button"
              className="chat-history__row"
              onClick={() => onOpenOutfit(entry.outfitId)}
            >
              {outfit ? (
                <img src={outfit.pixelCoverUrl} alt={outfit.name} data-pixel="true" />
              ) : null}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="chat-history__title">
                  <strong>{entry.theme}</strong>
                  <span>{entry.date}</span>
                </div>
                <p>{entry.last}</p>
                {outfit ? <em>当时搭了「{outfit.name}」</em> : null}
              </div>
              <span aria-hidden="true" className="chat-history__chevron">
                ›
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
