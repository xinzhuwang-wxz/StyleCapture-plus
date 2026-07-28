import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../docs/evidence/combo-drag"
);

async function shot(page: Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(outDir, `${name}.png`) });
}

async function openItems(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "我的数字衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await page.getByRole("tab", { name: "按单品" }).click();
  await expect(
    page.getByRole("button", { name: /加入组合衣柜/ }).first()
  ).toBeVisible({ timeout: 20_000 });
}

/** 长按到进入拖拽，然后把手指移到某处。 */
async function startDrag(page: Page, to: { x: number; y: number }) {
  const card = page.locator("article.item-card").first();
  const box = (await card.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(600); // 长按阈值 450ms
  await page.mouse.move(to.x, to.y, { steps: 12 });
}

test("the wardrobe stays inside the phone screen", async ({ page }) => {
  await openItems(page);
  const cabinet = page.locator(".combo-cabinet");
  await expect(cabinet).toBeVisible();

  // 从前它是通栏 fixed，左右都顶出了 390px 的手机边框。
  const screenBox = (await page.locator(".pixel-screen").boundingBox())!;
  const box = (await cabinet.boundingBox())!;
  expect(box.x).toBeGreaterThanOrEqual(screenBox.x - 1);
  expect(box.x + box.width).toBeLessThanOrEqual(
    screenBox.x + screenBox.width + 1
  );
  await shot(page, "01-wardrobe-inside-screen");
});

test("the dragged card follows across the whole screen and never gets stuck", async ({
  page
}) => {
  await openItems(page);
  await startDrag(page, { x: 300, y: 140 });

  const ghost = page.locator(".combo-ghost");
  await expect(ghost).toBeVisible();
  // 卡片带 transform，从前会把 fixed 的拖影困在卡片那一小块里。
  const near = (await ghost.boundingBox())!;
  // 落点要明确避开右下角的衣柜，否则测的就不是「在空白处松手」了。
  await page.mouse.move(70, 690, { steps: 12 });
  const far = (await ghost.boundingBox())!;
  expect(Math.abs(far.x - near.x)).toBeGreaterThan(150);
  expect(Math.abs(far.y - near.y)).toBeGreaterThan(400);
  await shot(page, "02-ghost-follows");

  // 在空白处松手：不放进衣柜，而且拖影必须消失。
  await page.mouse.up();
  await expect(ghost).toHaveCount(0);
  await expect(page.locator(".combo-cabinet__count")).toHaveText("0");
  await shot(page, "03-released-on-empty-space");
});

test("Escape gives a way out of a drag", async ({ page }) => {
  await openItems(page);
  await startDrag(page, { x: 200, y: 400 });
  await expect(page.locator(".combo-ghost")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.locator(".combo-ghost")).toHaveCount(0);
  await page.mouse.up();
  await expect(page.locator(".combo-cabinet__count")).toHaveText("0");
});

test("dropping on the wardrobe puts the item in", async ({ page }) => {
  await openItems(page);
  const cabinet = page.locator(".combo-cabinet");
  const box = (await cabinet.boundingBox())!;
  await startDrag(page, { x: box.x + box.width / 2, y: box.y + box.height / 2 });
  await shot(page, "04-over-the-wardrobe");
  await page.mouse.up();

  await expect(page.locator(".combo-cabinet__count")).toHaveText("1");
  await expect(page.locator(".combo-ghost")).toHaveCount(0);
  await shot(page, "05-item-inside");

  await cabinet.locator("button").click();
  await expect(page.getByLabel("组合衣柜")).toBeVisible();
  await shot(page, "06-combo-detail");
});
