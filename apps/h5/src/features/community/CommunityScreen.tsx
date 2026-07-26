import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { validateImage } from "../../api/client";
import { PixelWorldCanvas, type PixelWorldHandle } from "./PixelWorldCanvas";
import { useParty, type LookSpriteSource } from "./useParty";
import {
  createCommunityScene,
  lookById,
  randomOtherLook,
  reactToSelectedLook,
  replaceMyLook,
  selectPartyLook,
  selectedPartyLook,
  toggleSavedLook,
  wearLook,
  wornLook,
  type CommunityAvatarSource,
  type CommunityScene,
  type PartyLook,
  type PartyReaction
} from "./communityScene";
import { guestPersonas, personaById } from "./world/guests";
import { sceneMaps } from "./world/sceneMap";
import {
  CARD_HEIGHT,
  CARD_WIDTH,
  downloadBlob,
  drawShareCard,
  SCENE_RECT
} from "./world/shareMoment";
import { recordClip, supportedClipType } from "./world/recordMoment";
import {
  actorById,
  freezeParty,
  gatherForPhoto,
  playerOf,
  resumeParty,
  STAGE_GATHER_RADIUS,
  sayAsPlayer,
  startRunway
} from "./world/simulation";
import "./community.css";

export type { CommunityAvatarSource } from "./communityScene";
export { defaultCommunityAvatar } from "./communityScene";

const reactionLabels: Record<PartyReaction, { label: string; symbol: string }> = {
  palette: { label: "配色好会", symbol: "◈" },
  layering: { label: "层次感", symbol: "✦" },
  remix: { label: "想抄作业", symbol: "♡" }
};

const phaseCopy: Record<string, { eyebrow: string; title: string }> = {
  mingling: { eyebrow: "自由走动", title: "点地面走动，点角色去打招呼" },
  greeting: { eyebrow: "正在聊天", title: "走开就可以结束这段对话" },
  walking: { eyebrow: "RUNWAY LIVE", title: "沿星光走到舞池中央" },
  posing: { eyebrow: "POSE TIME", title: "定格今晚的主角时刻" },
  frozen: { eyebrow: "FREEZE", title: "画面已定格，可以带走这一刻" }
};

type ShareState = "idle" | "card" | "clip" | "error";

type CommunityScreenProps = {
  avatarSource?: CommunityAvatarSource;
  onExit?: () => void;
  onPublishLook?: (look: PartyLook) => void;
  onSaveInspiration?: (look: PartyLook) => void;
  onReaction?: (look: PartyLook, reaction: PartyReaction) => void;
  onShare?: (look: PartyLook) => void;
};

/** Long enough to read as a moment, short enough to send. */
const CLIP_MS = 3000;
const CLIP_FPS = 24;

export function CommunityScreen({
  avatarSource,
  onExit,
  onPublishLook,
  onSaveInspiration,
  onReaction,
  onShare
}: CommunityScreenProps) {
  const [scene, setScene] = useState<CommunityScene>(() =>
    createCommunityScene(avatarSource)
  );
  const [message, setMessage] = useState(
    "主题走秀舞会：先逛逛，和大家聊两句，再让你的 Look 上台"
  );
  const [shareState, setShareState] = useState<ShareState>("idle");
  const [selectedGuestId, setSelectedGuestId] = useState<string | null>(null);
  const [phaseLabel, setPhaseLabel] = useState("mingling");
  const [immersive, setImmersive] = useState(false);
  const [draft, setDraft] = useState("");
  const [cameraOpen, setCameraOpen] = useState(false);
  // Everyone would crowd the room, so the cast is a deliberate choice.
  const [castIds, setCastIds] = useState<readonly string[]>(() =>
    guestPersonas.slice(0, 4).map((persona) => persona.id)
  );
  const uploadedObjectUrl = useRef<string | null>(null);
  const worldHandle = useRef<PixelWorldHandle>(null);
  const shellRef = useRef<HTMLDivElement>(null);

  const spriteSources = useMemo<LookSpriteSource[]>(
    () =>
      scene.looks.map((look) => ({
        lookId: look.id,
        url: look.assetUrl,
        removeBackdrop: look.needsBackdropRemoval,
        poseRoot: look.poseRoot
      })),
    [scene.looks]
  );

  const party = useParty(
    sceneMaps[0].id,
    scene.wornLookId,
    spriteSources,
    castIds
  );
  const selectedLook = selectedPartyLook(scene);
  const worn = wornLook(scene);
  const selectedGuest = selectedGuestId ? personaById(selectedGuestId) : null;

  const syncPhase = useCallback(() => {
    setPhaseLabel(party.world.phase);
  }, [party.world]);

  // Leaving fullscreen with Esc or a system gesture must not leave the layout
  // stuck in immersive mode.
  useEffect(() => {
    const sync = () => {
      if (!document.fullscreenElement) setImmersive(false);
    };
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);

  // The world changes phase on its own — walking onto the runway, finishing a
  // conversation — so the HUD polls rather than waiting for a button press.
  useEffect(() => {
    const timer = window.setInterval(
      () => setPhaseLabel(party.world.phase),
      200
    );
    return () => window.clearInterval(timer);
  }, [party.world]);

  function announce(text: string) {
    setMessage(text);
    syncPhase();
  }

  /**
   * Full-screen the world. The browser Fullscreen API is unavailable on iOS
   * Safari, so the layout class is what actually enlarges the world and the
   * native call is a bonus when it exists.
   */
  async function toggleImmersive() {
    const next = !immersive;
    setImmersive(next);
    const shell = shellRef.current;
    try {
      if (next && shell?.requestFullscreen) {
        await shell.requestFullscreen();
      } else if (!next && document.fullscreenElement) {
        await document.exitFullscreen();
      }
    } catch {
      // Layout-only immersive mode still applies.
    }
    announce(next ? "已进入全屏世界，再点一次退出" : "已退出全屏");
  }

  /** Guest spots are limited, so inviting a fifth person retires the oldest. */
  function toggleCast(personaId: string) {
    const persona = personaById(personaId);
    if (!persona) return;
    setCastIds((current) => {
      if (current.includes(personaId)) {
        if (current.length === 1) return current;
        announce(`${persona.name} 先离开了`);
        return current.filter((id) => id !== personaId);
      }
      const next = [...current, personaId].slice(-4);
      announce(`${persona.name} 来了`);
      return next;
    });
    setSelectedGuestId(null);
  }

  function dressIn(lookId: string) {
    const next = wearLook(scene, lookId);
    setScene(next);
    party.updatePlayerLook(lookId);
    const look = lookById(next, lookId);
    announce(`已换上：${look?.title ?? "新的 Look"}`);
  }

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
    if (uploadedObjectUrl.current) URL.revokeObjectURL(uploadedObjectUrl.current);
    uploadedObjectUrl.current = nextUrl;
    const next = replaceMyLook(scene, {
      assetUrl: nextUrl,
      label: file.name,
      kind: "local-upload"
    });
    setScene(next);
    setShareState("idle");
    setMessage("已加入衣橱；点它换上，再点「上台走秀」登场");
  }

  function enterStage() {
    startRunway(party.world);
    onPublishLook?.(worn);
    setSelectedGuestId(null);
    setShareState("idle");
    announce("走秀开始：从后台走向舞池中央");
  }

  /** The shutter freezes the frame first, so you choose from a held moment. */
  function openCamera() {
    freezeParty(party.world);
    setCameraOpen(true);
    setShareState("idle");
    announce("画面已定格，选择要带走的合影");
  }

  function closeCamera() {
    resumeParty(party.world);
    setCameraOpen(false);
    announce("已回到舞台");
  }

  function inspectActor(actorId: string | null) {
    party.world.selectedActorId = actorId;
    if (!actorId) {
      setSelectedGuestId(null);
      return;
    }
    const actor = actorById(party.world, actorId);
    const persona = personaById(actorId);
    if (!actor || !persona) return;
    setSelectedGuestId(actorId);
    setScene((current) => selectPartyLook(current, actor.lookId));
    const reason = persona.reasons[party.sceneId];
    announce(`${persona.name}：${reason ?? persona.bio}`);
  }

  function react(reaction: PartyReaction) {
    setScene((current) => reactToSelectedLook(current, reaction));
    onReaction?.(selectedLook, reaction);
    setMessage(`已记录：${reactionLabels[reaction].label} · 仅本次体验`);
  }

  function saveInspiration() {
    if (selectedLook.sourceKind === "my-look") {
      dressIn(selectedLook.id);
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

  /**
   * Only guests actually inside the captured frame may be named. The card must
   * never claim company that is not in the picture.
   */
  function coStars(): string[] {
    const player = playerOf(party.world);
    const halfWidth = (STAGE_GATHER_RADIUS * 3.4) / 2;
    const halfHeight = halfWidth * (CARD_HEIGHT - 360) / (CARD_WIDTH - 48);
    return party.world.actors
      .filter((actor) => actor.kind === "guest")
      .filter(
        (actor) =>
          Math.abs(actor.x - player.x) < halfWidth &&
          Math.abs(actor.y - (player.y - 26)) < halfHeight
      )
      .map((actor) => actor.name)
      .slice(0, 3);
  }

  const settle = () => new Promise((resolve) => window.setTimeout(resolve, 120));

  /**
   * Gets everyone in position before the shutter fires.
   *
   * The runway walk clears guest targets every frame so nobody wanders across
   * the entrance, so the crowd can only be called in once the walk has landed.
   * Bounded, so a stalled canvas fails visibly instead of hanging the button.
   */
  async function settleForPhoto(timeoutMs = 4000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline && party.world.phase === "walking") {
      await settle();
    }
    gatherForPhoto(party.world);
    while (Date.now() < deadline) {
      const stillArriving = party.world.actors.some(
        (actor) => actor.kind === "guest" && actor.target
      );
      if (!stillArriving) return;
      await settle();
    }
  }

  const busy = shareState === "card" || shareState === "clip";
  // Recording needs MediaRecorder; the still card always works without it.
  const clipSupported = useMemo(() => supportedClipType() !== null, []);

  function shareSubject() {
    return {
      theme: scene.theme.title,
      eyebrow: scene.theme.eyebrow,
      lookTitle: worn.title,
      withNames: coStars(),
      tags: worn.tags,
      disclaimer: "像素合影 · 预设角色非真人 · 非实时社区"
    };
  }

  function renderCard(): HTMLCanvasElement | null {
    const frame = worldHandle.current?.captureFrame(
      SCENE_RECT.width,
      SCENE_RECT.height
    );
    if (!frame) return null;
    const canvas = document.createElement("canvas");
    drawShareCard(canvas, frame, shareSubject());
    return canvas;
  }

  async function exportCard() {
    if (busy) return;
    setShareState("card");
    setMessage("正在等大家入镜…");
    try {
      await settleForPhoto();
      setMessage("正在生成同框合影…");
      freezeParty(party.world);
      const canvas = renderCard();
      if (!canvas) throw new Error("画面还没有准备好");
      const blob: Blob | null = await new Promise((resolve) =>
        canvas.toBlob((result) => resolve(result), "image/png")
      );
      if (!blob) throw new Error("分享卡导出失败");
      downloadBlob(blob, "stylecapture-style-party.png");
      onShare?.(worn);
      setShareState("idle");
      setCameraOpen(false);
      announce("同框合影已保存");
    } catch {
      setShareState("error");
      setMessage("合影生成失败，请重试");
    }
  }

  /** The caption holds still while the scene inside the frame keeps moving. */
  async function exportClip() {
    if (busy) return;
    setShareState("clip");
    setMessage("正在等大家入镜…");
    try {
      resumeParty(party.world);
      await settleForPhoto();
      setMessage("正在录制合影视频…");
      const clip = await recordClip({
        durationMs: CLIP_MS,
        framesPerSecond: CLIP_FPS,
        width: CARD_WIDTH,
        height: CARD_HEIGHT,
        paint: (context) => {
          const card = renderCard();
          if (card) context.drawImage(card, 0, 0, CARD_WIDTH, CARD_HEIGHT);
        }
      });
      downloadBlob(clip.blob, `stylecapture-style-party.${clip.extension}`);
      onShare?.(worn);
      setShareState("idle");
      setCameraOpen(false);
      announce(
        clip.extension === "mp4"
          ? "合影视频已保存，可直接发到社交平台"
          : "合影视频已保存（WebM 格式）"
      );
    } catch {
      setShareState("error");
      setMessage("视频录制失败，请改用静态合影卡");
    }
  }

  const copy = phaseCopy[phaseLabel] ?? phaseCopy.mingling;

  return (
    <div
      ref={shellRef}
      className={`party-shell${immersive ? " party-shell--immersive" : ""}`}
    >
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
          <span>{party.scene.eyebrow}</span>
          <strong>{party.scene.title}</strong>
        </div>
        <span className="party-live-badge">互动 Demo</span>
      </header>

      <div className="party-world">
        <PixelWorldCanvas
          key={party.worldVersion}
          world={party.world}
          sprites={party.sprites}
          handleRef={worldHandle}
          onSelectActor={inspectActor}
          onWalk={syncPhase}
        />
        <div className="party-world__hud">
          <span>{copy.eyebrow}</span>
          <strong>{copy.title}</strong>
        </div>
        <button
          className="party-world__fullscreen"
          type="button"
          aria-pressed={immersive}
          aria-label={immersive ? "退出全屏世界" : "进入全屏世界"}
          onClick={() => void toggleImmersive()}
        >
          {immersive ? "⤡" : "⤢"}
        </button>
        <button
          className="party-camera"
          type="button"
          aria-expanded={cameraOpen}
          aria-label="拍合影"
          onClick={openCamera}
        >
          <span aria-hidden="true">📷</span>
        </button>
        {cameraOpen ? (
          <div className="party-camera__sheet" role="group" aria-label="合影选项">
            <p>
              <strong>画面已定格</strong>
              <small>合影只含像素形象和风格标签</small>
            </p>
            <button
              type="button"
              className="party-camera__primary"
              disabled={busy || !clipSupported}
              onClick={() => void exportClip()}
            >
              {shareState === "clip"
                ? "正在录制…"
                : clipSupported
                  ? "合影视频 · 3 秒"
                  : "此浏览器不支持录像"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void exportCard()}
            >
              {shareState === "card" ? "正在生成…" : "静态合影卡"}
            </button>
            <button type="button" disabled={busy} onClick={closeCamera}>
              继续舞会
            </button>
            {shareState === "error" ? (
              <p className="party-error" role="alert">
                生成失败，请重试
              </p>
            ) : null}
          </div>
        ) : null}
        <p className="party-world__note">
          {party.scene.occasion} · 预设角色非真人 · 非实时社区
        </p>
      </div>

      <p className="party-status" role="status">
        {message}
      </p>

      {party.failedLookIds.length ? (
        <p className="party-error" role="alert">
          有 {party.failedLookIds.length} 套 Look 没能加载，换一张图片再试
        </p>
      ) : null}

      <section className="party-dock" aria-label="舞会控制">
        <div className="party-actions">
          <button
            className="party-primary"
            type="button"
            aria-label="上台走秀"
            onClick={enterStage}
          >
            <strong>
              {phaseLabel === "posing" ? "再走一遍" : "上台走秀"}
            </strong>
            <small>从后台走到舞池中央</small>
          </button>
          <form
            className="party-say"
            onSubmit={(event) => {
              event.preventDefault();
              if (!sayAsPlayer(party.world, draft)) return;
              setDraft("");
              announce(`你说：${draft.trim()}`);
            }}
          >
            <input
              value={draft}
              maxLength={40}
              placeholder="说点什么…"
              aria-label="说一句话"
              onChange={(event) => setDraft(event.target.value)}
            />
            <button type="submit" disabled={!draft.trim()}>
              说
            </button>
          </form>
        </div>

        <div className="party-wardrobe" aria-label="我今晚的 Look">
          <div className="party-section-heading">
            <p className="party-kicker">我今晚的 LOOK</p>
            <button
              type="button"
              onClick={() => {
                const next = randomOtherLook(scene, Math.random());
                setScene(next);
                party.updatePlayerLook(next.wornLookId);
                announce(
                  `随机换上：${lookById(next, next.wornLookId)?.title ?? ""}`
                );
              }}
            >
              随机一套
            </button>
          </div>
          <div className="party-rail">
            {scene.looks.map((look) => (
              <button
                key={look.id}
                type="button"
                className="party-rail__item"
                aria-label={`换上${look.title}`}
                aria-pressed={look.id === scene.wornLookId}
                onClick={() => dressIn(look.id)}
              >
                <img src={look.assetUrl} alt="" aria-hidden="true" />
                <span>{look.title}</span>
                {look.poseRoot ? (
                  <b className="party-rail__badge">会动</b>
                ) : null}
              </button>
            ))}
            <label className="party-rail__item party-rail__upload">
              <input
                id="party-pixel-look-upload"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                aria-label="上传我的像素 Look"
                onChange={(event) => {
                  uploadPixelLook(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
              <span aria-hidden="true">＋</span>
              <span>上传</span>
            </label>
          </div>
        </div>

        <div className="party-cast" aria-label="选择在场的人">
          <div className="party-section-heading">
            <p className="party-kicker">今晚在场 · {castIds.length} 人</p>
            <small>最多 4 人同时在场</small>
          </div>
          <div className="party-cast__list">
            {guestPersonas.map((persona) => {
              const look = lookById(scene, persona.lookId);
              const active = castIds.includes(persona.id);
              return (
                <button
                  key={persona.id}
                  type="button"
                  className="party-cast__item"
                  aria-pressed={active}
                  aria-label={`${active ? "请走" : "邀请"}${persona.name}`}
                  onClick={() => toggleCast(persona.id)}
                >
                  <img src={look?.assetUrl} alt="" aria-hidden="true" />
                  <span>{persona.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="party-scenes" aria-label="切换场景">
          {sceneMaps.map((map) => (
            <button
              key={map.id}
              type="button"
              aria-pressed={map.id === party.sceneId}
              onClick={() => {
                party.setSceneId(map.id);
                announce(`${map.occasion}：${map.premise}`);
              }}
            >
              {map.title}
            </button>
          ))}
        </div>

        <section className="party-social" aria-labelledby="party-social-title">
          <div className="party-section-heading">
            <div>
              <p className="party-kicker">
                {selectedGuest ? "客人的 LOOK" : "LOOK SOCIAL"}
              </p>
              <h2 id="party-social-title">
                {selectedGuest
                  ? `${selectedGuest.name} · ${selectedLook.title}`
                  : selectedLook.title}
              </h2>
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
                ? "换上这套"
                : scene.savedLookIds.includes(selectedLook.id)
                  ? "已收藏"
                  : "收藏灵感"}
            </button>
          </div>
          <p>{selectedGuest ? selectedGuest.bio : selectedLook.description}</p>
          {selectedGuest ? (
            <p className="party-social__reason">
              {selectedGuest.reasons[party.sceneId] ?? party.scene.premise}
            </p>
          ) : null}
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

        <footer className="party-credit">
          场景复用 Pixel Agents 开源素材与 Canvas 循环 · MIT
        </footer>
      </section>
    </div>
  );
}
