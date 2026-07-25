import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent
} from "react";

import {
  createCommunityScene,
  moveAvatarTo,
  selectReaction,
  type CommunityReaction,
  type CommunityResident,
  type CommunityScene
} from "./communityScene";

const reactionLabels: Record<CommunityReaction, { label: string; symbol: string }> = {
  heart: { label: "心动", symbol: "♥" },
  sparkle: { label: "闪闪", symbol: "✦" },
  music: { label: "音乐", symbol: "♫" },
  wave: { label: "挥挥", symbol: "⌁" }
};

type SceneStyle = CSSProperties & Record<"--resident-x" | "--resident-y" | "--resident-accent" | "--avatar-x" | "--avatar-y", string>;

export type CommunityAvatarSource = {
  assetUrl: string;
  label: string;
  kind: "demo-fallback" | "public-render-artifact";
};

export const defaultCommunityAvatar: CommunityAvatarSource = {
  assetUrl: "/assets/char-default.png",
  label: "Demo 像素形象",
  kind: "demo-fallback"
};

type CommunityScreenProps = {
  avatarSource?: CommunityAvatarSource;
};

function drawShareCard(
  canvas: HTMLCanvasElement,
  scene: CommunityScene,
  avatarSource: CommunityAvatarSource,
  avatarImage: HTMLImageElement
) {
  const context = canvas.getContext("2d");
  if (!context) return;

  canvas.width = 720;
  canvas.height = 960;
  context.fillStyle = "#17112a";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#2c2054";
  context.fillRect(64, 112, 592, 624);
  context.fillStyle = "#9d68ff";
  context.fillRect(224, 278, 272, 272);
  context.fillStyle = "#ed68aa";
  context.fillRect(240, 294, 112, 112);
  context.fillStyle = "#86e6cf";
  context.fillRect(368, 422, 112, 112);
  const avatarX = 224 + ((scene.avatar.x - scene.bounds.minX) / (scene.bounds.maxX - scene.bounds.minX)) * 250;
  const avatarY = 278 + ((scene.avatar.y - scene.bounds.minY) / (scene.bounds.maxY - scene.bounds.minY)) * 250;
  context.drawImage(avatarImage, avatarX, avatarY, 92, 92);
  context.fillStyle = "#f8f2ff";
  context.font = "700 34px sans-serif";
  context.fillText("STYLECAPTURE", 64, 66);
  context.font = "700 52px sans-serif";
  context.fillText("今晚舞会", 64, 824);
  context.font = "30px sans-serif";
  context.fillText(scene.avatar.isDancing ? "我的搭配正在舞池发光" : "我的搭配来到像素舞会", 64, 874);
  context.fillText(
    `${scene.avatar.reaction ? reactionLabels[scene.avatar.reaction].symbol : "✦"} ${avatarSource.label} · #StyleCapture`,
    64,
    918
  );
}

export function CommunityScreen({ avatarSource = defaultCommunityAvatar }: CommunityScreenProps) {
  const [scene, setScene] = useState(createCommunityScene);
  const [selectedResident, setSelectedResident] = useState<CommunityResident | null>(null);
  const [message, setMessage] = useState("点击舞池，让你的搭配动起来");
  const [shareState, setShareState] = useState<"idle" | "ready" | "error">("idle");
  const shareCanvas = useRef<HTMLCanvasElement>(null);
  const avatarImage = useRef<HTMLImageElement>(null);
  const closeResidentButton = useRef<HTMLButtonElement>(null);
  const residentTrigger = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (shareCanvas.current && avatarImage.current) {
      drawShareCard(shareCanvas.current, scene, avatarSource, avatarImage.current);
    }
  }, [avatarSource, scene]);

  useEffect(() => {
    if (selectedResident) closeResidentButton.current?.focus();
  }, [selectedResident]);

  function move(target: { x: number; y: number }) {
    setScene((current) => {
      const next = moveAvatarTo(current, target);
      setMessage(next.avatar.isDancing ? "舞步已解锁，正在舞池发光" : "已走到新的位置");
      return next;
    });
  }

  function moveBy(delta: { x: number; y: number }) {
    move({ x: scene.avatar.x + delta.x, y: scene.avatar.y + delta.y });
  }

  function handleStagePointerUp(event: PointerEvent<HTMLDivElement>) {
    if (event.target instanceof Element && event.target.closest("button")) return;
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    move({
      x: ((event.clientX - rect.left) / rect.width) * 100,
      y: ((event.clientY - rect.top) / rect.height) * 100
    });
  }

  function handleStageKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const moves = {
      ArrowUp: { x: 0, y: -8 },
      ArrowDown: { x: 0, y: 8 },
      ArrowLeft: { x: -8, y: 0 },
      ArrowRight: { x: 8, y: 0 }
    } as const;
    const delta = moves[event.key as keyof typeof moves];
    if (!delta) return;
    event.preventDefault();
    moveBy(delta);
  }

  function react(reaction: CommunityReaction) {
    setScene((current) => selectReaction(current, reaction));
    setMessage(`发送了 ${reactionLabels[reaction].symbol}`);
  }

  function prepareShareCard() {
    try {
      const canvas = shareCanvas.current;
      if (!canvas || !avatarImage.current) throw new Error("分享卡还没有准备好");
      drawShareCard(canvas, scene, avatarSource, avatarImage.current);
      const link = document.createElement("a");
      link.href = canvas.toDataURL("image/png");
      link.download = "stylecapture-pixel-ballroom.png";
      link.click();
      setShareState("ready");
      setMessage("分享卡已准备好");
    } catch {
      setShareState("error");
      setMessage("分享卡生成失败，请重试");
    }
  }

  function closeResident() {
    setSelectedResident(null);
    setTimeout(() => residentTrigger.current?.focus(), 0);
  }

  return (
    <div className="community-shell app-shell">
      <header className="community-header">
        <div>
          <p className="eyebrow">STYLECAPTURE · COMMUNITY</p>
          <h1>今晚舞会</h1>
          <p>带着你的像素搭配，去舞池里碰见灵感。</p>
        </div>
        <span className="community-online" aria-label="当前有 4 个场景角色">
          4 个角色
        </span>
      </header>

      <section className="community-card" aria-labelledby="community-scene-title">
        <div className="community-card__heading">
          <div>
            <p className="section-kicker">PIXEL BALLROOM</p>
            <h2 id="community-scene-title">紫光舞池</h2>
          </div>
          <span>Demo 场景</span>
        </div>

        <div
          className="pixel-ballroom"
          aria-label="像素舞池地图"
          aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight"
          onPointerUp={handleStagePointerUp}
          onKeyDown={handleStageKeyDown}
          role="region"
          tabIndex={0}
        >
          <canvas aria-hidden="true" className="pixel-ballroom__backdrop" />
          <div className="pixel-ballroom__lights" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>
          <div className="pixel-ballroom__floor" aria-hidden="true" />
          {scene.residents.map((resident) => (
            <button
              key={resident.id}
              aria-label={`查看${resident.name}的公开穿搭`}
              className="scene-resident"
              style={{
                "--resident-x": `${resident.position.x}%`,
                "--resident-y": `${resident.position.y}%`,
                "--resident-accent": resident.accent
              } as SceneStyle}
              type="button"
              onClick={(event) => {
                residentTrigger.current = event.currentTarget;
                setSelectedResident(resident);
              }}
            >
              <span aria-hidden="true" className="pixel-person pixel-person--resident" />
              <small>{resident.name}</small>
            </button>
          ))}
          <div
            aria-label={scene.avatar.isDancing ? "我的形象正在跳舞" : "我的像素形象"}
            className={`scene-avatar ${scene.avatar.isDancing ? "is-dancing" : ""}`}
            style={{ "--avatar-x": `${scene.avatar.x}%`, "--avatar-y": `${scene.avatar.y}%` } as SceneStyle}
          >
            {scene.avatar.reaction ? (
              <span className="scene-avatar__reaction" aria-hidden="true">
                {reactionLabels[scene.avatar.reaction].symbol}
              </span>
            ) : null}
            <span className="pixel-person pixel-person--me" aria-hidden="true" />
            <img ref={avatarImage} src={avatarSource.assetUrl} alt="" />
            <small>我</small>
          </div>
        </div>

        <p className="community-avatar-source">
          {avatarSource.label}
          {avatarSource.kind === "demo-fallback" ? " · Look 封面接入后会自动替换" : " · 公开 Look 封面"}
        </p>

        <p className="community-hint" role="status">
          {message}
        </p>

        <div className="community-controls" aria-label="移动我的形象">
          <button aria-label="向上移动" type="button" onClick={() => moveBy({ x: 0, y: -8 })}>
            ↑
          </button>
          <button aria-label="向左移动" type="button" onClick={() => moveBy({ x: -8, y: 0 })}>
            ←
          </button>
          <button aria-label="向下移动" type="button" onClick={() => moveBy({ x: 0, y: 8 })}>
            ↓
          </button>
          <button aria-label="向右移动" type="button" onClick={() => moveBy({ x: 8, y: 0 })}>
            →
          </button>
        </div>
      </section>

      <section className="community-actions" aria-label="舞会互动">
        <div>
          <p className="section-kicker">做个反应</p>
          <h2>让搭配说话</h2>
        </div>
        <div className="reaction-list">
          {scene.reactions.map((reaction) => (
            <button key={reaction} type="button" onClick={() => react(reaction)}>
              <span aria-hidden="true">{reactionLabels[reaction].symbol}</span>
              {reactionLabels[reaction].label}
            </button>
          ))}
        </div>
      </section>

      <section className="community-share" aria-label="分享像素搭配">
        <div>
          <p className="section-kicker">SHARE CARD</p>
          <h2>带走今晚的像素瞬间</h2>
          <p>只包含你的像素形象和公开搭配氛围，不会带出原始参考图。</p>
        </div>
        <button type="button" onClick={prepareShareCard}>
          {shareState === "error" ? "重试生成分享卡" : "生成分享卡"}
        </button>
        <canvas ref={shareCanvas} aria-hidden="true" className="community-share__canvas" />
      </section>

      {selectedResident ? (
        <div
          className="community-dialog-backdrop"
          role="presentation"
          onPointerDown={(event) => {
            if (event.target === event.currentTarget) closeResident();
          }}
        >
          <section
            aria-describedby="community-resident-description"
            aria-labelledby="community-resident-title"
            aria-modal="true"
            className="community-dialog"
            role="dialog"
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                closeResident();
              }
              if (event.key === "Tab") {
                event.preventDefault();
                closeResidentButton.current?.focus();
              }
            }}
          >
            <button
              ref={closeResidentButton}
              aria-label={`关闭${selectedResident.name}的公开穿搭`}
              className="community-dialog__close"
              type="button"
              onClick={closeResident}
            >
              ×
            </button>
            <p className="section-kicker">{selectedResident.label}</p>
            <h2 id="community-resident-title">{selectedResident.name}的公开穿搭</h2>
            <p id="community-resident-description">这是舞会场景中的非真人灵感角色，仅展示公开搭配标签。</p>
            <div className="resident-tags">
              {selectedResident.publicTags.map((tag) => (
                <span key={tag}>#{tag}</span>
              ))}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
