import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { validateImage } from "../../api/client";
import { PixelBallroomCanvas } from "./PixelBallroomCanvas";
import { PixelGuest } from "./PixelGuest";
import {
  completeEntrance,
  createCommunityScene,
  defaultCommunityAvatar,
  enterMyLook,
  reactToSelectedLook,
  replaceMyLook,
  selectPartyLook,
  selectedPartyLook,
  startDance,
  toggleSavedLook,
  type CommunityAvatarSource,
  type PartyLook,
  type PartyReaction,
  type PartyStage
} from "./communityScene";
import "./community.css";

export type { CommunityAvatarSource } from "./communityScene";
export { defaultCommunityAvatar } from "./communityScene";

const reactionLabels: Record<
  PartyReaction,
  { label: string; symbol: string }
> = {
  palette: { label: "配色好会", symbol: "◈" },
  layering: { label: "层次感", symbol: "✦" },
  remix: { label: "想抄作业", symbol: "♡" }
};

const stageCopy: Record<PartyStage, { eyebrow: string; title: string }> = {
  gallery: { eyebrow: "正在逛场", title: "先看看今晚的 Look" },
  backstage: { eyebrow: "后台准备", title: "你的 Look 等待登场" },
  runway: { eyebrow: "RUNWAY LIVE", title: "沿星光走到舞池中央" },
  spotlight: { eyebrow: "POSE TIME", title: "定格今晚的主角时刻" },
  dance: { eyebrow: "DANCE MODE", title: "和灵感角色一起动起来" }
};

type ShareState = "idle" | "loading" | "ready" | "error";

type CommunityScreenProps = {
  avatarSource?: CommunityAvatarSource;
  onExit?: () => void;
  onPublishLook?: (look: PartyLook) => void;
  onSaveInspiration?: (look: PartyLook) => void;
  onReaction?: (look: PartyLook, reaction: PartyReaction) => void;
  onShare?: (look: PartyLook) => void;
};

function waitForImage(image: HTMLImageElement): Promise<void> {
  if (image.complete) {
    return image.naturalWidth > 0
      ? Promise.resolve()
      : Promise.reject(new Error("像素 Look 图片不可用"));
  }
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error("像素 Look 加载超时"));
    }, 5_000);
    const cleanup = () => {
      window.clearTimeout(timeout);
      image.removeEventListener("load", handleLoad);
      image.removeEventListener("error", handleError);
    };
    const handleLoad = () => {
      cleanup();
      image.naturalWidth > 0
        ? resolve()
        : reject(new Error("像素 Look 图片不可用"));
    };
    const handleError = () => {
      cleanup();
      reject(new Error("像素 Look 加载失败"));
    };
    image.addEventListener("load", handleLoad, { once: true });
    image.addEventListener("error", handleError, { once: true });
  });
}

function drawContainedImage(
  context: CanvasRenderingContext2D,
  image: HTMLImageElement,
  box: { x: number; y: number; width: number; height: number }
) {
  const imageRatio = image.naturalWidth / image.naturalHeight;
  const boxRatio = box.width / box.height;
  const width = imageRatio > boxRatio ? box.width : box.height * imageRatio;
  const height = imageRatio > boxRatio ? box.width / imageRatio : box.height;
  context.drawImage(
    image,
    box.x + (box.width - width) / 2,
    box.y + (box.height - height) / 2,
    width,
    height
  );
}

export function drawShareCard(
  canvas: HTMLCanvasElement,
  image: HTMLImageElement,
  look: PartyLook
) {
  const context = canvas.getContext("2d");
  if (!context) throw new Error("浏览器不支持分享卡绘制");
  if (image.naturalWidth <= 0 || image.naturalHeight <= 0) {
    throw new Error("像素 Look 还没有加载完成");
  }

  canvas.width = 720;
  canvas.height = 960;
  context.fillStyle = "#251c3c";
  context.fillRect(0, 0, 720, 960);
  context.fillStyle = "#f5c3d8";
  context.fillRect(28, 28, 664, 904);
  context.fillStyle = "#fff8fb";
  context.fillRect(42, 42, 636, 876);
  context.fillStyle = "#6e4b88";
  context.font = "800 26px sans-serif";
  context.fillText("STYLECAPTURE", 76, 83);
  context.fillStyle = "#b06f9b";
  context.font = "700 20px sans-serif";
  context.fillText("PIXEL RUNWAY BALL", 76, 116);
  context.fillStyle = "#eee4fa";
  context.fillRect(70, 145, 580, 566);
  drawContainedImage(context, image, {
    x: 86,
    y: 161,
    width: 548,
    height: 526
  });
  context.fillStyle = "#fff";
  context.fillRect(70, 735, 580, 151);
  context.fillStyle = "#9a6aa8";
  context.font = "800 18px sans-serif";
  context.fillText("本期主题 · 花房夜宴", 94, 772);
  context.fillStyle = "#3d2946";
  context.font = "800 42px sans-serif";
  context.fillText(look.title, 94, 823);
  context.fillStyle = "#7c687f";
  context.font = "21px sans-serif";
  context.fillText(
    look.tags.slice(0, 3).map((tag) => `#${tag}`).join("  "),
    94,
    858
  );
  context.fillStyle = "#76507e";
  context.font = "800 20px sans-serif";
  context.fillText("带你的像素 Look 来走秀 →", 76, 906);
}

function performerAnimation(stage: PartyStage, danceStep: number) {
  if (stage === "runway") {
    return {
      x: [-112, -52, 0],
      y: [82, 20, -34],
      scale: [0.72, 0.9, 1.08],
      rotate: [0, -2, 0]
    };
  }
  if (stage === "spotlight") {
    return { x: 0, y: -34, scale: 1.08, rotate: danceStep % 2 ? -3 : 3 };
  }
  if (stage === "dance") {
    return {
      x: [0, -18, 18, 0],
      y: [-34, -54, -34, -48, -34],
      scale: [1.08, 1.12, 1.08],
      rotate: danceStep % 2 ? [0, -7, 7, 0] : [0, 7, -7, 0]
    };
  }
  return { x: -112, y: 82, scale: 0.72, rotate: 0 };
}

export function CommunityScreen({
  avatarSource = defaultCommunityAvatar,
  onExit,
  onPublishLook,
  onSaveInspiration,
  onReaction,
  onShare
}: CommunityScreenProps) {
  const initialScene = useMemo(
    () => createCommunityScene(avatarSource),
    [avatarSource]
  );
  const [scene, setScene] = useState(initialScene);
  const [message, setMessage] = useState("先逛灵感，再让自己的像素 Look 上台");
  const [shareState, setShareState] = useState<ShareState>("idle");
  const [danceStep, setDanceStep] = useState(0);
  const shareCanvas = useRef<HTMLCanvasElement>(null);
  const shareImage = useRef<HTMLImageElement>(null);
  const uploadedObjectUrl = useRef<string | null>(null);
  const runwayTimer = useRef<number | null>(null);
  const selectedLook = selectedPartyLook(scene);
  const ownLook =
    scene.looks.find((look) => look.id === scene.myLookId) ?? selectedLook;
  const curatedLooks = scene.looks.filter(
    (look) => look.sourceKind === "curated-seed"
  );

  useEffect(
    () => () => {
      if (uploadedObjectUrl.current) {
        URL.revokeObjectURL(uploadedObjectUrl.current);
      }
      if (runwayTimer.current) window.clearTimeout(runwayTimer.current);
    },
    []
  );

  function uploadPixelLook(file: File | undefined) {
    if (!file) return;
    const validationError = validateImage(file);
    if (validationError) {
      setMessage(validationError);
      return;
    }
    const browserPreviewable =
      ["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      (!file.type && /\.(png|jpe?g|webp)$/i.test(file.name));
    if (!browserPreviewable) {
      setMessage("当前舞台仅支持浏览器可预览的 PNG、JPG 或 WebP");
      return;
    }
    const nextUrl = URL.createObjectURL(file);
    if (uploadedObjectUrl.current) {
      URL.revokeObjectURL(uploadedObjectUrl.current);
    }
    uploadedObjectUrl.current = nextUrl;
    setScene((current) =>
      replaceMyLook(current, {
        assetUrl: nextUrl,
        label: file.name,
        kind: "local-upload",
        presentation: "avatar"
      })
    );
    setShareState("idle");
    setMessage("已在后台预览；点击“上台走秀”才会登场");
  }

  function chooseLook(lookId: string) {
    setScene((current) => selectPartyLook(current, lookId));
    setShareState("idle");
    setMessage("已切换灵感 Look，可以收藏或送出风格回应");
  }

  function enterStage() {
    if (runwayTimer.current) window.clearTimeout(runwayTimer.current);
    setScene((current) => enterMyLook(current));
    onPublishLook?.(ownLook);
    setShareState("idle");
    setMessage("走秀开始：从后台走向舞池中央");
    runwayTimer.current = window.setTimeout(() => {
      setScene((current) => completeEntrance(current));
      setMessage("已到达主舞台：摆个 Pose，或者加入舞会");
    }, 1_650);
  }

  function dance() {
    setDanceStep((step) => step + 1);
    setScene((current) => startDance(current));
    setMessage(
      scene.stage === "dance" ? "换了一个舞步 ✦" : "舞会模式已开启 ✦"
    );
  }

  function react(reaction: PartyReaction) {
    setScene((current) => reactToSelectedLook(current, reaction));
    onReaction?.(selectedLook, reaction);
    setMessage(`已记录：${reactionLabels[reaction].label} · 仅本次体验`);
  }

  function saveInspiration() {
    if (selectedLook.sourceKind === "my-look") {
      chooseLook(curatedLooks[0]?.id ?? scene.myLookId);
      return;
    }
    const wasSaved = scene.savedLookIds.includes(selectedLook.id);
    setScene((current) => toggleSavedLook(current, selectedLook.id));
    if (!wasSaved) onSaveInspiration?.(selectedLook);
    setMessage(
      wasSaved
        ? `已取消收藏：${selectedLook.title}`
        : `已收藏：${selectedLook.title} · 仅本次体验`
    );
  }

  async function prepareShareCard() {
    if (shareState === "loading") return;
    setShareState("loading");
    setMessage("正在准备分享卡…");
    try {
      const canvas = shareCanvas.current;
      const image = shareImage.current;
      if (!canvas || !image) throw new Error("分享卡还没有准备好");
      await waitForImage(image);
      drawShareCard(canvas, image, selectedLook);
      const link = document.createElement("a");
      link.href = canvas.toDataURL("image/png");
      link.download = "stylecapture-pixel-runway.png";
      link.click();
      onShare?.(selectedLook);
      setShareState("ready");
      setMessage("分享卡已准备好");
    } catch {
      setShareState("error");
      setMessage("分享卡生成失败，请重试");
    }
  }

  return (
    <div className="party-shell">
      <header className="party-topbar">
        {onExit ? (
          <button
            className="party-back"
            type="button"
            aria-label="返回数字衣橱"
            onClick={onExit}
          >
            ‹
          </button>
        ) : (
          <span className="party-back party-back--placeholder" />
        )}
        <div>
          <span>{scene.theme.eyebrow}</span>
          <strong>{scene.theme.title}</strong>
        </div>
        <span className="party-live-badge">互动 Demo</span>
      </header>

      <main className="party-content">
        <section className="party-intro" aria-labelledby="party-theme-title">
          <p className="party-kicker">PIXEL RUNWAY BALL</p>
          <h1 id="party-theme-title">穿上今晚的 Look，走进舞会</h1>
          <p>
            你的像素搭配不再只是封面：上台走秀、和别人的 Look 互动，
            再把主角时刻分享出去。
          </p>
          <span>精选示例 · 非实时真人社区</span>
        </section>

        <section
          className={`pixel-ballroom is-${scene.stage}`}
          aria-label="花房夜宴像素走秀舞会"
        >
          <PixelBallroomCanvas stage={scene.stage} />
          <div className="pixel-ballroom__hud">
            <span>{stageCopy[scene.stage].eyebrow}</span>
            <strong>{stageCopy[scene.stage].title}</strong>
          </div>
          <div className="pixel-ballroom__audience" aria-label="今晚的灵感角色">
            {curatedLooks.map((look, index) => (
              <button
                key={look.id}
                type="button"
                className={`audience-look audience-look--${index + 1}`}
                aria-label={`查看${look.title}`}
                aria-pressed={look.id === selectedLook.id}
                onClick={() => chooseLook(look.id)}
              >
                <PixelGuest source={look.assetUrl} />
                <span>{look.title}</span>
              </button>
            ))}
          </div>
          <motion.div
            className="pixel-ballroom__performer"
            data-stage={scene.stage}
            animate={performerAnimation(scene.stage, danceStep)}
            transition={
              scene.stage === "dance"
                ? { duration: 1.45, repeat: Infinity, ease: "easeInOut" }
                : scene.stage === "runway"
                  ? { duration: 1.55, times: [0, 0.55, 1], ease: "easeInOut" }
                  : { duration: 0.42, ease: "easeOut" }
            }
          >
            <span>MY LOOK</span>
            <img src={ownLook.assetUrl} alt="我的像素 Look" />
          </motion.div>
          <div className="pixel-ballroom__stage-label">
            <span>{ownLook.sourceLabel}</span>
            <strong>{ownLook.title}</strong>
          </div>
        </section>

        <p className="party-status" role="status">
          {message}
        </p>

        <section className="party-controls" aria-label="走秀控制">
          <input
            id="party-pixel-look-upload"
            className="party-upload__input"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label="上传我的像素 Look"
            onChange={(event) => {
              uploadPixelLook(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <label className="party-upload" htmlFor="party-pixel-look-upload">
            <span aria-hidden="true">＋</span>
            <strong>换成我的像素 Look</strong>
            <small>PNG / JPG / WebP · 只在本机预览</small>
          </label>
          <button
            className="party-primary"
            type="button"
            aria-label="上台走秀"
            onClick={enterStage}
          >
            <span aria-hidden="true">✦</span>
            <strong>
              {scene.stage === "spotlight" || scene.stage === "dance"
                ? "再走一遍"
                : "上台走秀"}
            </strong>
            <small>从后台走到舞池中央</small>
          </button>
          <button
            className="party-dance"
            type="button"
            aria-pressed={scene.stage === "dance"}
            disabled={scene.stage !== "spotlight" && scene.stage !== "dance"}
            onClick={dance}
          >
            {scene.stage === "dance" ? "换一个舞步" : "加入舞会"}
          </button>
        </section>

        <section className="party-social" aria-labelledby="party-social-title">
          <div className="party-section-heading">
            <div>
              <p className="party-kicker">LOOK SOCIAL</p>
              <h2 id="party-social-title">{selectedLook.title}</h2>
              <small>{selectedLook.sourceLabel}</small>
            </div>
            <button
              type="button"
              aria-pressed={
                selectedLook.sourceKind === "curated-seed"
                  ? scene.savedLookIds.includes(selectedLook.id)
                  : undefined
              }
              onClick={saveInspiration}
            >
              {selectedLook.sourceKind === "my-look"
                ? "逛精选"
                : scene.savedLookIds.includes(selectedLook.id)
                  ? "已收藏"
                  : "收藏灵感"}
            </button>
          </div>
          <p>{selectedLook.description}</p>
          <div className="party-reactions__list">
            {scene.reactions.map((reaction) => (
              <button
                key={reaction}
                type="button"
                aria-pressed={scene.selectedReaction === reaction}
                onClick={() => react(reaction)}
              >
                <span aria-hidden="true">{reactionLabels[reaction].symbol}</span>
                {reactionLabels[reaction].label}
              </button>
            ))}
          </div>
          <small>只记录本次体验，不展示虚构点赞数。</small>
        </section>

        <section className="party-share" aria-labelledby="party-share-title">
          <div>
            <p className="party-kicker">SHARE THE MOMENT</p>
            <h2 id="party-share-title">带走你的像素主角时刻</h2>
            <p>分享卡只使用当前像素图和公开风格标签，不包含原始穿搭照片。</p>
          </div>
          <button
            type="button"
            disabled={shareState === "loading"}
            onClick={() => void prepareShareCard()}
          >
            {shareState === "loading"
              ? "正在准备分享卡…"
              : shareState === "error"
                ? "重试生成分享卡"
                : "生成像素分享卡"}
          </button>
          <img
            ref={shareImage}
            className="party-share__source"
            src={selectedLook.assetUrl}
            alt=""
            aria-hidden="true"
          />
          <canvas ref={shareCanvas} aria-hidden="true" />
        </section>

        <footer className="party-credit">
          场景复用 Pixel Agents 开源素材与 Canvas 循环 · MIT
        </footer>
      </main>
    </div>
  );
}
