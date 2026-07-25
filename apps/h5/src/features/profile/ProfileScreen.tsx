import type { BodyProfile } from "./profile";
import "./profile.css";

interface ProfileScreenProps {
  profile: BodyProfile;
  photos: readonly string[];
  activePhoto: number;
  itemCount: number;
  outfitCount: number;
  onOpenBodyInfo: () => void;
  onOpenPhotoManager: () => void;
  onUsePhoto: (index: number) => void;
  onAddPhoto: () => void;
}

/**
 * 我的页面：个人信息卡（可点进二级页编辑）、四格数据、形象照条、使用提示。
 */
export function ProfileScreen({
  profile,
  photos,
  activePhoto,
  itemCount,
  outfitCount,
  onOpenBodyInfo,
  onOpenPhotoManager,
  onUsePhoto,
  onAddPhoto
}: ProfileScreenProps) {
  return (
    <div>
      <button type="button" className="profile__card" onClick={onOpenBodyInfo}>
        <img
          src={photos[activePhoto] ?? "/assets/pixel-2.png"}
          alt="我的形象"
          data-pixel="true"
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="pixel-title profile__name">{profile.name}</h1>
          <span className="profile__level">Lv.3 穿搭收藏家</span>
        </div>
        <span className="profile__edit">编辑资料 ›</span>
      </button>

      <button type="button" className="profile__stats" onClick={onOpenBodyInfo}>
        <span>
          <b style={{ color: "var(--pixel-primary-dark)" }}>{profile.height}</b>
          <small>身高 cm</small>
        </span>
        <span>
          <b style={{ color: "var(--pixel-pink-dark)" }}>{profile.weight}</b>
          <small>体重 kg</small>
        </span>
        <span>
          <b style={{ color: "var(--pixel-accent-glow)" }}>{itemCount}</b>
          <small>单品</small>
        </span>
        <span>
          <b style={{ color: "var(--pixel-primary-dark)" }}>{outfitCount}</b>
          <small>穿搭</small>
        </span>
      </button>

      <div className="profile__section-head">
        <div>
          <p className="pixel-label" style={{ margin: 0 }}>
            AI 真人试穿参考
          </p>
          <h2 className="pixel-title" style={{ margin: 0, fontSize: "1.1rem" }}>
            我的形象照
          </h2>
        </div>
        <button type="button" className="pixel-tag" onClick={onOpenPhotoManager}>
          管理 ›
        </button>
      </div>

      <div className="profile__strip">
        {photos.map((photo, index) => (
          <button
            key={`${photo}-${index}`}
            type="button"
            className="profile__photo"
            data-active={index === activePhoto ? "true" : undefined}
            aria-label={`形象照 ${index + 1}${index === activePhoto ? "（使用中）" : ""}`}
            onClick={() => onUsePhoto(index)}
          >
            <img src={photo} alt="" />
            {index === activePhoto ? <span>✓ 使用中</span> : null}
          </button>
        ))}
        <button
          type="button"
          className="profile__photo-add"
          aria-label="添加新形象照"
          onClick={onAddPhoto}
        >
          ＋
        </button>
      </div>

      <section className="profile__tips">
        <h3 className="pixel-subtitle" style={{ marginBottom: "var(--px-2)" }}>
          💡 使用提示
        </h3>
        <ul>
          <li>上传正面全身照，作为真人试穿的参考图</li>
          <li>照片仅保存在本机，不会上传服务器</li>
          <li>补全身材数据，AI 生成的上身效果更准</li>
        </ul>
      </section>
    </div>
  );
}
