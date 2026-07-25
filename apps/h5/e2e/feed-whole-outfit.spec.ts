import { expect, test } from "@playwright/test";
import path from "node:path";

test("saves one Feed selection as a visible recoverable Look", async ({
  page
}) => {
  test.setTimeout(210_000);
  page.setDefaultTimeout(15_000);
  const initialLooksLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname.endsWith("/v1/looks")
  );
  await page.goto("/");
  await initialLooksLoaded;

  await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  await expect(page.getByRole("region", { name: "我的数字衣橱" })).toBeVisible();
  const existingLooks = await page.locator(".look-card").count();
  const feedEntry = page.getByRole("button", { name: "刷灵感 Feed" });
  const feedEntryBox = await feedEntry.boundingBox();
  expect(feedEntryBox).not.toBeNull();
  if (!feedEntryBox) return;
  await page.mouse.click(
    feedEntryBox.x + feedEntryBox.width / 2,
    feedEntryBox.y + feedEntryBox.height / 2
  );
  await expect(page.getByRole("region", { name: "穿搭灵感" })).toBeVisible();

  const firstVideo = page.getByLabel(/的穿搭视频/).first();
  const circleButton = page.getByRole("button", { name: "暂停并圈选" }).first();
  await expect(firstVideo).toBeVisible();
  await expect(circleButton).toBeEnabled();

  await firstVideo.click();
  const overlay = page.getByRole("application", { name: "圈选穿搭" });
  await expect(overlay).toBeVisible();
  await expect(page.getByRole("status", { name: "沿着衣服边缘画一圈" })).toBeVisible();
  await expect(circleButton).toBeEnabled();

  await page.screenshot({
    path: path.resolve(
      process.cwd(),
      "../../docs/evidence/pr12-integration/12-feed-pause-circle-guide.png"
    ),
    animations: "disabled"
  });

  await overlay.click({ position: { x: 12, y: 12 } });
  await expect(overlay).toHaveCount(0);
  await expect
    .poll(() => firstVideo.evaluate((video: HTMLVideoElement) => video.paused))
    .toBe(false);

  await circleButton.click();
  await expect(overlay).toBeVisible();
  await expect(circleButton).toBeEnabled();
  await circleButton.click();
  await expect(page.getByRole("status", { name: "沿着衣服边缘画一圈" })).toBeVisible();

  const box = await overlay.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;

  const points = [
    [box.x + box.width * 0.2, box.y + box.height * 0.18],
    [box.x + box.width * 0.8, box.y + box.height * 0.18],
    [box.x + box.width * 0.8, box.y + box.height * 0.72],
    [box.x + box.width * 0.2, box.y + box.height * 0.72],
    [box.x + box.width * 0.2, box.y + box.height * 0.18]
  ] as const;
  await page.mouse.move(...points[0]);
  await page.mouse.down();
  for (const point of points.slice(1)) {
    await page.mouse.move(...point, { steps: 8 });
  }
  await page.mouse.up();

  await expect(
    page.getByRole("group", { name: "已圈选的穿搭主体" })
  ).toBeVisible({ timeout: 3_000 });
  await page.getByRole("button", { name: "存整套", exact: true }).click();
  const savedLooksLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname.endsWith("/v1/looks")
  );
  await page
    .getByRole("button", { name: "保存整套到数字衣橱" })
    .click();
  await expect(page.getByText("已存入数字衣橱")).toBeVisible({
    timeout: 15_000
  });
  await savedLooksLoaded;

  await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  await expect(page.locator(".look-card")).toHaveCount(existingLooks + 1);
  const savedLook = page.locator(".look-card").first();
  await expect(savedLook).toContainText("Feed 穿搭灵感");
  await expect(savedLook).not.toContainText("正在拆解", {
    timeout: 150_000
  });
  await expect(savedLook).toContainText(/搭配已解析|已收藏 · 待补全|解析失败/);

  await page.screenshot({
    path: path.resolve(
      process.cwd(),
      "../../artifacts/issue-3/feed-whole-outfit-recovered-mobile.png"
    ),
    animations: "disabled",
    fullPage: true
  });
});
