import { useEffect, useState } from "react";
import { PixelButton } from "./PixelUI";

interface ShareModalProps {
  imageUrl: string;
  title: string;
  onClose: () => void;
}

export function ShareModal({ imageUrl, title, onClose }: ShareModalProps) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  const handleShare = () => {
    // Simulate share
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 1200);
  };

  const handleDownload = () => {
    const a = document.createElement("a");
    a.href = imageUrl;
    a.download = `stylecapture-${Date.now()}.png`;
    a.click();
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div
      className="pixel-share-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="pixel-share-modal__content">
        <h2 id="share-title" className="pixel-subtitle mb-4">
          {title}
        </h2>
        <img
          src={imageUrl}
          alt="分享卡片"
          className="pixel-share-modal__image"
        />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "var(--px-3)"
          }}
        >
          <PixelButton variant="accent" onClick={handleDownload}>
            <span>💾</span> 保存到本地
          </PixelButton>
          <PixelButton variant="primary" onClick={handleShare}>
            <span>📤</span> 分享到抖音
          </PixelButton>
        </div>
        <button
          type="button"
          onClick={onClose}
          style={{
            marginTop: "var(--px-3)",
            background: "transparent",
            border: "none",
            color: "var(--pixel-text-dim)",
            fontSize: "0.75rem",
            fontFamily: "var(--font-pixel)"
          }}
        >
          取消
        </button>
        {saved ? (
          <p
            style={{
              color: "var(--pixel-success)",
              fontFamily: "var(--font-pixel)",
              fontSize: "0.75rem",
              marginTop: "var(--px-2)"
            }}
          >
            ✓ 完成！
          </p>
        ) : null}
      </div>
    </div>
  );
}
