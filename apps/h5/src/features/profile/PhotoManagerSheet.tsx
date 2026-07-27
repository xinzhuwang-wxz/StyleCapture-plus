import { useRef, useState, type ChangeEvent } from "react";

import { validateImage } from "../../api/client";
import { PixelButton } from "../../components/PixelUI";
import { downscaleToDataUrl } from "../../media/downscaleImage";
import {
  MAX_REFERENCE_PHOTOS,
  addPhoto,
  isAlbumFull,
  removePhotos,
  setActivePhoto,
  writePhotoAlbum,
  type PhotoAlbum
} from "./photoStorage";

type PhotoManagerSheetProps = {
  album: PhotoAlbum;
  onChange: (album: PhotoAlbum) => void;
  onClose: () => void;
  onNotice?: (message: string) => void;
};

function storageMessage(reason: "quota" | "unavailable" | "failed"): string {
  if (reason === "quota") return "本机存储放不下了，先删掉几张再加新的";
  if (reason === "unavailable") return "这台设备不允许保存照片，试试关掉无痕模式";
  return "照片没能保存，请重试";
}

/**
 * 「形象照管理」二级页。
 *
 * 照片全程只在本机：选中的那张会被缩小成 data URL 存进 localStorage，不上传。
 * 界面上把这件事写出来，因为用户交出的是自己的全身照。
 */
export function PhotoManagerSheet({
  album,
  onChange,
  onClose,
  onNotice
}: PhotoManagerSheetProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<readonly string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function commit(next: PhotoAlbum, notice?: string): boolean {
    const result = writePhotoAlbum(next);
    if (!result.ok) {
      setError(storageMessage(result.reason));
      return false;
    }
    setError(null);
    onChange(next);
    if (notice) onNotice?.(notice);
    return true;
  }

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (isAlbumFull(album)) {
      setError(`最多保存 ${MAX_REFERENCE_PHOTOS} 张，先删掉一张再加`);
      return;
    }
    const invalid = validateImage(file);
    if (invalid) {
      setError(invalid);
      return;
    }

    setBusy(true);
    try {
      const dataUrl = await downscaleToDataUrl(file);
      const photo = {
        id: crypto.randomUUID(),
        dataUrl,
        addedAt: new Date().toISOString()
      };
      commit(addPhoto(album, photo), "照片已保存在本机");
    } catch (unknownError) {
      setError(
        unknownError instanceof Error
          ? unknownError.message
          : "照片处理失败，请重试"
      );
    } finally {
      setBusy(false);
    }
  }

  function toggleSelected(id: string) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((entry) => entry !== id)
        : [...current, id]
    );
  }

  function useSelectedForTryOn() {
    const [only] = selected;
    if (!only) return;
    if (commit(setActivePhoto(album, only), "已设为真人试穿参考照")) {
      setSelected([]);
    }
  }

  function deleteSelected() {
    if (!selected.length) return;
    if (commit(removePhotos(album, selected), `已删除 ${selected.length} 张`)) {
      setSelected([]);
    }
  }

  return (
    <section className="profile-page" aria-label="形象照管理">
      <div className="subpage__header">
        <PixelButton variant="ghost" onClick={onClose}>
          ‹ 返回
        </PixelButton>
        <h1 className="pixel-title" style={{ margin: 0 }}>
          形象照管理
        </h1>
      </div>

      {album.photos.length ? (
        <div className="photo-manager__grid" role="group" aria-label="我的形象照">
          {album.photos.map((photo, index) => {
            const isSelected = selected.includes(photo.id);
            const isActive = photo.id === album.activeId;
            return (
              <button
                key={photo.id}
                type="button"
                className="photo-manager__cell"
                data-selected={isSelected ? "true" : undefined}
                aria-pressed={isSelected}
                aria-label={`第 ${index + 1} 张形象照${isActive ? "（试穿使用中）" : ""}`}
                onClick={() => toggleSelected(photo.id)}
              >
                <img src={photo.dataUrl} alt="" />
                <span className="photo-manager__mark" aria-hidden="true">
                  {isSelected ? "✓" : ""}
                </span>
                {isActive ? (
                  <span className="photo-manager__active">✓ 试穿使用</span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="profile-empty-photo">
          <span aria-hidden="true">📸</span>
          <p>还没有形象照</p>
          <small>上传正面全身照，作为真人试穿的参考图</small>
        </div>
      )}

      {error ? (
        <div className="profile__error" role="alert">
          {error}
        </div>
      ) : null}

      <div className="photo-manager__actions">
        <PixelButton
          variant="primary"
          disabled={busy || isAlbumFull(album)}
          onClick={() => fileInputRef.current?.click()}
        >
          {busy ? "处理中…" : "＋ 上传"}
        </PixelButton>
        <PixelButton
          variant="accent"
          disabled={selected.length !== 1}
          onClick={useSelectedForTryOn}
        >
          设为试穿照
        </PixelButton>
        <PixelButton
          variant="ghost"
          disabled={!selected.length}
          onClick={deleteSelected}
        >
          删除所选
        </PixelButton>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
        className="visually-hidden"
        aria-label="上传形象照"
        onChange={(event) => void handleFile(event)}
      />

      <section className="profile__tips">
        <h3 className="pixel-subtitle" style={{ marginBottom: "var(--px-2)" }}>
          📸 拍照建议
        </h3>
        <ul>
          <li>正面全身、光线均匀，别逆光。</li>
          <li>贴身衣物更容易还原身材比例。</li>
          <li>
            最多保存 {MAX_REFERENCE_PHOTOS} 张，可随时切换；照片只存在这台设备上，不会上传服务器。
          </li>
        </ul>
      </section>
    </section>
  );
}
