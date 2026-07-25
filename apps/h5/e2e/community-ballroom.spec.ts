import { expect, test } from "@playwright/test";
import path from "node:path";

const evidence = (name: string) =>
  path.resolve(process.cwd(), `../../docs/evidence/issue-9/${name}`);

async function openStyleParty(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "数字衣橱" }).click();
  await page.getByRole("button", { name: "体验主题派对" }).click();
  await expect(page.getByRole("heading", { name: "花房晚宴" })).toBeVisible();
}

test("a mobile user can publish a pixel Look, browse, react, collect, and share", async ({
  page
}) => {
  await openStyleParty(page);

  await expect(page.getByText("主题陈列室 Demo · 非实时社区")).toBeVisible();
  await expect(
    page.getByRole("img", { name: "暖棕复古 Look 像素形象" })
  ).toBeVisible();
  await page.screenshot({
    path: evidence("01-style-party-theme.png"),
    animations: "disabled"
  });

  await page.getByRole("button", { name: "查看薄荷花园" }).click();
  await expect(
    page.getByRole("img", { name: "薄荷花园 Look 像素形象" })
  ).toBeVisible();
  await page.screenshot({
    path: evidence("02-browse-pixel-looks.png"),
    animations: "disabled"
  });

  await page.getByRole("button", { name: "收藏这个搭配灵感" }).click();
  await expect(page.getByRole("status")).toContainText("已收藏：薄荷花园");
  await expect(
    page.getByRole("button", { name: "已收藏这个搭配灵感" })
  ).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({
    path: evidence("03-collect-inspiration.png"),
    animations: "disabled"
  });

  await page.getByRole("button", { name: "带我的 Look 登场" }).click();
  await expect(page.getByRole("status")).toContainText("你的 Look 已站上主题舞台");
  await expect(page.getByRole("img", { name: "我的像素 Look" })).toBeVisible();
  await expect(page.locator(".party-stage__look")).toHaveCSS("opacity", "1");
  await page.locator(".party-stage").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: evidence("04-publish-my-look.png"),
    animations: "disabled"
  });

  await page.getByRole("button", { name: "层次感" }).click();
  await expect(page.getByRole("button", { name: "层次感" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await expect(page.getByRole("status")).toContainText("已记录：层次感");
  await page.screenshot({
    path: evidence("05-style-reaction.png"),
    animations: "disabled"
  });

  const shareButton = page.getByRole("button", { name: "生成像素分享卡" });
  await shareButton.scrollIntoViewIfNeeded();
  const download = page.waitForEvent("download");
  await shareButton.click();
  const shareCard = await download;
  expect(shareCard.suggestedFilename()).toBe("stylecapture-style-party.png");
  await shareCard.saveAs(evidence("07-style-party-share-card.png"));
  await expect(page.getByRole("status")).toHaveText("分享卡已准备好");
  await page.screenshot({
    path: evidence("06-share-ready.png"),
    animations: "disabled"
  });
});

test("share-card export has a visible retry path", async ({ page }) => {
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
  const shareButton = page.getByRole("button", { name: "生成像素分享卡" });
  await shareButton.scrollIntoViewIfNeeded();
  await shareButton.click();

  await expect(page.getByRole("status")).toHaveText("分享卡生成失败，请重试");
  await expect(
    page.getByRole("button", { name: "重试生成分享卡" })
  ).toBeVisible();
  await page.screenshot({
    path: evidence("08-share-retry.png"),
    animations: "disabled"
  });

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "重试生成分享卡" }).click();
  await download;
  await expect(page.getByRole("status")).toHaveText("分享卡已准备好");
});
