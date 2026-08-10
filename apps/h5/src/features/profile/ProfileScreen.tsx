import { useState } from "react";

import type { Look, RenderArtifact } from "../../api/client";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { BodyProfileSheet } from "./BodyProfileSheet";
import { PhotoManagerSheet } from "./PhotoManagerSheet";
import { readPhotoAlbum, type PhotoAlbum } from "./photoStorage";
import { readBodyProfile, type BodyProfile } from "./profileStorage";
import "./profile.css";

interface ProfileScreenProps {
  itemCount: number;
  subpage?: "main" | "body" | "photos";
  onSubpageChange?: (subpage: "main" | "body" | "photos") => void;
  photoAlbum?: PhotoAlbum;
  onPhotoAlbumChange?: (album: PhotoAlbum) => void;
  onNotice?: (message: string) => void;
  looks?: Look[];
  pixelArtifacts?: RenderArtifact[];
  pixelCovers?: Record<string, RenderArtifact | undefined>;
  onSetPixelCover?: (lookId: string, artifactId: string) => void;
}

export function ProfileScreen({
  itemCount,
  subpage = "main",
  onSubpageChange,
  photoAlbum,
  onPhotoAlbumChange,
  onNotice,
  looks = [],
  pixelArtifacts = [],
  pixelCovers = {},
  onSetPixelCover
}: ProfileScreenProps) {
  // 身材资料只在本机，读一次就够；保存后由 sheet 回传最新值。
  const [bodyProfile, setBodyProfile] = useState<BodyProfile>(readBodyProfile);
  const [localAlbum, setLocalAlbum] = useState<PhotoAlbum>(readPhotoAlbum);
  const album = photoAlbum ?? localAlbum;
  const changeAlbum = onPhotoAlbumChange ?? setLocalAlbum;
  const looksById = new Map(looks.map((look) => [look.id, look]));
  const pixelPeople = pixelArtifacts.flatMap((artifact) => {
    const owner = looksById.get(artifact.look_id);
    if (
      !owner ||
      artifact.status !== "succeeded" ||
      !artifact.output_image_url
    ) {
      return [];
    }
    return [{ look: owner, artifact }];
  });
  const profilePortraitUrl = "/assets/stylecapture-profile-portrait.png";
  if (subpage === "photos") {
    return (
      <PhotoManagerSheet
        album={album}
        onChange={changeAlbum}
        onClose={() => onSubpageChange?.("main")}
        onNotice={onNotice}
      />
    );
  }

  if (subpage === "body") {
    return (
      <BodyProfileSheet
        profile={bodyProfile}
        onSaved={setBodyProfile}
        onClose={() => onSubpageChange?.("main")}
        onNotice={onNotice}
      />
    );
  }

  return (
    <div className="profile-page">
      <section className="profile__card" aria-label="个人数字资产概览">
        <img src={profilePortraitUrl} alt="我的 StyleCapture 形象" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="pixel-title profile__name">{bodyProfile.nickname}</h1>
          <p className="profile__asset-count">
            已收录 {itemCount} 件单品 · {looks.length} 套穿搭
          </p>
        </div>
      </section>

      <PixelSectionHeader
        title="我的形象照"
        action={
          <PixelButton
            variant="ghost"
            className="profile__manage"
            onClick={() => onSubpageChange?.("photos")}
          >
            管理 ›
          </PixelButton>
        }
      />

      <div className="profile__strip" aria-label="形象照">
        {album.photos.map((photo, index) => (
          <button
            key={photo.id}
            type="button"
            className="profile__photo"
            aria-label={`第 ${index + 1} 张形象照${
              photo.id === album.activeId ? "（试穿使用中）" : ""
            }`}
            onClick={() => onSubpageChange?.("photos")}
          >
            <img src={photo.dataUrl} alt="" />
            {photo.id === album.activeId ? (
              <span className="photo-manager__active">✓ 使用中</span>
            ) : null}
          </button>
        ))}
        <button
          type="button"
          className="profile__photo-add"
          aria-label="添加形象照"
          onClick={() => onSubpageChange?.("photos")}
        >
          ＋
        </button>
      </div>

      <PixelSectionHeader
        title="我的像素小人"
        action={<span className="pixel-label">{pixelPeople.length} 张</span>}
      />

      <section className="profile__pixel-gallery" aria-label="我的像素小人陈列馆">
        {pixelPeople.length ? (
          pixelPeople.map(({ look, artifact }, galleryIndex) => {
            const isCover = pixelCovers[look.id]?.id === artifact.id;
            return (
              <article key={artifact.id} className="profile__pixel-person" data-cover={isCover}>
                <div className="profile__pixel-person-image">
                  <img
                    src={`${artifact.output_image_url}?v=${encodeURIComponent(
                      artifact.updated_at
                    )}`}
                    alt={`第 ${galleryIndex + 1} 个像素小人`}
                    data-pixel="true"
                  />
                </div>
                <button
                  type="button"
                  disabled={isCover}
                  onClick={() => {
                    onSetPixelCover?.(look.id, artifact.id);
                    onNotice?.("已设为这套穿搭的像素封面");
                  }}
                >
                  {isCover ? "当前穿搭封面" : "设为穿搭封面"}
                </button>
              </article>
            );
          })
        ) : (
          <div className="profile__pixel-gallery-empty">
            <strong>还没有像素小人</strong>
            <p>在穿搭详情完成真人试穿后，可以继续生成像素卡片。</p>
          </div>
        )}
      </section>

    </div>
  );
}
