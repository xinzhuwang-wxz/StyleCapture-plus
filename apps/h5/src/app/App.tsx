import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { CaptureSheet } from "../features/capture/CaptureSheet";
import { FeedScreen } from "../features/feed/FeedScreen";
import { ItemDetail } from "../features/wardrobe/ItemDetail";
import { WardrobeScreen } from "../features/wardrobe/WardrobeScreen";
import { AIRecommendScreen } from "../features/ai/AIRecommendScreen";
import { AnalysisScreen } from "../features/analysis/AnalysisScreen";
import { ProfileScreen } from "../features/profile/ProfileScreen";
import { OutfitDetailScreen } from "../features/outfit/OutfitDetailScreen";
import { PixelToast } from "../components/PixelUI";
import { mockApi } from "../mock/mockApi";

import {
  type CaptureAccepted,
  type Item,
  type Ownership,
  type SourceKind,
  ProductApiError,
  validateImage,
  wardrobeApi
} from "../api/client";
import type { PendingItem } from "../features/wardrobe/WardrobeScreen";

import "./styles.css";
import "./pixel-theme.css";

// ─── Config ────────────────────────────────────────────

const USE_MOCK = true;

const api = USE_MOCK ? mockApi : wardrobeApi;

// ─── Types ─────────────────────────────────────────────

/** 应用模式：feed = 抖音式 Feed 流入口；mini = 小程序 */
type Mode = "feed" | "mini";

type Tab = "wardrobe" | "ai" | "analysis" | "profile";

type Page =
  | { type: "tab"; tab: Tab }
  | { type: "outfit"; outfitId: string; from: Tab };

type Selection = {
  file: File;
  previewUrl: string;
  sourceKind: SourceKind;
};

// ─── Helpers ───────────────────────────────────────────

function errorMessage(error: unknown): string {
  if (error instanceof ProductApiError || error instanceof Error) {
    return error.message;
  }
  return "刚刚没有完成，请稍后再试";
}

// ─── App ───────────────────────────────────────────────

export function App() {
  const queryClient = useQueryClient();
  const cameraInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);

  const [mode, setMode] = useState<Mode>("feed");
  const [page, setPage] = useState<Page>({ type: "tab", tab: "wardrobe" });
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [aiPreset, setAiPreset] = useState<string | null>(null);

  const currentTab = page.type === "tab" ? page.tab : null;

  // ─── Data Queries ────────────────────────────────────

  const itemsQuery = useQuery({
    queryKey: ["wardrobe-items"],
    queryFn: api.listItems,
    refetchInterval: 2_000
  });
  const items = itemsQuery.data ?? [];

  const outfitsQuery = useQuery({
    queryKey: ["wardrobe-outfits"],
    queryFn: mockApi.listWardrobeOutfits,
    refetchInterval: 2_000
  });
  const outfits = outfitsQuery.data ?? [];

  // ─── Effects ─────────────────────────────────────────

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
            const job = await api.getJob(entry.jobId);
            setPending((current) =>
              current.map((candidate) =>
                candidate.jobId === entry.jobId
                  ? { ...candidate, state: job.state }
                  : candidate
              )
            );
          } catch {
            // Silent
          }
        })
      );
    }, 1_500);
    return () => window.clearInterval(timer);
  }, [pending]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 2_400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  // ─── Mutations ───────────────────────────────────────

  const updateMutation = useMutation({
    mutationFn: ({
      itemId,
      changes
    }: {
      itemId: string;
      changes: { ownership?: Ownership; corrections?: Record<string, string> };
    }) => api.updateItem(itemId, changes),
    onSuccess: (updated) => {
      setSelectedItem(updated);
      setNotice("修改已保存 ✓");
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
    },
    onError: (err) => setNotice(errorMessage(err))
  });

  const retryMutation = useMutation({
    mutationFn: (item: Item) => api.retryItem(item.id),
    onSuccess: () => {
      setNotice("已重新开始识别 🔄");
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
    },
    onError: (err) => setNotice(errorMessage(err))
  });

  // ─── Navigation ──────────────────────────────────────

  const navigateTo = useCallback((newPage: Page) => {
    setPage(newPage);
    window.scrollTo(0, 0);
  }, []);

  const goToTab = useCallback(
    (tab: Tab) => navigateTo({ type: "tab", tab }),
    [navigateTo]
  );

  const openOutfit = useCallback(
    (outfitId: string, from: Tab = "wardrobe") =>
      navigateTo({ type: "outfit", outfitId, from }),
    [navigateTo]
  );

  const enterMini = useCallback(() => {
    setMode("mini");
    goToTab("wardrobe");
    window.scrollTo(0, 0);
  }, [goToTab]);

  const backToFeed = useCallback(() => {
    setMode("feed");
    window.scrollTo(0, 0);
  }, []);

  /** Feed 单品标签 → 小程序 AI 推荐 */
  const viewAIFromFeed = useCallback(
    (tagLabel: string) => {
      setMode("mini");
      setAiPreset(`我在视频里圈到了「${tagLabel}」，帮我搭三套`);
      goToTab("ai");
    },
    [goToTab]
  );

  // ─── Capture（相册 / 拍照入库）────────────────────────

  const chooseFile = useCallback((file: File | undefined, sourceKind: SourceKind) => {
    if (!file) return;
    const validationError = validateImage(file);
    if (validationError) {
      setNotice(validationError);
      return;
    }
    setNotice(null);
    setSheetError(null);
    setSelection({ file, sourceKind, previewUrl: URL.createObjectURL(file) });
  }, []);

  const cancelSelection = useCallback(() => {
    if (selection) URL.revokeObjectURL(selection.previewUrl);
    setSelection(null);
    setSheetError(null);
  }, [selection]);

  const confirmSelection = useCallback(
    async (ownership: Ownership) => {
      if (!selection) return;
      setUploading(true);
      setSheetError(null);
      try {
        const accepted = await api.ingest(
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
        setNotice("已安全加入衣橱 ⭐");
        void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
      } catch (err) {
        setSheetError(errorMessage(err));
      } finally {
        setUploading(false);
      }
    },
    [selection, queryClient]
  );

  const acceptFeedCapture = useCallback(
    (accepted: CaptureAccepted, file: File) => {
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
    },
    [queryClient]
  );

  // ─── Feed 模式（独立入口，不是小程序的一个 Tab）─────────

  if (mode === "feed") {
    return (
      <main className="pixel-shell" style={{ background: "#050507" }}>
        <FeedScreen
          active
          api={api}
          onAccepted={acceptFeedCapture}
          onEnterMini={enterMini}
          onViewAI={viewAIFromFeed}
        />
        {notice ? <PixelToast message={notice} /> : null}
      </main>
    );
  }

  // ─── 小程序模式 ───────────────────────────────────────

  const renderTab = () => {
    if (page.type === "outfit") {
      return (
        <OutfitDetailScreen
          outfitId={page.outfitId}
          onBack={() => goToTab(page.from)}
        />
      );
    }

    switch (page.tab) {
      case "wardrobe":
        return (
          <>
            <header
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "var(--px-3)",
                marginBottom: "var(--px-4)"
              }}
            >
              <div>
                <p className="pixel-label">STYLECAPTURE</p>
                <h1 className="pixel-title" style={{ margin: 0 }}>
                  数字衣橱
                </h1>
              </div>
              <button
                type="button"
                className="pixel-tag"
                onClick={backToFeed}
                aria-label="回到穿搭 Feed"
              >
                📺 刷 Feed
              </button>
            </header>

            {/* 拍一件 / 从相册选 */}
            <section
              style={{
                padding: "var(--px-4)",
                background: "var(--pixel-surface)",
                border: "2px solid var(--pixel-border)",
                borderRadius: "var(--pixel-border-radius)",
                boxShadow: "var(--pixel-shadow)",
                marginBottom: "var(--px-5)"
              }}
            >
              <p className="pixel-label" style={{ marginBottom: "var(--px-3)" }}>
                新增单品
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--px-3)" }}>
                <button
                  type="button"
                  className="pixel-button pixel-button--primary"
                  onClick={() => cameraInput.current?.click()}
                >
                  📷 拍一件
                </button>
                <button
                  type="button"
                  className="pixel-button pixel-button--pink"
                  onClick={() => galleryInput.current?.click()}
                >
                  🖼️ 从相册选
                </button>
              </div>
            </section>

            <input
              ref={cameraInput}
              className="visually-hidden"
              type="file"
              aria-label="拍摄衣物照片"
              accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
              capture="environment"
              onChange={(event) => {
                chooseFile(event.target.files?.[0], "camera");
                event.target.value = "";
              }}
            />
            <input
              ref={galleryInput}
              className="visually-hidden"
              type="file"
              aria-label="选择衣物照片"
              accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
              onChange={(event) => {
                chooseFile(event.target.files?.[0], "upload");
                event.target.value = "";
              }}
            />

            <WardrobeScreen
              items={items}
              pending={pending}
              loading={itemsQuery.isLoading}
              outfits={outfits}
              onOpenItem={setSelectedItem}
              onOpenOutfit={(id) => openOutfit(id, "wardrobe")}
              onRetry={(item) => retryMutation.mutate(item)}
            />
          </>
        );
      case "ai":
        return (
          <AIRecommendScreen
            presetPrompt={aiPreset}
            onOutfitClick={(id) => openOutfit(id, "ai")}
          />
        );
      case "analysis":
        return (
          <AnalysisScreen
            items={items}
            outfits={outfits}
            onGoAI={() => goToTab("ai")}
            onGoWardrobe={() => goToTab("wardrobe")}
            onOpenOutfit={(id) => openOutfit(id, "analysis")}
          />
        );
      case "profile":
        return <ProfileScreen itemCount={items.length} outfitCount={outfits.length} />;
      default:
        return null;
    }
  };

  return (
    <main className="pixel-shell">
      <div className="pixel-app">{renderTab()}</div>

      {page.type === "tab" ? (
        <nav aria-label="主要功能" className="pixel-nav">
          <button
            aria-current={currentTab === "wardrobe" ? "page" : undefined}
            className={currentTab === "wardrobe" ? "is-active" : ""}
            type="button"
            onClick={() => goToTab("wardrobe")}
          >
            <span className="nav-icon">👕</span>
            <small>数字衣橱</small>
            {pending.length > 0 ? (
              <b
                aria-label={`${pending.length} 个处理中`}
                style={{
                  position: "absolute",
                  top: "0",
                  right: "6px",
                  background: "var(--pixel-pink)",
                  color: "#fff",
                  fontSize: "0.55rem",
                  padding: "1px 5px",
                  borderRadius: "999px"
                }}
              >
                {Math.min(pending.length, 9)}
              </b>
            ) : null}
          </button>
          <button
            aria-current={currentTab === "ai" ? "page" : undefined}
            className={currentTab === "ai" ? "is-active" : ""}
            type="button"
            onClick={() => {
              setAiPreset(null);
              goToTab("ai");
            }}
          >
            <span className="nav-icon">🤖</span>
            <small>AI推荐</small>
          </button>
          <button
            aria-current={currentTab === "analysis" ? "page" : undefined}
            className={currentTab === "analysis" ? "is-active" : ""}
            type="button"
            onClick={() => goToTab("analysis")}
          >
            <span className="nav-icon">📊</span>
            <small>穿搭分析</small>
          </button>
          <button
            aria-current={currentTab === "profile" ? "page" : undefined}
            className={currentTab === "profile" ? "is-active" : ""}
            type="button"
            onClick={() => goToTab("profile")}
          >
            <span className="nav-icon">👤</span>
            <small>我的</small>
          </button>
        </nav>
      ) : null}

      {notice ? <PixelToast message={notice} /> : null}

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
        onSave={(itemId, changes) => updateMutation.mutate({ itemId, changes })}
        onOpenOutfit={(id) => {
          setSelectedItem(null);
          openOutfit(id, "wardrobe");
        }}
      />
    </main>
  );
}
