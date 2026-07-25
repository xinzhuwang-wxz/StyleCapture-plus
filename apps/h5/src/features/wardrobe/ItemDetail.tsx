import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { PixelBadge, PixelButton } from "../../components/PixelUI";
import type { Item, Ownership } from "../../api/client";
import { douyinShopUrl, mockApi, type MockOutfit } from "../../mock/mockApi";
import { pixelAvatarDataUrl } from "../../utils/pixelAvatar";

interface ItemDetailProps {
  item: Item | null;
  saving: boolean;
  onClose: () => void;
  onSave: (itemId: string, changes: { ownership: Ownership }) => void;
  onOpenOutfit: (outfitId: string) => void;
}

/**
 * 单品详情页（写实展示）：
 * 上半 — 实物图；下半 — 「查看 AI 穿搭」长按钮 + 🛒 抖音商城。
 * 点击 AI 穿搭后：实物图缩小，下方出现三套搭配（三列），点击进穿搭详情。
 */
export function ItemDetail({
  item,
  saving,
  onClose,
  onSave,
  onOpenOutfit
}: ItemDetailProps) {
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [aiMode, setAiMode] = useState(false);
  const [outfits, setOutfits] = useState<MockOutfit[] | null>(null);
  const [loadingOutfits, setLoadingOutfits] = useState(false);

  useEffect(() => {
    setPhotoUrl(null);
    setAiMode(false);
    setOutfits(null);
    if (!item) return;
    let cancelled = false;
    void mockApi.sourceImage(item.id).then((url) => {
      if (!cancelled) setPhotoUrl(url);
    });
    return () => {
      cancelled = true;
    };
  }, [item?.id]);

  if (!item) return null;

  const name = String(
    item.attributes.subcategory?.value ??
      item.attributes.description?.value ??
      "单品"
  );
  const isOwned = item.ownership === "owned";

  const showAIOutfits = async () => {
    if (aiMode) {
      setAiMode(false);
      return;
    }
    setAiMode(true);
    if (outfits) return;
    setLoadingOutfits(true);
    const generated = await mockApi.generateOutfits(name);
    setOutfits(generated);
    setLoadingOutfits(false);
  };

  const openShop = () => {
    window.open(douyinShopUrl(`${name} 穿搭`), "_blank", "noreferrer");
  };

  return (
    <AnimatePresence>
      <motion.div
        className="pixel-sheet"
        role="presentation"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
      >
        <motion.section
          className="pixel-sheet__content"
          role="dialog"
          aria-modal="true"
          aria-label={`单品详情：${name}`}
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          transition={{ type: "spring", stiffness: 330, damping: 34 }}
        >
          {/* 顶部 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "var(--px-3)"
            }}
          >
            <div>
              <p className="pixel-label">单品详情</p>
              <h2 className="pixel-subtitle" style={{ color: "var(--pixel-text)", margin: 0 }}>
                {name}
              </h2>
            </div>
            <button
              type="button"
              className="pixel-button pixel-button--ghost"
              style={{ width: "2.5rem", height: "2.5rem", padding: 0 }}
              aria-label="关闭"
              onClick={onClose}
            >
              ×
            </button>
          </div>

          {/* 实物图（AI 模式下缩小） */}
          <motion.div
            layout
            style={{
              position: "relative",
              marginBottom: "var(--px-4)",
              borderRadius: "var(--pixel-border-radius)",
              overflow: "hidden",
              border: "2px solid var(--pixel-border)",
              boxShadow: "var(--pixel-shadow)"
            }}
            animate={{ height: aiMode ? "7.5rem" : "16rem" }}
            transition={{ type: "spring", stiffness: 260, damping: 28 }}
          >
            {photoUrl ? (
              <img
                src={photoUrl}
                alt={`${name} 实物图`}
                style={{ width: "100%", height: "100%", objectFit: "cover", imageRendering: "auto" }}
              />
            ) : (
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  display: "grid",
                  placeItems: "center",
                  background: "var(--pixel-bg)",
                  color: "var(--pixel-text-dim)",
                  fontFamily: "var(--font-pixel)",
                  fontSize: "0.8rem"
                }}
              >
                正在生成实物图…
              </div>
            )}
            <PixelBadge variant={isOwned ? "star" : "heart"}>
              {isOwned ? "⭐" : "💖"}
            </PixelBadge>
          </motion.div>

          {/* 拥有状态切换 */}
          <div
            style={{
              display: "flex",
              gap: "var(--px-2)",
              marginBottom: "var(--px-4)"
            }}
          >
            <button
              type="button"
              className="pixel-tag"
              style={
                isOwned
                  ? { background: "#fffbeb", borderColor: "var(--pixel-accent)", color: "#92600a" }
                  : undefined
              }
              disabled={saving}
              onClick={() => onSave(item.id, { ownership: "owned" })}
            >
              ⭐ 我已有这件
            </button>
            <button
              type="button"
              className="pixel-tag"
              style={
                !isOwned
                  ? { background: "#fdf2f8", borderColor: "var(--pixel-pink)", color: "#be185d" }
                  : undefined
              }
              disabled={saving}
              onClick={() => onSave(item.id, { ownership: "inspiration" })}
            >
              💖 还未拥有
            </button>
          </div>

          {/* 下半：AI 穿搭长按钮 + 购物车 */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto",
              gap: "var(--px-3)",
              marginBottom: "var(--px-4)"
            }}
          >
            <PixelButton
              variant="primary"
              className="w-full"
              onClick={() => void showAIOutfits()}
              ariaLabel="查看 AI 穿搭"
            >
              {aiMode ? "收起 AI 穿搭 ▲" : "🤖 点击查看 AI 穿搭"}
            </PixelButton>
            <PixelButton variant="accent" onClick={openShop} ariaLabel="去抖音商城购买">
              🛒
            </PixelButton>
          </div>

          {/* 三套 AI 搭配（三列竖向排列） */}
          {aiMode ? (
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <p className="pixel-label" style={{ marginBottom: "var(--px-2)" }}>
                三套搭配方案 · 点任意一套看详情
              </p>
              {loadingOutfits || !outfits ? (
                <p
                  style={{
                    textAlign: "center",
                    fontFamily: "var(--font-pixel)",
                    fontSize: "0.8rem",
                    color: "var(--pixel-text-dim)",
                    padding: "var(--px-6) 0"
                  }}
                >
                  <span className="pixel-pulse">🤖 正在为你搭配…</span>
                </p>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: "var(--px-2)"
                  }}
                >
                  {outfits.map((outfit) => (
                    <button
                      key={outfit.id}
                      type="button"
                      onClick={() => onOpenOutfit(outfit.id)}
                      style={{
                        padding: "var(--px-2)",
                        background: "var(--pixel-surface)",
                        border: "2px solid var(--pixel-border)",
                        borderRadius: "var(--pixel-radius-sm)",
                        boxShadow: "var(--pixel-shadow)",
                        textAlign: "center"
                      }}
                    >
                      <img
                        src={pixelAvatarDataUrl(outfit.seed, { size: 160 })}
                        alt={outfit.name}
                        data-pixel="true"
                        style={{ width: "100%", borderRadius: "8px", marginBottom: "6px" }}
                      />
                      <span
                        style={{
                          fontFamily: "var(--font-pixel)",
                          fontSize: "0.62rem",
                          color: "var(--pixel-text)",
                          lineHeight: 1.4,
                          display: "block"
                        }}
                      >
                        {outfit.name}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </motion.div>
          ) : null}
        </motion.section>
      </motion.div>
    </AnimatePresence>
  );
}
