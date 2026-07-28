import type { ReactNode } from "react";

/**
 * 演示用的 iPhone 外壳：拉丝钛合金边框 + 侧边实体按键，内部是 390×844 的屏幕。
 *
 * 真机上（视口比屏幕窄）边框会自动收起，应用直接铺满，不会出现「手机里再套一个
 * 手机」。评审/投屏时在桌面浏览器打开就能看到完整的手机比例。
 */
export function PhoneFrame({ children }: { children: ReactNode }) {
  return (
    <div className="pixel-stage">
      <div className="pixel-frame">
        <span className="pixel-frame__key pixel-frame__key--mute" aria-hidden="true" />
        <span className="pixel-frame__key pixel-frame__key--up" aria-hidden="true" />
        <span className="pixel-frame__key pixel-frame__key--down" aria-hidden="true" />
        <span className="pixel-frame__key pixel-frame__key--power" aria-hidden="true" />
        <div className="pixel-screen">{children}</div>
      </div>
    </div>
  );
}
