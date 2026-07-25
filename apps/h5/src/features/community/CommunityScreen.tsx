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
  returnAvatarBackstage,
  selectReaction,
  sendAvatarToRunway,
  type CommunityReaction,
  type CommunityResident,
  type CommunityScene,
  type PixelDollProfile
} from "./communityScene";

const reactionLabels: Record<CommunityReaction, { label: string; symbol: string }> = {
  heart: { label: "心动", symbol: "♥" },
  sparkle: { label: "闪闪", symbol: "✦" },
  music: { label: "音乐", symbol: "♫" },
  wave: { label: "挥挥", symbol: "⌁" }
};

type SceneStyle = CSSProperties & Record<string, string>;

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

function dollStyle(doll: PixelDollProfile): SceneStyle {
  return {
    "--doll-hair": doll.hair,
    "--doll-skin": doll.skin,
    "--doll-outfit": doll.outfit,
    "--doll-trim": doll.trim,
    "--doll-blush": doll.blush,
    "--doll-shoes": doll.shoes
  };
}

function PixelDoll({ doll, className = "" }: { doll: PixelDollProfile; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`pixel-doll ${className}`.trim()}
      data-accessory={doll.accessory}
      data-dress={doll.dressShape}
      data-hair={doll.hairStyle}
      style={dollStyle(doll)}
    >
      <i className="pixel-doll__hair" />
      <i className="pixel-doll__bangs" />
      <i className="pixel-doll__face" />
      <i className="pixel-doll__top" />
      <i className="pixel-doll__skirt" />
      <i className="pixel-doll__arms" />
      <i className="pixel-doll__legs" />
      <i className="pixel-doll__shoes" />
      <i className="pixel-doll__accessory" />
    </span>
  );
}

function drawPixelDoll(
  context: CanvasRenderingContext2D,
  doll: PixelDollProfile,
  x: number,
  y: number,
  scale: number
) {
  const pixel = (left: number, top: number, width: number, height: number, color: string) => {
    context.fillStyle = color;
    context.fillRect(x + left * scale, y + top * scale, width * scale, height * scale);
  };

  pixel(3, 0, 7, 2, doll.hair);
  pixel(2, 2, 9, 3, doll.hair);
  pixel(1, 4, 3, 8, doll.hair);
  pixel(9, 4, 3, 8, doll.hair);
  if (doll.hairStyle === "curly") {
    pixel(0, 8, 2, 2, doll.hair);
    pixel(10, 9, 2, 2, doll.hair);
    pixel(1, 12, 2, 2, doll.hair);
  }
  if (doll.hairStyle === "bob") {
    pixel(2, 9, 8, 2, doll.hair);
  }
  if (doll.hairStyle === "twin") {
    pixel(0, 6, 2, 5, doll.hair);
    pixel(11, 6, 2, 5, doll.hair);
  }
  pixel(4, 3, 5, 5, doll.skin);
  pixel(3, 4, 1, 2, doll.skin);
  pixel(9, 4, 1, 2, doll.skin);
  pixel(4, 3, 5, 1, doll.hair);
  pixel(5, 5, 1, 1, "#2d2438");
  pixel(8, 5, 1, 1, "#2d2438");
  pixel(5, 7, 1, 1, doll.blush);
  pixel(8, 7, 1, 1, doll.blush);
  pixel(6, 8, 2, 1, "#d86084");
  pixel(4, 9, 5, 4, doll.outfit);
  pixel(5, 9, 1, 1, doll.trim);
  pixel(7, 9, 1, 1, doll.trim);
  pixel(2, 10, 2, 5, doll.skin);
  pixel(9, 10, 2, 5, doll.skin);
  pixel(2, 10, 1, 3, doll.outfit);
  pixel(10, 10, 1, 3, doll.outfit);
  if (doll.dressShape === "jacket") {
    pixel(3, 13, 7, 3, doll.outfit);
    pixel(6, 10, 1, 6, doll.trim);
  } else if (doll.dressShape === "two-piece") {
    pixel(3, 14, 7, 2, doll.outfit);
    pixel(4, 13, 5, 1, doll.trim);
  } else {
    pixel(3, 13, 7, 2, doll.outfit);
    pixel(2, 15, 9, 3, doll.outfit);
    if (doll.dressShape === "pleated") {
      pixel(4, 14, 1, 4, doll.trim);
      pixel(7, 14, 1, 4, doll.trim);
    }
  }
  pixel(4, 18, 1, 4, doll.skin);
  pixel(8, 18, 1, 4, doll.skin);
  pixel(3, 22, 2, 1, doll.shoes);
  pixel(8, 22, 2, 1, doll.shoes);

  if (doll.accessory === "beret") pixel(3, -1, 5, 1, doll.outfit);
  if (doll.accessory === "handbag") pixel(10, 14, 2, 3, doll.trim);
  if (doll.accessory === "necklace") pixel(6, 9, 2, 1, "#fbdb83");
  if (doll.accessory === "ribbon" || doll.accessory === "bow") {
    pixel(0, 0, 2, 1, doll.trim);
    pixel(1, 1, 1, 1, doll.trim);
  }
}

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
  if (avatarSource.kind === "public-render-artifact" && avatarImage.complete && avatarImage.naturalWidth) {
    context.drawImage(avatarImage, avatarX, avatarY, 92, 92);
  } else {
    context.imageSmoothingEnabled = false;
    drawPixelDoll(context, scene.avatar.doll, avatarX + 2, avatarY + 6, 5);
  }
  context.fillStyle = "#f8f2ff";
  context.font = "700 34px sans-serif";
  context.fillText("STYLECAPTURE", 64, 66);
  context.font = "700 52px sans-serif";
  context.fillText("今晚舞会", 64, 824);
  context.font = "30px sans-serif";
  context.fillText(scene.avatar.isDancing ? "我的搭配正在舞池发光" : "我的搭配来到像素舞会", 64, 874);
  context.fillText(`${scene.runway.isShowing ? "正在走秀" : "等待上台"} · 喝彩 ${scene.runway.applause}`, 64, 918);
  context.fillText(
    `${scene.avatar.reaction ? reactionLabels[scene.avatar.reaction].symbol : "✦"} ${avatarSource.label} · #StyleCapture`,
    64,
    952
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

  function takeRunwayTurn() {
    setScene((current) => {
      const next = current.runway.isShowing ? returnAvatarBackstage(current) : sendAvatarToRunway(current);
      setMessage(next.runway.isShowing ? "正在走秀" : "已回到后台");
      return next;
    });
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
        <span
          className="community-online"
          aria-label={`当前有 ${scene.audience.length + scene.residents.length + 1} 个像素场景角色`}
        >
          {scene.audience.length + scene.residents.length + 1} 个像素角色
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
          <div className="runway-audience" aria-label="像素观众" role="region">
            {scene.audience.map((doll, index) => (
              <PixelDoll key={`audience-${index}`} className="pixel-doll--audience" doll={doll} />
            ))}
          </div>
          <div className="runway-lookboard" aria-label="走秀看板" role="region">
            <span>{scene.runway.isShowing ? "正在走秀" : "等待上台"}</span>
            <strong>{scene.runway.isShowing ? avatarSource.label : "今晚空位"}</strong>
            <small>喝彩 {scene.runway.applause}</small>
          </div>
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
              <PixelDoll doll={resident.doll} />
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
            <PixelDoll doll={scene.avatar.doll} className="pixel-doll--me" />
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

        <div className="community-runway-controls">
          <button type="button" onClick={takeRunwayTurn}>
            {scene.runway.isShowing ? "回到后台" : "轮到我上台"}
          </button>
          <span>当前喝彩 {scene.runway.applause}</span>
        </div>

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
        <img ref={avatarImage} src={avatarSource.assetUrl} alt="" className="community-share__avatar-source" />
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
