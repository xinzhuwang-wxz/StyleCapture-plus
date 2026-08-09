import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  ProductApiError,
  type Item,
  type OutfitPlan,
  type OutfitPlanSet,
  type SavedOutfitLook,
  wardrobeApi
} from "../../api/client";
import { PixelButton } from "../../components/PixelUI";
import { garmentLabel, sourceKindLabel } from "../wardrobe/localization";
import { ChatHistorySheet } from "./ChatHistorySheet";
import {
  readChatHistory,
  saveChatHistory,
  upsertChatRecord,
  type ChatRecord
} from "./chatHistory";

interface AIRecommendScreenProps {
  onGoWardrobe: () => void;
  onGoWardrobeItems?: () => void;
  onSavedLook: (result: SavedOutfitLook) => void;
  onOpenLook: (lookId: string) => void;
  presetPrompt?: string | null;
  anchorItemId?: string | null;
  onClearAnchor?: () => void;
  wardrobeItems?: Item[];
  onSelectAnchorItem?: (itemId: string) => void;
  /** 对话记录的开关由顶栏按钮控制，所以受控于外部。 */
  historyOpen?: boolean;
  onHistoryOpenChange?: (open: boolean) => void;
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

/** 一轮对话。AI 那一轮带着它当时给出的方案，回看时不会张冠李戴。 */
type Turn =
  | { role: "user"; text: string }
  | { role: "ai"; text: string; result: OutfitPlanSet | null };

type RecommendMode = "scene" | "item";
type AnalysisStage = "idle" | "wardrobe" | "candidates" | "reranking" | "complete";

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
        <span className="ai-plan__match">
          {plan.style_match_score}% 契合
        </span>
      </div>

      <div
        className="ai-plan-slots"
        style={{
          marginBottom: "var(--px-3)"
        }}
      >
        {plan.slots.map((slot) => (
          <div
            className="ai-plan-slot"
            key={`${slot.role}-${slot.item_id ?? slot.search_query}`}
          >
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
        className={saved ? "" : "ai-plan__save"}
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
  onGoWardrobeItems,
  onSavedLook,
  onOpenLook,
  presetPrompt,
  anchorItemId,
  onClearAnchor,
  wardrobeItems = [],
  onSelectAnchorItem,
  historyOpen = false,
  onHistoryOpenChange
}: AIRecommendScreenProps) {
  const [input, setInput] = useState("");
  const [weather, setWeather] = useState("");
  const [formality, setFormality] = useState("");
  const [comfort, setComfort] = useState("");
  const [outfitCount, setOutfitCount] = useState<3 | 4>(4);
  const [recommendMode, setRecommendMode] = useState<RecommendMode>(
    anchorItemId ? "item" : "scene"
  );
  const [itemPickerOpen, setItemPickerOpen] = useState(!anchorItemId);
  const [analysisStage, setAnalysisStage] = useState<AnalysisStage>("idle");
  const [savedLooks, setSavedLooks] = useState<Record<string, string>>({});
  const [, setProgressiveResult] =
    useState<OutfitPlanSet | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [history, setHistory] = useState<ChatRecord[]>(() => readChatHistory());
  // 一次对话一个 id，多聊几轮只更新同一条记录，不会在列表里刷屏。
  const [conversationId, setConversationId] = useState<string>(() =>
    crypto.randomUUID()
  );
  /*
   * 这次对话的主题和最后一句用 ref 而不是从 turns 里算。
   * mutation 的 onSuccess 拿到的是创建它那一轮的闭包，那时 setTurns 还没生效，
   * 读出来的是上一轮的 turns——主题会算成空的，于是什么都没记下来。
   */
  const themeRef = useRef("");
  const turnsRef = useRef<Turn[]>([]);
  const lastReplyRef = useRef("");
  const anchorItem = wardrobeItems.find((item) => item.id === anchorItemId) ?? null;
  const availableAnchorItems = wardrobeItems.filter(
    (item) => item.status === "ready" || item.status === "partial"
  );
  const visibleAnchorItems = availableAnchorItems.slice(0, 6);
  const hasGeneratedResult = turns.some(
    (turn) => turn.role === "ai" && turn.result
  );
  const itemConfigurationComplete =
    Boolean(anchorItemId) && Boolean(weather) && Boolean(formality) && Boolean(comfort);
  const planning = useMutation({
    onMutate: () => setAnalysisStage("wardrobe"),
    mutationFn: (scene: string) =>
      wardrobeApi.planOutfitsProgressively(
        {
          scene,
          outfitCount,
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
          setAnalysisStage(
            complete
              ? "complete"
              : result.plans.length >= outfitCount
                ? "reranking"
                : "candidates"
          );
        }
      ),
    onSuccess: (result, scene) => {
      setProgressiveResult(result);
      const reply = `已根据「${scene}」生成 ${result.plans.length} 套可选方案。${
        result.degraded
          ? "当前由稳定搭配规则完成排序，AI 解释暂时降级。"
          : "AI 已结合场景理解并完成重排。"
      }`;
      setTurns((current) => {
        const next: Turn[] = [...current, { role: "ai", text: reply, result }];
        turnsRef.current = next;
        return next;
      });
      // 聊过就算数，不必等到存下某一套——很多次对话本来就不会以保存收尾。
      lastReplyRef.current = reply;
      rememberConversation();
    },
    onError: () => setAnalysisStage("idle")
  });
  const saving = useMutation({
    mutationFn: ({ plan }: { plan: OutfitPlan }) =>
      wardrobeApi.saveOutfitPlan(plan, `save-outfit:${plan.id}`),
    onSuccess: (result, variables) => {
      setSavedLooks((current) => ({
        ...current,
        [variables.plan.id]: result.look_id
      }));
      // 「那天最终选定的搭配」就是在这里定下来的。
      rememberConversation({
        outfitTitle: variables.plan.title,
        outfitLookId: result.look_id
      });
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
      setTurns((current) => {
        const next = current.map((turn) => {
          if (turn.role !== "ai" || !turn.result) return turn;
          return {
            ...turn,
            result: {
              ...turn.result,
              plans: turn.result.plans.map((plan) =>
                plan.id === variables.plan.id ? replacement : plan
              )
            }
          };
        });
        turnsRef.current = next;
        return next;
      });
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

  /**
   * 把一段话追加到输入框，而不是直接发出去。
   *
   * 快捷场景和天气/正式度/舒适偏好都走这里：它们是「帮你少打几个字」，
   * 不是「替你做决定」。以前点一下就直接开始生成，用户还没来得及补充
   * 天气就拿到了方案。
   */
  function appendToInput(fragment: string) {
    setInput((current) => {
      const text = current.trim();
      if (!text) return fragment;
      if (text.includes(fragment)) return text;
      return `${text}，${fragment}`;
    });
  }

  function submit(scene: string) {
    const trimmed =
      scene.trim() ||
      (recommendMode === "item" && anchorItemId
        ? "日常通用，围绕这件单品搭配"
        : "");
    if (!trimmed || planning.isPending) return;
    // 输入框清空，好接着说下一句——这是多轮对话和单发表单的区别。
    setInput("");
    setProgressiveResult(null);
    setTurns((current) => {
      const next: Turn[] = [...current, { role: "user", text: trimmed }];
      turnsRef.current = next;
      return next;
    });
    if (!themeRef.current) themeRef.current = trimmed;
    // 把之前说过的一并带上，AI 才知道这句是在调整上一套，而不是重新开始。
    const said = turns
      .filter((turn): turn is Turn & { role: "user" } => turn.role === "user")
      .map((turn) => turn.text);
    planning.mutate([...said, trimmed].join("；"));
  }

  useEffect(() => {
    if (!anchorItemId) return;
    setRecommendMode("item");
    setItemPickerOpen(false);
  }, [anchorItemId]);

  /**
   * 重试用的是「上次说过的话」，不是输入框。
   *
   * 发送后输入框会清空好接着说下一句，所以失败重试不能再依赖它——
   * 否则按钮永远是禁用的。也不重复追加一轮，那次已经说过了。
   */
  const lastSaid =
    [...turns].reverse().find((turn) => turn.role === "user")?.text ?? "";

  function retryLast() {
    if (!lastSaid || planning.isPending) return;
    const said = turns
      .filter((turn): turn is Turn & { role: "user" } => turn.role === "user")
      .map((turn) => turn.text);
    setProgressiveResult(null);
    planning.mutate(said.join("；"));
  }

  /** 这一轮的落点：主题取第一句，最后一句取 AI 的收尾。 */
  function rememberConversation(patch?: Partial<ChatRecord>) {
    const theme = themeRef.current;
    if (!theme) return;
    setHistory((current) => {
      /*
       * 先把这条已有的内容读出来再覆盖。
       *
       * 从前这里无条件写 outfitLookId: null，于是「存了一套穿搭之后又多聊
       * 了一句」就把那条链接抹掉了，点对话记录只能进到新对话——正是用户
       * 报的那个现象。存过的搭配是这条记录里最有价值的东西，只能被显式
       * 传进来的 patch 覆盖。
       *
       * 用函数式更新是因为这个函数会从 mutation 的 onSuccess 里被调，
       * 那里拿到的 history 是创建 mutation 那一轮的旧值。
       */
      const existing = current.find((entry) => entry.id === conversationId);
      const next = upsertChatRecord(current, {
        outfitTitle: existing?.outfitTitle ?? null,
        outfitLookId: existing?.outfitLookId ?? null,
        ...existing,
        id: conversationId,
        date: new Date().toISOString(),
        theme,
        last: lastReplyRef.current,
        messages: turnsRef.current.map((turn) => ({
          role: turn.role,
          text: turn.text
        })),
        ...patch
      });
      saveChatHistory(next);
      return next;
    });
  }

  if (historyOpen) {
    return (
      <ChatHistorySheet
        records={history}
        onReopen={(record) => {
          // 回到那次对话：把说过的话铺回线程，并接着用同一条记录，
          // 免得同一次聊天在列表里裂成两条。
          const restored: Turn[] = record.messages.map((message) =>
            message.role === "ai"
              ? { role: "ai", text: message.text, result: null }
              : { role: "user", text: message.text }
          );
          setTurns(restored);
          turnsRef.current = restored;
          themeRef.current = record.theme;
          lastReplyRef.current = record.last;
          setConversationId(record.id);
          setProgressiveResult(null);
          onHistoryOpenChange?.(false);
        }}
        onClose={() => onHistoryOpenChange?.(false)}
      />
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "calc(100dvh - 9.5rem)"
      }}
    >
      <div className="ai-mode-switch" role="group" aria-label="推荐方式">
        <button
          type="button"
          className={recommendMode === "scene" ? "is-selected" : ""}
          aria-pressed={recommendMode === "scene"}
          onClick={() => {
            setRecommendMode("scene");
            if (anchorItemId) onClearAnchor?.();
          }}
        >
          按场景推荐
        </button>
        <button
          type="button"
          className={recommendMode === "item" ? "is-selected" : ""}
          aria-pressed={recommendMode === "item"}
          onClick={() => setRecommendMode("item")}
        >
          按单品搭配
        </button>
      </div>

      <section className="ai-intro-card">
        <span className="ai-intro-card__sparkles" aria-hidden="true">✦</span>
        <p>
          {recommendMode === "scene"
            ? "告诉我你要去哪里、想给人什么感觉。AI 会先读取真实衣橱，再筛选和重排候选。"
            : "选定一件搭配核心。每套结果都会使用它，并清楚标出已有、收藏和待补齐的部分。"}
        </p>
      </section>

      {recommendMode === "scene" ? <div
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
            onClick={() => appendToInput(scene)}
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
      </div> : (
        <section className="ai-anchor-panel" aria-label="本次搭配核心">
          <div className="ai-anchor-panel__heading">
            <div>
              <span>本次搭配核心</span>
              <strong>{anchorItem ? garmentLabel(anchorItem.attributes?.subcategory?.value ?? anchorItem.attributes?.category?.value) : "选择一件衣服"}</strong>
            </div>
            <div className="ai-anchor-panel__actions">
              <button type="button" onClick={onGoWardrobeItems ?? onGoWardrobe}>
                更多
              </button>
              {anchorItemId ? (
                <button type="button" onClick={() => setItemPickerOpen((open) => !open)}>
                  更换
                </button>
              ) : null}
            </div>
          </div>
          {anchorItem ? (
            <div className="ai-anchor-card">
              <img
                src={anchorItem.pixel_image_url ?? anchorItem.display_image_url}
                alt={garmentLabel(anchorItem.attributes?.subcategory?.value ?? anchorItem.attributes?.category?.value)}
              />
              <div>
                <strong>必须出现在每套方案中</strong>
                <span>{anchorItem.ownership === "owned" ? "已拥有" : "已收藏"} · 真实衣橱单品</span>
              </div>
              <span className="ai-anchor-card__lock">已锁定</span>
            </div>
          ) : null}
          {itemPickerOpen || !anchorItemId ? (
            <div className="ai-item-picker" aria-label="选择搭配单品">
              {visibleAnchorItems.map((item) => {
                const label = garmentLabel(
                  item.attributes?.subcategory?.value ?? item.attributes?.category?.value
                );
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-label={`选择${label}`}
                    onClick={() => {
                      onSelectAnchorItem?.(item.id);
                      setItemPickerOpen(false);
                    }}
                  >
                    <img src={item.pixel_image_url ?? item.display_image_url} alt="" />
                    <span>{label}</span>
                  </button>
                );
              })}
              {availableAnchorItems.length === 0 ? (
                <button type="button" onClick={onGoWardrobe}>先去衣橱添加单品</button>
              ) : null}
            </div>
          ) : null}
        </section>
      )}

      <section className="ai-constraints" aria-label="搭配条件">
        <div className="ai-constraints__row">
          <span>方案数</span>
          <div role="group" aria-label="推荐方案数">
            {([3, 4] as const).map((count) => (
              <button
                key={count}
                type="button"
                className={outfitCount === count ? "is-selected" : ""}
                aria-pressed={outfitCount === count}
                onClick={() => setOutfitCount(count)}
              >
                {count} 套
              </button>
            ))}
          </div>
        </div>
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
                  onClick={() => {
                    const next = selected === option ? "" : option;
                    setSelected(next);
                    // 场景模式里，条件按钮也是帮用户少打字；单品模式首次推荐时，
                    // 它们作为结构化条件随请求提交，不污染后续补充输入框。
                    if (next && (recommendMode === "scene" || hasGeneratedResult)) {
                      appendToInput(option);
                    }
                  }}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        ))}
        {recommendMode === "item" && !hasGeneratedResult ? (
          <div className="ai-confirm-block">
            <PixelButton
              variant="primary"
              className="ai-anchor-confirm"
              disabled={planning.isPending || !itemConfigurationComplete}
              onClick={() => submit(input)}
            >
              确定并推荐
            </PixelButton>
            {!itemConfigurationComplete ? (
              <span>
                先选择必须包含的单品，并确定天气、正式度和舒适偏好。
              </span>
            ) : null}
          </div>
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
        {turns.map((turn, index) =>
          turn.role === "user" ? (
            <div
              key={`${turn.role}-${index}`}
              className="pixel-chat-bubble pixel-chat-bubble--user"
            >
              {turn.text}
            </div>
          ) : turn.result ? (
            <div key={`${turn.role}-${index}`} className="ai-result-group">
              <div className="pixel-chat-bubble pixel-chat-bubble--ai">
                ◇ {turn.text}
              </div>
              <div className={`ai-result-proof ${turn.result.degraded ? "is-degraded" : ""}`}>
                <strong>{turn.result.degraded ? "规则推荐" : "AI 已完成分析与重排"}</strong>
                <span>{turn.result.degraded ? "AI 暂不可用，已明确降级" : "真实衣橱召回 · 硬规则筛选 · AI 闭集重排"}</span>
              </div>
              {turn.result.plans.map((plan, planIndex) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  index={planIndex}
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
            </div>
          ) : null
        )}

        {planning.isPending ? (
          <section className="ai-analysis-progress" role="status" aria-label="AI 分析进度">
            <div className="ai-analysis-progress__title">
              <span className="ai-analysis-progress__pulse" aria-hidden="true" />
              <div><strong>正在分析你的真实衣橱</strong><span>不会用等待动画假装思考，以下状态来自实际推荐流程</span></div>
            </div>
            {[
              ["wardrobe", "读取可搭配的真实单品"],
              ["candidates", "应用场景、季节和品类硬规则"],
              ["reranking", "AI 比较配色、廓形与衣物复用"],
              ["complete", "整理推荐依据"]
            ].map(([stage, label], index, stages) => {
              const current = stages.findIndex(([value]) => value === analysisStage);
              const status = index < current ? "completed" : index === current ? "active" : "pending";
              return <div key={stage} className={`ai-analysis-step is-${status}`}><span>{status === "completed" ? "✓" : index + 1}</span><strong>{label}</strong></div>;
            })}
          </section>
        ) : null}

        {planning.isError ? (
          <div className="pixel-chat-bubble pixel-chat-bubble--ai" role="alert">
            ◇ {errorMessage(planning.error)}
            <div style={{ marginTop: "var(--px-2)", display: "flex", gap: "var(--px-2)", flexWrap: "wrap" }}>
              <PixelButton
                variant="primary"
                disabled={planning.isPending || !lastSaid}
                onClick={retryLast}
              >
                重试当前需求
              </PixelButton>
              <PixelButton variant="ghost" onClick={onGoWardrobe}>
                打开数字衣橱
              </PixelButton>
            </div>
          </div>
        ) : null}

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
      </div>

      <div className="ai-composer">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") submit(input);
          }}
          placeholder={recommendMode === "item" ? "可选：补充场景或想要的感觉" : "例如：下周一面试，想显得可靠又有个性"}
          aria-label="穿搭需求"
        />
        <PixelButton
          variant="primary"
          className="ai-composer__send"
          onClick={() => submit(input)}
          disabled={
            planning.isPending ||
            (recommendMode === "scene"
              ? !input.trim()
              : !hasGeneratedResult || !input.trim())
          }
          ariaLabel="生成穿搭推荐"
        >
          <span aria-hidden="true">➤</span>
        </PixelButton>
      </div>
    </div>
  );
}
