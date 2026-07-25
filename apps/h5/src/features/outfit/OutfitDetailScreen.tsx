import { useEffect, useState } from "react";
import { PixelButton } from "../../components/PixelUI";
import { ShareModal } from "../../components/ShareModal";
import {
  douyinShopUrl,
  mockApi,
  type MockOutfit
} from "../../mock/mockApi";
import {
  buildShareCard,
  pixelAvatarDataUrl,
  pixelGarmentIcon
} from "../../utils/pixelAvatar";

interface OutfitDetailScreenProps {
  outfitId: string;
  onBack: () => void;
}

/**
 * 穿搭详情分析页（一屏看完全部内容）：
 * 上方 — 左拼贴 / 右虚化试穿（紧凑）；
 * 下方 — 单品小卡片一行陈列（已有点亮 / 未拥有灰色 → 抖音商城）；
 * 标题右侧 — 小红书式收藏小星星。
 */
export function OutfitDetailScreen({ outfitId, onBack }: OutfitDetailScreenProps) {
  const [outfit, setOutfit] = useState<MockOutfit | null>(null);
  const [loading, setLoading] = useState(true);
  const [showTryOn, setShowTryOn] = useState(false);
  const [saved, setSaved] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void mockApi.getOutfit(outfitId).then((o) => {
      if (!cancelled) {
        setOutfit(o);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [outfitId]);

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
  };

  const saveToWardrobe = async () => {
    await mockApi.saveOutfit(outfit.id);
    setSaved(true);
  };

  return (
    <div>
      {/* 顶栏：返回 + 标题 + 收藏小星星 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--px-2)",
          marginBottom: "var(--px-3)"
        }}
      >
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: 0, fontSize: "0.6rem" }}>
            {outfit.style} · {outfit.scene}
          </p>
          <h1
            className="pixel-title"
            style={{
              fontSize: "1rem",
              margin: 0,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis"
            }}
          >
            {outfit.name}
          </h1>
        </div>
        <button
          type="button"
          onClick={() => void toggleFavorite()}
          aria-label={outfit.favorited ? "取消收藏" : "收藏这套穿搭"}
          aria-pressed={outfit.favorited}
          style={{
            background: "none",
            border: "none",
            fontSize: "1.5rem",
            lineHeight: 1,
            padding: "var(--px-1)",
            filter: outfit.favorited
              ? "drop-shadow(0 2px 4px rgba(245,158,11,0.5))"
              : "grayscale(1) opacity(0.45)",
            transition: "transform 0.15s ease, filter 0.15s ease",
            transform: outfit.favorited ? "scale(1.15)" : "scale(1)"
          }}
        >
          ⭐
        </button>
      </div>

      {/* 上方大图（紧凑）：左拼贴 / 右虚化试穿 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          borderRadius: "var(--pixel-border-radius)",
          overflow: "hidden",
          border: "2px solid var(--pixel-border)",
          boxShadow: "var(--pixel-shadow)",
          marginBottom: "var(--px-3)",
          height: "11.5rem"
        }}
      >
        <div
          style={{
            background: "linear-gradient(160deg, #faf5ff, #fdeef5)",
            display: "grid",
            placeItems: "center",
            padding: "var(--px-2)"
          }}
        >
          <img
            src={pixelAvatarDataUrl(outfit.seed, { size: 220 })}
            alt={`${outfit.name} 平面拼贴`}
            data-pixel="true"
            style={{ maxHeight: "100%", width: "auto", maxWidth: "100%", borderRadius: "10px" }}
          />
        </div>

        <div
          style={{
            position: "relative",
            display: "grid",
            placeItems: "center",
            overflow: "hidden"
          }}
        >
          <img
            src={pixelAvatarDataUrl(outfit.seed, { size: 220, backdrop: true })}
            alt=""
            aria-hidden="true"
            data-pixel="true"
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: showTryOn ? "none" : "blur(12px) saturate(1.1)",
              transform: "scale(1.25)",
              transition: "filter 0.35s ease"
            }}
          />
          {showTryOn ? (
            <span
              style={{
                position: "absolute",
                bottom: "var(--px-1)",
                left: "50%",
                transform: "translateX(-50%)",
                padding: "1px 8px",
                fontFamily: "var(--font-pixel)",
                fontSize: "0.56rem",
                background: "rgba(255,255,255,0.9)",
                borderRadius: "999px",
                color: "var(--pixel-primary-dark)",
                whiteSpace: "nowrap"
              }}
            >
              ✨ 真人试穿效果（示意）
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => setShowTryOn(!showTryOn)}
            style={{
              position: "relative",
              zIndex: 2,
              padding: "var(--px-1) var(--px-3)",
              fontFamily: "var(--font-pixel)",
              fontSize: "0.62rem",
              background: showTryOn ? "var(--pixel-primary)" : "rgba(255,255,255,0.94)",
              color: showTryOn ? "#fff" : "var(--pixel-primary-dark)",
              border: "2px solid var(--pixel-primary)",
              borderRadius: "999px",
              boxShadow: "var(--pixel-shadow)",
              maxWidth: "92%"
            }}
          >
            {showTryOn ? "收起试穿" : "👤 显示真人试穿效果"}
          </button>
        </div>
      </div>

      <p
        style={{
          fontSize: "0.72rem",
          color: "var(--pixel-text-muted)",
          lineHeight: 1.6,
          marginBottom: "var(--px-3)"
        }}
      >
        {outfit.description}
      </p>

      {/* 单品小卡片：一行陈列 */}
      <p className="pixel-label" style={{ marginBottom: "var(--px-2)", fontSize: "0.6rem" }}>
        搭配单品 · 灰色可去商城购买 ›
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${outfit.slots.length}, 1fr)`,
          gap: "var(--px-2)",
          marginBottom: "var(--px-4)"
        }}
      >
        {outfit.slots.map((slot) => (
          <button
            key={slot.name}
            type="button"
            onClick={() => {
              if (!slot.owned) {
                window.open(douyinShopUrl(slot.name), "_blank", "noreferrer");
              }
            }}
            style={{
              padding: "var(--px-1)",
              background: slot.owned ? "var(--pixel-surface)" : "#f1eff5",
              border: `1.5px solid ${slot.owned ? "var(--pixel-secondary)" : "#e2deeb"}`,
              borderRadius: "var(--pixel-radius-sm)",
              boxShadow: slot.owned ? "var(--pixel-shadow)" : "none",
              textAlign: "center",
              cursor: slot.owned ? "default" : "pointer",
              filter: slot.owned ? "none" : "grayscale(0.5)"
            }}
            aria-label={
              slot.owned ? `${slot.name}（已有）` : `${slot.name}（未拥有，点击去抖音商城）`
            }
          >
            <img
              src={pixelGarmentIcon(slot.category, { owned: slot.owned, size: 90 })}
              alt={slot.name}
              data-pixel="true"
              style={{
                width: "70%",
                margin: "0 auto 2px",
                filter: slot.owned ? "none" : "opacity(0.6)"
              }}
            />
            <strong
              style={{
                fontFamily: "var(--font-pixel)",
                fontSize: "0.54rem",
                color: slot.owned ? "var(--pixel-text)" : "var(--pixel-text-dim)",
                display: "block",
                lineHeight: 1.3,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis"
              }}
            >
              {slot.name}
            </strong>
            <span
              style={{
                fontFamily: "var(--font-pixel)",
                fontSize: "0.52rem",
                color: slot.owned ? "var(--pixel-accent-glow)" : "var(--pixel-pink-dark)"
              }}
            >
              {slot.owned ? "已有" : `¥${slot.price ?? "--"}`}
            </span>
          </button>
        ))}
      </div>

      {/* 操作 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--px-3)"
        }}
      >
        <PixelButton variant="primary" onClick={() => void saveToWardrobe()} disabled={saved}>
          {saved ? "✓ 已存入衣橱" : "💜 存进数字衣橱"}
        </PixelButton>
        <PixelButton
          variant="accent"
          onClick={() =>
            setShareUrl(
              buildShareCard({
                seed: outfit.seed,
                title: outfit.name,
                subtitle: `${outfit.style} · ${outfit.scene}`,
                badge: "star"
              })
            )
          }
        >
          📤 分享像素图鉴
        </PixelButton>
      </div>

      {shareUrl ? (
        <ShareModal
          imageUrl={shareUrl}
          title={`分享：${outfit.name}`}
          onClose={() => setShareUrl(null)}
        />
      ) : null}
    </div>
  );
}
