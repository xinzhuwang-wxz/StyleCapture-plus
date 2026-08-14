/**
 * 形象照的本机相册。
 *
 * 用户添加的真人全身照属于最敏感的一类数据，所以只以缩小后的 data URL 存在
 * 这台设备上。产品方授权的路演参考照也在构建时内联为 data URL；它不会打开额外
 * 的图片请求，并且只在没有本机相册记录的新会话里作为默认值出现。
 *
 * 设计里写明「最多保存 6 张，可随时切换」——上限不是装饰，是 localStorage
 * 容量的现实约束。
 */

import demoReferencePhotoDataUrl from "../../assets/stylecapture-demo-reference-20260814.jpg?inline";

import {
  asRecord,
  asTrimmedString,
  readLocal,
  writeLocal,
  type LocalStoreDefinition,
  type WriteResult
} from "../../storage/localStore";

export const MAX_REFERENCE_PHOTOS = 6;
export const DEMO_REFERENCE_PHOTO_ID = "stylecapture-demo-reference-20260814";

export type ReferencePhoto = {
  id: string;
  /** 缩小后的 JPEG data URL。 */
  dataUrl: string;
  addedAt: string;
};

export type PhotoAlbum = {
  photos: ReferencePhoto[];
  /** 当前用于真人试穿的那张；相册为空时是 null。 */
  activeId: string | null;
};

export function emptyAlbum(): PhotoAlbum {
  return { photos: [], activeId: null };
}

/**
 * Fresh deployments start with the authorized roadshow portrait ready for try-on.
 * Returning a new object keeps the local-store fallback mutation-safe.
 */
export function demoAlbum(): PhotoAlbum {
  return {
    photos: [
      {
        id: DEMO_REFERENCE_PHOTO_ID,
        dataUrl: demoReferencePhotoDataUrl,
        addedAt: "2026-08-14T00:00:00.000Z"
      }
    ],
    activeId: DEMO_REFERENCE_PHOTO_ID
  };
}

function parsePhoto(raw: unknown): ReferencePhoto | null {
  const record = asRecord(raw);
  if (!record) return null;
  const id = asTrimmedString(record.id, 64);
  const addedAt = asTrimmedString(record.addedAt, 40);
  const dataUrl = typeof record.dataUrl === "string" ? record.dataUrl : "";
  // 只认 data URL：外部链接会把本机照片变成一次网络请求。
  if (!id || !addedAt || !dataUrl.startsWith("data:image/")) return null;
  return { id, dataUrl, addedAt };
}

export const photoAlbumStore: LocalStoreDefinition<PhotoAlbum> = {
  key: "stylecapture:reference-photos:v1",
  fallback: demoAlbum,
  parse: (raw) => {
    const record = asRecord(raw);
    if (!record) return null;
    if (!Array.isArray(record.photos)) return null;

    const photos = record.photos
      .map(parsePhoto)
      .filter((photo): photo is ReferencePhoto => photo !== null)
      .slice(0, MAX_REFERENCE_PHOTOS);

    const activeId =
      typeof record.activeId === "string" &&
      photos.some((photo) => photo.id === record.activeId)
        ? record.activeId
        : (photos[0]?.id ?? null);

    return { photos, activeId };
  }
};

export function readPhotoAlbum(): PhotoAlbum {
  return readLocal(photoAlbumStore);
}

export function writePhotoAlbum(album: PhotoAlbum): WriteResult {
  return writeLocal(photoAlbumStore, album);
}

export function isAlbumFull(album: PhotoAlbum): boolean {
  return album.photos.length >= MAX_REFERENCE_PHOTOS;
}

/** 加一张；相册满了就原样返回，由调用方给出提示。 */
export function addPhoto(album: PhotoAlbum, photo: ReferencePhoto): PhotoAlbum {
  if (isAlbumFull(album)) return album;
  const photos = [...album.photos, photo];
  // 第一张自动成为试穿照，省掉一次多余的点击。
  return { photos, activeId: album.activeId ?? photo.id };
}

/** 删若干张；删掉的正好是当前试穿照时，自动顺延到剩下的第一张。 */
export function removePhotos(
  album: PhotoAlbum,
  ids: readonly string[]
): PhotoAlbum {
  const doomed = new Set(ids);
  const photos = album.photos.filter((photo) => !doomed.has(photo.id));
  const activeId =
    album.activeId && !doomed.has(album.activeId)
      ? album.activeId
      : (photos[0]?.id ?? null);
  return { photos, activeId };
}

export function setActivePhoto(album: PhotoAlbum, id: string): PhotoAlbum {
  return album.photos.some((photo) => photo.id === id)
    ? { ...album, activeId: id }
    : album;
}

export function activePhoto(album: PhotoAlbum): ReferencePhoto | null {
  return album.photos.find((photo) => photo.id === album.activeId) ?? null;
}

/**
 * Turn a locally stored reference photo back into an uploadable file.
 * The album deliberately stores data URLs only, so choosing an existing
 * portrait never performs a network request before the user starts try-on.
 */
export function referencePhotoFile(photo: ReferencePhoto): File {
  const match = /^data:(image\/[a-z0-9.+-]+);base64,(.+)$/i.exec(photo.dataUrl);
  if (!match) throw new Error("这张形象照暂时无法读取，请重新上传");

  let binary: string;
  try {
    binary = window.atob(match[2]);
  } catch {
    throw new Error("这张形象照暂时无法读取，请重新上传");
  }
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const contentType = match[1].toLowerCase();
  const extension = contentType === "image/png" ? "png" : "jpg";
  return new File([bytes], `stylecapture-reference-${photo.id}.${extension}`, {
    type: contentType
  });
}
