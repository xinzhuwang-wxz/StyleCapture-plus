import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const outDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../docs/evidence/design-restyle"
);

async function shot(page: Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true });
  // 字体和图片都是异步的。不等字体会拍到回落字体，看不出换皮效果；
  // 不等图片会拍到一片灰底，那种截图会误导人。
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() =>
    Promise.all(
      Array.from(document.images)
        .filter((img) => !img.complete)
        .map((img) => img.decode().catch(() => undefined))
    )
  );
  await page.screenshot({
    path: path.join(outDir, `${name}.png`),
    animations: "disabled",
    fullPage: true
  });
}

test("capture the restyled screens", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  // 衣橱现在就是首页（main 的「让数字衣橱成为稳定的产品首页」），不再有入口按钮。
  await expect(page.getByRole("heading", { name: "我的数字衣橱" })).toBeVisible({
    timeout: 20_000
  });
  await shot(page, "01-wardrobe-looks");

  await page.getByRole("tab", { name: "按单品" }).click();
  await expect(
    page.getByRole("button", { name: /加入组合衣柜/ }).first()
  ).toBeVisible({ timeout: 20_000 });
  await shot(page, "03-wardrobe-items");

  await page.getByRole("button", { name: "添加衣服或试试像素形象" }).click();
  const addDialog = page.getByRole("dialog", { name: "添加到 StyleCapture" });
  await expect(addDialog).toBeVisible();
  await shot(page, "04-add-sheet");

  await addDialog.getByText("试试像素形象").click();
  await expect(
    page.getByRole("heading", { name: "我的 StyleCapture" })
  ).toBeVisible();
  await shot(page, "05-profile");

  await page.getByRole("button", { name: "编辑资料 ›" }).click();
  await expect(page.getByLabel("我的个人信息")).toBeVisible();
  await shot(page, "06-body-metrics");

});
