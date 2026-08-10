import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { MAX_BASKET_ITEMS, auditBasket, type BasketEntry } from "./basketRules";
import "./combo.css";

type ComboDetailSheetProps = {
  basket: readonly BasketEntry[];
  busy?: boolean;

  onRemove: (itemId: string) => void;
  onClear: () => void;
  /** 存成穿搭并生成效果封面。 */
  onCompose: () => void;
  /** 存成穿搭并打开详情，在那里走已有的上传+试穿流程。 */
  onTryOn: () => void;
  onClose: () => void;
};

/**
 * 组合衣柜的二级页：这一柜里都有什么，以及拿它做点什么。
 *
 * 两个生成按钮都必须手动点。它们各要跑一次真实的模型调用，自动触发等于
 * 每放一件衣服就烧一次额度。
 *
 * 关于顺序：后端的渲染是挂在已保存的穿搭上的，没有「草稿穿搭」这一层，
 * 所以这里是先存成穿搭再生成，而不是先看效果再决定存不存。按钮文案如实
 * 写成「存成穿搭并生成…」，不做「看完再说」的暗示。
 */
export function ComboDetailSheet({
  basket,
  busy,
  onRemove,
  onClear,
  onCompose,
  onTryOn,
  onClose
}: ComboDetailSheetProps) {
  const audit = auditBasket(basket);

  return (
    <section className="profile-page" aria-label="组合衣柜">
      <div className="subpage__header">
        <PixelButton variant="ghost" onClick={onClose}>
          ‹ 返回
        </PixelButton>
        <h2>组合衣柜</h2>
      </div>

      <PixelSectionHeader
        kicker={`已放入 ${basket.length} 件 · 最多 ${MAX_BASKET_ITEMS} 件`}
        title="这一柜里都有什么"
      />

      {basket.length === 0 ? (
        <p className="profile__summary">
          长按单品拖进衣柜，或点卡片上的「加入组合」。
        </p>
      ) : (
        <ul className="combo-detail__list">
          {basket.map((entry) => (
            <li key={entry.itemId}>
              {entry.imageUrl ? (
                <img src={entry.imageUrl} alt="" />
              ) : (
                <span className="combo-detail__blank" aria-hidden="true" />
              )}
              <span className="combo-detail__label">{entry.label}</span>
              <button
                type="button"
                aria-label={`把${entry.label}移出组合`}
                onClick={() => onRemove(entry.itemId)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="combo-detail__audit" role="status">
        {audit.ok ? "这一柜可以存成一套" : audit.reason}
      </p>

      <div className="combo-detail__actions">
        <PixelButton
          variant="primary"
          disabled={!audit.ok || busy}
          onClick={onCompose}
        >
          {busy ? "正在生成…" : "存成穿搭并生成效果封面"}
        </PixelButton>
        <PixelButton variant="accent" disabled={!audit.ok || busy} onClick={onTryOn}>
          存成穿搭去试穿
        </PixelButton>
        <PixelButton
          variant="ghost"
          disabled={!basket.length || busy}
          onClick={onClear}
        >
          清空
        </PixelButton>
      </div>

      <p className="combo-detail__audit">
        「去试穿」会存成穿搭并打开它的详情，在那里选一张全身照生成上身效果。
      </p>
    </section>
  );
}
