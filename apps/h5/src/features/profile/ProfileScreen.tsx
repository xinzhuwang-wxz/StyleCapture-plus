import { useState } from "react";

import type { Look, RenderArtifact } from "../../api/client";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { BodyProfileSheet } from "./BodyProfileSheet";
import { PhotoManagerSheet } from "./PhotoManagerSheet";
import { readPhotoAlbum, type PhotoAlbum } from "./photoStorage";
import {
  isDefaultBodyProfile,
  readBodyProfile,
  type BodyProfile
} from "./profileStorage";
import "./profile.css";

interface ProfileScreenProps {
  itemCount: number;
  photoAlbum?: PhotoAlbum;
  onPhotoAlbumChange?: (album: PhotoAlbum) => void;
  onNotice?: (message: string) => void;
  looks?: Look[];
  pixelArtifacts?: RenderArtifact[];
  pixelCovers?: Record<string, RenderArtifact | undefined>;
  activePixelCoverIds?: Record<string, string | null>;
  onSetPixelCover?: (lookId: string, artifactId: string) => void;
}

export function ProfileScreen({
  itemCount,
  photoAlbum,
  onPhotoAlbumChange,
  onNotice,
  looks = [],
  pixelArtifacts = [],
  pixelCovers = {},
  activePixelCoverIds = {},
  onSetPixelCover
}: ProfileScreenProps) {
  // 身材资料只在本机，读一次就够；保存后由 sheet 回传最新值。
  const [bodyProfile, setBodyProfile] = useState<BodyProfile>(readBodyProfile);
  const [editingBody, setEditingBody] = useState(false);
  const [localAlbum, setLocalAlbum] = useState<PhotoAlbum>(readPhotoAlbum);
  const album = photoAlbum ?? localAlbum;
  const changeAlbum = onPhotoAlbumChange ?? setLocalAlbum;
  const [managingPhotos, setManagingPhotos] = useState(false);
  const looksById = new Map(looks.map((look, index) => [look.id, { look, index }]));
  const pixelPeople = pixelArtifacts.flatMap((artifact) => {
    const owner = looksById.get(artifact.look_id);
    if (
      !owner ||
      artifact.status !== "succeeded" ||
      !artifact.output_image_url
    ) {
      return [];
    }
    return [{ ...owner, artifact }];
  });
  const profilePortraitUrl = "/assets/stylecapture-profile-portrait.png";
  const statusCopy = pixelPeople.length
    ? `已生成 ${pixelPeople.length} 个像素小人`
    : "还没有生成像素小人";

  if (managingPhotos) {
    return (
      <PhotoManagerSheet
        album={album}
        onChange={changeAlbum}
        onClose={() => setManagingPhotos(false)}
        onNotice={onNotice}
      />
    );
  }

  if (editingBody) {
    return (
      <BodyProfileSheet
        profile={bodyProfile}
        onSaved={setBodyProfile}
        onClose={() => setEditingBody(false)}
        onNotice={onNotice}
      />
    );
  }

  return (
    <div className="profile-page">
      {/*
        身材资料原本另起了一个板块，但这张卡本来就装得下。两处并存只是让
        「改我的资料」有了两个入口，整张卡就是那个入口。
      */}
      <button
        type="button"
        className="profile__card profile__card--button"
        aria-label="编辑我的个人信息"
        onClick={() => setEditingBody(true)}
      >
        <img src={profilePortraitUrl} alt="我的 StyleCapture 形象" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="pixel-title profile__name">{bodyProfile.nickname}</h1>
          <span className="profile__level">
            {itemCount > 0 ? `已收录 ${itemCount} 件单品` : "数字衣橱新用户"}
          </span>
          <span className="profile__body" aria-label="身材资料">
            {isDefaultBodyProfile(bodyProfile)
              ? "补全身材数据，上身效果更准 ›"
              : `${bodyProfile.height} cm · ${bodyProfile.weight} kg · ${bodyProfile.bust}/${bodyProfile.waist}/${bodyProfile.hip} · ${bodyProfile.shape}`}
          </span>
        </div>
        <span className="profile__edit">{statusCopy}</span>
      </button>

      <PixelSectionHeader
        kicker="AI 真人试穿参考"
        title="我的形象照"
        action={
          <PixelButton variant="ghost" onClick={() => setManagingPhotos(true)}>
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
            onClick={() => setManagingPhotos(true)}
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
          onClick={() => setManagingPhotos(true)}
        >
          ＋
        </button>
      </div>

      <PixelSectionHeader
        kicker="穿搭像素资产"
        title="我的像素小人"
        action={<span className="pixel-label">{pixelPeople.length} 张</span>}
      />

      <section className="profile__pixel-gallery" aria-label="我的像素小人陈列馆">
        {pixelPeople.length ? (
          pixelPeople.map(({ look, artifact, index }) => {
            const isCover = pixelCovers[look.id]?.id === artifact.id;
            return (
              <article key={artifact.id} className="profile__pixel-person" data-cover={isCover}>
                <div className="profile__pixel-person-image">
                  <img
                    src={`${artifact.output_image_url}?v=${encodeURIComponent(
                      artifact.updated_at
                    )}`}
                    alt={`第 ${index + 1} 个像素小人`}
                    data-pixel="true"
                  />
                  {isCover ? <span>封面</span> : null}
                </div>
                <strong>
                  {look.source === "feed_saved" ? "Feed 穿搭" : "我的穿搭"} {index + 1}
                </strong>
                <small>来自这套穿搭的像素卡片</small>
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

      <section className="profile__tips">
        <h3 className="pixel-subtitle" style={{ marginBottom: "var(--px-2)" }}>
          使用提示
        </h3>
        <ul>
          <li>像素小人来自已经保存的穿搭，不再单独上传照片试验。</li>
          <li>每张像素卡片都与对应穿搭关联，可设为那套穿搭的封面。</li>
          <li>这里保存的默认形象照，会在穿搭详情的“真人试穿”中优先选中。</li>
        </ul>
      </section>
    </div>
  );
}
