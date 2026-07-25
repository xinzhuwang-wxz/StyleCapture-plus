import { useEffect, useState } from "react";
import { PixelButton, PixelCard, PixelSectionHeader } from "../../components/PixelUI";
import type { Item } from "../../api/client";
import { mockApi } from "../../mock/mockApi";

interface OutfitDetailScreenProps {
  outfitId: string;
  onBack: () => void;
  onItemClick: (itemId: string) => void;
}

export function OutfitDetailScreen({
  outfitId,
  onBack,
  onItemClick
}: OutfitDetailScreenProps) {
  const [outfit, setOutfit] = useState<any>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [showTryOn, setShowTryOn] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const o = await mockApi.getOutfit(outfitId);
      setOutfit(o);
      if (o) {
        const allItems = await mockApi.listItems();
        const outfitItems = allItems.filter((i: Item) => o.items.includes(i.id));
        setItems(outfitItems);
      }
      setLoading(false);
    }
    void load();
  }, [outfitId]);

  if (loading) {
    return (
      <div className="pixel-app">
        <div className="pixel-loading">
          <div className="pixel-loading__skeleton" />
          <div className="pixel-loading__skeleton" />
        </div>
      </div>
    );
  }

  if (!outfit) {
    return (
      <div className="pixel-app">
        <div style={{ textAlign: "center", padding: "4rem 1rem" }}>
          <p className="pixel-subtitle">穿搭方案未找到</p>
          <PixelButton variant="primary" onClick={onBack}>
            返回
          </PixelButton>
        </div>
      </div>
    );
  }

  return (
    <div className="pixel-app">
      {/* Top Bar */}
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
        <h1 className="pixel-title" style={{ fontSize: "1.1rem", margin: 0 }}>
          {outfit.name}
        </h1>
      </div>

      {/* Collage Image */}
      <div
        style={{
          position: "relative",
          border: "3px solid var(--pixel-border)",
          boxShadow: "4px 4px 0 rgba(0,0,0,0.3)",
          marginBottom: "var(--px-4)",
          overflow: "hidden"
        }}
      >
        <img
          src={outfit.collageUrl}
          alt={outfit.name}
          style={{
            width: "100%",
            aspectRatio: "4/5",
            objectFit: "cover",
            filter: showTryOn ? "blur(8px)" : "none",
            transition: "filter 0.3s"
          }}
        />
        {showTryOn ? (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              background: "rgba(0,0,0,0.3)"
            }}
          >
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  fontSize: "4rem",
                  marginBottom: "var(--px-3)",
                  filter: "drop-shadow(3px 3px 0 rgba(0,0,0,0.5))"
                }}
              >
                👾
              </div>
              <p className="pixel-subtitle" style={{ color: "#fff" }}>
                真人试穿效果预览
              </p>
            </div>
          </div>
        ) : null}
        <button
          type="button"
          onClick={() => setShowTryOn(!showTryOn)}
          style={{
            position: "absolute",
            bottom: "var(--px-3)",
            right: "var(--px-3)",
            padding: "var(--px-2) var(--px-4)",
            fontFamily: "var(--font-pixel)",
            fontSize: "0.7rem",
            background: showTryOn ? "var(--pixel-primary)" : "var(--pixel-surface)",
            color: "#fff",
            border: "2px solid var(--pixel-border)",
            boxShadow: "2px 2px 0 rgba(0,0,0,0.3)"
          }}
        >
          {showTryOn ? "隐藏试穿" : "👤 显示真人试穿"}
        </button>
      </div>

      {/* Description */}
      <p
        style={{
          fontSize: "0.85rem",
          color: "var(--pixel-text-muted)",
          lineHeight: 1.6,
          marginBottom: "var(--px-5)"
        }}
      >
        {outfit.description}
      </p>

      {/* Item Cards */}
      <PixelSectionHeader
        kicker="搭配单品"
        title="组成这件穿搭的单品"
      />

      <div className="pixel-grid" style={{ marginBottom: "var(--px-6)" }}>
        {items.map((item) => (
          <PixelCard
            key={item.id}
            onClick={() => onItemClick(item.id)}
            ariaLabel={String(
              item.attributes.description?.value ?? "单品"
            )}
          >
            <div
              style={{
                position: "relative",
                aspectRatio: "1",
                background:
                  item.ownership === "owned"
                    ? "linear-gradient(145deg, #2d1b4e, #3d2b5e)"
                    : "linear-gradient(145deg, #1a0f2e, #251540)",
                overflow: "hidden"
              }}
            >
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  display: "grid",
                  placeItems: "center",
                  fontSize: "3rem"
                }}
              >
                {item.ownership === "owned" ? "⭐" : "💖"}
              </div>
              <span
                style={{
                  position: "absolute",
                  bottom: 0,
                  left: 0,
                  right: 0,
                  padding: "var(--px-2)",
                  background: "rgba(0,0,0,0.6)",
                  fontSize: "0.65rem",
                  fontFamily: "var(--font-pixel)",
                  color: item.ownership === "owned" ? "var(--pixel-accent)" : "var(--pixel-primary)"
                }}
              >
                {item.ownership === "owned" ? "✓ 已拥有" : "✧ 未拥有"}
              </span>
            </div>
            <div style={{ padding: "var(--px-3)" }}>
              <strong
                style={{
                  fontFamily: "var(--font-pixel)",
                  fontSize: "0.8rem",
                  color: "var(--pixel-text)"
                }}
              >
                {String(item.attributes.subcategory?.value ?? item.attributes.category?.value ?? "单品")}
              </strong>
              <p
                style={{
                  margin: "4px 0 0",
                  fontSize: "0.7rem",
                  color: "var(--pixel-text-dim)"
                }}
              >
                {String(item.attributes.description?.value ?? "").slice(0, 20)}
              </p>
            </div>
          </PixelCard>
        ))}
      </div>

      {/* Action Buttons */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--px-3)",
          marginBottom: "var(--px-6)"
        }}
      >
        <PixelButton variant="primary">
          <span>💾</span> 保存穿搭
        </PixelButton>
        <PixelButton variant="accent">
          <span>📤</span> 分享穿搭
        </PixelButton>
      </div>
    </div>
  );
}
