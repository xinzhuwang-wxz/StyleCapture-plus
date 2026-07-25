import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient
} from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  type CaptureAccepted,
  type Item,
  type Look,
  type Ownership,
  type RenderArtifact,
  type RenderKind,
  type SourceKind,
  ProductApiError,
  validateImage,
  wardrobeApi
} from "../api/client";
import { CaptureSheet } from "../features/capture/CaptureSheet";
import { AIRecommendScreen } from "../features/ai/AIRecommendScreen";
import { AnalysisScreen } from "../features/analysis/AnalysisScreen";
import { FeedScreen } from "../features/feed/FeedScreen";
import { ProfileScreen } from "../features/profile/ProfileScreen";
import { ItemDetail } from "../features/wardrobe/ItemDetail";
import { LookDetail } from "../features/wardrobe/LookDetail";
import type { PendingItem } from "../features/wardrobe/ItemCard";
import { WardrobeScreen } from "../features/wardrobe/WardrobeScreen";
import "./styles.css";
import "./pixel-theme.css";

type Selection = {
  file: File;
  previewUrl: string;
  sourceKind: SourceKind;
};

type Destination = "feed" | "wardrobe" | "analysis" | "ai" | "profile";
type FeedRestoreTarget = {
  videoRef: string;
  timestampMs: number;
  requestId: string;
};

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
  const [destination, setDestination] = useState<Destination>("feed");
  const [feedRestoreTarget, setFeedRestoreTarget] =
    useState<FeedRestoreTarget | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [selectedLookId, setSelectedLookId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const itemsQuery = useQuery({
    queryKey: ["wardrobe-items"],
    queryFn: wardrobeApi.listItems,
    refetchInterval: 2_000
  });
  const items = itemsQuery.data ?? [];
  const looksQuery = useQuery({
    queryKey: ["wardrobe-looks"],
    queryFn: wardrobeApi.listLooks,
    refetchInterval: 2_000
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
  const pixelCovers = Object.fromEntries(
    looks.flatMap((look, index) => {
      const cover = lookRenderQueries[index]?.data?.find(
        (render) =>
          render.kind === "pixel_cover" &&
          render.status === "succeeded" &&
          render.share_eligible &&
          render.output_image_url !== null
      );
      return cover ? [[look.id, cover] as const] : [];
    })
  );
  const lookQuery = useQuery({
    queryKey: ["wardrobe-look", selectedLookId],
    queryFn: () => wardrobeApi.getLook(selectedLookId!),
    enabled: selectedLookId !== null,
    refetchInterval: (query) =>
      query.state.data?.look.status === "processing" ||
      query.state.data?.look.status === "partial"
        ? 2_000
        : false
  });
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

  useEffect(() => {
    if (!items.length) return;
    const captures = new Set(items.map((item) => item.capture_id));
    setPending((current) =>
      current.filter((entry) => {
        if (!captures.has(entry.captureId)) return true;
        URL.revokeObjectURL(entry.previewUrl);
        return false;
      })
    );
  }, [items]);

  useEffect(() => {
    if (!pending.length) return;
    const timer = window.setInterval(() => {
      void Promise.all(
        pending.map(async (entry) => {
          try {
            const job = await wardrobeApi.getJob(entry.jobId);
            setPending((current) =>
              current.map((candidate) =>
                candidate.jobId === entry.jobId
                  ? { ...candidate, state: job.state }
                  : candidate
              )
            );
          } catch {
            // The wardrobe query remains the source of truth if a status refresh is interrupted.
          }
        })
      );
    }, 1_500);
    return () => window.clearInterval(timer);
  }, [pending]);

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

  const deleteMutation = useMutation({
    mutationFn: (itemId: string) => wardrobeApi.deleteSource(itemId),
    onSuccess: (_, itemId) => {
      queryClient.setQueryData<Item[]>(["wardrobe-items"], (current) =>
        current?.map((item) =>
          item.id === itemId ? { ...item, source_available: false } : item
        )
      );
      setSelectedItem(null);
      setNotice("原图已删除，文字资产仍保留在衣橱中");
    },
    onError: (error) => setNotice(errorMessage(error))
  });

  const lookReasonMutation = useMutation({
    mutationFn: ({ lookId, reason }: { lookId: string; reason: string }) =>
      wardrobeApi.addLikingReason(lookId, reason, crypto.randomUUID()),
    onSuccess: () => {
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
  const autoRenderKey = useRef<string | null>(null);

  useEffect(() => {
    const detail = lookQuery.data;
    if (
      !detail ||
      !detail.components.some((component) => component.item_id !== null) ||
      (detail.look.status !== "ready" && detail.look.status !== "partial")
    ) {
      return;
    }
    const key = `auto-collage:${detail.look.id}:${detail.look.updated_at}`;
    if (autoRenderKey.current === key) return;
    autoRenderKey.current = key;
    renderMutation.mutate({
      lookId: detail.look.id,
      kind: "collage",
      idempotencyKey: key
    });
  }, [lookQuery.data]);

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
      previewUrl: URL.createObjectURL(file)
    });
  }

  function cancelSelection() {
    if (selection) URL.revokeObjectURL(selection.previewUrl);
    setSelection(null);
    setSheetError(null);
  }

  async function confirmSelection(ownership: Ownership) {
    if (!selection) return;
    setUploading(true);
    setSheetError(null);
    try {
      const accepted = await wardrobeApi.ingest(
        selection.file,
        selection.sourceKind,
        ownership,
        crypto.randomUUID()
      );
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
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-looks"] });
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
      return;
    }
    setPending((current) => [
      {
        captureId: accepted.capture_id,
        jobId: accepted.job_id,
        previewUrl: URL.createObjectURL(file),
        ownership: "inspiration",
        state: accepted.state
      },
      ...current
    ]);
    void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
  }

  return (
    <main
      className={`product-shell pixel-shell ${
        destination === "feed" ? "product-shell--feed" : "product-shell--wardrobe"
      }`}
    >
      <section
        aria-label="穿搭灵感"
        className="product-view product-view--feed"
        hidden={destination !== "feed"}
      >
        <FeedScreen
          active={destination === "feed"}
          onAccepted={acceptFeedCapture}
          restoreTarget={feedRestoreTarget}
        />
      </section>

      <div
        className="product-view product-view--wardrobe pixel-app"
        hidden={destination === "feed"}
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
            </section>

            <WardrobeScreen
              looks={looks}
              pixelCovers={pixelCovers}
              items={items}
              pending={pending}
              itemsLoading={itemsQuery.isLoading}
              looksLoading={looksQuery.isLoading}
              onOpen={setSelectedItem}
              onOpenLook={(look: Look) => setSelectedLookId(look.id)}
              onRetry={(item) => retryMutation.mutate(item)}
            />
          </div>
        ) : null}

        {destination === "analysis" ? (
          <AnalysisScreen
            items={items}
            looks={looks}
            onGoAI={() => setDestination("ai")}
            onGoWardrobe={() => setDestination("wardrobe")}
            onOpenLook={(lookId) => setSelectedLookId(lookId)}
          />
        ) : null}

        {destination === "ai" ? (
          <AIRecommendScreen
            onGoWardrobe={() => setDestination("wardrobe")}
            presetPrompt={null}
          />
        ) : null}

        {destination === "profile" ? (
          <ProfileScreen itemCount={items.length + pending.length} outfitCount={looks.length} />
        ) : null}

        <CaptureSheet
          key={selection?.previewUrl ?? "closed"}
          selection={selection}
          busy={uploading}
          error={sheetError}
          onCancel={cancelSelection}
          onConfirm={(ownership) => void confirmSelection(ownership)}
        />
        <ItemDetail
          item={selectedItem}
          saving={updateMutation.isPending}
          onClose={() => setSelectedItem(null)}
          onSave={(itemId, changes) =>
            updateMutation.mutate({ itemId, changes })
          }
          onDeleteSource={(itemId) => deleteMutation.mutate(itemId)}
        />
        <LookDetail
          detail={lookQuery.data ?? null}
          loading={lookQuery.isLoading}
          renders={rendersQuery.data ?? []}
          rendersLoading={rendersQuery.isLoading}
          generatingKind={
            renderMutation.isPending ? renderMutation.variables.kind : null
          }
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
        />
      </div>

      <nav aria-label="主要功能" className="pixel-nav">
        <button
          aria-current={destination === "feed" ? "page" : undefined}
          className={destination === "feed" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("feed")}
        >
          <span className="nav-icon" aria-hidden="true">⌁</span>
          <small>逛灵感</small>
        </button>
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
          aria-current={destination === "ai" ? "page" : undefined}
          className={destination === "ai" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("ai")}
        >
          <span className="nav-icon" aria-hidden="true">◇</span>
          <small>AI</small>
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
    </main>
  );
}
