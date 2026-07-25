import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { CaptureSheet } from "../features/capture/CaptureSheet";
import { FeedScreen } from "../features/feed/FeedScreen";
import { ItemDetail } from "../features/wardrobe/ItemDetail";
import { WardrobeScreen } from "../features/wardrobe/WardrobeScreen";
import { AIRecommendScreen } from "../features/ai/AIRecommendScreen";
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

type Tab = "feed" | "wardrobe" | "ai" | "profile";

type Page =
  | { type: "tab"; tab: Tab }
  | { type: "outfit"; outfitId: string };

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

  const [page, setPage] = useState<Page>({ type: "tab", tab: "wardrobe" });
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const currentTab = page.type === "tab" ? page.tab : null;

  // ─── Data Queries ────────────────────────────────────

  const itemsQuery = useQuery({
    queryKey: ["wardrobe-items"],
    queryFn: api.listItems,
    refetchInterval: 2_000
  });
  const items = itemsQuery.data ?? [];

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

  // ─── Mutations ───────────────────────────────────────

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

  const deleteMutation = useMutation({
    mutationFn: (itemId: string) => api.deleteSource(itemId),
    onSuccess: (_, itemId) => {
      queryClient.setQueryData<Item[]>(["wardrobe-items"], (current) =>
        current?.map((item) =>
          item.id === itemId ? { ...item, source_available: false } : item
        )
      );
      setSelectedItem(null);
      setNotice("原图已删除 🗑️");
    },
    onError: (err) => setNotice(errorMessage(err))
  });

  // ─── Actions ─────────────────────────────────────────

  const navigateTo = useCallback((newPage: Page) => {
    setPage(newPage);
    window.scrollTo(0, 0);
  }, []);

  const goToTab = useCallback(
    (tab: Tab) => navigateTo({ type: "tab", tab }),
    [navigateTo]
  );

  const chooseFile = useCallback(
    (file: File | undefined, sourceKind: SourceKind) => {
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
    },
    []
  );

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

  // ─── Render Content ──────────────────────────────────

  const renderContent = () => {
    switch (page.type) {
      case "tab":
        switch (page.tab) {
          case "feed":
            return (
              <FeedScreen
                active={currentTab === "feed"}
                onAccepted={acceptFeedCapture}
              />
            );
          case "wardrobe":
            return (
              <>
                <header
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "var(--px-3)",
                    marginBottom: "var(--px-4)",
                    paddingBottom: "var(--px-3)",
                    borderBottom: "2px dashed var(--pixel-border)"
                  }}
                >
                  <div>
                    <p className="pixel-label">STYLECAPTURE</p>
                    <h1 className="pixel-title">我的衣橱</h1>
                  </div>
                  <div
                    style={{
                      width: "3.5rem",
                      height: "3.5rem",
                      border: "3px solid var(--pixel-border)",
                      background: "var(--pixel-surface-raised)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: "2rem",
                      boxShadow: "3px 3px 0 rgba(0,0,0,0.3)"
                    }}
                  >
                    👾
                  </div>
                </header>

                <section
                  style={{
                    padding: "var(--px-4)",
                    background: "var(--pixel-surface-raised)",
                    border: "3px solid var(--pixel-border)",
                    boxShadow: "4px 4px 0 rgba(0,0,0,0.3)",
                    marginBottom: "var(--px-5)"
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "var(--px-4)"
                    }}
                  >
                    <div>
                      <p className="pixel-label">新增单品</p>
                      <h2
                        className="pixel-subtitle"
                        style={{ color: "var(--pixel-text)" }}
                      >
                        今天想存哪一件？
                      </h2>
                    </div>
                    <span style={{ fontSize: "1.5rem" }}>✨</span>
                  </div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: "var(--px-3)"
                    }}
                  >
                    <button
                      type="button"
                      className="pixel-button pixel-button--primary"
                      onClick={() => cameraInput.current?.click()}
                      style={{ flexDirection: "column", minHeight: "5rem" }}
                    >
                      <span style={{ fontSize: "1.5rem" }}>📷</span>
                      <span>
                        <strong>拍一件</strong>
                        <small
                          style={{
                            display: "block",
                            fontSize: "0.6rem",
                            opacity: 0.7
                          }}
                        >
                          记录真实衣服
                        </small>
                      </span>
                    </button>
                    <button
                      type="button"
                      className="pixel-button pixel-button--accent"
                      onClick={() => galleryInput.current?.click()}
                      style={{ flexDirection: "column", minHeight: "5rem" }}
                    >
                      <span style={{ fontSize: "1.5rem" }}>🖼️</span>
                      <span>
                        <strong>从相册选</strong>
                        <small
                          style={{
                            display: "block",
                            fontSize: "0.6rem",
                            opacity: 0.7
                          }}
                        >
                          导入灵感
                        </small>
                      </span>
                    </button>
                  </div>
                </section>

                <input
                  ref={cameraInput}
                  className="visually-hidden"
                  type="file"
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
                  onOpenItem={setSelectedItem}
                  onOpenOutfit={(id) =>
                    navigateTo({ type: "outfit", outfitId: id })
                  }
                  onRetry={(item) => retryMutation.mutate(item)}
                />
              </>
            );
          case "ai":
            return (
              <AIRecommendScreen
                onOutfitClick={(id) =>
                  navigateTo({ type: "outfit", outfitId: id })
                }
              />
            );
          case "profile":
            return <ProfileScreen onBack={() => goToTab("wardrobe")} />;
          default:
            return null;
        }
      case "outfit":
        return (
          <OutfitDetailScreen
            outfitId={page.outfitId}
            onBack={() => goToTab("wardrobe")}
            onItemClick={(itemId) => {
              const item = items.find((i: Item) => i.id === itemId);
              if (item) setSelectedItem(item);
            }}
          />
        );
      default:
        return null;
    }
  };

  return (
    <main className="pixel-shell">
      <div className="pixel-app">{renderContent()}</div>

      {page.type === "tab" ? (
        <nav aria-label="主要功能" className="pixel-nav">
          <button
            aria-current={currentTab === "feed" ? "page" : undefined}
            className={currentTab === "feed" ? "is-active" : ""}
            type="button"
            onClick={() => goToTab("feed")}
          >
            <span className="nav-icon">📺</span>
            <small>逛灵感</small>
          </button>
          <button
            aria-current={currentTab === "wardrobe" ? "page" : undefined}
            className={currentTab === "wardrobe" ? "is-active" : ""}
            type="button"
            onClick={() => goToTab("wardrobe")}
          >
            <span className="nav-icon">👕</span>
            <small>衣橱</small>
            {pending.length > 0 ? (
              <b
                aria-label={`${pending.length} 个处理中`}
                style={{
                  position: "absolute",
                  top: "2px",
                  right: "4px",
                  background: "var(--pixel-primary)",
                  color: "#fff",
                  fontSize: "0.6rem",
                  padding: "1px 5px",
                  border: "2px solid var(--pixel-surface)"
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
            onClick={() => goToTab("ai")}
          >
            <span className="nav-icon">🤖</span>
            <small>AI搭配</small>
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
        onDeleteSource={(itemId) => deleteMutation.mutate(itemId)}
      />
    </main>
  );
}
