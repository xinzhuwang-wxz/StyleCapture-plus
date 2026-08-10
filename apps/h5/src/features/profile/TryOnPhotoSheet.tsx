import { motion } from "motion/react";
import { useRef, useState, type ChangeEvent } from "react";

import { validateImage } from "../../api/client";
import { downscaleToDataUrl } from "../../media/downscaleImage";
import {
  MAX_REFERENCE_PHOTOS,
  addPhoto,
  isAlbumFull,
  referencePhotoFile,
  setActivePhoto,
  writePhotoAlbum,
  type PhotoAlbum,
  type ReferencePhoto
} from "./photoStorage";
import "./tryOnPhotoSheet.css";

type TryOnPhotoSheetProps = {
  album: PhotoAlbum;
  busy?: boolean;
  onAlbumChange: (album: PhotoAlbum) => void;
  onChoose: (file: File) => void;
  onClose: () => void;
};

function storageMessage(reason: "quota" | "unavailable" | "failed"): string {
  if (reason === "quota") return "本机存储空间不足，请先在‘我的形象照’中删除一张";
  if (reason === "unavailable") return "当前浏览器无法保存形象照，请关闭无痕模式后再试";
  return "形象照没有保存成功，请重试";
}

export function TryOnPhotoSheet({
  album,
  busy = false,
  onAlbumChange,
  onChoose,
  onClose
}: TryOnPhotoSheetProps) {
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"existing" | "new">(
    album.photos.length ? "existing" : "new"
  );
  const [selectedId, setSelectedId] = useState<string | null>(
    album.activeId ?? album.photos[0]?.id ?? null
  );
  const [freshFile, setFreshFile] = useState<{ id: string; file: File } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPhoto =
    album.photos.find((photo) => photo.id === selectedId) ?? null;

  function commit(next: PhotoAlbum): boolean {
    const result = writePhotoAlbum(next);
    if (!result.ok) {
      setError(storageMessage(result.reason));
      return false;
    }
    onAlbumChange(next);
    setError(null);
    return true;
  }

  async function addNewPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const validationError = validateImage(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (isAlbumFull(album)) {
      setError(`最多保存 ${MAX_REFERENCE_PHOTOS} 张，请先在“我的形象照”中删除一张`);
      return;
    }

    setSaving(true);
    try {
      const photo: ReferencePhoto = {
        id: crypto.randomUUID(),
        dataUrl: await downscaleToDataUrl(file),
        addedAt: new Date().toISOString()
      };
      const next = addPhoto(album, photo);
      if (!commit(next)) return;
      setSelectedId(photo.id);
      setFreshFile({ id: photo.id, file });
      setMode("existing");
    } catch (unknownError) {
      setError(
        unknownError instanceof Error
          ? unknownError.message
          : "这张照片暂时无法处理，请换一张重试"
      );
    } finally {
      setSaving(false);
    }
  }

  function choosePhoto() {
    if (!selectedPhoto || busy || saving) return;
    try {
      const file =
        freshFile?.id === selectedPhoto.id
          ? freshFile.file
          : referencePhotoFile(selectedPhoto);
      onChoose(file);
    } catch (unknownError) {
      setError(
        unknownError instanceof Error
          ? unknownError.message
          : "这张形象照暂时无法读取，请重新上传"
      );
    }
  }

  function makeDefault() {
    if (!selectedPhoto || selectedPhoto.id === album.activeId) return;
    commit(setActivePhoto(album, selectedPhoto.id));
  }

  return (
    <motion.div
      className="tryon-photo-picker-layer"
      role="presentation"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <motion.section
        className="tryon-photo-picker"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tryon-photo-picker-title"
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        exit={{ y: "100%" }}
        transition={{ type: "spring", damping: 28, stiffness: 300 }}
      >
        <div className="sheet-handle" aria-hidden="true" />
        <header className="tryon-photo-picker__header">
          <div>
            <h2 id="tryon-photo-picker-title">选择试穿形象</h2>
            <p>从“我的形象照”选择，或新建一张全身照</p>
          </div>
          <button type="button" aria-label="关闭形象照选择" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="tryon-photo-picker__tabs" role="tablist" aria-label="形象照来源">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "existing"}
            onClick={() => setMode("existing")}
          >
            使用已有形象
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "new"}
            onClick={() => setMode("new")}
          >
            新建形象
          </button>
        </div>

        {error ? (
          <div className="tryon-photo-picker__error" role="alert">
            {error}
          </div>
        ) : null}

        {mode === "existing" ? (
          album.photos.length ? (
            <>
              <div className="tryon-photo-picker__grid" role="radiogroup" aria-label="我的形象照">
                {album.photos.map((photo, index) => {
                  const selected = photo.id === selectedId;
                  const active = photo.id === album.activeId;
                  return (
                    <button
                      key={photo.id}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      aria-label={`第 ${index + 1} 张形象照${active ? "，默认试穿照" : ""}`}
                      className="tryon-photo-picker__photo"
                      data-selected={selected ? "true" : undefined}
                      onClick={() => {
                        setSelectedId(photo.id);
                        setError(null);
                      }}
                    >
                      <img src={photo.dataUrl} alt="" />
                      {active ? <span>默认试穿照</span> : null}
                      <i aria-hidden="true">{selected ? "✓" : ""}</i>
                    </button>
                  );
                })}
              </div>
              <button
                className="tryon-photo-picker__default"
                type="button"
                disabled={!selectedPhoto || selectedPhoto.id === album.activeId}
                onClick={makeDefault}
              >
                {selectedPhoto?.id === album.activeId ? "当前默认试穿照" : "设为默认试穿照"}
              </button>
              <button
                className="primary-action"
                type="button"
                disabled={!selectedPhoto || busy || saving}
                onClick={choosePhoto}
              >
                {busy ? "正在上传并生成…" : "使用这张形象试穿"}
              </button>
            </>
          ) : (
            <div className="tryon-photo-picker__empty">
              <strong>还没有形象照</strong>
              <p>新建一张正面全身照后，就能在每套穿搭中重复使用。</p>
              <button
                className="tryon-photo-picker__create-button"
                type="button"
                onClick={() => setMode("new")}
              >
                新建形象
              </button>
            </div>
          )
        ) : (
          <div className="tryon-photo-picker__new">
            <button
              type="button"
              disabled={saving || busy || isAlbumFull(album)}
              onClick={() => cameraInputRef.current?.click()}
            >
              <span aria-hidden="true">◎</span>
              <strong>拍照新建</strong>
              <small>拍摄正面全身照</small>
            </button>
            <button
              type="button"
              disabled={saving || busy || isAlbumFull(album)}
              onClick={() => galleryInputRef.current?.click()}
            >
              <span aria-hidden="true">▧</span>
              <strong>从相册上传</strong>
              <small>选择已有全身照</small>
            </button>
            {isAlbumFull(album) ? (
              <p>形象照已达到 {MAX_REFERENCE_PHOTOS} 张，请先到“我的”页面管理。</p>
            ) : (
              <p>{saving ? "正在保存到我的形象照…" : "新照片会同步保存到“我的形象照”"}</p>
            )}
          </div>
        )}

        <input
          ref={cameraInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
          capture="user"
          className="visually-hidden"
          aria-label="拍照新建试穿形象"
          onChange={(event) => void addNewPhoto(event)}
        />
        <input
          ref={galleryInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
          className="visually-hidden"
          aria-label="从相册新建试穿形象"
          onChange={(event) => void addNewPhoto(event)}
        />
      </motion.section>
    </motion.div>
  );
}
