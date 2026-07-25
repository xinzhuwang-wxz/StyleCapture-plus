import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  type CaptureAccepted,
  type Item,
  type Ownership,
  type SourceKind,
  ProductApiError,
  validateImage,
  wardrobeApi
} from "../api/client";
import { CaptureSheet } from "../features/capture/CaptureSheet";
import { FeedScreen } from "../features/feed/FeedScreen";
import { ItemDetail } from "../features/wardrobe/ItemDetail";
import type { PendingItem } from "../features/wardrobe/ItemCard";
import { WardrobeScreen } from "../features/wardrobe/WardrobeScreen";
import "./styles.css";

type Selection = {
  file: File;
  previewUrl: string;
  sourceKind: SourceKind;
};

type Destination = "feed" | "wardrobe";

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
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const itemsQuery = useQuery({
    queryKey: ["wardrobe-items"],
    queryFn: wardrobeApi.listItems,
    refetchInterval: 2_000
  });
  const items = itemsQuery.data ?? [];

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
    <main className={`product-shell product-shell--${destination}`}>
      <section
        aria-label="穿搭灵感"
        className="product-view product-view--feed"
        hidden={destination !== "feed"}
      >
        <FeedScreen
          active={destination === "feed"}
          onAccepted={acceptFeedCapture}
        />
      </section>

      <div
        className="product-view product-view--wardrobe app-shell"
        hidden={destination !== "wardrobe"}
      >
        <header className="wardrobe-header">
          <div>
            <p className="eyebrow">STYLECAPTURE</p>
            <h1>我的衣橱</h1>
            <p className="subtitle">把拥有和喜欢的，都变成可搭配的数字资产。</p>
          </div>
          <div className="avatar-orbit">
            <img src="/assets/char-default.png" alt="我的 StyleCapture 形象" />
            <span aria-hidden="true">✦</span>
          </div>
        </header>

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
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
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
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            aria-label="选择衣物照片"
            onChange={(event) => {
              chooseFile(event.target.files?.[0], "upload");
              event.target.value = "";
            }}
          />
        </section>

        <WardrobeScreen
          items={items}
          pending={pending}
          loading={itemsQuery.isLoading}
          onOpen={setSelectedItem}
          onRetry={(item) => retryMutation.mutate(item)}
        />

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
      </div>

      <nav aria-label="主要功能" className="product-nav">
        <button
          aria-current={destination === "feed" ? "page" : undefined}
          className={destination === "feed" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("feed")}
        >
          <span aria-hidden="true">⌁</span>
          <small>逛灵感</small>
        </button>
        <button
          aria-current={destination === "wardrobe" ? "page" : undefined}
          className={destination === "wardrobe" ? "is-active" : ""}
          type="button"
          onClick={() => setDestination("wardrobe")}
        >
          <span aria-hidden="true">✦</span>
          <small>数字衣橱</small>
          {pending.length > 0 ? (
            <b aria-label={`${pending.length} 个处理中`}>
              {Math.min(pending.length, 9)}
            </b>
          ) : null}
        </button>
      </nav>
    </main>
  );
}
