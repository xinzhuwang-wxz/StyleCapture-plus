import { useMemo } from "react";

import type { Item, Look } from "../../api/client";
import { PixelButton } from "../../components/PixelUI";

interface AnalysisScreenProps {
  items: Item[];
  looks: Look[];
  onGoAI: () => void;
  onGoWardrobe: () => void;
  onOpenLook: (lookId: string) => void;
}

const STATUS_LABELS: Record<Look["status"], string> = {
  processing: "拆解中",
  partial: "待补全",
  ready: "已解析",
  error: "需重试"
};

const STATUS_COLORS: Record<Look["status"], string> = {
  processing: "var(--pixel-primary-dark)",
  partial: "var(--pixel-accent-glow)",
  ready: "var(--pixel-success)",
  error: "var(--pixel-error)"
};

export function AnalysisScreen({
  items,
  looks,
  onGoAI,
  onGoWardrobe,
  onOpenLook
}: AnalysisScreenProps) {
  const stats = useMemo(() => {
    const owned = items.filter((item) => item.ownership === "owned").length;
    const inspiration = items.filter((item) => item.ownership === "inspiration").length;
    const byStatus = looks.reduce(
      (acc, look) => {
        acc[look.status] += 1;
        return acc;
      },
      { processing: 0, partial: 0, ready: 0, error: 0 } satisfies Record<Look["status"], number>
    );
    return { owned, inspiration, byStatus };
  }, [items, looks]);

  const latestLook = looks[0];

  return (
    <div>
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
          真实衣橱数据
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
          { n: stats.owned, label: "我的单品", color: "var(--pixel-accent-glow)" },
          { n: stats.inspiration, label: "灵感单品", color: "var(--pixel-pink-dark)" },
          { n: looks.length, label: "整套穿搭", color: "var(--pixel-primary-dark)" }
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

      <section
        style={{
          padding: "var(--px-3)",
          background: "var(--pixel-surface)",
          border: "2px solid var(--pixel-border)",
          borderRadius: "var(--pixel-radius-sm)",
          boxShadow: "var(--pixel-shadow)",
          marginBottom: "var(--px-3)"
        }}
      >
        <h3
          className="pixel-subtitle"
          style={{ fontSize: "0.72rem", margin: "0 0 var(--px-2)" }}
        >
          👕 整套穿搭状态
        </h3>
        <div style={{ display: "grid", gap: "var(--px-2)" }}>
          {(Object.keys(stats.byStatus) as Look["status"][]).map((status) => {
            const count = stats.byStatus[status];
            const ratio = looks.length > 0 ? count / looks.length : 0;
            return (
              <div key={status}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    color: "var(--pixel-text-muted)",
                    fontFamily: "var(--font-pixel)",
                    fontSize: "0.62rem",
                    marginBottom: "3px"
                  }}
                >
                  <span>{STATUS_LABELS[status]}</span>
                  <span>{count}</span>
                </div>
                <div
                  aria-label={`${STATUS_LABELS[status]} ${count} 套`}
                  style={{
                    height: "8px",
                    borderRadius: "999px",
                    background: "var(--pixel-border-light)",
                    overflow: "hidden"
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      width: `${Math.round(ratio * 100)}%`,
                      height: "100%",
                      background: STATUS_COLORS[status]
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {latestLook ? (
        <button
          type="button"
          onClick={() => onOpenLook(latestLook.id)}
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
          {latestLook.display_image_url ? (
            <img
              src={latestLook.display_image_url}
              alt="最近收藏的真实穿搭"
              style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: "8px" }}
            />
          ) : (
            <span
              style={{
                display: "grid",
                placeItems: "center",
                width: "100%",
                aspectRatio: "1",
                background: "var(--pixel-bg-light)",
                borderRadius: "8px"
              }}
              aria-hidden="true"
            >
              ✦
            </span>
          )}
          <div style={{ minWidth: 0 }}>
            <span className="pixel-label" style={{ fontSize: "0.52rem", display: "block" }}>
              最近收藏的真实穿搭
            </span>
            <strong
              style={{
                fontFamily: "var(--font-pixel)",
                fontSize: "0.72rem",
                color: "var(--pixel-text)",
                display: "block"
              }}
            >
              {latestLook.source === "feed_saved" ? "Feed 穿搭灵感" : "我的搭配"}
            </strong>
          </div>
          <span style={{ color: "var(--pixel-text-dim)", fontSize: "0.9rem" }}>›</span>
        </button>
      ) : null}

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
          分析只来自真实衣橱和真实 Feed 收藏，不展示模拟搭配。
        </p>
        <div style={{ display: "flex", gap: "var(--px-2)", justifyContent: "center" }}>
          <PixelButton variant="primary" onClick={onGoAI}>
            ◇ AI 状态
          </PixelButton>
          <PixelButton variant="ghost" onClick={onGoWardrobe}>
            👕 打开衣橱
          </PixelButton>
        </div>
      </section>
    </div>
  );
}
