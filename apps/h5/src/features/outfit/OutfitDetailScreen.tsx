import { useEffect, useState } from "react";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
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
 * 穿搭详情分析页：
 * 上方大图 — 左半拼贴图，右半虚化背景 + 「显示真人试穿效果」；
 * 下方 — 单品卡片：已有=点亮，未拥有=灰色（点击跳抖音商城）。
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

  const ownedCount = outfit.slots.filter((s) => s.owned).length;

  const saveToAtlas = async () => {
    await mockApi.saveOutfit(outfit.id);
    setSaved(true);
  };

  return (
    <div>
      {/* 顶栏 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--px-3)",
          marginBottom: "var(--px-4)",
          paddingBottom: "var(--px-3)",
          borderBottom: "2px dashed var(--pixel-border)"
        }}
      >
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <div style={{ flex: 1 }}>
          <p className="pixel-label" style={{ margin: 0 }}>
            {outfit.style} · {outfit.scene}
          </p>
          <h1 className="pixel-title" style={{ fontSize: "1.1rem", margin: 0 }}>
            {outfit.name}
          </h1>
        </div>
        <span
          style={{
            fontFamily: "var(--font-pixel)",
            fontSize: "0.68rem",
            color: "var(--pixel-text-dim)"
          }}
        >
          已有 {ownedCount}/{outfit.slots.length}
        </span>
      </div>

      {/* 上方大图：左拼贴 / 右虚化 + 试穿 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          borderRadius: "var(--pixel-border-radius)",
          overflow: "hidden",
          border: "2px solid var(--pixel-border)",
          boxShadow: "var(--pixel-shadow)",
          marginBottom: "var(--px-4)",
          minHeight: "15rem"
        }}
      >
        {/* 左半：拼贴图 */}
        <div
          style={{
            background: "linear-gradient(160deg, #faf5ff, #fdeef5)",
            display: "grid",
            placeItems: "center",
            padding: "var(--px-3)"
          }}
        >
          <img
            src={pixelAvatarDataUrl(outfit.seed, { size: 260 })}
            alt={`${outfit.name} 平面拼贴`}
            data-pixel="true"
            style={{ width: "100%", borderRadius: "10px" }}
          />
        </div>

        {/* 右半：虚化背景 + 真人试穿 */}
        <div
          style={{
            position: "relative",
            display: "grid",
            placeItems: "center",
            overflow: "hidden"
          }}
        >
          <img
            src={pixelAvatarDataUrl(outfit.seed, { size: 260, backdrop: true })}
            alt=""
            aria-hidden="true"
            data-pixel="true"
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: showTryOn ? "none" : "blur(14px) saturate(1.1)",
              transform: "scale(1.3)",
              transition: "filter 0.35s ease"
            }}
          />
          {showTryOn ? (
            <span
              style={{
                position: "absolute",
                bottom: "var(--px-2)",
                left: "50%",
                transform: "translateX(-50%)",
                padding: "2px 10px",
                fontFamily: "var(--font-pixel)",
                fontSize: "0.62rem",
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
              padding: "var(--px-2) var(--px-4)",
              fontFamily: "var(--font-pixel)",
              fontSize: "0.72rem",
              background: showTryOn ? "var(--pixel-primary)" : "rgba(255,255,255,0.94)",
              color: showTryOn ? "#fff" : "var(--pixel-primary-dark)",
              border: "2px solid var(--pixel-primary)",
              borderRadius: "999px",
              boxShadow: "var(--pixel-shadow)",
              maxWidth: "88%"
            }}
          >
            {showTryOn ? "收起试穿" : "👤 显示真人试穿效果"}
          </button>
        </div>
      </div>

      <p
        style={{
          fontSize: "0.82rem",
          color: "var(--pixel-text-muted)",
          lineHeight: 1.7,
          marginBottom: "var(--px-5)"
        }}
      >
        {outfit.description}
      </p>

      {/* 单品卡片：已有点亮 / 未拥有灰色 → 抖音商城 */}
      <PixelSectionHeader
        kicker="搭配单品"
        title="这套穿搭用了什么"
        action={
          <span
            style={{
              fontFamily: "var(--font-pixel)",
              fontSize: "0.62rem",
              color: "var(--pixel-text-dim)"
            }}
          >
            灰色可去商城购买 ›
          </span>
        }
      />

      <div className="pixel-grid" style={{ marginBottom: "var(--px-6)" }}>
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
              position: "relative",
              padding: "var(--px-3)",
              background: slot.owned ? "var(--pixel-surface)" : "#f1eff5",
              border: `2px solid ${slot.owned ? "var(--pixel-secondary)" : "#e2deeb"}`,
              borderRadius: "var(--pixel-border-radius)",
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
              src={pixelGarmentIcon(slot.category, { owned: slot.owned, size: 120 })}
              alt={slot.name}
              data-pixel="true"
              style={{
                width: "56%",
                margin: "0 auto var(--px-2)",
                filter: slot.owned ? "none" : "opacity(0.6)"
              }}
            />
            <strong
              style={{
                fontFamily: "var(--font-pixel)",
                fontSize: "0.72rem",
                color: slot.owned ? "var(--pixel-text)" : "var(--pixel-text-dim)",
                display: "block"
              }}
            >
              {slot.name}
            </strong>
            <span
              style={{
                fontFamily: "var(--font-pixel)",
                fontSize: "0.62rem",
                color: slot.owned ? "var(--pixel-accent-glow)" : "var(--pixel-pink-dark)"
              }}
            >
              {slot.owned ? "⭐ 已有" : `💖 ¥${slot.price ?? "--"} · 去商城`}
            </span>
          </button>
        ))}
      </div>

      {/* 操作 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--px-3)",
          marginBottom: "var(--px-6)"
        }}
      >
        <PixelButton variant="primary" onClick={() => void saveToAtlas()} disabled={saved}>
          {saved ? "✓ 已存入图鉴" : "💜 存进穿搭图鉴"}
        </PixelButton>
        <PixelButton
          variant="accent"
          onClick={() =>
            setShareUrl(
              buildShareCard({
                seed: outfit.seed,
                title: outfit.name,
                subtitle: `${outfit.style} · ${outfit.scene}`,
                badge: outfit.slots.every((s) => s.owned) ? "star" : "heart"
              })
            )
          }
        >
          📤 分享穿搭
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
