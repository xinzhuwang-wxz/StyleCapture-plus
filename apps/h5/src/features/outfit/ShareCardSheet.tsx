import { createPortal } from "react-dom";

import "./outfit.css";

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
 * 像素封面分享面板。
 *
 * 关于抖音：H5 里没有任何办法代替用户发布内容。能做的是把图交给系统分享面板
 * ——用户在那里选抖音——或者存进相册再自己发。所以按钮写的是「分享到抖音」和
 * 「保存到相册」，不写「一键发抖音」，也不显示假的发布成功。
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
  /*
   * 这层是 position:absolute，它找的是最近的定位祖先。原地渲染时那个祖先在
   * 详情页的滚动内容里，于是弹层落在了卡片下方、跟着内容滚。挂到 .pixel-screen
   * 上才会真的浮在整屏之上，同时不会跑出演示手机的外壳（fixed 会）。
   * 拿不到宿主时（单测里直接渲染组件）就地渲染，行为不变。
   */
  const host =
    typeof document === "undefined"
      ? null
      : document.querySelector(".pixel-screen");

  const sheet = (
    <div className="share-card" role="dialog" aria-label="分享像素封面" aria-modal="true">
      <div className="share-card__inner">
        <div className="share-card__paper">
          <button className="share-card__close" type="button" aria-label="关闭分享" onClick={onClose}>
            ×
          </button>
          <h2>✦ 分享像素封面 ✦</h2>
          <p className="share-card__subtitle">仅分享像素封面，不包含原始穿搭照片。</p>

          <div className="share-card__frame">
            {sharing ? (
              <div className="share-card__frame-busy" role="status">
                正在准备图片…
              </div>
            ) : (
              <img src={imageUrl} alt={`${title}的像素图鉴`} />
            )}
          </div>

          {message ? (
            <p className="share-card__note" role="status">
              {message}
            </p>
          ) : null}

          <div className="share-card__actions">
            <button
              className="share-card__douyin"
              type="button"
              aria-label="分享到抖音"
              disabled={sharing}
              onClick={() => void onShare()}
            >
              ♫ 分享至抖音
            </button>
            <button
              className="share-card__save"
              type="button"
              aria-label="保存到相册"
              disabled={sharing}
              onClick={() => void onSave()}
            >
              ▣ 保存到相册
            </button>
            <button className="share-card__dismiss" type="button" onClick={onClose}>
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return host ? createPortal(sheet, host) : sheet;
}
