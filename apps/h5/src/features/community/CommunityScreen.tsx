import { motion } from "motion/react";
import { useMemo, useRef, useState } from "react";

import {
  completeEntrance,
  createCommunityScene,
  defaultCommunityAvatar,
  enterMyLook,
  reactToSelectedLook,
  selectPartyLook,
  selectedPartyLook,
  toggleSavedLook,
  type CommunityAvatarSource,
  type PartyLook,
  type PartyReaction
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
      if (image.naturalWidth > 0) resolve();
      else reject(new Error("像素 Look 图片不可用"));
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
  context.fillStyle = "#fff9fb";
  context.fillRect(0, 0, 720, 960);
  context.fillStyle = "#eadcff";
  context.fillRect(28, 28, 664, 904);
  context.fillStyle = "#fff8fb";
  context.fillRect(42, 42, 636, 876);

  context.fillStyle = "#cf8daf";
  context.fillRect(42, 42, 12, 876);
  context.fillStyle = "#76507e";
  context.font = "800 26px sans-serif";
  context.fillText("STYLECAPTURE", 76, 83);
  context.fillStyle = "#a27ba9";
  context.font = "700 20px sans-serif";
  context.fillText("PIXEL STYLE PARTY", 76, 116);

  context.fillStyle = "#f1e6f8";
  context.fillRect(500, 58, 142, 48);
  context.fillStyle = "#7d5a84";
  context.font = "700 18px sans-serif";
  context.fillText("THEME 01", 524, 89);

  context.fillStyle = "#fffdfd";
  context.fillRect(70, 145, 580, 566);
  context.fillStyle = "#f1d5e4";
  context.fillRect(70, 145, 580, 8);
  context.fillRect(70, 703, 580, 8);
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
  context.fillText("本期主题 · 花房晚宴", 94, 772);
  context.textAlign = "left";
  context.fillStyle = "#3d2946";
  context.font = "800 42px sans-serif";
  context.fillText(look.title, 94, 823);
  context.fillStyle = "#7c687f";
  context.font = "21px sans-serif";
  context.fillText(look.tags.slice(0, 3).map((tag) => `#${tag}`).join("  "), 94, 858);
  context.fillStyle = "#76507e";
  context.font = "800 20px sans-serif";
  context.fillText("带你的像素 Look 来参加 →", 76, 906);
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
  const [message, setMessage] = useState(
    "先逛精选 Look，再带自己的搭配登场"
  );
  const [shareState, setShareState] = useState<ShareState>("idle");
  const shareCanvas = useRef<HTMLCanvasElement>(null);
  const stageImage = useRef<HTMLImageElement>(null);
  const selectedLook = selectedPartyLook(scene);

  function chooseLook(lookId: string) {
    setScene((current) => selectPartyLook(current, lookId));
    setShareState("idle");
    setMessage("已切换 Look，看看它为什么适合今晚");
  }

  function enterStage() {
    setScene((current) => completeEntrance(enterMyLook(current)));
    const ownLook = scene.looks.find((look) => look.id === scene.myLookId);
    if (ownLook) onPublishLook?.(ownLook);
    setShareState("idle");
    setMessage("你的 Look 已站上主题舞台 · 仅本次体验");
  }

  function react(reaction: PartyReaction) {
    setScene((current) => reactToSelectedLook(current, reaction));
    onReaction?.(selectedLook, reaction);
    setMessage(
      `已记录：${reactionLabels[reaction].label} · 仅本次体验`
    );
  }

  function saveInspiration() {
    if (selectedLook.sourceKind === "my-look") {
      const firstCurated = scene.looks.find(
        (look) => look.sourceKind === "curated-seed"
      );
      if (firstCurated) chooseLook(firstCurated.id);
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
      const image = stageImage.current;
      if (!canvas || !image) throw new Error("分享卡还没有准备好");
      await waitForImage(image);
      drawShareCard(canvas, image, selectedLook);
      const link = document.createElement("a");
      link.href = canvas.toDataURL("image/png");
      link.download = "stylecapture-style-party.png";
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
          <strong>Style Party</strong>
        </div>
        <span className="party-demo-badge">概念验证</span>
      </header>

      <main className="party-content">
        <section className="party-intro" aria-labelledby="party-theme-title">
          <div className="party-intro__copy">
            <p className="party-kicker">本期主题</p>
            <h1 id="party-theme-title">{scene.theme.title}</h1>
            <p>{scene.theme.prompt}</p>
          </div>
          <div className="party-intro__promise">
            <span aria-hidden="true">✦</span>
            <p>{scene.theme.promise}</p>
          </div>
          <p className="party-truth-label">
            主题陈列室 Demo · 非实时社区
          </p>
        </section>

        <section className="party-stage" aria-label="花房主题舞台">
          <div className="party-stage__curtain party-stage__curtain--left" />
          <div className="party-stage__curtain party-stage__curtain--right" />
          <div className="party-stage__window" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>
          <div className="party-stage__lights" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>
          <div className="party-stage__flowers" aria-hidden="true">
            <i>✿</i>
            <i>❀</i>
            <i>✿</i>
            <i>❀</i>
          </div>

          <motion.div
            key={selectedLook.id}
            className={`party-stage__look ${
              selectedLook.sourceKind === "my-look" ? "is-my-look" : ""
            } ${selectedLook.presentation === "avatar" ? "is-avatar-art" : ""}`}
            initial={{ opacity: 0, x: 42, scale: 0.94 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            transition={{ duration: 0.38, ease: "easeOut" }}
          >
            <span className="party-stage__source">
              {selectedLook.sourceLabel}
            </span>
            <div className="party-stage__portrait">
              <img
                ref={stageImage}
                src={selectedLook.assetUrl}
                alt={selectedLook.alt}
              />
              {scene.selectedReaction ? (
                <motion.span
                  className="party-stage__reaction"
                  initial={{ opacity: 0, y: 12, scale: 0.6 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  aria-hidden="true"
                >
                  {reactionLabels[scene.selectedReaction].symbol}
                </motion.span>
              ) : null}
            </div>
            <div className="party-stage__caption">
              <span>
                {selectedLook.sourceKind === "my-look"
                  ? "MY LOOK"
                  : "CURATED LOOK"}
              </span>
              <h2>{selectedLook.title}</h2>
              <div>
                {selectedLook.tags.map((tag) => (
                  <small key={tag}>#{tag}</small>
                ))}
              </div>
            </div>
          </motion.div>
          <div className="party-stage__floor" aria-hidden="true" />
        </section>

        <p className="party-status" role="status">
          {message}
        </p>

        <div className="party-primary-actions">
          <button
            className="party-primary"
            type="button"
            aria-label="带我的 Look 登场"
            onClick={enterStage}
          >
            <span aria-hidden="true">✦</span>
            <span>
              <small>投稿到本期主题</small>
              带我的 Look 登场
            </span>
          </button>
          <button
            className="party-secondary"
            type="button"
            aria-pressed={
              selectedLook.sourceKind === "curated-seed"
                ? scene.savedLookIds.includes(selectedLook.id)
                : undefined
            }
            onClick={saveInspiration}
          >
            {selectedLook.sourceKind === "my-look"
              ? "继续浏览精选 Look"
              : scene.savedLookIds.includes(selectedLook.id)
                ? "已收藏这个搭配灵感"
                : "收藏这个搭配灵感"}
          </button>
        </div>

        <section className="party-reactions" aria-labelledby="party-reaction-title">
          <div>
            <p className="party-kicker">STYLE REACTION</p>
            <h2 id="party-reaction-title">喜欢它哪里？</h2>
          </div>
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
          <small>此 Demo 仅记录本次体验，不展示虚构点赞数。</small>
        </section>

        <section className="party-lookbook" aria-labelledby="party-lookbook-title">
          <div className="party-section-heading">
            <div>
              <p className="party-kicker">LOOKBOOK</p>
              <h2 id="party-lookbook-title">今晚的灵感角色</h2>
            </div>
            <span>滑动浏览</span>
          </div>
          <div className="party-lookbook__rail">
            {scene.looks
              .filter((look) => look.sourceKind === "curated-seed")
              .map((look) => (
                <button
                  key={look.id}
                  type="button"
                  aria-label={`查看${look.title}`}
                  aria-pressed={look.id === selectedLook.id}
                  onClick={() => chooseLook(look.id)}
                >
                  <img src={look.assetUrl} alt="" />
                  <span>{look.sourceLabel}</span>
                  <strong>{look.title}</strong>
                  <small>{look.tags.slice(0, 2).join(" · ")}</small>
                </button>
              ))}
          </div>
        </section>

        <section className="party-look-note" aria-label="当前 Look 搭配解读">
          <div>
            <p className="party-kicker">WHY IT WORKS</p>
            <h2>{selectedLook.title}</h2>
            <p>{selectedLook.description}</p>
          </div>
          <ol>
            {selectedLook.outfitFormula.map((item, index) => (
              <li key={item}>
                <span>0{index + 1}</span>
                {item}
              </li>
            ))}
          </ol>
        </section>

        <section className="party-share" aria-labelledby="party-share-title">
          <div className="party-share__icon" aria-hidden="true">
            ♡
          </div>
          <div>
            <p className="party-kicker">SHARE-SAFE</p>
            <h2 id="party-share-title">带走这张像素邀请函</h2>
            <p>分享卡只使用当前可见像素图和公开风格标签，不包含原始穿搭照片。</p>
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
          <canvas ref={shareCanvas} aria-hidden="true" />
        </section>
      </main>

    </div>
  );
}
