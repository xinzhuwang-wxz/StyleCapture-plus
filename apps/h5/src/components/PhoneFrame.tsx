import type { ReactNode } from "react";

import experienceGroupQr from "../assets/stylecapture-experience-group-qr.jpg";
import websiteQr from "../assets/stylecapture-website-qr.jpg";

type ShowcaseQrProps = {
  image: string;
  imageAlt: string;
  label: string;
  variant?: "website";
};

function ShowcaseQr({ image, imageAlt, label, variant }: ShowcaseQrProps) {
  const imageClassName = [
    "showcase-qr__image",
    variant === "website" ? "showcase-qr__image--website" : ""
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <figure className="showcase-qr" aria-label={label}>
      <div className="showcase-qr__viewport">
        <img className={imageClassName} src={image} alt={imageAlt} />
      </div>
      <figcaption>{label}</figcaption>
    </figure>
  );
}

/**
 * 演示用的 iPhone 外壳：拉丝钛合金边框 + 侧边实体按键，内部是 390×844 的屏幕。
 *
 * 真机上（视口比屏幕窄）边框会自动收起，应用直接铺满，不会出现「手机里再套一个
 * 手机」。评审/投屏时在桌面浏览器打开就能看到完整的手机比例。
 */
export function PhoneFrame({ children }: { children: ReactNode }) {
  return (
    <div className="pixel-stage">
      <ShowcaseQr
        image={websiteQr}
        imageAlt="StyleCapture 网站二维码"
        label="网站"
        variant="website"
      />
      <div className="pixel-frame">
        <span className="pixel-frame__key pixel-frame__key--mute" aria-hidden="true" />
        <span className="pixel-frame__key pixel-frame__key--up" aria-hidden="true" />
        <span className="pixel-frame__key pixel-frame__key--down" aria-hidden="true" />
        <span className="pixel-frame__key pixel-frame__key--power" aria-hidden="true" />
        <div className="pixel-screen">{children}</div>
      </div>
      <ShowcaseQr
        image={experienceGroupQr}
        imageAlt="StyleCapture 体验群二维码"
        label="体验群"
      />
    </div>
  );
}
