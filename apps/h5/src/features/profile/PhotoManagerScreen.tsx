import { useState } from "react";

import { PixelButton } from "../../components/PixelUI";
import "./profile.css";

/** 形象照管理二级页：多选、设为试穿照、删除、上传。 */
export function PhotoManagerScreen({
  photos,
  activePhoto,
  onBack,
  onUpload,
  onUseSelected,
  onDeleteSelected
}: {
  photos: readonly string[];
  activePhoto: number;
  onBack: () => void;
  onUpload: () => void;
  onUseSelected: (index: number) => void;
  onDeleteSelected: (indexes: readonly number[]) => void;
}) {
  const [picked, setPicked] = useState<number[]>([]);

  const toggle = (index: number) =>
    setPicked((current) =>
      current.includes(index)
        ? current.filter((candidate) => candidate !== index)
        : [...current, index]
    );

  return (
    <div className="pixel-subpage">
      <div className="subpage__header">
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: 0 }}>
            {picked.length ? `已选中 ${picked.length} 张` : "点选照片可设为试穿照或删除"}
          </p>
          <h1 className="pixel-title" style={{ margin: 0, fontSize: "1.18rem" }}>
            形象照管理
          </h1>
        </div>
        <button type="button" className="pixel-tag" onClick={onUpload}>
          ＋ 上传
        </button>
      </div>

      <div className="photo-manager__grid">
        {photos.map((photo, index) => {
          const selected = picked.includes(index);
          return (
            <button
              key={`${photo}-${index}`}
              type="button"
              className="photo-manager__cell"
              data-selected={selected ? "true" : undefined}
              aria-pressed={selected}
              aria-label={`形象照 ${index + 1}`}
              onClick={() => toggle(index)}
            >
              <img src={photo} alt="" />
              <span className="photo-manager__mark">{selected ? "✓" : ""}</span>
              {index === activePhoto ? (
                <span className="photo-manager__active">✓ 试穿使用</span>
              ) : null}
            </button>
          );
        })}
      </div>

      <div className="photo-manager__actions">
        <PixelButton
          variant="primary"
          disabled={picked.length === 0}
          onClick={() => {
            onUseSelected(picked[0]);
            setPicked([]);
          }}
        >
          设为试穿照
        </PixelButton>
        <PixelButton
          disabled={picked.length === 0}
          onClick={() => {
            onDeleteSelected(picked);
            setPicked([]);
          }}
        >
          删除所选
        </PixelButton>
      </div>

      <section className="profile__tips">
        <h3 className="pixel-subtitle" style={{ marginBottom: "var(--px-2)" }}>
          📸 拍照建议
        </h3>
        <ul>
          <li>正面全身、光线均匀，别逆光</li>
          <li>贴身衣物更容易还原身材比例</li>
          <li>最多保存 6 张，可随时切换</li>
        </ul>
      </section>
    </div>
  );
}
