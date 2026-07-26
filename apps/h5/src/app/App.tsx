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
import { CaptureSheet } from "../features/capture/CaptureSheet";
import { PhoneFrame } from "../components/PhoneFrame";
import { AIRecommendScreen } from "../features/ai/AIRecommendScreen";
import { AnalysisScreen } from "../features/analysis/AnalysisScreen";
import type { CommunityAvatarSource } from "../features/community/CommunityScreen";
import { FeedScreen } from "../features/feed/FeedScreen";
import { ProfileScreen } from "../features/profile/ProfileScreen";
import { ItemDetail } from "../features/wardrobe/ItemDetail";
import { LookDetail } from "../features/wardrobe/LookDetail";
import type { PendingItem } from "../features/wardrobe/ItemCard";
import { WardrobeScreen } from "../features/wardrobe/WardrobeScreen";
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

export function App() {
  const queryClient = useQueryClient();
  const cameraInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);
  const addMenuTrigger = useRef<HTMLButtonElement>(null);
  const addMenuClose = useRef<HTMLButtonElement>(null);
  const wardrobeView = useRef<HTMLDivElement>(null);
  const restoredLookId = useRef(restoreSelectedLookId());
  const [destination, setDestination] = useState<Destination>(() =>
    restoredLookId.current ? "wardrobe" : "feed"
  );
  const [feedRestoreTarget, setFeedRestoreTarget] =
    useState<FeedRestoreTarget | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pending, setPending] = useState<PendingItem[]>(restorePendingItems);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
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
      enabled: look.status === "ready" || look.status === "partial",
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
        ownership: Ownership;
        corrections: Record<string, string>;
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

  useEffect(() => {
    const detail = lookQuery.data;
    if (
      !detail ||
      detail.look.source === "ai_generated" ||
      detail.look.source === "user_created" ||
      !detail.components.some((component) => component.item_id !== null) ||
      (detail.look.status !== "ready" && detail.look.status !== "partial")
    ) {
      return;
    }
    const kind: RenderKind = "collage";
    const key = `auto-${kind}:${detail.look.id}:${detail.look.updated_at}`;
    if (autoRenderKey.current === key) return;
    autoRenderKey.current = key;
    renderMutation.mutate({
      lookId: detail.look.id,
      kind,
      idempotencyKey: key
    });
  }, [lookQuery.data]);

  const ensuredPixelLookIds = useRef(new Set<string>());

  useEffect(() => {
    if (renderMutation.isPending) return;
    const candidate = looks.find((look, index) => {
      if (look.status !== "ready" && look.status !== "partial") return false;
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
          <header className="wardrobe-header">
            <div>
              <p className="pixel-label">STYLECAPTURE</p>
              <h1 className="pixel-title">
                {destination === "wardrobe"
                  ? "我的衣橱"
                  : destination === "analysis"
                    ? "穿搭分析"
                    : destination === "ai"
                      ? "AI 推荐"
                      : "我的"}
              </h1>
              <p className="subtitle">把拥有和喜欢的，都变成可搭配的数字资产。</p>
            </div>
            <div className="avatar-orbit">
              <img src="/assets/char-default.png" alt="我的 StyleCapture 形象" />
              <span aria-hidden="true">✦</span>
            </div>
            <button
              type="button"
              className="wardrobe-header__feed"
              onClick={() => setDestination("feed")}
            >
              刷灵感 Feed
            </button>
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
          <div>
            <section className="capture-panel" aria-labelledby="capture-title">
              <div className="capture-panel__heading">
                <div>
                  <p className="section-kicker">新增单品</p>
                  <h2 id="capture-title">今天想存哪一件？</h2>
                </div>
                <span className="capture-panel__sparkle" aria-hidden="true">
                  ✦
                </span>
              </div>
              <div className="capture-actions">
                <button
                  className="capture-button capture-button--primary"
                  type="button"
                  aria-label="拍一件"
                  onClick={() => cameraInput.current?.click()}
                >
                  <span className="capture-button__icon" aria-hidden="true">
                    ◉
                  </span>
                  <span>
                    <strong>拍一件</strong>
                    <small>记录衣柜里的真实衣服</small>
                  </span>
                </button>
                <button
                  className="capture-button capture-button--secondary"
                  type="button"
                  aria-label="从相册选"
                  onClick={() => galleryInput.current?.click()}
                >
                  <span className="capture-button__icon" aria-hidden="true">
                    ✦
                  </span>
                  <span>
                    <strong>从相册选</strong>
                    <small>导入单品或穿搭灵感</small>
                  </span>
                </button>
              </div>
            </section>

            <WardrobeScreen
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
            />
          </div>
        ) : null}

        {destination === "analysis" ? (
          <AnalysisScreen
            items={items}
            looks={looks}
            pixelCovers={pixelCovers}
            onGoAI={() => setDestination("ai")}
            onGoWardrobe={() => setDestination("wardrobe")}
            onOpenLook={(lookId) => setSelectedLookId(lookId)}
          />
        ) : null}

        {destination === "ai" ? (
          <AIRecommendScreen
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
              void queryClient.invalidateQueries({ queryKey: ["look-renders", lookId] });
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
        ) : null}

        <div hidden={destination !== "profile"}>
          <ProfileScreen
            itemCount={items.length + pending.length}
            outfitCount={looks.length}
            onNotice={setNotice}
          />
        </div>

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

        <CaptureSheet
          key={selection ? `${selection.file.name}:${selection.file.size}` : "closed"}
          selection={selection}
          busy={uploading}
          error={sheetError}
          onCancel={cancelSelection}
          onConfirm={(ownership, intent) =>
            void confirmSelection(ownership, intent)
          }
        />
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
        <LookDetail
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
          onClose={() => setSelectedLookId(null)}
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
      </div>

      {destination !== "feed" && destination !== "world" ? (
      <nav aria-label="主要功能" className="pixel-nav">
        <button
          aria-current={destination === "wardrobe" ? "page" : undefined}
          className={destination === "wardrobe" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("wardrobe")}
        >
          <span className="nav-icon" aria-hidden="true">✦</span>
          <small>数字衣橱</small>
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
          <span className="nav-icon" aria-hidden="true">◈</span>
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
          <small>添加</small>
        </button>
        <button
          aria-current={destination === "ai" ? "page" : undefined}
          className={destination === "ai" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("ai")}
        >
          <span className="nav-icon" aria-hidden="true">◇</span>
          <small>AI</small>
        </button>
        <button
          type="button"
          onClick={() => setDestination("world")}
        >
          <span className="nav-icon" aria-hidden="true">▦</span>
          <small>像素世界</small>
        </button>
        <button
          aria-current={destination === "profile" ? "page" : undefined}
          className={destination === "profile" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("profile")}
        >
          <span className="nav-icon" aria-hidden="true">☻</span>
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
