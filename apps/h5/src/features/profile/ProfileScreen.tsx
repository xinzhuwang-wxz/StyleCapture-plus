import { useCallback, useRef, useState } from "react";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { pixelAvatarDataUrl } from "../../utils/pixelAvatar";

interface ProfileScreenProps {
  itemCount: number;
  outfitCount: number;
}

/**
 * 我的页面：
 * 像素形象 + 尚未接入服务端前的形象照本机预览。
 */
export function ProfileScreen({ itemCount, outfitCount }: ProfileScreenProps) {
  const [photos, setPhotos] = useState<string[]>([]);
  const [activePhoto, setActivePhoto] = useState<number>(0);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const reader = new FileReader();
    reader.onload = (e) => {
      const url = e.target?.result as string;
      setPhotos((prev) => [url, ...prev].slice(0, 6));
      setActivePhoto(0);
      setUploading(false);
    };
    reader.readAsDataURL(file);
    event.target.value = "";
  }, []);

  return (
    <div>
      {/* 用户信息卡 */}
      <section
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--px-4)",
          padding: "var(--px-4)",
          background: "linear-gradient(135deg, #f3edfd, #fdeef5)",
          border: "2px solid var(--pixel-secondary)",
          borderRadius: "var(--pixel-border-radius)",
          marginBottom: "var(--px-5)"
        }}
      >
        <img
          src={pixelAvatarDataUrl("user-profile", { size: 120, hat: false })}
          alt="我的像素形象"
          data-pixel="true"
          style={{
            width: "4.5rem",
            height: "4.5rem",
            borderRadius: "50%",
            border: "3px solid #fff",
            boxShadow: "var(--pixel-shadow)"
          }}
        />
        <div style={{ flex: 1 }}>
          <h1 className="pixel-title" style={{ fontSize: "1.2rem", margin: "0 0 4px" }}>
            小甜甜
          </h1>
          <span
            style={{
              fontFamily: "var(--font-pixel)",
              fontSize: "0.68rem",
              padding: "2px 10px",
              background: "var(--pixel-primary)",
              color: "#fff",
              borderRadius: "999px"
            }}
          >
            Lv.3 穿搭收藏家
          </span>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontFamily: "var(--font-pixel)", fontSize: "1.2rem", color: "var(--pixel-primary-dark)" }}>
            {itemCount}
          </div>
          <div style={{ fontSize: "0.62rem", color: "var(--pixel-text-dim)" }}>单品</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontFamily: "var(--font-pixel)", fontSize: "1.2rem", color: "var(--pixel-pink-dark)" }}>
            {outfitCount}
          </div>
          <div style={{ fontSize: "0.62rem", color: "var(--pixel-text-dim)" }}>穿搭</div>
        </div>
      </section>

      {/* 我的形象 */}
      <PixelSectionHeader
        kicker="形象照草稿"
        title="本机预览"
        action={
          uploading ? (
            <span className="pixel-label">处理中…</span>
          ) : null
        }
      />

      {photos.length === 0 ? (
        <section
          style={{
            padding: "var(--px-6) var(--px-4)",
            background: "var(--pixel-surface)",
            border: "2px dashed var(--pixel-secondary)",
            borderRadius: "var(--pixel-border-radius)",
            textAlign: "center",
            marginBottom: "var(--px-5)"
          }}
        >
          <span style={{ fontSize: "2.5rem" }} aria-hidden="true">📸</span>
          <p
            style={{
              fontFamily: "var(--font-pixel)",
              fontSize: "0.85rem",
              color: "var(--pixel-text-muted)",
              lineHeight: 1.7,
              margin: "var(--px-3) 0 var(--px-4)"
            }}
          >
            还没有形象照
            <br />
            <small style={{ fontSize: "0.68rem", color: "var(--pixel-text-dim)" }}>
              当前试穿使用固定模特；这里的照片不会参与生成
            </small>
          </p>
          <div style={{ display: "flex", gap: "var(--px-3)", justifyContent: "center" }}>
            <PixelButton variant="primary" onClick={() => fileInputRef.current?.click()}>
              📷 预览照片
            </PixelButton>
            <PixelButton variant="accent" onClick={() => fileInputRef.current?.click()}>
              🤳 拍照预览
            </PixelButton>
          </div>
        </section>
      ) : (
        <section style={{ marginBottom: "var(--px-5)" }}>
          {/* 当前使用的形象 */}
          <div
            style={{
              position: "relative",
              width: "60%",
              margin: "0 auto var(--px-4)",
              borderRadius: "var(--pixel-border-radius)",
              overflow: "hidden",
              border: "3px solid var(--pixel-primary)",
              boxShadow: "var(--pixel-shadow-lg)"
            }}
          >
            <img
              src={photos[activePhoto]}
              alt="当前使用的形象照"
              style={{ width: "100%", aspectRatio: "3/4", objectFit: "cover", imageRendering: "auto" }}
            />
            <span
              style={{
                position: "absolute",
                top: "var(--px-2)",
                left: "var(--px-2)",
                padding: "2px 10px",
                fontFamily: "var(--font-pixel)",
                fontSize: "0.62rem",
                background: "var(--pixel-primary)",
                color: "#fff",
                borderRadius: "999px"
              }}
            >
              仅本机预览
            </span>
          </div>

          {/* 照片列表 + 新增 */}
          <div style={{ display: "flex", gap: "var(--px-2)", overflowX: "auto", paddingBottom: "var(--px-2)" }}>
            {photos.map((url, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setActivePhoto(i)}
                aria-label={`形象照 ${i + 1}${i === activePhoto ? "（使用中）" : ""}`}
                style={{
                  flex: "0 0 auto",
                  width: "4rem",
                  padding: 0,
                  borderRadius: "var(--pixel-radius-sm)",
                  overflow: "hidden",
                  border: `3px solid ${i === activePhoto ? "var(--pixel-primary)" : "var(--pixel-border)"}`,
                  background: "none"
                }}
              >
                <img
                  src={url}
                  alt=""
                  style={{ width: "100%", aspectRatio: "3/4", objectFit: "cover", imageRendering: "auto" }}
                />
              </button>
            ))}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              aria-label="添加新形象照"
              style={{
                flex: "0 0 auto",
                width: "4rem",
                aspectRatio: "3/4",
                borderRadius: "var(--pixel-radius-sm)",
                border: "2px dashed var(--pixel-secondary)",
                background: "var(--pixel-surface)",
                color: "var(--pixel-primary)",
                fontSize: "1.4rem"
              }}
            >
              +
            </button>
          </div>
        </section>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="visually-hidden"
        onChange={handleFileSelect}
      />

      {/* 提示 */}
      <section
        style={{
          padding: "var(--px-4)",
          background: "var(--pixel-surface)",
          border: "2px solid var(--pixel-border)",
          borderRadius: "var(--pixel-border-radius)"
        }}
      >
        <h3 className="pixel-subtitle" style={{ marginBottom: "var(--px-2)" }}>
          💡 使用提示
        </h3>
        <ul
          style={{
            margin: 0,
            paddingLeft: "var(--px-5)",
            color: "var(--pixel-text-dim)",
            fontSize: "0.75rem",
            lineHeight: 1.8
          }}
        >
          <li>当前真人效果使用固定模特，不会读取这里的照片</li>
          <li>照片仅在当前页面内存中预览，不会上传服务器</li>
          <li>刷新页面后预览会清除；接入真实形象资产 API 后再开放保存</li>
        </ul>
      </section>
    </div>
  );
}
