import { useMemo } from "react";

import type { MockOutfit } from "../../mock/mockApi";
import "./analysis.css";

interface AnalysisScreenProps {
  outfits: MockOutfit[];
  onGoAI: () => void;
  onGoWardrobe: () => void;
  onOpenOutfit: (outfitId: string) => void;
  onOpenFavorites: () => void;
}

/** 风格配色，与衣橱卡片的 style chip 同一套。 */
const STYLE_COLORS: Record<string, string> = {
  甜美: "#f9a8d4",
  复古: "#a78bfa",
  休闲: "#93c5fd",
  简约: "#fcd34d",
  自由: "#86efac"
};

const FALLBACK_COLOR = "#c4b5fd";

type StyleSlice = {
  readonly style: string;
  readonly percent: number;
  readonly color: string;
};

/**
 * 按衣橱里穿搭的风格算占比。占比是真实算出来的，衣橱变了饼图就会变，
 * 不是写死的示意数据。
 */
function useStyleBreakdown(outfits: MockOutfit[]): StyleSlice[] {
  return useMemo(() => {
    if (outfits.length === 0) return [];
    const counts = new Map<string, number>();
    outfits.forEach((outfit) => {
      counts.set(outfit.style, (counts.get(outfit.style) ?? 0) + 1);
    });

    const slices = [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([style, count]) => ({
        style,
        percent: Math.round((count / outfits.length) * 100),
        color: STYLE_COLORS[style] ?? FALLBACK_COLOR
      }));

    // 四舍五入后补齐到 100%，避免饼图留一条缝
    const total = slices.reduce((sum, slice) => sum + slice.percent, 0);
    if (slices.length > 0 && total !== 100) {
      slices[0] = { ...slices[0], percent: slices[0].percent + (100 - total) };
    }
    return slices;
  }, [outfits]);
}

function conicGradient(slices: StyleSlice[]): string {
  if (slices.length === 0) return "conic-gradient(#ece5f8 0 100%)";
  let cursor = 0;
  const stops = slices.map((slice) => {
    const from = cursor;
    cursor += slice.percent;
    return `${slice.color} ${from}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(", ")})`;
}

export function AnalysisScreen({
  outfits,
  onGoAI,
  onGoWardrobe,
  onOpenOutfit,
  onOpenFavorites
}: AnalysisScreenProps) {
  const slices = useStyleBreakdown(outfits);
  const dominant = slices[0]?.style ?? "待补充";

  const gap = useMemo(() => {
    const counts = new Map<string, number>();
    outfits.forEach((outfit) =>
      outfit.slots.forEach((slot) => {
        counts.set(slot.category, (counts.get(slot.category) ?? 0) + 1);
      })
    );
    const outerwear = counts.get("外套") ?? 0;
    return outerwear <= 1
      ? { title: `外套只有 ${outerwear} 件`, hint: "补一件就能多搭 4 套" }
      : { title: "品类比较齐全", hint: "可以试试换配饰做变化" };
  }, [outfits]);

  const favorites = outfits.filter((outfit) => outfit.favorited);
  const strip = favorites.length ? favorites : outfits;

  return (
    <div>
      <div className="analysis__header">
        <h1 className="pixel-title" style={{ margin: 0, fontSize: "1.3rem" }}>
          穿搭分析
        </h1>
        <span className="pixel-label">衣橱构成</span>
      </div>

      <section className="analysis__pie-card">
        <div
          className="analysis__pie"
          style={{ background: conicGradient(slices) }}
          role="img"
          aria-label={`衣橱风格占比：${slices
            .map((slice) => `${slice.style} ${slice.percent}%`)
            .join("，")}`}
        >
          <div className="analysis__pie-hole">
            {dominant}
            <br />
            为主
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 className="analysis__pie-title">👗 衣橱风格占比</h3>
          <div className="analysis__legend">
            {slices.map((slice) => (
              <span key={slice.style}>
                <i style={{ background: slice.color }} />
                {slice.style} {slice.percent}%
              </span>
            ))}
          </div>
        </div>
      </section>

      <div className="analysis__section-head">
        <p className="pixel-label" style={{ margin: 0 }}>
          最近收藏的穿搭
        </p>
        <button type="button" className="pixel-tag" onClick={onOpenFavorites}>
          全部 ›
        </button>
      </div>
      <div className="analysis__strip">
        {strip.map((outfit) => (
          <article
            key={outfit.id}
            className="pixel-card analysis__strip-card"
            onClick={() => onOpenOutfit(outfit.id)}
          >
            <div className="analysis__strip-cover">
              {outfit.pixelCoverUrl ? (
                <img src={outfit.pixelCoverUrl} alt={outfit.name} data-pixel="true" />
              ) : (
                <span aria-hidden="true">🧩</span>
              )}
            </div>
            <div className="analysis__strip-name">{outfit.name}</div>
          </article>
        ))}
      </div>

      <section className="analysis__duo">
        <div className="analysis__mini-card">
          <p className="pixel-label" style={{ marginBottom: "10px" }}>
            常穿色系
          </p>
          <div className="analysis__swatches">
            <i style={{ background: "#c8952a" }} />
            <i style={{ background: "#5b3320" }} />
            <i style={{ background: "#f5c4d1" }} />
            <i style={{ background: "#b7cf9e" }} />
          </div>
          <p className="analysis__mini-note">棕黄系最常穿</p>
        </div>
        <div className="analysis__mini-card">
          <p className="pixel-label" style={{ marginBottom: "10px" }}>
            缺口提示
          </p>
          <p className="analysis__gap">
            {gap.title}
            <br />
            {gap.hint}
          </p>
        </div>
      </section>

      <section className="analysis__cta">
        <p>继续收藏，这里的分析会随你生长 🌱</p>
        <div>
          <button type="button" className="pixel-button pixel-button--primary" onClick={onGoAI}>
            🤖 去 AI 推荐
          </button>
          <button type="button" className="pixel-button" onClick={onGoWardrobe}>
            👕 打开衣橱
          </button>
        </div>
      </section>
    </div>
  );
}
