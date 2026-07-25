import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  ProductApiError,
  type OutfitPlan,
  wardrobeApi
} from "../../api/client";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";

interface AIRecommendScreenProps {
  onGoWardrobe: () => void;
  presetPrompt?: string | null;
}

const SCENE_PRESETS = [
  "通勤面试，利落但不刻板",
  "周末约会，松弛又有层次",
  "旅行拍照，显眼但方便走路",
  "日常上课，舒适耐看"
];

const ROLE_LABELS: Record<string, string> = {
  tops: "上衣",
  bottoms: "下装",
  dresses: "连衣裙",
  outerwear: "外套",
  shoes: "鞋履",
  accessories: "配饰"
};

const OWNERSHIP_LABELS: Record<string, string> = {
  owned: "我有",
  inspiration: "已收藏",
  cart: "待购买",
  purchased: "已购买"
};

function errorMessage(error: unknown): string {
  if (error instanceof ProductApiError) {
    if (error.code === "outfit_wardrobe_empty") {
      return "衣橱里还没有可搭配的单品。先去收藏一套灵感，或上传一件自己的衣服吧。";
    }
    return error.message;
  }
  return "搭配请求暂时没有完成，请稍后再试。";
}

function PlanCard({ plan, index }: { plan: OutfitPlan; index: number }) {
  return (
    <article
      aria-label={`搭配方案 ${index + 1}`}
      style={{
        padding: "var(--px-3)",
        borderRadius: "var(--pixel-border-radius)",
        border: "2px solid var(--pixel-border)",
        background: "var(--pixel-surface)",
        boxShadow: "var(--pixel-shadow)"
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "var(--px-2)",
          alignItems: "start",
          marginBottom: "var(--px-3)"
        }}
      >
        <div>
          <p
            style={{
              margin: 0,
              color: "var(--pixel-text-muted)",
              fontSize: "0.68rem"
            }}
          >
            LOOK {String(index + 1).padStart(2, "0")}
          </p>
          <h3 style={{ margin: "0.25rem 0 0", fontSize: "1rem" }}>{plan.title}</h3>
        </div>
        <span
          style={{
            flex: "0 0 auto",
            padding: "0.25rem 0.55rem",
            borderRadius: "999px",
            background: "var(--pixel-primary)",
            color: "white",
            fontSize: "0.68rem",
            fontWeight: 800
          }}
        >
          {plan.style_match_score}% 契合
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: "var(--px-2)",
          marginBottom: "var(--px-3)"
        }}
      >
        {plan.slots.map((slot) => (
          <div key={`${slot.role}-${slot.item_id ?? slot.search_query}`}>
            <div
              style={{
                aspectRatio: "1",
                display: "grid",
                placeItems: "center",
                overflow: "hidden",
                borderRadius: "0.8rem",
                border: slot.item_id
                  ? "2px solid var(--pixel-border-light)"
                  : "2px dashed var(--pixel-secondary)",
                background: "var(--pixel-bg-light)"
              }}
            >
              {slot.image_url ? (
                <img
                  src={slot.image_url}
                  alt={slot.item_name ?? ROLE_LABELS[slot.role] ?? "衣橱单品"}
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "contain"
                  }}
                />
              ) : (
                <span
                  aria-label="衣橱缺口"
                  style={{
                    color: "var(--pixel-secondary)",
                    fontSize: "1.3rem"
                  }}
                >
                  ＋
                </span>
              )}
            </div>
            <p
              style={{
                margin: "0.35rem 0 0",
                fontSize: "0.62rem",
                lineHeight: 1.35,
                color: "var(--pixel-text-muted)"
              }}
            >
              {ROLE_LABELS[slot.role] ?? slot.role}
              <br />
              {slot.ownership
                ? OWNERSHIP_LABELS[slot.ownership] ?? slot.ownership
                : "待补齐"}
            </p>
          </div>
        ))}
      </div>

      <p
        style={{
          margin: 0,
          fontSize: "0.76rem",
          lineHeight: 1.75,
          color: "var(--pixel-text)"
        }}
      >
        {plan.rationale}
      </p>
      {plan.missing_count > 0 ? (
        <p
          style={{
            margin: "var(--px-2) 0 0",
            color: "var(--pixel-primary)",
            fontSize: "0.7rem",
            fontWeight: 700
          }}
        >
          还差 {plan.missing_count} 件，已为你生成补齐方向
        </p>
      ) : null}
    </article>
  );
}

export function AIRecommendScreen({
  onGoWardrobe,
  presetPrompt
}: AIRecommendScreenProps) {
  const [input, setInput] = useState("");
  const planning = useMutation({
    mutationFn: (scene: string) =>
      wardrobeApi.planOutfits({
        scene,
        style: scene.includes("利落")
          ? "简洁利落"
          : scene.includes("松弛")
            ? "松弛有层次"
            : undefined
      })
  });

  useEffect(() => {
    if (presetPrompt) setInput(presetPrompt);
  }, [presetPrompt]);

  function submit(scene: string) {
    const trimmed = scene.trim();
    if (!trimmed || planning.isPending) return;
    setInput(trimmed);
    planning.mutate(trimmed);
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "calc(100dvh - 9.5rem)"
      }}
    >
      <PixelSectionHeader
        kicker="AI 穿搭闺蜜"
        title="从真实衣橱开始搭"
        action={<span style={{ fontSize: "1.4rem" }} aria-hidden="true">◇</span>}
      />

      <section
        style={{
          padding: "var(--px-3)",
          borderRadius: "var(--pixel-border-radius)",
          background:
            "linear-gradient(135deg, color-mix(in srgb, var(--pixel-primary) 14%, white), var(--pixel-surface))",
          border: "2px solid var(--pixel-border-light)",
          margin: "var(--px-2) 0 var(--px-3)"
        }}
      >
        <p
          style={{
            margin: 0,
            color: "var(--pixel-text)",
            fontSize: "0.78rem",
            lineHeight: 1.75
          }}
        >
          告诉我你要去哪里、想给人什么感觉。优先使用你已有和收藏的衣服，
          缺的部分会明确标出，不会假装你已经拥有。
        </p>
      </section>

      <div
        style={{
          display: "flex",
          gap: "var(--px-2)",
          overflowX: "auto",
          paddingBottom: "var(--px-3)"
        }}
        aria-label="快捷场景"
      >
        {SCENE_PRESETS.map((scene) => (
          <button
            key={scene}
            type="button"
            onClick={() => submit(scene)}
            disabled={planning.isPending}
            style={{
              flex: "0 0 auto",
              padding: "0.55rem 0.8rem",
              border: "2px solid var(--pixel-border-light)",
              borderRadius: "999px",
              background: "var(--pixel-surface)",
              color: "var(--pixel-text)",
              fontFamily: "var(--font-body)",
              fontSize: "0.7rem",
              cursor: "pointer"
            }}
          >
            {scene.split("，")[0]}
          </button>
        ))}
      </div>

      <div
        aria-live="polite"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: "var(--px-3)",
          paddingBottom: "7rem"
        }}
      >
        {!planning.data && !planning.isPending && !planning.isError ? (
          <div
            style={{
              padding: "2.5rem var(--px-3)",
              textAlign: "center",
              border: "2px dashed var(--pixel-border-light)",
              borderRadius: "var(--pixel-border-radius)",
              color: "var(--pixel-text-muted)"
            }}
          >
            <div style={{ fontSize: "2rem", marginBottom: "0.75rem" }}>✦</div>
            <p style={{ margin: 0, fontSize: "0.78rem", lineHeight: 1.7 }}>
              选择一个场景，或写下你的穿搭需求
            </p>
          </div>
        ) : null}

        {planning.isPending ? (
          <div className="pixel-chat-bubble pixel-chat-bubble--ai" role="status">
            ◇ 正在读取真实衣橱，并从拥有、收藏和待补齐三个层次组织方案…
          </div>
        ) : null}

        {planning.isError ? (
          <div className="pixel-chat-bubble pixel-chat-bubble--ai" role="alert">
            ◇ {errorMessage(planning.error)}
            <div style={{ marginTop: "var(--px-2)" }}>
              <PixelButton variant="ghost" onClick={onGoWardrobe}>
                打开数字衣橱
              </PixelButton>
            </div>
          </div>
        ) : null}

        {planning.data ? (
          <>
            <div className="pixel-chat-bubble pixel-chat-bubble--ai">
              ◇ 已根据「{input}」从你的真实衣橱生成 {planning.data.plans.length} 套方案。
              {planning.data.degraded
                ? "当前由稳定搭配规则完成排序，AI 解释暂时降级。"
                : "AI 已结合场景理解完成重排。"}
            </div>
            {planning.data.plans.map((plan, index) => (
              <PlanCard key={plan.id} plan={plan} index={index} />
            ))}
          </>
        ) : null}
      </div>

      <div
        style={{
          position: "sticky",
          bottom: "5.4rem",
          zIndex: 2,
          display: "flex",
          gap: "var(--px-2)",
          padding: "var(--px-3)",
          borderRadius: "var(--pixel-border-radius)",
          border: "2px solid var(--pixel-border)",
          background: "color-mix(in srgb, var(--pixel-surface) 94%, transparent)",
          backdropFilter: "blur(14px)",
          boxShadow: "var(--pixel-shadow)"
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") submit(input);
          }}
          placeholder="例如：下周一面试，想显得可靠又有个性"
          aria-label="穿搭需求"
          style={{
            flex: 1,
            minWidth: 0,
            padding: "var(--px-2) var(--px-3)",
            fontFamily: "var(--font-body)",
            fontSize: "0.78rem",
            background: "var(--pixel-bg-light)",
            border: "2px solid var(--pixel-border-light)",
            borderRadius: "999px",
            color: "var(--pixel-text)",
            outline: "none"
          }}
        />
        <PixelButton
          variant="primary"
          onClick={() => submit(input)}
          disabled={!input.trim() || planning.isPending}
          ariaLabel="生成穿搭"
        >
          ➤
        </PixelButton>
      </div>
    </div>
  );
}
