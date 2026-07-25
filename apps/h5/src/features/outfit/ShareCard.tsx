import type { MockOutfit } from "../../mock/mockApi";
import type { RenderArtifact } from "../render/domain/renderArtifact";

/**
 * 卡通像素图鉴分享卡。
 *
 * Issue #5 的隐私约束：「分享产物只包含允许公开的像素 Look 和必要文案，不包含
 * 用户参考照、私有源图或长期签名 URL。」
 *
 * 所以这里只接受像素封面和真实单品拼贴两种产物，**不接收**试穿图——
 * 试穿图可能来自用户自己的形象照，不允许出现在可对外传播的卡片上。
 */
export function ShareCard({
  outfit,
  ownedCount,
  pixelCover,
  collage,
  onNotice,
  onClose
}: {
  outfit: MockOutfit;
  ownedCount: number;
  pixelCover: RenderArtifact;
  collage: RenderArtifact;
  onNotice: (message: string) => void;
  onClose: () => void;
}) {
  // 优先用像素封面；它还没生成时退回真实单品拼贴，两者都可公开。
  const shareable =
    pixelCover.status === "ready" && pixelCover.imageUrl ? pixelCover : collage;
  const isPixel = shareable === pixelCover;

  return (
    <div
      className="share-card"
      role="dialog"
      aria-label="分享像素图鉴"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="share-card__inner">
        <div className="share-card__paper">
          <span className="share-card__doodle share-card__doodle--star">⭐</span>
          <span className="share-card__doodle share-card__doodle--heart">💜</span>

          <div className="share-card__frame">
            {shareable.imageUrl ? (
              <img src={shareable.imageUrl} alt={`${outfit.name} 像素图鉴`} data-pixel="true" />
            ) : (
              <div className="share-card__frame-busy" role="status">
                正在生成图鉴…
              </div>
            )}
            <span className="share-card__tag">
              {outfit.style} · {outfit.scene}
            </span>
            {!isPixel ? (
              <span className="share-card__note">像素封面还没生成，先用真实拼贴</span>
            ) : null}
          </div>

          <div className="share-card__meta">
            <div style={{ minWidth: 0 }}>
              <strong>{outfit.name}</strong>
              <span>
                已有 {ownedCount}/{outfit.slots.length} 件
              </span>
            </div>
            <div className="share-card__thumbs">
              {outfit.slots.slice(0, 3).map((slot) => (
                <img key={slot.itemId} src={slot.imageUrl} alt="" data-pixel="true" />
              ))}
            </div>
          </div>

          <div className="share-card__footer">
            <span>@码上搭 · 我的数字衣橱</span>
            <span>扫码看同款 ›</span>
          </div>
        </div>

        <div className="share-card__actions">
          <button
            type="button"
            className="share-card__douyin"
            onClick={() => {
              onNotice("已跳转抖音 · 图鉴已带上 🎵");
              onClose();
            }}
          >
            🎵 分享到抖音
          </button>
          <button
            type="button"
            className="pixel-button"
            onClick={() => {
              onNotice("已保存到相册 💾");
              onClose();
            }}
          >
            💾 保存到相册
          </button>
        </div>

        <button type="button" className="share-card__close" onClick={onClose}>
          关闭
        </button>
      </div>
    </div>
  );
}
