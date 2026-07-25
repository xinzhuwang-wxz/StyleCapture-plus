import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { CaptureSheet } from "../features/capture/CaptureSheet";
import { FeedScreen } from "../features/feed/FeedScreen";
import { ItemDetail } from "../features/wardrobe/ItemDetail";
import { WardrobeScreen } from "../features/wardrobe/WardrobeScreen";
import { AIRecommendScreen } from "../features/ai/AIRecommendScreen";
import { ChatHistoryScreen } from "../features/ai/ChatHistoryScreen";
import { AnalysisScreen } from "../features/analysis/AnalysisScreen";
import { FavoritesScreen } from "../features/analysis/FavoritesScreen";
import { ProfileScreen } from "../features/profile/ProfileScreen";
import { BodyInfoScreen } from "../features/profile/BodyInfoScreen";
import { PhotoManagerScreen } from "../features/profile/PhotoManagerScreen";
import { OutfitDetailScreen } from "../features/outfit/OutfitDetailScreen";
import { PhoneFrame } from "../components/PhoneFrame";
import { PixelToast } from "../components/PixelUI";
import { mockApi } from "../mock/mockApi";
import { REFERENCE_PHOTOS } from "../features/wardrobe/catalog";
import { DEFAULT_PROFILE, type BodyProfile } from "../features/profile/profile";

import {
  type CaptureAccepted,
  type Ownership,
  type SourceKind,
  ProductApiError,
  validateImage,
  wardrobeApi
} from "../api/client";
import type { PendingItem } from "../features/wardrobe/WardrobeScreen";

import "./styles.css";
import "./pixel-theme.css";
import "../features/wardrobe/wardrobe.css";

// ─── Config ────────────────────────────────────────────

const USE_MOCK = true;

const api = USE_MOCK ? mockApi : wardrobeApi;

// ─── Types ─────────────────────────────────────────────

/** 应用模式：feed = 抖音式 Feed 流入口；mini = 小程序 */
type Mode = "feed" | "mini";

type Tab = "wardrobe" | "ai" | "analysis" | "profile";

type Page =
  | { type: "tab"; tab: Tab }
  | { type: "outfit"; outfitId: string; from: Tab }
  | { type: "item"; itemId: string; from: Tab }
  /** 二级页：个人信息 / 形象照管理 / 对话记录 / 收藏全部 */
  | { type: "body"; from: Tab }
  | { type: "photos"; from: Tab }
  | { type: "history"; from: Tab }
  | { type: "favorites"; from: Tab };

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
  const scrollRef = useRef<HTMLDivElement>(null);

  const [mode, setMode] = useState<Mode>("feed");
  const [page, setPage] = useState<Page>({ type: "tab", tab: "wardrobe" });
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [aiPreset, setAiPreset] = useState<string | null>(null);
  const [addSheetOpen, setAddSheetOpen] = useState(false);

  /**
   * 悬浮层容器：在滚动区之外，用于承载悬浮衣柜、拖影和底部抽屉。
   * 放在 .pixel-app 里会被它的 overflow 裁掉并跟着内容滚走。
   */
  const [overlay, setOverlay] = useState<HTMLDivElement | null>(null);

  const [profile, setProfile] = useState<BodyProfile>(DEFAULT_PROFILE);
  const [photos, setPhotos] = useState<string[]>([...REFERENCE_PHOTOS]);
  const [activePhoto, setActivePhoto] = useState(0);

  const currentTab = page.type === "tab" ? page.tab : null;
  /** 设为「试穿使用」的形象照，交给 RenderPort 决定能不能叫真人试穿 */
  const referencePhotoUrl = photos[activePhoto] ?? null;

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

  const retryMutation = useMutation({
    mutationFn: (entry: PendingItem) => api.retryItem(entry.captureId),
    onSuccess: () => {
      setNotice("已重新开始识别 🔄");
      void queryClient.invalidateQueries({ queryKey: ["wardrobe-items"] });
    },
    onError: (error) => setNotice(errorMessage(error))
  });

  // ─── Navigation ──────────────────────────────────────

  /** 屏幕滚动区在 .pixel-app 上，翻页时把它滚回顶部。 */
  const navigateTo = useCallback((next: Page) => {
    setPage(next);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
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

  const openItem = useCallback(
    (itemId: string, from: Tab = "wardrobe") =>
      navigateTo({ type: "item", itemId, from }),
    [navigateTo]
  );

  const closeSubpage = useCallback(() => {
    if (page.type === "tab") return;
    goToTab(page.from);
  }, [page, goToTab]);

  const enterMini = useCallback(() => {
    setMode("mini");
    goToTab("wardrobe");
  }, [goToTab]);

  const backToFeed = useCallback(() => setMode("feed"), []);

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
      } catch (error) {
        setSheetError(errorMessage(error));
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

  // ─── 自由组合 ─────────────────────────────────────────

  /**
   * 保存组合后直接跳穿搭详情页 —— 和从「按穿搭」列表点进去的是同一个组件，
   * 因此视觉与交互完全一致。
   */
  const saveCombo = useCallback(
    async (itemIds: string[]) => {
      const outfit = await mockApi.saveCustomOutfit(itemIds);
      await queryClient.invalidateQueries({ queryKey: ["wardrobe-outfits"] });
      setNotice("新穿搭已保存到「按穿搭」⭐");
      openOutfit(outfit.id, "wardrobe");
    },
    [queryClient, openOutfit]
  );

  // ─── Feed 模式（独立入口，不是小程序的一个 Tab）─────────

  if (mode === "feed") {
    return (
      <PhoneFrame>
        <main className="pixel-shell" style={{ background: "#050507" }}>
          <FeedScreen
            active
            api={api}
            onAccepted={acceptFeedCapture}
            onEnterMini={enterMini}
            onViewAI={viewAIFromFeed}
          />
        </main>
        {notice ? <PixelToast message={notice} /> : null}
      </PhoneFrame>
    );
  }

  // ─── 小程序模式 ───────────────────────────────────────

  const renderPage = () => {
    switch (page.type) {
      case "outfit":
        return (
          <OutfitDetailScreen
            outfitId={page.outfitId}
            referencePhotoUrl={referencePhotoUrl}
            onBack={closeSubpage}
            onOpenItem={(itemId) => openItem(itemId, page.from)}
            onNotice={setNotice}
          />
        );
      case "item":
        return (
          <ItemDetail
            itemId={page.itemId}
            items={items}
            inCombo={false}
            onBack={closeSubpage}
            onAddToCombo={() => {
              setNotice("回到「按单品」长按拖进衣柜就能组合 🚪");
              goToTab("wardrobe");
            }}
            onNotice={setNotice}
          />
        );
      case "body":
        return (
          <BodyInfoScreen
            profile={profile}
            onChange={(patch) => setProfile((current) => ({ ...current, ...patch }))}
            onBack={closeSubpage}
            onSave={() => {
              closeSubpage();
              setNotice("资料已保存 💜");
            }}
          />
        );
      case "photos":
        return (
          <PhotoManagerScreen
            photos={photos}
            activePhoto={activePhoto}
            onBack={closeSubpage}
            onUpload={() => galleryInput.current?.click()}
            onUseSelected={(index) => {
              setActivePhoto(index);
              setNotice("已设为试穿照 ✓");
            }}
            onDeleteSelected={(indexes) => {
              setPhotos((current) =>
                current.filter((_, index) => !indexes.includes(index))
              );
              setActivePhoto(0);
              setNotice("已删除所选照片");
            }}
          />
        );
      case "history":
        return (
          <ChatHistoryScreen
            onBack={closeSubpage}
            onOpenOutfit={(outfitId) => openOutfit(outfitId, page.from)}
          />
        );
      case "favorites":
        return (
          <FavoritesScreen
            outfits={outfits}
            onBack={closeSubpage}
            onOpenOutfit={(outfitId) => openOutfit(outfitId, page.from)}
          />
        );
      default:
        break;
    }

    switch (page.tab) {
      case "wardrobe":
        return (
          <>
            <header className="wardrobe__header">
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
                📺 刷 Feed ›
              </button>
            </header>

            <WardrobeScreen
              items={items}
              pending={pending}
              loading={itemsQuery.isLoading}
              outfits={outfits}
              onOpenItem={(itemId) => openItem(itemId, "wardrobe")}
              onOpenOutfit={(outfitId) => openOutfit(outfitId, "wardrobe")}
              onSaveCombo={saveCombo}
              onRetry={(entry) => retryMutation.mutate(entry)}
              onNotice={setNotice}
              overlayContainer={overlay}
            />
          </>
        );
      case "ai":
        return (
          <AIRecommendScreen
            presetPrompt={aiPreset}
            onOutfitClick={(outfitId) => openOutfit(outfitId, "ai")}
            onOpenHistory={() => navigateTo({ type: "history", from: "ai" })}
          />
        );
      case "analysis":
        return (
          <AnalysisScreen
            outfits={outfits}
            onGoAI={() => goToTab("ai")}
            onGoWardrobe={() => goToTab("wardrobe")}
            onOpenOutfit={(outfitId) => openOutfit(outfitId, "analysis")}
            onOpenFavorites={() => navigateTo({ type: "favorites", from: "analysis" })}
          />
        );
      case "profile":
        return (
          <ProfileScreen
            profile={profile}
            photos={photos}
            activePhoto={activePhoto}
            itemCount={items.length}
            outfitCount={outfits.length}
            onOpenBodyInfo={() => navigateTo({ type: "body", from: "profile" })}
            onOpenPhotoManager={() => navigateTo({ type: "photos", from: "profile" })}
            onUsePhoto={(index) => {
              setActivePhoto(index);
              setNotice("已设为试穿照 ✓");
            }}
            onAddPhoto={() => galleryInput.current?.click()}
          />
        );
      default:
        return null;
    }
  };

  const navButton = (tab: Tab, icon: string, label: string, badge?: number) => (
    <button
      aria-current={currentTab === tab ? "page" : undefined}
      className={currentTab === tab ? "is-active" : ""}
      type="button"
      onClick={() => {
        if (tab === "ai") setAiPreset(null);
        goToTab(tab);
      }}
    >
      <span className="nav-icon">{icon}</span>
      <small>{label}</small>
      {badge ? (
        <b aria-label={`${badge} 个处理中`} className="pixel-nav__badge">
          {Math.min(badge, 9)}
        </b>
      ) : null}
    </button>
  );

  return (
    <PhoneFrame>
      <main className="pixel-shell">
        <div
          className={`pixel-app${page.type === "tab" ? "" : " pixel-app--nonav"}`}
          ref={scrollRef}
        >
          {renderPage()}
        </div>
        <div className="pixel-overlay" ref={setOverlay} />
      </main>

      {page.type === "tab" ? (
        <nav aria-label="主要功能" className="pixel-nav">
          {navButton("wardrobe", "👕", "数字衣橱", pending.length)}
          {navButton("ai", "🤖", "AI推荐")}
          <button
            type="button"
            className="pixel-nav__add"
            aria-label="新增单品"
            aria-haspopup="dialog"
            aria-expanded={addSheetOpen}
            onClick={() => setAddSheetOpen(true)}
          >
            {/* 用 SVG 描边而不是「＋」字形，保证加号正落在圆心 */}
            <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
              <path
                d="M10 3.4v13.2M3.4 10h13.2"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
              />
            </svg>
          </button>
          {navButton("analysis", "📊", "穿搭分析")}
          {navButton("profile", "👤", "我的")}
        </nav>
      ) : null}

      {/* ＋ 新增单品：拍一件 / 从相册选 */}
      {addSheetOpen ? (
        <div
          className="pixel-sheet"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) setAddSheetOpen(false);
          }}
        >
          <section
            className="pixel-sheet__content"
            role="dialog"
            aria-modal="true"
            aria-label="新增单品"
          >
            <p className="pixel-label" style={{ marginBottom: "var(--px-3)" }}>
              新增单品
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--px-3)" }}>
              <button
                type="button"
                className="pixel-button pixel-button--primary"
                style={{ flexDirection: "column", minHeight: "5rem" }}
                onClick={() => {
                  setAddSheetOpen(false);
                  cameraInput.current?.click();
                }}
              >
                <span style={{ fontSize: "1.4rem" }}>📷</span>
                拍一件
              </button>
              <button
                type="button"
                className="pixel-button pixel-button--pink"
                style={{ flexDirection: "column", minHeight: "5rem" }}
                onClick={() => {
                  setAddSheetOpen(false);
                  galleryInput.current?.click();
                }}
              >
                <span style={{ fontSize: "1.4rem" }}>🖼️</span>
                从相册选
              </button>
            </div>
            <button
              type="button"
              className="pixel-button pixel-button--ghost w-full"
              style={{ marginTop: "var(--px-3)" }}
              onClick={() => setAddSheetOpen(false)}
            >
              取消
            </button>
          </section>
        </div>
      ) : null}

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

      {notice ? <PixelToast message={notice} /> : null}

      <CaptureSheet
        key={selection?.previewUrl ?? "closed"}
        selection={selection}
        busy={uploading}
        error={sheetError}
        onCancel={cancelSelection}
        onConfirm={(ownership) => void confirmSelection(ownership)}
      />
    </PhoneFrame>
  );
}
