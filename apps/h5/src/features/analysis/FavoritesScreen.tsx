import { PixelButton, PixelEmpty } from "../../components/PixelUI";
import type { MockOutfit } from "../../mock/mockApi";
import "./analysis.css";

/** 「全部 ›」二级页：收藏穿搭网格。 */
export function FavoritesScreen({
  outfits,
  onBack,
  onOpenOutfit
}: {
  outfits: MockOutfit[];
  onBack: () => void;
  onOpenOutfit: (outfitId: string) => void;
}) {
  const favoriteCount = outfits.filter((outfit) => outfit.favorited).length;

  return (
    <div className="pixel-subpage">
      <div className="subpage__header">
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: 0 }}>
            共 {outfits.length} 套 · {favoriteCount} 套已加星
          </p>
          <h1 className="pixel-title" style={{ margin: 0, fontSize: "1.18rem" }}>
            收藏的穿搭
          </h1>
        </div>
      </div>

      {outfits.length === 0 ? (
        <PixelEmpty icon="⭐" title="还没有收藏" description="去衣橱里点个星星就会出现在这里。" />
      ) : (
        <div className="pixel-grid">
          {outfits.map((outfit) => (
            <article
              key={outfit.id}
              className="pixel-card wardrobe-card"
              onClick={() => onOpenOutfit(outfit.id)}
            >
              <div className="wardrobe-card__cover wardrobe-card__cover--outfit">
                {outfit.pixelCoverUrl ? (
                  <img src={outfit.pixelCoverUrl} alt={outfit.name} data-pixel="true" />
                ) : (
                  <div className="wardrobe-card__placeholder">
                    🧩<span>拼贴封面</span>
                  </div>
                )}
                {outfit.favorited ? (
                  <span className="wardrobe-card__star" aria-label="已收藏">
                    ⭐
                  </span>
                ) : null}
              </div>
              <div className="wardrobe-card__meta">
                <strong>{outfit.name}</strong>
                <span className="wardrobe-card__source">
                  {outfit.style} · 已有 {outfit.slots.filter((slot) => slot.owned).length}/
                  {outfit.slots.length}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
