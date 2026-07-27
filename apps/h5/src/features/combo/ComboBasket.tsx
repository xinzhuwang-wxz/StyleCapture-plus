import { PixelButton } from "../../components/PixelUI";
import {
  MAX_BASKET_ITEMS,
  auditBasket,
  type BasketEntry
} from "./basketRules";
import "./combo.css";

type ComboBasketProps = {
  basket: readonly BasketEntry[];
  open: boolean;
  /** 有人正在拖东西过来，把落点放大提示。 */
  receiving?: boolean;
  saving?: boolean;
  onToggle: () => void;
  onRemove: (itemId: string) => void;
  onClear: () => void;
  onSave: () => void;
};

/**
 * 「我的组合衣柜」——一个常驻的落点。
 *
 * 拖拽只是把东西放进来的一种方式，卡片上还有「加入组合」按钮走同一条路径；
 * 所以这个抽屉不依赖任何指针手势也能用完。
 */
export function ComboBasket({
  basket,
  open,
  receiving,
  saving,
  onToggle,
  onRemove,
  onClear,
  onSave
}: ComboBasketProps) {
  const audit = auditBasket(basket);

  return (
    <aside
      className="combo-door"
      data-open={open ? "true" : undefined}
      data-receiving={receiving ? "true" : undefined}
    >
      <button
        type="button"
        className="combo-door__handle"
        aria-expanded={open}
        aria-label={`我的组合衣柜，已放入 ${basket.length} 件`}
        onClick={onToggle}
      >
        <span aria-hidden="true">🚪</span>
        <strong>我的组合衣柜</strong>
        <span className="combo-door__count">{basket.length}</span>
      </button>

      {open ? (
        <div className="combo-door__panel">
          {basket.length ? (
            <ul className="combo-door__list">
              {basket.map((entry) => (
                <li key={entry.itemId}>
                  {entry.imageUrl ? (
                    <img src={entry.imageUrl} alt="" />
                  ) : (
                    <span className="combo-door__blank" aria-hidden="true" />
                  )}
                  <span className="combo-door__label">{entry.label}</span>
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
          ) : (
            <p className="combo-door__empty">
              长按单品拖进来，或点卡片上的「加入组合」
            </p>
          )}

          <p className="combo-door__audit" role="status">
            {audit.ok
              ? `可以存成一套（最多 ${MAX_BASKET_ITEMS} 件）`
              : audit.reason}
          </p>

          <div className="combo-door__actions">
            <PixelButton
              variant="primary"
              disabled={!audit.ok || saving}
              onClick={onSave}
            >
              {saving ? "保存中…" : "保存为新的穿搭 ✨"}
            </PixelButton>
            <PixelButton
              variant="ghost"
              disabled={!basket.length || saving}
              onClick={onClear}
            >
              清空
            </PixelButton>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
