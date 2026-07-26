import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  ProductApiError,
  type OutfitPlan,
  type OutfitPlanSet,
  type SavedOutfitLook,
  wardrobeApi
} from "../../api/client";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { sourceKindLabel } from "../wardrobe/localization";

interface AIRecommendScreenProps {
  onGoWardrobe: () => void;
  onSavedLook: (result: SavedOutfitLook) => void;
  onOpenLook: (lookId: string) => void;
  presetPrompt?: string | null;
  anchorItemId?: string | null;
  onClearAnchor?: () => void;
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
};

const WEATHER_OPTIONS = ["炎热高温", "温和", "寒冷低温"];
const FORMALITY_OPTIONS = ["轻松休闲", "日常得体", "正式商务"];
const COMFORT_OPTIONS = ["方便走路", "久坐舒适", "拍照优先"];

function errorMessage(error: unknown): string {
  if (error instanceof ProductApiError) {
    if (error.code === "outfit_wardrobe_empty") {
      return "衣橱里还没有可搭配的单品。先去收藏一套灵感，或上传一件自己的衣服吧。";
    }
    return error.message;
  }
  return "搭配请求暂时没有完成，请稍后再试。";
}

function PlanCard({
  plan,
  index,
  saving,
  saved,
  replacingRole,
  onSave,
  onOpen,
  onReplace
}: {
  plan: OutfitPlan;
  index: number;
  saving: boolean;
  saved: boolean;
  replacingRole: string | null;
  onSave: () => void;
  onOpen: () => void;
  onReplace: (role: OutfitPlan["slots"][number]["role"]) => void;
}) {
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
            方案 {String(index + 1).padStart(2, "0")}
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
              {slot.source_kind ? (
                <>
                  <br />
                  {sourceKindLabel(slot.source_kind)}
                </>
              ) : null}
            </p>
            {slot.item_id ? (
              <button
                type="button"
                className="ai-slot-action"
                disabled={replacingRole !== null}
                onClick={() => onReplace(slot.role)}
              >
                {replacingRole === slot.role ? "替换中…" : "换一件"}
              </button>
            ) : slot.search_query ? (
              <a
                className="ai-slot-action"
                href={`https://www.douyin.com/search/${encodeURIComponent(slot.search_query)}`}
                target="_blank"
                rel="noreferrer"
              >
                去搜同款
              </a>
            ) : null}
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
      <PixelButton
        variant={saved ? "ghost" : "primary"}
        disabled={saving}
        onClick={saved ? onOpen : onSave}
      >
        {saving
          ? "正在保存…"
          : saved
            ? "已存入衣橱 · 查看"
            : "保存这套"}
      </PixelButton>
    </article>
  );
}

export function AIRecommendScreen({
  onGoWardrobe,
  onSavedLook,
  onOpenLook,
  presetPrompt,
  anchorItemId,
  onClearAnchor
}: AIRecommendScreenProps) {
  const [input, setInput] = useState("");
  const [weather, setWeather] = useState("");
  const [formality, setFormality] = useState("");
  const [comfort, setComfort] = useState("");
  const [savedLooks, setSavedLooks] = useState<Record<string, string>>({});
  const [progressiveResult, setProgressiveResult] =
    useState<OutfitPlanSet | null>(null);
  const [reasoningComplete, setReasoningComplete] = useState(false);
  const planning = useMutation({
    mutationFn: (scene: string) =>
      wardrobeApi.planOutfitsProgressively(
        {
          scene,
          style: scene.includes("利落")
            ? "简洁利落"
            : scene.includes("松弛")
              ? "松弛有层次"
              : undefined,
          weather: weather || undefined,
          formality: formality || undefined,
          comfort: comfort || undefined,
          anchorItemId: anchorItemId ?? undefined
        },
        (result, complete) => {
          setProgressiveResult(result);
          setReasoningComplete(complete);
        }
      ),
    onSuccess: (result) => {
      setProgressiveResult(result);
      setReasoningComplete(true);
    }
  });
  const saving = useMutation({
    mutationFn: ({ plan }: { plan: OutfitPlan }) =>
      wardrobeApi.saveOutfitPlan(plan, `save-outfit:${plan.id}`),
    onSuccess: (result, variables) => {
      setSavedLooks((current) => ({
        ...current,
        [variables.plan.id]: result.look_id
      }));
      onSavedLook(result);
    }
  });
  const replacing = useMutation({
    mutationFn: ({
      plan,
      role
    }: {
      plan: OutfitPlan;
      role: OutfitPlan["slots"][number]["role"];
    }) => wardrobeApi.replaceOutfitSlot(plan, role),
    onSuccess: (replacement, variables) => {
      setProgressiveResult((current) => {
        const source = current ?? planning.data;
        if (!source) return current;
        return {
          ...source,
          plans: source.plans.map((plan) =>
            plan.id === variables.plan.id ? replacement : plan
          )
        };
      });
    }
  });

  useEffect(() => {
    if (presetPrompt) setInput(presetPrompt);
  }, [presetPrompt]);

  function submit(scene: string) {
    const trimmed = scene.trim();
    if (!trimmed || planning.isPending) return;
    setInput(trimmed);
    setProgressiveResult(null);
    setReasoningComplete(false);
    planning.mutate(trimmed);
  }

  const displayedResult = progressiveResult ?? planning.data ?? null;

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

      <section className="ai-constraints" aria-label="搭配条件">
        {(
          [
            ["天气", WEATHER_OPTIONS, weather, setWeather],
            ["正式度", FORMALITY_OPTIONS, formality, setFormality],
            ["舒适偏好", COMFORT_OPTIONS, comfort, setComfort]
          ] as const
        ).map(([label, options, selected, setSelected]) => (
          <div key={label} className="ai-constraints__row">
            <span>{label}</span>
            <div>
              {options.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={selected === option ? "is-selected" : ""}
                  aria-pressed={selected === option}
                  onClick={() => setSelected(selected === option ? "" : option)}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        ))}
        {anchorItemId ? (
          <p className="ai-constraints__anchor">
            已锁定从单品详情带来的目标衣服，每套方案都会使用它。
            {onClearAnchor ? (
              <button type="button" onClick={onClearAnchor}>
                取消锁定
              </button>
            ) : null}
          </p>
        ) : null}
      </section>

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
        {planning.isPending && !displayedResult ? (
          <div className="pixel-chat-bubble pixel-chat-bubble--ai" role="status">
            ◇ 正在读取真实衣橱，并从拥有、收藏和待补齐三个层次组织方案…
          </div>
        ) : null}

        {planning.isError ? (
          <div className="pixel-chat-bubble pixel-chat-bubble--ai" role="alert">
            ◇ {errorMessage(planning.error)}
            <div style={{ marginTop: "var(--px-2)", display: "flex", gap: "var(--px-2)", flexWrap: "wrap" }}>
              <PixelButton
                variant="primary"
                disabled={planning.isPending || !input.trim()}
                onClick={() => submit(input)}
              >
                重试当前需求
              </PixelButton>
              <PixelButton variant="ghost" onClick={onGoWardrobe}>
                打开数字衣橱
              </PixelButton>
            </div>
          </div>
        ) : null}

        {displayedResult ? (
          <>
            <div className="pixel-chat-bubble pixel-chat-bubble--ai">
              ◇ 已根据「{input}」先生成 {displayedResult.plans.length} 套可选方案。
              {!reasoningComplete
                ? "新方案会逐套出现，AI 正在继续理解和细化。"
                : displayedResult.degraded
                ? "当前由稳定搭配规则完成排序，AI 解释暂时降级。"
                : "AI 已结合场景理解完成重排。"}
            </div>
            {displayedResult.plans.map((plan, index) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                index={index}
                saving={saving.isPending && saving.variables?.plan.id === plan.id}
                saved={Boolean(savedLooks[plan.id])}
                replacingRole={
                  replacing.isPending && replacing.variables?.plan.id === plan.id
                    ? replacing.variables.role
                    : null
                }
                onSave={() =>
                  saving.mutate({
                    plan
                  })
                }
                onOpen={() => onOpenLook(savedLooks[plan.id]!)}
                onReplace={(role) => replacing.mutate({ plan, role })}
              />
            ))}
            {saving.isError ? (
              <div className="pixel-chat-bubble pixel-chat-bubble--ai" role="alert">
                ◇ {errorMessage(saving.error)}
              </div>
            ) : null}
            {replacing.isError ? (
              <div className="pixel-chat-bubble pixel-chat-bubble--ai" role="alert">
                ◇ {errorMessage(replacing.error)}
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <div
        style={{
          position: "sticky",
          bottom: "-1.4rem",
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
          ariaLabel="生成穿搭推荐"
        >
          ➤
        </PixelButton>
      </div>
    </div>
  );
}
