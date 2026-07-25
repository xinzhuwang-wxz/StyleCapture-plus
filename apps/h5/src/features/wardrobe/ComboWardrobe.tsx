import type { CatalogItem } from "./catalog";

/**
 * 悬浮像素衣柜：长按单品拖进来即可组合成新穿搭。
 *
 * 拖入瞬间柜门自动打开、角标数字 +1，随后柜门自动关闭（由父组件的 `doorOpen`
 * 驱动）。点击整个组件展开底部抽屉查看已选单品。
 */
export function ComboWardrobe({
  count,
  doorOpen,
  highlighted,
  onOpen,
  wardrobeRef
}: {
  count: number;
  doorOpen: boolean;
  /** 拖影正悬停在衣柜上方，给一个即将入柜的视觉提示 */
  highlighted: boolean;
  onOpen: () => void;
  wardrobeRef: React.RefObject<HTMLButtonElement>;
}) {
  const doorTransform = (side: "left" | "right") => {
    const angle = side === "left" ? -72 : 72;
    return doorOpen
      ? `perspective(200px) rotateY(${angle}deg)`
      : "perspective(200px) rotateY(0deg)";
  };

  return (
    <button
      type="button"
      ref={wardrobeRef}
      onClick={onOpen}
      aria-label={`像素衣柜 · 自由组合，已选 ${count} 件`}
      className="combo-wardrobe"
      data-highlighted={highlighted ? "true" : undefined}
    >
      <div className="combo-wardrobe__body">
        <div className="combo-wardrobe__interior">自由<br />组合</div>
        <div
          className="combo-wardrobe__door combo-wardrobe__door--left"
          style={{ transform: doorTransform("left") }}
        >
          <i />
        </div>
        <div
          className="combo-wardrobe__door combo-wardrobe__door--right"
          style={{ transform: doorTransform("right") }}
        >
          <i />
        </div>
        <span className="combo-wardrobe__count">{count}</span>
      </div>
      <span className="combo-wardrobe__hint">长按拖进来</span>
    </button>
  );
}

/** 展开后的底部抽屉：查看、移除、清空，并保存为新穿搭。 */
export function ComboBasketSheet({
  items,
  busy,
  onRemove,
  onClear,
  onSave,
  onClose
}: {
  items: readonly CatalogItem[];
  busy: boolean;
  onRemove: (itemId: string) => void;
  onClear: () => void;
  onSave: () => void;
  onClose: () => void;
}) {
  return (
    <div
      className="pixel-sheet"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="pixel-sheet__content"
        role="dialog"
        aria-modal="true"
        aria-label="自由组合衣柜"
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--px-2)",
            marginBottom: "var(--px-1)"
          }}
        >
          <h2 className="pixel-title" style={{ fontSize: "1.05rem", margin: 0 }}>
            🚪 我的组合衣柜
          </h2>
          <button type="button" className="pixel-tag" onClick={onClear} disabled={busy}>
            清空
          </button>
        </div>
        <p className="pixel-label" style={{ marginBottom: "var(--px-3)" }}>
          {items.length
            ? `已选 ${items.length} 件 · 长按单品拖进衣柜可继续加`
            : "长按单品，拖到衣柜里就能开始搭"}
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "var(--px-2)",
            marginBottom: "var(--px-4)"
          }}
        >
          {items.map((item) => (
            <div key={item.id} className="combo-basket__card">
              <img src={item.imageUrl} alt={item.name} data-pixel="true" />
              <div className="combo-basket__meta">
                <strong>{item.name}</strong>
                <span>{item.category}</span>
              </div>
              <button
                type="button"
                aria-label={`把${item.name}移出衣柜`}
                onClick={() => onRemove(item.id)}
                className="combo-basket__remove"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <button
          type="button"
          className="pixel-button pixel-button--primary w-full"
          onClick={onSave}
          disabled={busy}
        >
          {busy ? "AI 正在拼图 🧩" : "保存为新的穿搭 ✨"}
        </button>
        <p
          className="pixel-label text-center"
          style={{ marginTop: "var(--px-2)", marginBottom: 0 }}
        >
          AI 会先检查品类有没有重复，再用真实单品图生成拼贴
        </p>
      </section>
    </div>
  );
}
