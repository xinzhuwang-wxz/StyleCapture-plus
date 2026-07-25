import { useMemo } from "react";
import { PixelButton } from "../../components/PixelUI";
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

const STYLE_COLORS = ["#f9a8d4", "#a78bfa", "#93c5fd", "#fcd34d", "#86efac"];

/**
 * 穿搭分析（驾驶舱 · 一屏看完）：
 * 统计数字 + 风格占比饼图 + 最近收藏 + 探索引导。
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
    const favorited = outfits.filter((o) => o.favorited).length;

    const styleCount = new Map<string, number>();
    outfits.forEach((o) => styleCount.set(o.style, (styleCount.get(o.style) ?? 0) + 1));
    const total = outfits.length || 1;
    const styles = [...styleCount.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([name, count], i) => ({
        name,
        ratio: count / total,
        color: STYLE_COLORS[i % STYLE_COLORS.length]
      }));

    return { owned, favorited, styles };
  }, [items, outfits]);

  const latest = outfits[0];

  // 饼图扇形
  const pieSegments = useMemo(() => {
    let acc = 0;
    return stats.styles.map((s) => {
      const start = acc;
      acc += s.ratio;
      return { ...s, start, end: acc };
    });
  }, [stats.styles]);

  const donut = (size: number) => {
    const r = size / 2;
    const ir = r * 0.58;
    if (pieSegments.length === 0) return null;
    const arc = (from: number, to: number, radius: number) => {
      const a0 = from * Math.PI * 2 - Math.PI / 2;
      const a1 = to * Math.PI * 2 - Math.PI / 2;
      return [
        `${radius * Math.cos(a0) + r} ${radius * Math.sin(a0) + r}`,
        `${radius * Math.cos(a1) + r} ${radius * Math.sin(a1) + r}`
      ];
    };
    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="风格占比饼图">
        {pieSegments.map((seg) => {
          const [x0, y0] = arc(seg.start, seg.end, r - 1);
          const [x1, y1] = arc(seg.end, seg.start, ir);
          const large = seg.end - seg.start > 0.5 ? 1 : 0;
          return (
            <path
              key={seg.name}
              d={`M ${x0} A ${r - 1} ${r - 1} 0 ${large} 1 ${y0} L ${y1} A ${ir} ${ir} 0 ${large} 0 ${x1} Z`}
              fill={seg.color}
              stroke="#fff"
              strokeWidth="1.5"
            />
          );
        })}
      </svg>
    );
  };

  return (
    <div>
      {/* 标题 + 数字（一行压缩） */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: "var(--px-3)"
        }}
      >
        <h1 className="pixel-title" style={{ fontSize: "1.15rem", margin: 0 }}>
          穿搭分析
        </h1>
        <span className="pixel-label" style={{ fontSize: "0.6rem" }}>
          穿搭数字资产
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "var(--px-2)",
          marginBottom: "var(--px-3)"
        }}
      >
        {[
          { n: stats.owned, label: "已有单品", color: "var(--pixel-accent-glow)" },
          { n: stats.favorited, label: "心动收藏", color: "var(--pixel-pink-dark)" },
          { n: outfits.length, label: "穿搭图鉴", color: "var(--pixel-primary-dark)" }
        ].map((s) => (
          <div
            key={s.label}
            style={{
              padding: "var(--px-2)",
              background: "var(--pixel-surface)",
              border: "2px solid var(--pixel-border)",
              borderRadius: "var(--pixel-radius-sm)",
              boxShadow: "var(--pixel-shadow)",
              textAlign: "center"
            }}
          >
            <div style={{ fontFamily: "var(--font-pixel)", fontSize: "1.2rem", color: s.color }}>
              {s.n}
            </div>
            <div style={{ fontSize: "0.56rem", color: "var(--pixel-text-dim)", marginTop: "2px" }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* 风格占比（压扁卡片：饼图 + 图例一行） */}
      <section
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--px-3)",
          padding: "var(--px-3)",
          background: "var(--pixel-surface)",
          border: "2px solid var(--pixel-border)",
          borderRadius: "var(--pixel-radius-sm)",
          boxShadow: "var(--pixel-shadow)",
          marginBottom: "var(--px-3)"
        }}
      >
        {donut(72)}
        <div style={{ flex: 1 }}>
          <h3
            className="pixel-subtitle"
            style={{ fontSize: "0.72rem", margin: "0 0 var(--px-1)" }}
          >
            👕 衣橱风格占比
          </h3>
          {pieSegments.length === 0 ? (
            <p style={{ fontSize: "0.65rem", color: "var(--pixel-text-dim)", margin: 0 }}>
              衣橱还是空的，先去存几件吧。
            </p>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "2px var(--px-2)" }}>
              {pieSegments.map((seg) => (
                <span
                  key={seg.name}
                  style={{
                    fontFamily: "var(--font-pixel)",
                    fontSize: "0.6rem",
                    color: "var(--pixel-text-muted)",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "3px"
                  }}
                >
                  <i
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "2px",
                      background: seg.color,
                      display: "inline-block"
                    }}
                  />
                  {seg.name} {Math.round(seg.ratio * 100)}%
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* 最近收藏（压缩小行） */}
      {latest ? (
        <button
          type="button"
          onClick={() => onOpenOutfit(latest.id)}
          style={{
            display: "grid",
            gridTemplateColumns: "3.2rem 1fr auto",
            gap: "var(--px-2)",
            alignItems: "center",
            width: "100%",
            padding: "var(--px-2)",
            background: "var(--pixel-surface)",
            border: "2px solid var(--pixel-border)",
            borderRadius: "var(--pixel-radius-sm)",
            boxShadow: "var(--pixel-shadow)",
            marginBottom: "var(--px-3)",
            textAlign: "left"
          }}
        >
          <img
            src={pixelAvatarDataUrl(latest.seed, { size: 120 })}
            alt={latest.name}
            data-pixel="true"
            style={{ width: "100%", borderRadius: "8px", border: "1px solid var(--pixel-border)" }}
          />
          <div style={{ minWidth: 0 }}>
            <span
              className="pixel-label"
              style={{ fontSize: "0.52rem", display: "block" }}
            >
              最近收藏的穿搭
            </span>
            <strong
              style={{
                fontFamily: "var(--font-pixel)",
                fontSize: "0.72rem",
                color: "var(--pixel-text)",
                display: "block",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis"
              }}
            >
              {latest.name}
            </strong>
          </div>
          <span style={{ color: "var(--pixel-text-dim)", fontSize: "0.9rem" }}>›</span>
        </button>
      ) : null}

      {/* 引导（压缩） */}
      <section
        style={{
          padding: "var(--px-3)",
          background: "linear-gradient(135deg, #f3edfd, #fdeef5)",
          border: "2px solid var(--pixel-secondary)",
          borderRadius: "var(--pixel-radius-sm)",
          textAlign: "center"
        }}
      >
        <p
          style={{
            fontFamily: "var(--font-pixel)",
            fontSize: "0.72rem",
            color: "var(--pixel-text)",
            lineHeight: 1.6,
            margin: "0 0 var(--px-2)"
          }}
        >
          继续探索穿搭，这里的分析会随你的收藏生长 🌱
        </p>
        <div style={{ display: "flex", gap: "var(--px-2)", justifyContent: "center" }}>
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
