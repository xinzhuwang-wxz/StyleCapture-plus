import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient
} from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import {
  type CaptureAccepted,
  type Item,
  type Look,
  type Ownership,
  type PurchaseDemand,
  type RenderArtifact,
  type RenderKind,
  type SourceKind,
  ProductApiError,
  validateImage,
  wardrobeApi
} from "../api/client";
import { PhoneFrame } from "../components/PhoneFrame";
import type { CommunityAvatarSource } from "../features/community/CommunityScreen";
import { FeedScreen } from "../features/feed/FeedScreen";
import type { PendingItem } from "../features/wardrobe/ItemCard";
import type { LookItemAction } from "../features/wardrobe/LookItemActionSheet";
import type { WardrobeView } from "../features/wardrobe/WardrobeScreen";
import {
  createBrowserImagePreview,
  releaseBrowserImagePreview
} from "../media/browserImagePreview";
import "./styles.css";
import "./pixel-theme.css";

type Selection = {
  file: File;
  previewUrl: string | null;
  sourceKind: SourceKind;
};

type Destination =
  | "feed"
  | "wardrobe"
  | "analysis"
  | "ai"
  | "world"
  | "profile";
type FeedRestoreTarget = {
  videoRef: string;
  timestampMs: number;
  requestId: string;
};

const PENDING_ITEMS_STORAGE_KEY = "stylecapture:pending-items:v1";
const SELECTED_LOOK_STORAGE_KEY = "stylecapture:selected-look:v1";
const CommunityScreen = lazy(() =>
  import("../features/community/CommunityScreen").then((module) => ({
    default: module.CommunityScreen
  }))
);
const CaptureSheet = lazy(() =>
  import("../features/capture/CaptureSheet").then((module) => ({
    default: module.CaptureSheet
  }))
);
const ItemDetail = lazy(() =>
  import("../features/wardrobe/ItemDetail").then((module) => ({
    default: module.ItemDetail
  }))
);
const LookDetail = lazy(() =>
  import("../features/wardrobe/LookDetail").then((module) => ({
    default: module.LookDetail
  }))
);
const LookItemActionSheet = lazy(() =>
  import("../features/wardrobe/LookItemActionSheet").then((module) => ({
    default: module.LookItemActionSheet
  }))
);
const AIRecommendScreen = lazy(() =>
  import("../features/ai/AIRecommendScreen").then((module) => ({
    default: module.AIRecommendScreen
  }))
);
const AnalysisScreen = lazy(() =>
  import("../features/analysis/AnalysisScreen").then((module) => ({
    default: module.AnalysisScreen
  }))
);
const ProfileScreen = lazy(() =>
  import("../features/profile/ProfileScreen").then((module) => ({
    default: module.ProfileScreen
  }))
);
const WardrobeScreen = lazy(() =>
  import("../features/wardrobe/WardrobeScreen").then((module) => ({
    default: module.WardrobeScreen
  }))
);

type NavIconName = "wardrobe" | "analysis" | "ai" | "world" | "profile";

function NavIcon({ name }: { name: NavIconName }) {
  if (name === "wardrobe") {
    return (
      <svg
        aria-hidden="true"
        className="nav-icon"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="m9.5 4-2 3L4 8.4 5.7 13l3.1-1.3V20h6.4v-8.3l3.1 1.3L20 8.4 16.5 7l-2-3h-5Z" />
      </svg>
    );
  }

  if (name === "analysis") {
    return (
      <svg
        aria-hidden="true"
        className="nav-icon"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="M4 19V5m0 14h16M8 15l3-4 3 2 4-6" />
        <path d="m16 7 2-1 1 2" />
      </svg>
    );
  }

  if (name === "ai") {
    return (
      <svg
        aria-hidden="true"
        className="nav-icon"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="M12 3v4.5M12 16.5V21M3 12h4.5M16.5 12H21M6.5 6.5l3.2 3.2m4.6 4.6 3.2 3.2m0-11-3.2 3.2M9.7 14.3l-3.2 3.2" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    );
  }

  if (name === "world") {
    return (
      <svg
        aria-hidden="true"
        className="nav-icon"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="M4.5 13.2c2.3-3.4 6.5-5.8 10.6-5.1 3.2.5 5 2.5 4.4 4.5-.8 2.5-5.7 4.4-10.1 3.7-2.3-.4-4.2-1.5-4.9-3.1Z" />
        <path d="M8.8 8.4 12 4l2.2 4M6.5 17.2l-1 2.3m11.6-4.1 1.5 2.1" />
        <circle cx="15.8" cy="11.3" r="1" />
      </svg>
    );
  }

  return (
    <svg
      aria-hidden="true"
      className="nav-icon"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <circle cx="12" cy="8.2" r="3.2" />
      <path d="M5.5 20c.6-4 3.1-6.2 6.5-6.2s5.9 2.2 6.5 6.2" />
    </svg>
  );
}

function restoreSelectedLookId(): string | null {
  if (typeof window === "undefined") return null;
  const stored = window.sessionStorage.getItem(SELECTED_LOOK_STORAGE_KEY);
  return stored && stored.trim() ? stored : null;
}

function restorePendingItems(): PendingItem[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(
      window.sessionStorage.getItem(PENDING_ITEMS_STORAGE_KEY) ?? "[]"
    ) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.flatMap((entry) => {
      if (
        typeof entry !== "object" ||
        entry === null ||
        !("captureId" in entry) ||
        !("jobId" in entry) ||
        typeof entry.captureId !== "string" ||
        typeof entry.jobId !== "string"
      ) {
        return [];
      }
      const ownership = entry.ownership === "inspiration" ? "inspiration" : "owned";
      const state =
        entry.state === "processing" ||
        entry.state === "partial" ||
        entry.state === "ready" ||
        entry.state === "error"
          ? entry.state
          : "queued";
      return [
        {
          captureId: entry.captureId,
          jobId: entry.jobId,
          previewUrl: null,
          ownership,
          state,
          errorCode:
            "errorCode" in entry && typeof entry.errorCode === "string"
              ? entry.errorCode
              : null,
          errorMessage: null
        } satisfies PendingItem
      ];
    });
  } catch {
    return [];
  }
}

function errorMessage(error: unknown): string {
  if (error instanceof ProductApiError || error instanceof Error) {
    return error.message;
  }
  return "刚刚没有完成，请稍后再试";
}

function DeferredScreenFallback() {
  return (
    <div className="wardrobe-loading" role="status">
      正在打开数字衣橱…
    </div>
  );
}

export function App() {
  const queryClient = useQueryClient();
  const cameraInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);
  const addMenuTrigger = useRef<HTMLButtonElement>(null);
  const addMenuClose = useRef<HTMLButtonElement>(null);
  const wardrobeView = useRef<HTMLDivElement>(null);
  const restoredLookId = useRef(restoreSelectedLookId());
  const [destination, setDestination] = useState<Destination>("wardrobe");
  const [wardrobeViewMode, setWardrobeViewMode] = useState<WardrobeView>("looks");
  const [feedRestoreTarget, setFeedRestoreTarget] =
    useState<FeedRestoreTarget | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pending, setPending] = useState<PendingItem[]>(restorePendingItems);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [lookItemAction, setLookItemAction] = useState<LookItemAction | null>(null);
  const [aiHistoryOpen, setAiHistoryOpen] = useState(false);
  const [selectedLookId, setSelectedLookId] = useState<string | null>(
    restoredLookId.current
  );
  const [aiAnchorItemId, setAiAnchorItemId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [feedLikingLookId, setFeedLikingLookId] = useState<string | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 6_000);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  useEffect(() => {
    if (selectedLookId) {
      window.sessionStorage.setItem(SELECTED_LOOK_STORAGE_KEY, selectedLookId);
      return;
    }
    window.sessionStorage.removeItem(SELECTED_LOOK_STORAGE_KEY);
  }, [selectedLookId]);

  useEffect(() => {
    if (!feedLikingLookId) return;
    const timeout = window.setTimeout(() => setFeedLikingLookId(null), 10_000);
    return () => window.clearTimeout(timeout);
  }, [feedLikingLookId]);

  useEffect(() => {
    const durablePending = pending.map(({ previewUrl: _previewUrl, ...entry }) => ({
      ...entry,
      previewUrl: null,
      errorMessage: null
    }));
    if (durablePending.length === 0) {
      window.sessionStorage.removeItem(PENDING_ITEMS_STORAGE_KEY);
      return;
    }
    window.sessionStorage.setItem(
      PENDING_ITEMS_STORAGE_KEY,
      JSON.stringify(durablePending)
    );
  }, [pending]);

  useEffect(() => {
    if (!addMenuOpen) return;
    addMenuClose.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setAddMenuOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      window.setTimeout(() => addMenuTrigger.current?.focus(), 0);
    };
  }, [addMenuOpen]);

  useEffect(() => {
    if (destination === "feed") return;
    const container = wardrobeView.current;
    if (!container) return;
    if (typeof container.scrollTo === "function") {
      container.scrollTo({ top: 0, behavior: "auto" });
      return;
    }
    container.scrollTop = 0;
  }, [destination]);

  const itemsQuery = useQuery({
    queryKey: ["wardrobe-items"],
    queryFn: wardrobeApi.listItems,
    enabled: destination !== "feed",
    refetchIntervalInBackground: true,
    refetchInterval: (query) =>
      pending.length > 0 ||
      query.state.data?.some(
        (item) =>
          item.status === "processing" ||
          item.status === "partial" ||
          item.pixel_image_status === "queued" ||
          item.pixel_image_status === "running"
      )
        ? 1_500
        : false
  });
  const items = itemsQuery.data ?? [];
  const looksQuery = useQuery({
    queryKey: ["wardrobe-looks"],
    queryFn: wardrobeApi.listLooks,
    enabled: destination !== "feed",
    refetchIntervalInBackground: true,
    refetchInterval: (query) =>
      query.state.data?.some(
        (look) => look.status === "processing" || look.status === "partial"
      )
        ? 1_500
        : false
  });
  const looks = looksQuery.data ?? [];
  const lookRenderQueries = useQueries({
    queries: looks.map((look) => ({
      queryKey: ["look-renders", look.id],
      queryFn: () => wardrobeApi.listRenders(look.id),
      enabled:
        destination !== "feed" &&
        (look.status === "ready" || look.status === "partial"),
      refetchInterval: (query: {
        state: { data?: RenderArtifact[] };
      }) =>
        query.state.data?.some(
          (render) => render.status === "queued" || render.status === "running"
        )
          ? 1_500
          : false
    }))
  });
  const pixelCovers = useMemo(
    () =>
      Object.fromEntries(
        looks.flatMap((look, index) => {
          const cover = lookRenderQueries[index]?.data?.find(
            (render) => render.kind === "pixel_cover"
          );
          return cover ? [[look.id, cover] as const] : [];
        })
      ),
    [lookRenderQueries, looks]
  );
  const communityLooks = useMemo<CommunityAvatarSource[]>(
    () =>
      looks.flatMap((look, index) => {
        const cover = pixelCovers[look.id];
        if (cover?.status !== "succeeded" || !cover.output_image_url) return [];
        return [
          {
            lookId: look.id,
            assetUrl: cover.output_image_url,
            label:
              look.source === "feed_saved"
                ? `Feed 穿搭 ${index + 1}`
                : `我的穿搭 ${index + 1}`,
            kind: "public-render-artifact" as const,
            tags: [
              look.source === "feed_saved" ? "Feed 灵感" : "我的搭配",
              "像素封面"
            ]
          }
        ];
      }),
    [looks, pixelCovers]
  );
  const lookQuery = useQuery({
    queryKey: ["wardrobe-look", selectedLookId],
    queryFn: () => wardrobeApi.getLook(selectedLookId!),
    enabled: selectedLookId !== null,
    refetchIntervalInBackground: true,
    refetchInterval: (query) =>
      query.state.data?.look.status === "processing" ||
      query.state.data?.look.status === "partial"
        ? 2_000
        : false
  });
  useEffect(() => {
    if (!selectedLookId || !lookQuery.isError) return;
    setNotice(errorMessage(lookQuery.error));
    setSelectedLookId(null);
  }, [lookQuery.error, lookQuery.isError, selectedLookId]);
  const rendersQuery = useQuery({
    queryKey: ["look-renders", selectedLookId],
    queryFn: () => wardrobeApi.listRenders(selectedLookId!),
    enabled: selectedLookId !== null,
    refetchInterval: (query) =>
      query.state.data?.some(
        (render) => render.status === "queued" || render.status === "running"
      )
        ? 1_500
        : false
  });
  const purchaseDemandsQuery = useQuery({
    queryKey: ["look-purchase-demands", selectedLookId],
    queryFn: () => wardrobeApi.listPurchaseDemands(selectedLookId!),
    enabled: selectedLookId !== null
  });

  useEffect(() => {
    if (!items.length) return;
    const captures = new Set(items.map((item) => item.capture_id));
    setPending((current) =>
      current.filter((entry) => {
        if (!captures.has(entry.captureId)) return true;
        releaseBrowserImagePreview(entry.previewUrl);
        return false;
      })
    );
  }, [items]);

  useEffect(() => {
    const active = pending.filter(
      (entry) => entry.state === "queued" || entry.state === "processing"
    );
    if (!active.length) return;
    const timer = window.setInterval(() => {
      void Promise.all(
        active.map(async (entry) => {
          try {
            const job = await wardrobeApi.getJob(entry.jobId);
            if (job.state === "ready" || job.state === "partial") {
              const [refreshedItems, refreshedLooks] = await Promise.all([
                wardrobeApi.listItems(),
                wardrobeApi.listLooks()
              ]);
              queryClient.setQueryData(["wardrobe-items"], refreshedItems);
              queryClient.setQueryData(["wardrobe-looks"], refreshedLooks);
              if (!refreshedItems.some((item) => item.capture_id === entry.captureId)) {
                return;
              }
              releaseBrowserImagePreview(entry.previewUrl);
              setPending((current) =>
                current.filter((candidate) => candidate.jobId !== entry.jobId)
              );
              return;
            }
            setPending((current) =>
              current.map((candidate) =>
                candidate.jobId === entry.jobId
                  ? {
                      ...candidate,
                      state: job.state,
                      errorCode: job.error_code,
                      errorMessage: job.error_message
                    }
                  : candidate
              )
            );
          } catch (error) {
            if (error instanceof ProductApiError && error.code === "job_not_found") {
              releaseBrowserImagePreview(entry.previewUrl);
              setPending((current) =>
                current.filter((candidate) => candidate.jobId !== entry.jobId)
              );
            }
            // Transient failures keep the local placeholder while the wardrobe query
            // remains the source of truth. A missing job is terminal and is removed.
          }
        })
      );
    }, 1_500);
    return () => window.clearInterval(timer);
  }, [pending, queryClient]);

  const updateMutation = useMutation({
    mutationFn: ({
      itemId,
      changes
    }: {
      itemId: string;
      changes: {
        ownership?: Ownership;
        corrections?: Record<string, string>;
      };
    }) => wardrobeApi.updateItem(itemId, changes),
    onSuccess: (updated) => {
      setSelectedItem(updated);
      setNotice("修改已保存，之后的 AI 更新不会覆盖你的选择");
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
    },
    onError: (error) => setNotice(errorMessage(error))
  });

  const retryMutation = useMutation({
    mutationFn: (item: Item) => wardrobeApi.retryItem(item.id),
    onSuccess: () => {
      setNotice("已经重新开始理解，稍后自动更新");
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
    },
    onError: (error) => setNotice(errorMessage(error))
  });

  const retryPixelMutation = useMutation({
    mutationFn: (item: Item) => wardrobeApi.retryItemPixel(item.id),
    onSuccess: () => {
      setNotice("像素展示图已重新排队，真实单品不受影响");
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
    },
    onError: (error) => setNotice(errorMessage(error))
  });

  const retryPendingMutation = useMutation({
    mutationFn: (jobId: string) => wardrobeApi.retryJob(jobId),
    onSuccess: (job) => {
      setPending((current) =>
        current.map((entry) =>
          entry.jobId === job.job_id
            ? {
                ...entry,
                state: job.state,
                errorCode: null,
                errorMessage: null
              }
            : entry
        )
      );
      setNotice("已经重新开始识别，完成后会自动出现");
    },
    onError: (error) => setNotice(errorMessage(error))
  });

  /**
   * 把组合衣柜里的单品存成一套真实的 Look。
   *
   * 走的是既有的搭配接口：把选中的单品作为必选项交给后端出方案，再保存该方案。
   * 没有为此新增任何端点，也没有在前端凭空拼一个 Look——衣橱资产必须由后端产生。
   */
  /**
   * 把组合衣柜存成一套穿搭，然后按用户点的那个按钮接着做一件事。
   *
   * 两件都只在手动点击后发生：各要跑一次真实模型调用，自动触发等于每放
   * 一件衣服就烧一次额度。
   *
   * 试穿这条不在这里直接生成——它需要一张已上传的照片对象，而形象照存在
   * 本机是 data URL。详情页里已经有一条能正常工作的上传+试穿流程，所以
   * 这里存完就把那套打开，让用户在那里选照片，而不是另造一条半成品。
   */
  async function saveCombo(
    entries: readonly { itemId: string }[],
    intent: "cover" | "try_on" = "cover"
  ) {
    if (entries.length < 2) return;
    try {
      /*
       * 只把选中的这几件交给规划器，其余全部排除。
       *
       * planOutfits 的职责是「补全一整套」，只给 mustInclude 的话它会自作
       * 主张往里塞外套、鞋子、配饰——用户明明没选，存下来却多出几件。
       * 排除掉其余单品之后，补不上的位置会留成空缺（待补齐），而不是被
       * 别的衣服填满。
       */
      const chosen = new Set(entries.map((entry) => entry.itemId));
      const plans = await wardrobeApi.planOutfits({
        scene: "自由组合",
        mustIncludeItemIds: [...chosen],
        excludeItemIds: items
          .map((item) => item.id)
          .filter((id) => !chosen.has(id))
      });
      const plan = plans.plans?.[0];
      if (!plan) {
        setNotice("这套组合暂时没能生成方案，换一件再试");
        return;
      }
      const saved = await wardrobeApi.saveOutfitPlan(plan, crypto.randomUUID());
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-looks"] });

      if (intent === "cover") {
        await wardrobeApi.createRender(
          saved.look_id,
          "pixel_cover",
          crypto.randomUUID()
        );
        setNotice("已存为新的穿搭，效果封面正在生成");
      } else {
        setNotice("已存为新的穿搭，选一张形象照就能试穿");
      }
      setSelectedLookId(saved.look_id);
    } catch (error) {
      setNotice(errorMessage(error));
    }
  }

  function dismissPending(entry: PendingItem) {
    releaseBrowserImagePreview(entry.previewUrl);
    setPending((current) =>
      current.filter((candidate) => candidate.jobId !== entry.jobId)
    );
    setNotice("已从当前列表移除，衣橱里的其他内容不受影响");
  }

  const deleteMutation = useMutation({
    mutationFn: (itemId: string) => wardrobeApi.deleteSource(itemId),
    onSuccess: (_, itemId) => {
      const deletedItem = items.find((item) => item.id === itemId);
      queryClient.setQueryData<Item[]>(["wardrobe-items"], (current) =>
        current?.map((item) =>
          item.id === itemId ? { ...item, source_available: false } : item
        )
      );
      setSelectedItem(null);
      setNotice(
        deletedItem?.display_image_kind === "derived_garment"
          ? "原始上传图已删除，标准化单品图和文字资产仍保留"
          : "原始上传图已删除，文字资产仍保留在衣橱中"
      );
    },
    onError: (error) => setNotice(errorMessage(error))
  });

  const lookReasonMutation = useMutation({
    mutationFn: ({ lookId, reason }: { lookId: string; reason: string }) =>
      wardrobeApi.addLikingReason(lookId, reason, crypto.randomUUID()),
    onSuccess: () => {
      setFeedLikingLookId(null);
      setNotice("喜欢原因已记住，会用于之后的搭配");
      void queryClient.invalidateQueries({
        queryKey: ["wardrobe-look", selectedLookId]
      });
    },
    onError: (error) => setNotice(errorMessage(error))
  });
  const lookRetryMutation = useMutation({
    mutationFn: (lookId: string) => wardrobeApi.retryLook(lookId),
    onSuccess: () => {
      setNotice("已经继续解析，原始穿搭和已有单品都会保留");
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-looks"] });
      void queryClient.invalidateQueries({
        queryKey: ["wardrobe-look", selectedLookId]
      });
    },
    onError: (error) => setNotice(errorMessage(error))
  });
  const renderMutation = useMutation({
    mutationFn: ({
      lookId,
      kind,
      idempotencyKey
    }: {
      lookId: string;
      kind: RenderKind;
      idempotencyKey: string;
    }) => wardrobeApi.createRender(lookId, kind, idempotencyKey),
    onSuccess: (render) => {
      queryClient.setQueryData<RenderArtifact[]>(
        ["look-renders", render.look_id],
        (current = []) => [
          render,
          ...current.filter((candidate) => candidate.id !== render.id)
        ]
      );
    },
    onError: (error) => setNotice(errorMessage(error)),
    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["look-renders", variables.lookId]
      });
    }
  });
  const tryOnMutation = useMutation({
    mutationFn: async ({ lookId, file }: { lookId: string; file: File }) => {
      const subjectObjectKey = await wardrobeApi.uploadPrivateImage(file);
      try {
        return await wardrobeApi.createRender(
          lookId,
          "try_on",
          `personal-try-on:${crypto.randomUUID()}`,
          subjectObjectKey
        );
      } catch (error) {
        await wardrobeApi.discardPrivateUpload(subjectObjectKey).catch(() => undefined);
        throw error;
      }
    },
    onSuccess: (render) => {
      queryClient.setQueryData<RenderArtifact[]>(
        ["look-renders", render.look_id],
        (current = []) => [
          render,
          ...current.filter((candidate) => candidate.id !== render.id)
        ]
      );
      setNotice("全身照已安全上传，真人试穿正在后台生成");
    },
    onError: (error) => setNotice(errorMessage(error)),
    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["look-renders", variables.lookId]
      });
    }
  });
  const deleteTryOnPhotoMutation = useMutation({
    mutationFn: (artifactId: string) =>
      wardrobeApi.deleteTryOnSubject(artifactId),
    onSuccess: () => {
      setNotice("试穿原照已删除，生成结果仍保留");
    },
    onError: (error) => setNotice(errorMessage(error)),
    onSettled: () => {
      if (selectedLookId) {
        void queryClient.invalidateQueries({
          queryKey: ["look-renders", selectedLookId]
        });
      }
    }
  });
  const purchaseDemandMutation = useMutation({
    mutationFn: ({
      demandId,
      status
    }: {
      demandId: string;
      status: PurchaseDemand["status"];
    }) => wardrobeApi.advancePurchaseDemand(demandId, status),
    onSuccess: (updated) => {
      queryClient.setQueryData<PurchaseDemand[]>(
        ["look-purchase-demands", updated.look_id],
        (current = []) =>
          current.map((demand) => (demand.id === updated.id ? updated : demand))
      );
      setNotice(
        updated.status === "purchased_pending"
          ? updated.can_mark_owned
            ? "已记为下单，收到后可确认转为“我的衣服”"
            : "已记为下单，收到后请拍照上传并完成识别入库"
          : "已确认收到，关联单品已转为“我的衣服”"
      );
    },
    onError: (error) => setNotice(errorMessage(error))
  });
  const autoRenderKey = useRef<string | null>(null);
  const autoCollageAttemptedLookIds = useRef(new Set<string>());
  const flatLayAttemptedItemIds = useRef(new Set<string>());

  useEffect(() => {
    const detail = lookQuery.data;
    const collageRenders = (rendersQuery.data ?? []).filter(
      (render) => render.kind === "collage"
    );
    const usableOrInFlightCollage = collageRenders.some(
      (render) =>
        render.status === "queued" ||
        render.status === "running" ||
        ((render.status === "succeeded" || render.status === "degraded") &&
          render.output_image_url !== null)
    );
    if (
      !detail ||
      detail.look.source === "ai_generated" ||
      detail.look.fixed_presentation ||
      !rendersQuery.isSuccess ||
      usableOrInFlightCollage ||
      autoCollageAttemptedLookIds.current.has(detail.look.id) ||
      !detail.components.some((component) => component.item_id !== null) ||
      (detail.look.status !== "ready" && detail.look.status !== "partial")
    ) {
      return;
    }
    const kind: RenderKind = "collage";
    const latestFailedCollage = collageRenders
      .filter(
        (render) =>
          render.status === "failed" ||
          ((render.status === "succeeded" || render.status === "degraded") &&
            render.output_image_url === null)
      )
      .sort((left, right) => right.updated_at.localeCompare(left.updated_at))[0];
    const key = latestFailedCollage
      ? `auto-${kind}-retry:${detail.look.id}:${latestFailedCollage.id}:${latestFailedCollage.updated_at}`
      : `auto-${kind}:${detail.look.id}:${detail.look.updated_at}`;
    if (autoRenderKey.current === key) return;
    autoRenderKey.current = key;
    autoCollageAttemptedLookIds.current.add(detail.look.id);
    renderMutation.mutate({
      lookId: detail.look.id,
      kind,
      idempotencyKey: key
    });
  }, [lookQuery.data, rendersQuery.data, rendersQuery.isSuccess]);

  useEffect(() => {
    const detail = lookQuery.data;
    const collageReady = (rendersQuery.data ?? []).some(
      (render) =>
        render.kind === "collage" &&
        (render.status === "succeeded" || render.status === "degraded") &&
        render.output_image_url
    );
    if (!detail || !collageReady) return;
    const itemIds = [...new Set(
      detail.components
        .map((component) => component.item_id)
        .filter((itemId): itemId is string => itemId !== null)
    )];
    for (const itemId of itemIds) {
      if (flatLayAttemptedItemIds.current.has(itemId)) continue;
      flatLayAttemptedItemIds.current.add(itemId);
      void wardrobeApi.ensureItemFlatLayPresentation(itemId).catch(() => {
        // The detail page keeps the real item display asset when this optional
        // presentation cannot be queued, and its own request permits recovery.
      });
    }
  }, [lookQuery.data, rendersQuery.data]);

  const ensuredPixelLookIds = useRef(new Set<string>());

  useEffect(() => {
    if (renderMutation.isPending) return;
    const candidate = looks.find((look, index) => {
      if (look.status !== "ready" && look.status !== "partial") return false;
      if (look.fixed_presentation) return false;
      const query = lookRenderQueries[index];
      if (!query?.isSuccess || ensuredPixelLookIds.current.has(look.id)) return false;
      return !query.data.some((render) => render.kind === "pixel_cover");
    });
    if (!candidate) return;
    ensuredPixelLookIds.current.add(candidate.id);
    renderMutation.mutate({
      lookId: candidate.id,
      kind: "pixel_cover",
      idempotencyKey: `auto-pixel:${candidate.id}:${candidate.updated_at}`
    });
  }, [lookRenderQueries, looks, renderMutation.isPending]);

  function chooseFile(file: File | undefined, sourceKind: SourceKind) {
    if (!file) return;
    const validationError = validateImage(file);
    if (validationError) {
      setNotice(validationError);
      return;
    }
    setNotice(null);
    setSheetError(null);
    setSelection({
      file,
      sourceKind,
      previewUrl: createBrowserImagePreview(file)
    });
  }

  function cancelSelection() {
    if (selection) releaseBrowserImagePreview(selection.previewUrl);
    setSelection(null);
    setSheetError(null);
  }

  async function confirmSelection(
    ownership: Ownership,
    intent: "item" | "whole_outfit"
  ) {
    if (!selection) return;
    setUploading(true);
    setSheetError(null);
    try {
      const accepted = await wardrobeApi.ingest(
        selection.file,
        selection.sourceKind,
        ownership,
        crypto.randomUUID(),
        intent
      );
      if (accepted.look_id) {
        setWardrobeViewMode("looks");
        releaseBrowserImagePreview(selection.previewUrl);
        setSelection(null);
        setNotice("整套已保存，AI 正在拆解单品并准备像素小人");
        void queryClient.invalidateQueries({ queryKey: ["wardrobe-looks"] });
        void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
        return;
      }
      setPending((current) => [
        {
          captureId: accepted.capture_id,
          jobId: accepted.job_id,
          previewUrl: selection.previewUrl,
          ownership,
          state: accepted.state
        },
        ...current
      ]);
      setWardrobeViewMode("items");
      setSelection(null);
      setNotice("已安全加入，识别会在后台继续");
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
    } catch (error) {
      setSheetError(errorMessage(error));
    } finally {
      setUploading(false);
    }
  }

  function acceptFeedCapture(accepted: CaptureAccepted, file: File) {
    if (accepted.look_id) {
      setWardrobeViewMode("looks");
      setNotice("整套已收藏，AI 正在后台拆成真实单品");
      setFeedLikingLookId(accepted.look_id);
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-looks"] });
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
      return;
    }
    setPending((current) => [
      {
        captureId: accepted.capture_id,
        jobId: accepted.job_id,
        previewUrl: createBrowserImagePreview(file),
        ownership: "inspiration",
        state: accepted.state
      },
      ...current
    ]);
    setWardrobeViewMode("items");
    void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
  }

  return (
    <PhoneFrame>
      <main
        className={`product-shell pixel-shell ${
          destination === "feed"
            ? "product-shell--feed"
            : destination === "world"
              ? "product-shell--world"
              : "product-shell--wardrobe"
        }`}
      >
      <section
        aria-label="像素世界"
        className="product-view product-view--world"
        hidden={destination !== "world"}
      >
        {destination === "world" ? (
          <Suspense
            fallback={
              <div className="pixel-world-loading" role="status">
                <span aria-hidden="true">✦</span>
                <strong>正在打开像素世界</strong>
              </div>
            }
          >
            <CommunityScreen
              avatarSources={communityLooks}
              onExit={() => setDestination("wardrobe")}
            />
          </Suspense>
        ) : null}
      </section>

      <section
        aria-label="穿搭灵感"
        className="product-view product-view--feed feed-standalone"
        hidden={destination !== "feed"}
      >
        <div className="feed-topbar">
          <div className="feed-topbar__brand">
            <span>STYLECAPTURE</span>
            <strong>穿搭灵感</strong>
          </div>
          <button
            type="button"
            className="feed-topbar__mini"
            aria-label="数字衣橱"
            onClick={() => setDestination("wardrobe")}
          >
            进入数字衣橱
          </button>
        </div>
        <FeedScreen
          active={destination === "feed"}
          onAccepted={acceptFeedCapture}
          restoreTarget={feedRestoreTarget}
        />
        {feedLikingLookId ? (
          <aside className="feed-liking-prompt" aria-label="可选补充喜欢原因">
            <strong>顺手记一下喜欢它哪里？</strong>
            <span>可选，不会打断继续刷 Feed</span>
            <div>
              {["配色舒服", "层次感", "氛围感", "显瘦利落"].map((reason) => (
                <button
                  type="button"
                  key={reason}
                  disabled={lookReasonMutation.isPending}
                  onClick={() => lookReasonMutation.mutate({ lookId: feedLikingLookId, reason })}
                >
                  {reason}
                </button>
              ))}
              <button type="button" onClick={() => setFeedLikingLookId(null)}>
                跳过
              </button>
            </div>
          </aside>
        ) : null}
      </section>

      <div
        ref={wardrobeView}
        className="product-view product-view--wardrobe pixel-app"
        hidden={destination === "feed" || destination === "world"}
      >
        {destination !== "feed" ? (
          <header className={`wardrobe-header${destination === "wardrobe" ? " wardrobe-header--home" : ""}`}>
            {destination === "wardrobe" ? (
              <div className="wardrobe-header__intro">
                <h1 id="wardrobe-title" className="pixel-title wardrobe-header__title">
                  我的衣橱
                </h1>
                <p className="subtitle wardrobe-header__summary">
                  收藏喜欢的穿搭，沉淀你的数字衣橱
                </p>
                <p className="wardrobe-header__count">
                  <strong>{looks.length}</strong> 套穿搭
                </p>
              </div>
            ) : (
              <>
                <h1
                  className={`pixel-title wardrobe-header__title${
                    destination === "profile" ? " wardrobe-header__title--profile" : ""
                  }`}
                >
                  {destination === "analysis"
                    ? "穿搭分析"
                    : destination === "ai"
                      ? "AI 推荐"
                      : "我的"}
                </h1>
                <p className="subtitle wardrobe-header__summary">
                  拥有的和喜欢的，<br />
                  都是可搭配的数字资产
                </p>
              </>
            )}
            {/* AI 页的右上角是这次聊天的出口，不是再去刷 Feed——
                正在跟闺蜜聊搭配的人，想回看的是聊过什么。 */}
            {destination === "ai" ? (
              <button
                type="button"
                className="wardrobe-header__feed"
                onClick={() => setAiHistoryOpen(true)}
              >
                对话记录 ›
              </button>
            ) : (
              <button
                type="button"
                className="wardrobe-header__feed"
                aria-label="刷灵感 Feed"
                onClick={() => setDestination("feed")}
              >
                {destination === "wardrobe" ? (
                  <>
                    <span className="wardrobe-header__feed-plus" aria-hidden="true">＋</span>
                    <span>刷灵感</span>
                  </>
                ) : "刷灵感 Feed"}
              </button>
            )}
          </header>
        ) : null}

        {notice ? (
          <div className="notice" role="alert">
            <span>{notice}</span>
            <button
              type="button"
              aria-label="关闭提示"
              onClick={() => setNotice(null)}
            >
              ×
            </button>
          </div>
        ) : null}

        {destination === "wardrobe" ? (
          <Suspense fallback={<DeferredScreenFallback />}>
            <WardrobeScreen
              view={wardrobeViewMode}
              onViewChange={setWardrobeViewMode}
              looks={looks}
              pixelCovers={pixelCovers}
              items={items}
              pending={pending}
              itemsLoading={itemsQuery.isLoading}
              looksLoading={looksQuery.isLoading}
              itemsError={itemsQuery.isError}
              looksError={looksQuery.isError}
              onRetryItems={() => void itemsQuery.refetch()}
              onRetryLooks={() => void looksQuery.refetch()}
              onOpen={setSelectedItem}
              onOpenLook={(look: Look) => setSelectedLookId(look.id)}
              onRetry={(item) => retryMutation.mutate(item)}
              onRetryPixel={(item) => retryPixelMutation.mutate(item)}
              onRetryPending={(entry) => retryPendingMutation.mutate(entry.jobId)}
              onDismissPending={dismissPending}
              onNotice={setNotice}
              onSaveCombo={saveCombo}
            />
          </Suspense>
        ) : null}

        {destination === "analysis" ? (
          <Suspense fallback={<DeferredScreenFallback />}>
            <AnalysisScreen
              items={items}
              looks={looks}
              pixelCovers={pixelCovers}
              onGoAI={() => setDestination("ai")}
              onGoWardrobe={() => setDestination("wardrobe")}
              onOpenLook={(lookId) => setSelectedLookId(lookId)}
            />
          </Suspense>
        ) : null}

        {destination === "ai" ? (
          <Suspense fallback={<DeferredScreenFallback />}>
            <AIRecommendScreen
              historyOpen={aiHistoryOpen}
              onHistoryOpenChange={setAiHistoryOpen}
              onGoWardrobe={() => setDestination("wardrobe")}
              onSavedLook={(result) => {
                const lookId = result.look_id;
                setNotice(
                  result.presentation_state === "queued"
                    ? "穿搭已保存；真实拼贴和像素封面正在后台生成"
                    : result.presentation_state === "pending_retry"
                      ? "穿搭已保存；展示生成排队失败，可进入详情重试"
                      : "穿搭已保存；当前未配置展示生成，可先查看真实单品"
                );
                void queryClient.invalidateQueries({ queryKey: ["wardrobe-looks"] });
                void queryClient.invalidateQueries({
                  queryKey: ["look-renders", lookId]
                });
                if (selectedLookId === lookId) {
                  void queryClient.invalidateQueries({
                    queryKey: ["wardrobe-look", lookId]
                  });
                }
              }}
              onOpenLook={(lookId) => {
                setSelectedLookId(lookId);
                setDestination("wardrobe");
              }}
              presetPrompt={null}
              anchorItemId={aiAnchorItemId}
              onClearAnchor={() => setAiAnchorItemId(null)}
            />
          </Suspense>
        ) : null}

        {destination === "profile" ? (
          <Suspense fallback={<DeferredScreenFallback />}>
            <ProfileScreen
              itemCount={items.length + pending.length}
              onNotice={setNotice}
            />
          </Suspense>
        ) : null}

        <input
          ref={cameraInput}
          className="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
          capture="environment"
          aria-label="拍摄衣物照片"
          onChange={(event) => {
            chooseFile(event.target.files?.[0], "camera");
            event.target.value = "";
          }}
        />
        <input
          ref={galleryInput}
          className="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
          aria-label="选择衣物照片"
          onChange={(event) => {
            chooseFile(event.target.files?.[0], "upload");
            event.target.value = "";
          }}
        />

        <Suspense fallback={null}>
          {selection ? (
            <CaptureSheet
              key={`${selection.file.name}:${selection.file.size}`}
              selection={selection}
              busy={uploading}
              error={sheetError}
              onCancel={cancelSelection}
              onConfirm={(ownership, intent) =>
                void confirmSelection(ownership, intent)
              }
            />
          ) : null}
          {selectedItem ? (
            <ItemDetail
            item={selectedItem}
            saving={updateMutation.isPending}
            onClose={() => setSelectedItem(null)}
            onSave={(itemId, changes) =>
              updateMutation.mutate({ itemId, changes })
            }
            onDeleteSource={(itemId) => deleteMutation.mutate(itemId)}
            onBuildOutfit={(itemId) => {
              setAiAnchorItemId(itemId);
              setSelectedItem(null);
              setDestination("ai");
            }}
            onReturnToFeed={(videoRef, timestampMs) => {
              setSelectedItem(null);
              setFeedRestoreTarget({
                videoRef,
                timestampMs,
                requestId: crypto.randomUUID()
              });
              setDestination("feed");
            }}
          />
          ) : null}
          {selectedLookId ? (
            <LookDetail
              onOpenItem={(action) => {
                const target = action.itemId
                  ? items.find((item) => item.id === action.itemId)
                  : null;
                setLookItemAction({
                  ...action,
                  ownership: target?.ownership ?? action.ownership,
                  purchaseSearchUrl:
                    target?.purchase_search_url ?? action.purchaseSearchUrl
                });
              }}
              detail={lookQuery.data ?? null}
              loading={lookQuery.isLoading}
              renders={rendersQuery.data ?? []}
              rendersLoading={rendersQuery.isLoading}
              purchaseDemands={purchaseDemandsQuery.data ?? []}
              purchaseDemandsLoading={purchaseDemandsQuery.isLoading}
              updatingPurchaseDemandId={
                purchaseDemandMutation.isPending
                  ? purchaseDemandMutation.variables.demandId
                  : null
              }
              generatingKind={
                tryOnMutation.isPending
                  ? "try_on"
                  : renderMutation.isPending
                    ? renderMutation.variables.kind
                    : null
              }
              tryOnUploading={tryOnMutation.isPending}
              deletingTryOnPhoto={deleteTryOnPhotoMutation.isPending}
              deletingSource={false}
              retrying={lookRetryMutation.isPending}
              saving={lookReasonMutation.isPending}
              onClose={() => {
                setLookItemAction(null);
                setSelectedLookId(null);
              }}
              onReturnToSource={(videoRef, timestampMs) => {
                setSelectedLookId(null);
                setFeedRestoreTarget({
                  videoRef,
                  timestampMs,
                  requestId: crypto.randomUUID()
                });
                setDestination("feed");
              }}
              onRetry={(lookId) => lookRetryMutation.mutate(lookId)}
              onSaveReason={(lookId, reason) =>
                lookReasonMutation.mutate({ lookId, reason })
              }
              onGenerate={(lookId, kind) =>
                renderMutation.mutate({
                  lookId,
                  kind,
                  idempotencyKey: `manual-${kind}:${crypto.randomUUID()}`
                })
              }
              onTryOn={(lookId, file) =>
                tryOnMutation.mutate({ lookId, file })
              }
              onDeleteTryOnPhoto={(artifactId) =>
                deleteTryOnPhotoMutation.mutate(artifactId)
              }
              onAdvancePurchaseDemand={(demandId, status) =>
                purchaseDemandMutation.mutate({ demandId, status })
              }
            />
          ) : null}
          <LookItemActionSheet
            action={lookItemAction}
            onClose={() => setLookItemAction(null)}
            onBuildOutfit={(itemId) => {
              setAiAnchorItemId(itemId);
              setLookItemAction(null);
              setSelectedLookId(null);
              setDestination("ai");
            }}
            onCheckCompatibility={(itemId) => {
              setAiAnchorItemId(itemId);
              setLookItemAction(null);
              setSelectedLookId(null);
              setDestination("ai");
            }}
          />
        </Suspense>
      </div>

      {destination !== "feed" && destination !== "world" ? (
      <nav aria-label="主要功能" className="pixel-nav">
        <button
          aria-current={destination === "wardrobe" ? "page" : undefined}
          className={destination === "wardrobe" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("wardrobe")}
        >
          <NavIcon name="wardrobe" />
          <small>衣橱</small>
          {pending.length > 0 ? (
            <b aria-label={`${pending.length} 个处理中`}>
              {Math.min(pending.length, 9)}
            </b>
          ) : null}
        </button>
        <button
          aria-current={destination === "analysis" ? "page" : undefined}
          className={destination === "analysis" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("analysis")}
        >
          <NavIcon name="analysis" />
          <small>分析</small>
        </button>
        <button
          ref={addMenuTrigger}
          className="pixel-nav__add"
          type="button"
          aria-label="添加衣服或试试像素形象"
          onClick={() => setAddMenuOpen(true)}
        >
          <span className="nav-icon" aria-hidden="true">＋</span>
        </button>
        <button
          aria-current={destination === "ai" ? "page" : undefined}
          className={destination === "ai" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("ai")}
        >
          <NavIcon name="ai" />
          <small>AI</small>
        </button>
        <button
          type="button"
          onClick={() => setDestination("world")}
        >
          <NavIcon name="world" />
          <small>像素世界</small>
        </button>
        <button
          aria-current={destination === "profile" ? "page" : undefined}
          className={destination === "profile" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("profile")}
        >
          <NavIcon name="profile" />
          <small>我的</small>
        </button>
      </nav>
      ) : null}

      {addMenuOpen ? (
        <div
          className="pixel-add-sheet"
          role="dialog"
          aria-modal="true"
          aria-label="添加到 StyleCapture"
        >
          <button
            type="button"
            className="pixel-add-sheet__backdrop"
            aria-label="关闭添加菜单"
            onClick={() => setAddMenuOpen(false)}
          />
          <section className="pixel-add-sheet__panel">
            <header>
              <div>
                <p className="pixel-label">快速入口</p>
                <h2 className="pixel-title">今天想怎么玩？</h2>
              </div>
              <button
                ref={addMenuClose}
                type="button"
                aria-label="关闭"
                onClick={() => setAddMenuOpen(false)}
              >
                ×
              </button>
            </header>
            <button
              type="button"
              onClick={() => {
                setAddMenuOpen(false);
                cameraInput.current?.click();
              }}
            >
              <span aria-hidden="true">◉</span>
              <strong>拍下真实衣服</strong>
              <small>识别单品或整套，确认后入库</small>
            </button>
            <button
              type="button"
              onClick={() => {
                setAddMenuOpen(false);
                galleryInput.current?.click();
              }}
            >
              <span aria-hidden="true">✦</span>
              <strong>从相册导入</strong>
              <small>支持实物图、穿搭照和收藏图片</small>
            </button>
            <button
              type="button"
              onClick={() => {
                setAddMenuOpen(false);
                setDestination("profile");
                setNotice("在“我的”里上传全身照，生成不入库的像素形象");
              }}
            >
              <span aria-hidden="true">👾</span>
              <strong>试试像素形象</strong>
              <small>只生成展示，不加入数字衣橱</small>
            </button>
          </section>
        </div>
      ) : null}
      </main>
    </PhoneFrame>
  );
}
