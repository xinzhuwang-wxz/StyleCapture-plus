import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type ChangeEvent } from "react";

import { ProductApiError, type PixelTrial, validateImage, wardrobeApi } from "../../api/client";
import { PixelButton, PixelSectionHeader } from "../../components/PixelUI";
import { pixelAvatarDataUrl } from "../../utils/pixelAvatar";
import "./profile.css";

interface ProfileScreenProps {
  itemCount: number;
  outfitCount: number;
  onNotice?: (message: string) => void;
}

function messageFor(error: unknown): string {
  if (error instanceof ProductApiError || error instanceof Error) {
    return error.message;
  }
  return "像素形象暂时没有生成，请稍后再试";
}

function trialPreviewUrl(trial: PixelTrial | null): string {
  if (trial?.status === "succeeded" && trial.output_image_url) {
    return `${trial.output_image_url}?v=${encodeURIComponent(trial.updated_at)}`;
  }
  return pixelAvatarDataUrl("user-profile", { size: 180, hat: false });
}

export function ProfileScreen({ itemCount, outfitCount, onNotice }: ProfileScreenProps) {
  const queryClient = useQueryClient();
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const [trialId, setTrialId] = useState<string | null>(null);
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const trialQuery = useQuery({
    queryKey: ["pixel-trial", trialId],
    queryFn: () => wardrobeApi.getPixelTrial(trialId!),
    enabled: trialId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1_500 : false;
    }
  });
  const trial = trialQuery.data ?? null;
  const generating = trial?.status === "queued" || trial?.status === "running";

  const createTrialMutation = useMutation({
    mutationFn: (file: File) =>
      wardrobeApi.createPixelTrial(file, `profile-pixel:${crypto.randomUUID()}`),
    onSuccess: (created) => {
      setTrialId(created.id);
      setError(null);
      onNotice?.("全身照已上传，像素形象正在后台生成；不会加入数字衣橱");
      void queryClient.invalidateQueries({ queryKey: ["pixel-trial", created.id] });
    },
    onError: (unknownError) => {
      setError(messageFor(unknownError));
    }
  });

  const deleteTrialMutation = useMutation({
    mutationFn: (id: string) => wardrobeApi.deletePixelTrial(id),
    onSuccess: () => {
      setTrialId(null);
      setError(null);
      if (localPreviewUrl) {
        URL.revokeObjectURL(localPreviewUrl);
        setLocalPreviewUrl(null);
      }
      onNotice?.("像素形象草稿已删除，衣橱资产没有变化");
    },
    onError: (unknownError) => setError(messageFor(unknownError))
  });

  function handleFileSelect(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const validationError = validateImage(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl);
    setLocalPreviewUrl(URL.createObjectURL(file));
    setError(null);
    createTrialMutation.mutate(file);
  }

  const imageUrl = trialPreviewUrl(trial);
  const statusCopy =
    trial?.status === "succeeded"
      ? "已生成，可作为展示形象"
      : generating
        ? "生成中，可以切走页面"
        : trial?.status === "failed"
          ? "生成失败，可重新上传"
          : "上传全身照，一键生成像素形象";

  return (
    <div className="profile-page">
      <section className="profile__card" aria-label="我的资料">
        <img
          src={imageUrl}
          alt={trial?.status === "succeeded" ? "生成的像素形象" : "默认像素形象"}
          data-pixel="true"
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="pixel-title profile__name">我的 StyleCapture</h1>
          <span className="profile__level">Lv.3 穿搭收藏家</span>
        </div>
        <span className="profile__edit">{statusCopy}</span>
      </section>

      <div className="profile__stats" aria-label="衣橱统计">
        <span>
          <b style={{ color: "var(--pixel-primary-dark)" }}>{itemCount}</b>
          <small>单品</small>
        </span>
        <span>
          <b style={{ color: "var(--pixel-pink-dark)" }}>{outfitCount}</b>
          <small>穿搭</small>
        </span>
        <span>
          <b style={{ color: "var(--pixel-accent-glow)" }}>
            {trial?.status === "succeeded" ? 1 : 0}
          </b>
          <small>像素形象</small>
        </span>
        <span>
          <b style={{ color: "var(--pixel-primary-dark)" }}>
            {generating ? "…" : "0"}
          </b>
          <small>处理中</small>
        </span>
      </div>

      <PixelSectionHeader
        kicker="Try Pixel"
        title="拍自己，生成像素风格图"
        action={
          generating ? <span className="pixel-label">后台生成中…</span> : null
        }
      />

      <section className="profile__pixel-trial">
        <div className="profile__trial-preview">
          {trial?.status === "succeeded" && trial.output_image_url ? (
            <img src={imageUrl} alt="像素形象生成结果" data-pixel="true" />
          ) : localPreviewUrl ? (
            <img src={localPreviewUrl} alt="本次上传的全身照预览" />
          ) : (
            <img
              src={pixelAvatarDataUrl("profile-empty", { size: 260, hat: false })}
              alt="默认像素小人"
              data-pixel="true"
            />
          )}
          <span>
            {trial?.status === "succeeded"
              ? "生成完成"
              : generating
                ? "生成中"
                : "未上传"}
          </span>
        </div>
        <p>
          这条链路只用于快速体验“真人照片 → 像素形象”，不会新增单品或套装；真正入库仍从拍照/相册/Feed 入口完成。
        </p>
        {error ? <div className="profile__error" role="alert">{error}</div> : null}
        {trial?.failure_message ? (
          <div className="profile__error" role="alert">{trial.failure_message}</div>
        ) : null}
        <div className="profile__actions">
          <PixelButton
            variant="primary"
            disabled={createTrialMutation.isPending}
            onClick={() => cameraInputRef.current?.click()}
          >
            拍一张全身照
          </PixelButton>
          <PixelButton
            variant="accent"
            disabled={createTrialMutation.isPending}
            onClick={() => galleryInputRef.current?.click()}
          >
            从相册试试
          </PixelButton>
          {trialId ? (
            <PixelButton
              variant="ghost"
              disabled={deleteTrialMutation.isPending}
              onClick={() => deleteTrialMutation.mutate(trialId)}
            >
              删除草稿
            </PixelButton>
          ) : null}
        </div>
      </section>

      <input
        ref={cameraInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
        capture="user"
        className="visually-hidden"
        aria-label="拍摄全身照生成像素形象"
        onChange={handleFileSelect}
      />
      <input
        ref={galleryInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
        className="visually-hidden"
        aria-label="选择全身照生成像素形象"
        onChange={handleFileSelect}
      />

      <section className="profile__tips">
        <h3 className="pixel-subtitle" style={{ marginBottom: "var(--px-2)" }}>
          使用提示
        </h3>
        <ul>
          <li>这里是体验入口：只生成像素图，不写入数字衣橱。</li>
          <li>想把真实衣服入库，请用底部“添加”或 Feed 圈选入口。</li>
          <li>已保存套装里的“真人试穿”仍在穿搭详情中上传全身照。</li>
        </ul>
      </section>
    </div>
  );
}
