import { expect, test } from "@playwright/test";
import path from "node:path";

test("saves one Feed selection as a visible recoverable Look", async ({
  page
}) => {
  test.setTimeout(210_000);
  const initialLooksLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname.endsWith("/v1/looks")
  );
  await page.goto("/");
  await initialLooksLoaded;

  await page.getByRole("button", { name: "数字衣橱", exact: true }).click();
  const existingLooks = await page.locator(".look-card").count();
  await page.getByRole("button", { name: "逛灵感", exact: true }).click();

  await page.getByRole("button", { name: "暂停并圈选" }).first().click();
  const overlay = page.getByRole("application", { name: "圈选穿搭" });
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
