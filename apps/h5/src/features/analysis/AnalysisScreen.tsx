import { useMemo } from "react";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import type { Item } from "../../api/client";
import type { MockOutfit } from "../../mock/mockApi";
import { pixelAvatarDataUrl } from "../../utils/pixelAvatar";

interface AnalysisScreenProps {
  items: Item[];
  outfits: MockOutfit[];
  onGoAI: () => void;
  onGoWardrobe: () => void;
  onOpenOutfit: (outfitId: string) => void;
}

/**
 * 穿搭分析（驾驶舱）：
 * 个人穿搭偏好分析 + 引导语，沉淀穿搭数字资产。
 */
export function AnalysisScreen({
  items,
  outfits,
  onGoAI,
  onGoWardrobe,
  onOpenOutfit
}: AnalysisScreenProps) {
  const stats = useMemo(() => {
    const owned = items.filter((i) => i.ownership === "owned").length;
    const inspiration = items.length - owned;

    const categoryCount = new Map<string, number>();
    items.forEach((i) => {
      const c = String(i.attributes.category?.value ?? "其他");
      categoryCount.set(c, (categoryCount.get(c) ?? 0) + 1);
    });
    const topCategories = [...categoryCount.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
    const maxCount = topCategories[0]?.[1] ?? 1;

    const styleCount = new Map<string, number>();
    outfits.forEach((o) => styleCount.set(o.style, (styleCount.get(o.style) ?? 0) + 1));
    const topStyles = [...styleCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);

    const ownedRatio = items.length ? Math.round((owned / items.length) * 100) : 0;

    return { owned, inspiration, topCategories, maxCount, topStyles, ownedRatio };
  }, [items, outfits]);

  const latest = outfits[0];

  return (
    <div>
      <PixelSectionHeader
        kicker="穿搭数字资产"
        title="我的穿搭分析"
        action={<span style={{ fontSize: "1.4rem" }} aria-hidden="true">📊</span>}
      />

      {/* 总览数字 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "var(--px-3)",
          marginBottom: "var(--px-5)"
        }}
      >
        {[
          { n: stats.owned, label: "已有单品", color: "var(--pixel-accent-glow)" },
          { n: stats.inspiration, label: "心动收藏", color: "var(--pixel-pink-dark)" },
          { n: outfits.length, label: "穿搭图鉴", color: "var(--pixel-primary-dark)" }
        ].map((s) => (
          <div
            key={s.label}
            style={{
              padding: "var(--px-4) var(--px-2)",
              background: "var(--pixel-surface)",
              border: "2px solid var(--pixel-border)",
              borderRadius: "var(--pixel-border-radius)",
              boxShadow: "var(--pixel-shadow)",
              textAlign: "center"
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-pixel)",
                fontSize: "1.5rem",
                color: s.color
              }}
            >
              {s.n}
            </div>
            <div style={{ fontSize: "0.65rem", color: "var(--pixel-text-dim)", marginTop: "4px" }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* 单品构成 */}
      <section
        style={{
          padding: "var(--px-4)",
          background: "var(--pixel-surface)",
          border: "2px solid var(--pixel-border)",
          borderRadius: "var(--pixel-border-radius)",
          boxShadow: "var(--pixel-shadow)",
          marginBottom: "var(--px-4)"
        }}
      >
        <h3 className="pixel-subtitle" style={{ marginBottom: "var(--px-3)" }}>
          👕 衣橱构成
        </h3>
        {stats.topCategories.length === 0 ? (
          <p style={{ fontSize: "0.75rem", color: "var(--pixel-text-dim)", margin: 0 }}>
            衣橱还是空的，先去存几件吧。
          </p>
        ) : (
          stats.topCategories.map(([cat, count]) => (
            <div key={cat} style={{ marginBottom: "var(--px-2)" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontFamily: "var(--font-pixel)",
                  fontSize: "0.72rem",
                  color: "var(--pixel-text-muted)",
                  marginBottom: "4px"
                }}
              >
                <span>{cat}</span>
                <span>{count} 件</span>
              </div>
              <div
                style={{
                  height: "10px",
                  borderRadius: "999px",
                  background: "var(--pixel-border-light)",
                  overflow: "hidden"
                }}
              >
                <div
                  style={{
                    width: `${Math.round((count / stats.maxCount) * 100)}%`,
                    height: "100%",
                    borderRadius: "999px",
                    background: "linear-gradient(90deg, var(--pixel-secondary), var(--pixel-pink))"
                  }}
                />
              </div>
            </div>
          ))
        )}
        {items.length > 0 ? (
          <p
            style={{
              margin: "var(--px-3) 0 0",
              fontFamily: "var(--font-pixel)",
              fontSize: "0.68rem",
              color: "var(--pixel-text-dim)"
            }}
          >
            ⭐ 衣橱拥有率 {stats.ownedRatio}% ·{" "}
            {stats.topStyles.length > 0
              ? `偏爱 ${stats.topStyles.map(([s]) => s).join(" / ")} 风`
              : "风格还在形成中"}
          </p>
        ) : null}
      </section>

      {/* 最新穿搭 */}
      {latest ? (
        <section
          style={{
            padding: "var(--px-4)",
            background: "var(--pixel-surface)",
            border: "2px solid var(--pixel-border)",
            borderRadius: "var(--pixel-border-radius)",
            boxShadow: "var(--pixel-shadow)",
            marginBottom: "var(--px-4)"
          }}
        >
          <h3 className="pixel-subtitle" style={{ marginBottom: "var(--px-3)" }}>
            ✨ 最近收藏的穿搭
          </h3>
          <button
            type="button"
            onClick={() => onOpenOutfit(latest.id)}
            style={{
              display: "grid",
              gridTemplateColumns: "5.5rem 1fr",
              gap: "var(--px-3)",
              alignItems: "center",
              width: "100%",
              padding: 0,
              border: "none",
              background: "none",
              textAlign: "left"
            }}
          >
            <img
              src={pixelAvatarDataUrl(latest.seed, { size: 160 })}
              alt={latest.name}
              data-pixel="true"
              style={{ width: "100%", borderRadius: "12px", border: "2px solid var(--pixel-border)" }}
            />
            <div>
              <strong
                style={{
                  fontFamily: "var(--font-pixel)",
                  fontSize: "0.9rem",
                  color: "var(--pixel-text)",
                  display: "block",
                  marginBottom: "4px"
                }}
              >
                {latest.name}
              </strong>
              <span style={{ fontSize: "0.7rem", color: "var(--pixel-text-dim)", lineHeight: 1.5 }}>
                {latest.description}
              </span>
            </div>
          </button>
        </section>
      ) : null}

      {/* 引导 */}
      <section
        style={{
          padding: "var(--px-5)",
          background: "linear-gradient(135deg, #f3edfd, #fdeef5)",
          border: "2px solid var(--pixel-secondary)",
          borderRadius: "var(--pixel-border-radius)",
          marginBottom: "var(--px-4)",
          textAlign: "center"
        }}
      >
        <p
          style={{
            fontFamily: "var(--font-pixel)",
            fontSize: "0.9rem",
            color: "var(--pixel-text)",
            lineHeight: 1.8,
            margin: "0 0 var(--px-4)"
          }}
        >
          在不同页面继续探索穿搭，
          <br />
          这里的分析会随着你的收藏不断生长 🌱
        </p>
        <div style={{ display: "flex", gap: "var(--px-3)", justifyContent: "center" }}>
          <PixelButton variant="primary" onClick={onGoAI}>
            🤖 去 AI 推荐
          </PixelButton>
          <PixelButton variant="ghost" onClick={onGoWardrobe}>
            👕 打开衣橱
          </PixelButton>
        </div>
      </section>
    </div>
  );
}
