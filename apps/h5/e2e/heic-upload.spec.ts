import { expect, test } from "@playwright/test";
import fs from "node:fs";

const heicFixture = process.env.STYLECAPTURE_HEIC_FIXTURE ?? "";

test("accepts a real iPhone HEIC upload through the public wardrobe flow", async ({
  page
}) => {
  test.skip(!heicFixture || !fs.existsSync(heicFixture), "Set STYLECAPTURE_HEIC_FIXTURE");
  test.setTimeout(120_000);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator('[aria-label="穿搭灵感 Feed"]')).toBeVisible();
  await page.getByRole("button", { name: "数字衣橱", exact: true }).click();

  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "添加衣服或试试像素形象" }).click();
  await page.getByRole("dialog", { name: "添加到 StyleCapture" }).getByText("从相册导入").click();
  const chooser = await chooserPromise;
  await chooser.setFiles(heicFixture);

  const confirmation = page.getByRole("dialog", { name: "确认加入衣橱" });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "单件衣服" }).click();
  await confirmation.getByRole("button", { name: "我的衣服" }).click();
  const accepted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/v1/captures"
  );
  await confirmation.getByRole("button", { name: "加入单品衣橱" }).click();
  expect((await accepted).status()).toBe(202);

  await expect(page.getByRole("alert")).toContainText("已安全加入，识别会在后台继续");
  await expect(page.getByRole("button", { name: /数字衣橱 1 个处理中/ })).toBeVisible();
  await expect(page.getByText("不支持的文件格式")).toHaveCount(0);
});
