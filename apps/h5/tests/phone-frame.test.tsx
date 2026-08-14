import { render, screen, within } from "@testing-library/react";
// @ts-expect-error Vitest runs on Node while the browser app intentionally excludes Node globals.
import { readFileSync } from "node:fs";
// @ts-expect-error Vitest runs on Node while the browser app intentionally excludes Node globals.
import { resolve } from "node:path";

import { PhoneFrame } from "../src/components/PhoneFrame";

describe("PhoneFrame desktop showcase", () => {
  it("keeps the phone content and exposes equal-purpose website and group QR cards", () => {
    render(
      <PhoneFrame>
        <main>手机内容</main>
      </PhoneFrame>
    );

    expect(screen.getByText("手机内容")).toBeInTheDocument();

    const website = screen.getByRole("figure", { name: "网站" });
    const group = screen.getByRole("figure", { name: "体验群" });

    expect(within(website).getByRole("img", { name: "StyleCapture 网站二维码" })).toBeInTheDocument();
    expect(within(group).getByRole("img", { name: "StyleCapture 体验群二维码" })).toBeInTheDocument();
    expect(within(website).getByText("网站")).toBeInTheDocument();
    expect(within(group).getByText("体验群")).toBeInTheDocument();
  });

  it("shows the roadshow rails on Retina-sized desktop CSS viewports", () => {
    const runtime = globalThis as typeof globalThis & { process: { cwd: () => string } };
    const stylesheet = readFileSync(
      resolve(runtime.process.cwd(), "src/app/pixel-theme.css"),
      "utf8"
    );

    expect(stylesheet).toContain("@media (min-width: 900px) and (min-height: 480px)");
    expect(stylesheet).toContain("minmax(0, 1fr)");
  });
});
