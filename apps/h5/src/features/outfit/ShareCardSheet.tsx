import { useState } from "react";

import { PixelButton } from "../../components/PixelUI";

type ShareCardSheetProps = {
  /** 要分享的像素封面；拿不到就不该打开这个面板。 */
  imageUrl: string;
  title: string;
  /** 系统分享/下载都复用调用方已有的实现，这里不重写一套。 */
  onShare: () => void | Promise<void>;
  onSave: () => void | Promise<void>;
  sharing?: boolean;
  message?: string | null;
  onClose: () => void;
};

/**
 * 「分享图鉴」面板。
 *
 * 关于抖音：H5 里没有任何办法代替用户发布内容。能做的是把图交给系统分享面板
 * ——用户在那里选抖音——或者存进相册再自己发。所以按钮写的是「分享到…」和
 * 「保存到相册」，不写「一键发抖音」，也不显示假的发布成功。
 *
 * 关于扫码：这里不画二维码。画一个扫不出东西的码比不画更糟，所以给的是"复制
 * 链接"，用户拿到的是真的可以打开的地址。
 */
export function ShareCardSheet({
  imageUrl,
  title,
  onShare,
  onSave,
  sharing,
  message,
  onClose
}: ShareCardSheetProps) {
  const [copied, setCopied] = useState<string | null>(null);

  async function copyLink() {
    const link = window.location.href;
    try {
      await navigator.clipboard.writeText(link);
      setCopied("链接已复制，发给朋友就能看同款");
    } catch {
      setCopied("这台设备不让自动复制，请手动复制地址栏链接");
    }
  }

  return (
    <div className="share-card" role="dialog" aria-label="分享图鉴" aria-modal="true">
      <div className="share-card__inner">
        <div className="share-card__paper">
          <span className="share-card__doodle share-card__doodle--star" aria-hidden="true">
            ✦
          </span>
          <span className="share-card__doodle share-card__doodle--heart" aria-hidden="true">
            ♡
          </span>

          <div className="share-card__frame">
            {sharing ? (
              <div className="share-card__frame-busy" role="status">
                正在准备图片…
              </div>
            ) : (
              <img src={imageUrl} alt={`${title}的像素图鉴`} />
            )}
            <span className="share-card__tag">@码上搭 · 我的数字衣橱</span>
          </div>

          <p className="share-card__note">
            图鉴只包含像素形象和公开风格标签，不含原始穿搭照片。
          </p>

          {message || copied ? (
            <p className="share-card__note" role="status">
              {message ?? copied}
            </p>
          ) : null}

          <div className="profile__actions">
            <PixelButton
              variant="primary"
              disabled={sharing}
              onClick={() => void onShare()}
            >
              分享到…
            </PixelButton>
            <PixelButton
              variant="accent"
              disabled={sharing}
              onClick={() => void onSave()}
            >
              保存到相册
            </PixelButton>
            <PixelButton variant="ghost" onClick={() => void copyLink()}>
              复制链接看同款
            </PixelButton>
          </div>

          <div style={{ marginTop: "var(--px-2)" }}>
            <PixelButton variant="ghost" onClick={onClose}>
              关闭
            </PixelButton>
          </div>
        </div>
      </div>
    </div>
  );
}
