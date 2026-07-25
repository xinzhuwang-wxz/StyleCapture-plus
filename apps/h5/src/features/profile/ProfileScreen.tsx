import { useCallback, useRef, useState } from "react";
import { PixelButton, PixelCard } from "../../components/PixelUI";

interface ProfileScreenProps {
  onBack: () => void;
}

export function ProfileScreen({ onBack }: ProfileScreenProps) {
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [avatarHistory, setAvatarHistory] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;

      setUploading(true);
      const reader = new FileReader();
      reader.onload = (e) => {
        const url = e.target?.result as string;
        setAvatarUrl(url);
        setAvatarHistory((prev) => [url, ...prev].slice(0, 5));
        setUploading(false);
      };
      reader.readAsDataURL(file);
      event.target.value = "";
    },
    []
  );

  return (
    <div className="pixel-app">
      {/* Top Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--px-3)",
          marginBottom: "var(--px-5)",
          paddingBottom: "var(--px-3)",
          borderBottom: "2px dashed var(--pixel-border)"
        }}
      >
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <h1 className="pixel-title" style={{ fontSize: "1.1rem", margin: 0 }}>
          我的形象
        </h1>
      </div>

      {/* Avatar Display */}
      <div
        style={{
          display: "grid",
          placeItems: "center",
          marginBottom: "var(--px-5)"
        }}
      >
        <div
          style={{
            width: "10rem",
            height: "10rem",
            border: "3px solid var(--pixel-border)",
            background: avatarUrl
              ? "transparent"
              : "linear-gradient(145deg, var(--pixel-surface-raised), var(--pixel-bg-light))",
            boxShadow: "4px 4px 0 rgba(0,0,0,0.3)",
            display: "grid",
            placeItems: "center",
            overflow: "hidden",
            position: "relative"
          }}
        >
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt="我的形象"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                imageRendering: "auto"
              }}
            />
          ) : (
            <span style={{ fontSize: "4rem" }}>👤</span>
          )}
          {uploading ? (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(0,0,0,0.5)",
                display: "grid",
                placeItems: "center",
                fontFamily: "var(--font-pixel)",
                color: "#fff"
              }}
            >
              处理中…
            </div>
          ) : null}
        </div>
      </div>

      {/* Upload Actions */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--px-3)",
          marginBottom: "var(--px-6)"
        }}
      >
        <PixelButton
          variant="primary"
          onClick={() => fileInputRef.current?.click()}
        >
          <span>📷</span> 上传照片
        </PixelButton>
        <PixelButton
          variant="accent"
          onClick={() => fileInputRef.current?.click()}
        >
          <span>🎨</span> 拍照录入
        </PixelButton>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="user"
        className="visually-hidden"
        onChange={handleFileSelect}
      />

      {/* Instructions */}
      <div
        style={{
          padding: "var(--px-4)",
          background: "var(--pixel-surface-raised)",
          border: "2px solid var(--pixel-border)",
          marginBottom: "var(--px-5)"
        }}
      >
        <h3
          className="pixel-subtitle"
          style={{ marginBottom: "var(--px-3)" }}
        >
          💡 使用提示
        </h3>
        <ul
          style={{
            margin: 0,
            paddingLeft: "var(--px-5)",
            color: "var(--pixel-text-dim)",
            fontSize: "0.78rem",
            lineHeight: 1.7
          }}
        >
          <li>请上传正面全身照，用于 AI 试穿效果生成</li>
          <li>照片仅保存在本地，不会上传服务器</li>
          <li>建议穿着贴身衣物拍摄，效果更好</li>
          <li>可以保存多张照片，随时切换使用</li>
        </ul>
      </div>

      {/* Avatar History */}
      {avatarHistory.length > 0 ? (
        <>
          <h3
            className="pixel-subtitle"
            style={{ marginBottom: "var(--px-3)" }}
          >
            📚 历史形象
          </h3>
          <div
            style={{
              display: "flex",
              gap: "var(--px-3)",
              overflowX: "auto",
              paddingBottom: "var(--px-3)",
              marginBottom: "var(--px-5)"
            }}
          >
            {avatarHistory.map((url, i) => (
              <PixelCard
                key={i}
                onClick={() => setAvatarUrl(url)}
                className={avatarUrl === url ? "is-active" : ""}
              >
                <div
                  style={{
                    width: "5rem",
                    height: "5rem",
                    overflow: "hidden"
                  }}
                >
                  <img
                    src={url}
                    alt={`历史形象 ${i + 1}`}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      imageRendering: "auto"
                    }}
                  />
                </div>
              </PixelCard>
            ))}
          </div>
        </>
      ) : null}

      {/* Stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--px-3)",
          marginBottom: "var(--px-5)"
        }}
      >
        <div
          style={{
            padding: "var(--px-4)",
            background: "var(--pixel-surface-raised)",
            border: "2px solid var(--pixel-border)",
            textAlign: "center"
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-pixel)",
              fontSize: "1.5rem",
              color: "var(--pixel-accent)"
            }}
          >
            12
          </div>
          <div
            style={{
              fontSize: "0.7rem",
              color: "var(--pixel-text-dim)",
              marginTop: "4px"
            }}
          >
            已存单品
          </div>
        </div>
        <div
          style={{
            padding: "var(--px-4)",
            background: "var(--pixel-surface-raised)",
            border: "2px solid var(--pixel-border)",
            textAlign: "center"
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-pixel)",
              fontSize: "1.5rem",
              color: "var(--pixel-primary)"
            }}
          >
            5
          </div>
          <div
            style={{
              fontSize: "0.7rem",
              color: "var(--pixel-text-dim)",
              marginTop: "4px"
            }}
          >
            搭配方案
          </div>
        </div>
      </div>
    </div>
  );
}
