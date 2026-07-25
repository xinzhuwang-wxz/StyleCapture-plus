import { useEffect, useMemo, useState } from "react";

import { PixelButton } from "../../components/PixelUI";
import { douyinShopUrl, mockApi, type MockOutfit } from "../../mock/mockApi";
import type { LookRenderInput } from "../render/application/renderPort";
import { useLookRender } from "../render/useLookRender";
import { ShareCard } from "./ShareCard";
import { TryOnPane } from "./TryOnPane";
import "./outfit.css";

interface OutfitDetailScreenProps {
  outfitId: string;
  /** 用户设为「试穿使用」的形象照，没有则为 null */
  referencePhotoUrl: string | null;
  onBack: () => void;
  onOpenItem: (itemId: string) => void;
  onNotice: (message: string) => void;
}

/**
 * 穿搭详情页。
 *
 * 左 = 由真实 Item 图片确定性生成的拼贴，立即可见；
 * 右 = 走 RenderPort 的真人试穿，按真实状态展示 processing / 成功 / 降级。
 *
 * 从「按穿搭」列表进来，和从「按单品」的组合衣柜保存后跳进来，是同一个组件，
 * 因此视觉和交互完全一致。
 */
export function OutfitDetailScreen({
  outfitId,
  referencePhotoUrl,
  onBack,
  onOpenItem,
  onNotice
}: OutfitDetailScreenProps) {
  const [outfit, setOutfit] = useState<MockOutfit | null>(null);
  const [loading, setLoading] = useState(true);
  const [revealed, setRevealed] = useState(false);
  const [saved, setSaved] = useState(false);
  const [sharing, setSharing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setRevealed(false);
    void mockApi.getOutfit(outfitId).then((result) => {
      if (cancelled) return;
      setOutfit(result);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [outfitId]);

  const renderInput = useMemo<LookRenderInput | null>(() => {
    if (!outfit) return null;
    return {
      lookId: outfit.id,
      items: outfit.slots.map((slot) => ({
        itemId: slot.itemId,
        imageUrl: slot.imageUrl
      })),
      referencePhotoUrl,
      curatedSeed: {
        modelPhotoUrl: outfit.modelPhotoUrl,
        pixelCoverUrl: outfit.pixelCoverUrl
      }
    };
  }, [outfit, referencePhotoUrl]);

  const renderSet = useLookRender(renderInput);

  if (loading) {
    return (
      <div className="pixel-loading">
        <div className="pixel-loading__skeleton" />
        <div className="pixel-loading__skeleton" />
      </div>
    );
  }

  if (!outfit) {
    return (
      <div style={{ textAlign: "center", padding: "4rem 1rem" }}>
        <p className="pixel-subtitle">这套穿搭走丢了</p>
        <PixelButton variant="primary" onClick={onBack}>
          返回
        </PixelButton>
      </div>
    );
  }

  const toggleFavorite = async () => {
    const favorited = await mockApi.toggleFavoriteOutfit(outfit.id);
    setOutfit((current) => (current ? { ...current, favorited } : current));
    onNotice(favorited ? "已收藏这套穿搭 ⭐" : "已取消收藏");
  };

  const saveToWardrobe = async () => {
    await mockApi.saveOutfit(outfit.id);
    setSaved(true);
    onNotice("已存进数字衣橱 💜");
  };

  const ownedCount = outfit.slots.filter((slot) => slot.owned).length;

  return (
    <div className="outfit-detail">
      <div className="outfit-detail__header">
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: 0 }}>
            {outfit.style} · {outfit.scene}
          </p>
          <h1 className="pixel-title outfit-detail__title">{outfit.name}</h1>
        </div>
        <button
          type="button"
          onClick={() => void toggleFavorite()}
          aria-label={outfit.favorited ? "取消收藏" : "收藏这套穿搭"}
          aria-pressed={outfit.favorited}
          className="outfit-detail__star"
          data-on={outfit.favorited ? "true" : undefined}
        >
          ⭐
        </button>
      </div>

      {/* 左：真实单品拼贴（立即可见）｜右：真人试穿（按真实状态展示） */}
      <div className="outfit-detail__panes">
        <div className="outfit-detail__collage">
          {renderSet?.collage.status === "ready" && renderSet.collage.imageUrl ? (
            <img src={renderSet.collage.imageUrl} alt="真实单品拼贴图" />
          ) : renderSet?.collage.status === "error" ? (
            <p className="outfit-detail__collage-note">
              {renderSet.collage.notice ?? "拼贴暂时生成不了"}
            </p>
          ) : (
            <div className="outfit-detail__collage-busy" role="status">
              <span className="tryon-pane__spinner" aria-hidden="true" />
              正在合成拼贴
            </div>
          )}
          <span className="outfit-detail__collage-tag">🧩 单品拼贴</span>
        </div>

        {renderSet ? (
          <TryOnPane
            tryOn={renderSet.tryOn}
            collage={renderSet.collage}
            revealed={revealed}
            onToggleReveal={() => setRevealed((current) => !current)}
          />
        ) : null}
      </div>

      <div className="outfit-detail__comment">
        <span aria-hidden="true">🤖</span>
        <p>{outfit.description}</p>
      </div>

      <p className="pixel-label" style={{ marginBottom: "var(--px-2)" }}>
        搭配单品 · 灰色可去商城购买 ›
      </p>
      <div className="outfit-detail__slots">
        {outfit.slots.map((slot) => (
          <button
            key={slot.itemId}
            type="button"
            className="outfit-detail__slot"
            data-owned={slot.owned ? "true" : undefined}
            aria-label={
              slot.owned
                ? `${slot.name}（已有，查看单品详情）`
                : `${slot.name}（未拥有，¥${slot.price}，去抖音商城）`
            }
            onClick={() => {
              if (slot.owned) {
                onOpenItem(slot.itemId);
                return;
              }
              window.open(douyinShopUrl(slot.name), "_blank", "noreferrer");
              onNotice(`去抖音商城看「${slot.name}」🛍`);
            }}
          >
            <img src={slot.imageUrl} alt={slot.name} data-pixel="true" />
            <strong>{slot.name}</strong>
            <span>{slot.owned ? "已有" : `¥${slot.price}`}</span>
          </button>
        ))}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--px-3)",
          marginTop: "auto"
        }}
      >
        <PixelButton variant="primary" onClick={() => void saveToWardrobe()} disabled={saved}>
          {saved ? "✓ 已存入衣橱" : "💜 存进衣橱"}
        </PixelButton>
        <PixelButton variant="accent" onClick={() => setSharing(true)}>
          📤 分享图鉴
        </PixelButton>
      </div>

      {sharing && renderSet ? (
        <ShareCard
          outfit={outfit}
          ownedCount={ownedCount}
          pixelCover={renderSet.pixelCover}
          collage={renderSet.collage}
          onNotice={onNotice}
          onClose={() => setSharing(false)}
        />
      ) : null}
    </div>
  );
}
