import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../docs/evidence/fixes"
);
const configuredBaseUrl = process.env.STYLECAPTURE_E2E_BASE_URL;
const runsAgainstProductionBundle = configuredBaseUrl
  ? !["127.0.0.1", "localhost"].includes(new URL(configuredBaseUrl).hostname)
  : false;

/**
 * 像素封面的底是饱和的粉紫渐变，还撒着亮点。原来的去底按颜色判断（近白、
 * 低饱和），只吃掉浅的那部分，深的留下来——人物就拖着一块有色底走进像素
 * 世界。这里合成一张同样形态的图，把行为钉住。
 */
test("a saturated gradient backdrop is cut away, the figure survives", async ({
  page
}) => {
  test.skip(
    runsAgainstProductionBundle,
    "This source-module algorithm check runs against the local Vite server; the production bundle does not expose /src modules"
  );
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const result = await page.evaluate(async () => {
    const size = 240;
    const source = document.createElement("canvas");
    source.width = size;
    source.height = size;
    const draw = source.getContext("2d")!;

    // 饱和的粉→紫渐变底，和真实封面一样。
    const gradient = draw.createLinearGradient(0, 0, size, size);
    gradient.addColorStop(0, "#fce7f3");
    gradient.addColorStop(0.5, "#f9a8d4");
    gradient.addColorStop(1, "#c4b5fd");
    draw.fillStyle = gradient;
    draw.fillRect(0, 0, size, size);

    // 撒几颗亮点，看它们会不会被当成人物留下来。
    draw.fillStyle = "#ffffff";
    for (const [x, y] of [[24, 30], [200, 46], [40, 205], [210, 190]]) {
      draw.fillRect(x, y, 4, 4);
    }

    // 中间一个不碰边的人形。
    draw.fillStyle = "#3d2c5e";
    draw.fillRect(size / 2 - 22, 60, 44, 120);
    draw.beginPath();
    draw.arc(size / 2, 52, 20, 0, Math.PI * 2);
    draw.fill();

    const url = source.toDataURL("image/png");
    const mod = await import(
      "/src/features/community/world/spriteLoader.ts"
    );
    const sprite = await mod.loadCharacterSprite({
      url,
      removeBackdrop: true
    });

    const out = document.createElement("canvas");
    out.width = sprite.width;
    out.height = sprite.height;
    const ctx = out.getContext("2d")!;
    ctx.drawImage(sprite.image as CanvasImageSource, 0, 0);
    const data = ctx.getImageData(0, 0, out.width, out.height).data;
    const alphaAt = (x: number, y: number) =>
      data[(y * out.width + x) * 4 + 3];

    let opaque = 0;
    for (let i = 3; i < data.length; i += 4) if (data[i] > 20) opaque += 1;

    return {
      width: out.width,
      height: out.height,
      corners: [
        alphaAt(0, 0),
        alphaAt(out.width - 1, 0),
        alphaAt(0, out.height - 1),
        alphaAt(out.width - 1, out.height - 1)
      ],
      centreAlpha: alphaAt(Math.floor(out.width / 2), Math.floor(out.height / 2)),
      opaqueRatio: opaque / (out.width * out.height),
      png: out.toDataURL("image/png")
    };
  });

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(
    path.join(outDir, "cutout-gradient-backdrop.png"),
    Buffer.from(result.png.split(",")[1], "base64")
  );

  // 四角必须透明：有底色时它们一定是实的。
  for (const alpha of result.corners) expect(alpha).toBeLessThan(20);
  // 人物还在。
  expect(result.centreAlpha).toBeGreaterThan(200);
  // 剪完会把透明边裁掉，所以剩下的这块几乎全是人物——比例高才是对的。
  expect(result.opaqueRatio).toBeGreaterThan(0.85);
  // 而且画布确实缩窄了：背景是被剪掉，不是只换了个颜色。
  expect(result.width).toBeLessThan(result.height * 0.75);
});
