import { useRef } from "react";

import "./styles.css";

export function App() {
  const cameraInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);

  return (
    <main className="app-shell">
      <header className="wardrobe-header">
        <div>
          <p className="eyebrow">STYLECAPTURE</p>
          <h1>我的衣橱</h1>
          <p className="subtitle">把喜欢和拥有的，都变成可搭配的数字资产。</p>
        </div>
        <div className="avatar-orbit" aria-hidden="true">
          <span>✦</span>
        </div>
      </header>

      <section className="capture-panel" aria-labelledby="capture-title">
        <div>
          <p className="section-kicker">新增单品</p>
          <h2 id="capture-title">今天想存哪一件？</h2>
        </div>
        <div className="capture-actions">
          <button
            className="capture-button capture-button--primary"
            type="button"
            aria-label="拍一件"
            aria-describedby="camera-action-description"
            onClick={() => cameraInput.current?.click()}
          >
            <span className="capture-button__icon" aria-hidden="true">
              ◉
            </span>
            <span>
              <strong>拍一件</strong>
              <small id="camera-action-description">直接拍摄衣柜里的衣服</small>
            </span>
          </button>
          <button
            className="capture-button capture-button--secondary"
            type="button"
            aria-label="从相册选"
            aria-describedby="gallery-action-description"
            onClick={() => galleryInput.current?.click()}
          >
            <span className="capture-button__icon" aria-hidden="true">
              ✦
            </span>
            <span>
              <strong>从相册选</strong>
              <small id="gallery-action-description">导入已有的单品照片</small>
            </span>
          </button>
        </div>
        <input
          ref={cameraInput}
          className="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
          capture="environment"
          aria-label="拍摄衣物照片"
        />
        <input
          ref={galleryInput}
          className="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
          aria-label="选择衣物照片"
        />
      </section>

      <section className="wardrobe-empty" aria-labelledby="wardrobe-empty-title">
        <div className="empty-sparkles" aria-hidden="true">
          <span>✦</span>
          <span>✧</span>
          <span>✦</span>
        </div>
        <div className="empty-figure" aria-hidden="true">
          <span>♡</span>
        </div>
        <h2 id="wardrobe-empty-title">衣橱正在等第一件单品</h2>
        <p>上传后可以离开这里，识别会在后台继续。</p>
      </section>
    </main>
  );
}
