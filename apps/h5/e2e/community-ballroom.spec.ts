import { expect, test } from "@playwright/test";
import path from "node:path";

const evidence = (name: string) =>
  path.resolve(process.cwd(), `../../docs/evidence/issue-9/${name}`);

async function openStyleParty(page: import("@playwright/test").Page) {
  await page.goto("/?demo=style-party");
  await expect(
    page.getByRole("heading", { name: "穿上今晚的 Look，走进舞会" })
  ).toBeVisible();
}

test("a mobile user can preview, explicitly publish, walk, dance, react, collect, and share", async ({
  page
}) => {
  await openStyleParty(page);
  await expect(
    page.getByLabel("使用 Pixel Agents 开源素材构成的像素舞会场景")
  ).toBeVisible();
  await expect(page.locator(".pixel-ballroom__performer")).toHaveAttribute(
    "data-stage",
    "gallery"
  );
  await expect(page.locator(".audience-look").first()).toHaveCSS(
    "animation-name",
    "guest-patrol-left"
  );
  await expect(page.locator(".audience-look").first()).toHaveCSS(
    "background-color",
    "rgba(0, 0, 0, 0)"
  );
  await page.screenshot({
    path: evidence("01-pixel-runway-ball.png"),
    animations: "disabled"
  });

  await page.getByRole("button", { name: "查看薄荷花园" }).click();
  await page.getByRole("button", { name: "收藏灵感" }).click();
  await expect(page.getByRole("status")).toContainText("已收藏：薄荷花园");
  await expect(page.getByRole("button", { name: "已收藏" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await page.screenshot({
    path: evidence("02-browse-and-collect.png"),
    animations: "disabled"
  });

  await page
    .getByLabel("上传我的像素 Look")
    .setInputFiles(path.resolve(process.cwd(), "public/assets/char-default.png"));
  await expect(page.getByRole("status")).toContainText("已在后台预览");
  await expect(page.locator(".pixel-ballroom__performer")).toHaveAttribute(
    "data-stage",
    "backstage"
  );
  await expect(page.getByRole("button", { name: "加入舞会" })).toBeDisabled();

  await page.getByRole("button", { name: "上台走秀" }).click();
  await expect(page.locator(".pixel-ballroom__performer")).toHaveAttribute(
    "data-stage",
    "runway"
  );
  await page.screenshot({
    path: evidence("03-runway-in-motion.png")
  });
  await expect(page.getByRole("status")).toContainText("已到达主舞台", {
    timeout: 3_000
  });
  await expect(page.locator(".pixel-ballroom__performer")).toHaveAttribute(
    "data-stage",
    "spotlight"
  );

  await page.getByRole("button", { name: "加入舞会" }).click();
  await expect(page.locator(".pixel-ballroom__performer")).toHaveAttribute(
    "data-stage",
    "dance"
  );
  await expect(page.getByRole("button", { name: "换一个舞步" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await page.locator(".pixel-ballroom").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: evidence("04-dance-mode.png")
  });

  await page.getByRole("button", { name: "层次感" }).click();
  await expect(page.getByRole("button", { name: "层次感" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );

  const shareButton = page.getByRole("button", { name: "生成像素分享卡" });
  await shareButton.scrollIntoViewIfNeeded();
  const download = page.waitForEvent("download");
  await shareButton.click();
  const shareCard = await download;
  expect(shareCard.suggestedFilename()).toBe("stylecapture-pixel-runway.png");
  await shareCard.saveAs(evidence("05-pixel-runway-share-card.png"));
  await expect(page.getByRole("status")).toHaveText("分享卡已准备好");
  await page.screenshot({
    path: evidence("06-share-ready.png"),
    animations: "disabled"
  });
});

test("invalid upload and share-card failure both have recovery paths", async ({
  page
}) => {
  await page.addInitScript(() => {
    let attempts = 0;
    const original = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function (...args) {
      attempts += 1;
      if (attempts === 1) throw new Error("export unavailable");
      return original.apply(this, args);
    };
  });
  await openStyleParty(page);

  await page.getByLabel("上传我的像素 Look").setInputFiles({
    name: "not-a-look.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("invalid")
  });
  await expect(page.getByRole("status")).toContainText(
    "请选择 JPG、PNG、WebP 或 HEIC 图片"
  );
  await expect(page.locator(".pixel-ballroom__performer")).toHaveAttribute(
    "data-stage",
    "gallery"
  );

  const shareButton = page.getByRole("button", { name: "生成像素分享卡" });
  await shareButton.scrollIntoViewIfNeeded();
  await shareButton.click();
  await expect(page.getByRole("status")).toHaveText("分享卡生成失败，请重试");
  await page.screenshot({
    path: evidence("07-recovery-states.png"),
    animations: "disabled"
  });

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "重试生成分享卡" }).click();
  await download;
  await expect(page.getByRole("status")).toHaveText("分享卡已准备好");
});
